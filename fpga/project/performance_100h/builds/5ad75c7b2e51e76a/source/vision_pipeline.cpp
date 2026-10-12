#include "vision_pipeline.h"
#include "template_tracker.h"
#include "stereo_demo/stereo_depth.h"

#include <QElapsedTimer>
#include <QMutex>
#include <QMutexLocker>
#include <QWaitCondition>
#include <opencv2/imgproc.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <deque>
#include <map>
#include <optional>
#include <stdexcept>
#include <vector>
#include <time.h>

namespace {
qint64 monotonicMs() {
    timespec ts{};
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return qint64(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
}
cv::Mat gray(const VisionFrame& f) {
    cv::Mat rgb(f.image.height(), f.image.width(), CV_8UC3,
                const_cast<uchar*>(f.image.constBits()), f.image.bytesPerLine());
    cv::Mat result;
    cv::cvtColor(rgb, result, cv::COLOR_RGB2GRAY);
    return result;
}
tdm::TrackerOptions trackerOptions(const VisionOptions& options, int limit) {
    tdm::TrackerOptions result;
    result.maxTracks = std::clamp(limit, 1, 12);
    result.maxDetectionAgeMs = std::max(1, options.trackingMaxDetectionAgeMs);
    return result;
}
cv::Rect2f rawBox(const Detection& v) {
    return cv::Rect2f(v.x1, v.y1 - 80, v.x2 - v.x1, v.y2 - v.y1);
}
bool nearBox(const cv::Rect2f& a, const cv::Rect2f& b) {
    const float area = (a & b).area();
    const float combined = a.area() + b.area() - area;
    return combined > 0 && area / combined >= 0.7f &&
           cv::norm((a.tl() + a.br()) * 0.5f - (b.tl() + b.br()) * 0.5f) <=
               std::max(4.0f, std::min(a.width, a.height) * 0.15f);
}
}

struct VisionPipeline::Impl {
    explicit Impl(VisionPipeline* owner, VisionOptions value)
        : q(owner), options(std::move(value)) {
        stereoMask = options.stereoCameraMask();
        for (const auto& pair : options.stereoPairs()) {
            auto state = std::make_unique<StereoState>();
            state->options = pair;
            stereoStates.push_back(std::move(state));
        }
    }
    VisionPipeline* q;
    VisionOptions options;
    struct Config {
        quint64 epoch = 0;
        int generation = 0, camera = 0;
        bool lane = false;
        QStringList models;
    } config, active;
    struct Pending {
        quint64 epoch = 0, frameId = 0;
        int generation = 0;
        qint64 sentMs = 0;
    };
    struct Reply {
        Pending request;
        QString model;
        QVector<Detection> detections;
        double inferMs = 0;
    };
    QMutex mutex;
    QWaitCondition changed;
    bool stopping = false;
    // Only selected/configured stereo cameras are accepted; at most two owned frames
    // per camera. Replacements never form a queued Qt invocation per frame.
    std::map<int, std::deque<VisionFrame>> frameSlots;
    std::map<int, quint64> highWater;
    std::optional<Pending> pending;
    std::optional<Reply> reply;
    // A frame identity is submitted once even across configure/timeout. This
    // also prevents a late reply from identifying a newer request for that frame.
    std::map<std::pair<int, int>, quint64> submittedThrough; // generation, camera

    struct History {
        VisionFrame frame;
        cv::Mat gray;
        std::map<QString, tdm::TemplateTracker> snapshots;
    };
    std::deque<History> history;
    std::map<QString, tdm::TemplateTracker> trackers;
    std::map<QString, int> trackBudgets;
    std::map<QString, bool> lost;
    std::map<QString, int> publishedCounts;
    struct Depth {
        double meters = 0;
        qint64 capturedMs = 0;
        cv::Rect2f box;
    };
    struct StereoState {
        StereoPairOptions options;
        std::map<std::pair<QString, uint64_t>, Depth> depths;
        quint64 pairedLeft = 0, pairedRight = 0;
        qint64 lastPreviewMs = -1, lastAttemptMs = -1;
        qint64 lastPairCapturedMs = -1; // oldest host capture in the latest attempted pair
        struct Window {
            quint64 computeSuccess = 0, computeFailure = 0, noFreshPairPolls = 0;
            double computeTotalMs = 0, computeMaxMs = 0;
        } window;
        bool staleReported = false;
        stereo::Calibration calibration;
        // The calibration address given to DepthEngine remains stable.
        std::unique_ptr<stereo::DepthEngine> engine;
        cv::Mat roiRotation, roiProjection;
        bool calibrated = false;
        QString calibrationStatus;
        void resetRuntime() {
            depths.clear(); pairedLeft = pairedRight = 0;
            lastPreviewMs = lastAttemptMs = -1; staleReported = false;
            lastPairCapturedMs = -1;
        }
    };
    std::vector<std::unique_ptr<StereoState>> stereoStates;
    quint32 stereoMask = 0;
    size_t nextStereo = 0;
    quint64 currentFrame = 0;
    qint64 currentCapturedMs = -1;
    qint64 lastRequestMs = -1, lastStereoFinishedMs = -1;
    qint64 lastDiagnosticMs = -1;
    qint64 stereoWindowStartMs = -1;
    int requests = 0, matchedFrames = 0;
    double matchTotalMs = 0;

    StereoState* selectedStereo() {
        for (auto& state : stereoStates)
            if (state->options.left == active.camera) return state.get();
        return nullptr; // right cameras never receive left-image target depth
    }
    StereoState* previewStereo() {
        if (active.camera < 0) return stereoStates.empty() ? nullptr : stereoStates.front().get();
        for (auto& state : stereoStates)
            if (state->options.left == active.camera || state->options.right == active.camera)
                return state.get();
        return nullptr;
    }

    bool live(quint64 epoch) {
        QMutexLocker lock(&mutex);
        return !stopping && config.epoch == epoch;
    }
    void reset(const Config& value) {
        active = value;
        trackers.clear(); trackBudgets.clear(); lost.clear(); publishedCounts.clear(); history.clear();
        for (auto& state : stereoStates) state->resetRuntime();
        currentFrame = 0; currentCapturedMs = -1;
        lastRequestMs = lastStereoFinishedMs = -1;
        nextStereo = 0;
        // Start with the displayed pair, then rotate fairly among ready groups.
        for (size_t i = 0; i < stereoStates.size(); ++i)
            if (stereoStates[i].get() == previewStereo()) { nextStereo = i; break; }
        const int total = std::clamp(options.maxTracks, 1, 12);
        const int count = active.models.size();
        for (int i = 0; i < count; ++i) {
            const int bound = total / count + (i < total % count ? 1 : 0);
            trackBudgets[active.models[i]] = bound;
            trackers.emplace(active.models[i], tdm::TemplateTracker(trackerOptions(options, bound)));
        }
    }
    void prepareStereo() {
        for (auto& state : stereoStates) prepareStereo(*state);
    }
    void prepareStereo(StereoState& state) {
        stereo::MatcherOptions matcher;
        matcher.scale = options.stereoScale;
        matcher.numDisparities = options.stereoDisparities;
        auto& calibration = state.calibration;
        auto& engine = state.engine;
        auto& calibrated = state.calibrated;
        auto& calibrationStatus = state.calibrationStatus;
        calibrationStatus = QStringLiteral("not calibrated");
        try {
            if (!state.options.calibrationPath.isEmpty()) {
                calibration = stereo::Calibration::load(state.options.calibrationPath.toStdString());
                if (calibration.imageSize != cv::Size(640, 480))
                    throw std::invalid_argument("calibration image size must be 640x480");
                engine.reset(new stereo::DepthEngine(matcher, &calibration));
                const cv::Size size(cvRound(640 * matcher.scale), cvRound(480 * matcher.scale));
                cv::Mat k1 = calibration.K1.clone(), k2 = calibration.K2.clone();
                for (int x = 0; x < 3; ++x) {
                    k1.at<double>(0, x) *= double(size.width) / calibration.imageSize.width;
                    k1.at<double>(1, x) *= double(size.height) / calibration.imageSize.height;
                    k2.at<double>(0, x) *= double(size.width) / calibration.imageSize.width;
                    k2.at<double>(1, x) *= double(size.height) / calibration.imageSize.height;
                }
                cv::Mat r2, p2, Q;
                cv::stereoRectify(k1, calibration.D1, k2, calibration.D2, size,
                    calibration.R, calibration.T, state.roiRotation, r2, state.roiProjection, p2, Q,
                    0, 0.0, size);
                calibrated = true;
                calibrationStatus = QStringLiteral("calibrated");
                return;
            }
        } catch (const std::exception& e) {
            calibrationStatus = QStringLiteral("not calibrated: %1").arg(QString::fromUtf8(e.what()));
        }
        calibrated = false;
        try { engine.reset(new stereo::DepthEngine(matcher)); }
        catch (const std::exception& e) {
            engine.reset();
            calibrationStatus = QStringLiteral("stereo unavailable: %1").arg(QString::fromUtf8(e.what()));
        }
    }
    void prune(qint64 now) {
        while (!history.empty() && (history.size() > 8 ||
                now - history.front().frame.capturedMs > 1000)) history.pop_front();
        for (auto& state : stereoStates) {
            if (state.get() != selectedStereo()) { state->depths.clear(); continue; }
            auto& depths = state->depths;
            for (auto it = depths.begin(); it != depths.end();) {
                if (now - it->second.capturedMs > 300) it = depths.erase(it);
                else ++it;
            }
        }
    }
    QVector<Detection> detectionsFor(const QString& model, qint64 time, qint64 now) {
        QVector<Detection> result;
        auto modelIt = trackers.find(model);
        if (modelIt == trackers.end()) return result;
        for (const auto& track : modelIt->second.tracks(time)) {
            Detection d;
            d.cls = track.cls; d.score = track.detectionScore;
            d.x1 = track.box.x; d.x2 = track.box.x + track.box.width;
            d.y1 = track.box.y + 80; d.y2 = track.box.y + track.box.height + 80;
            d.trackId = track.id; d.matchScore = track.matchScore; d.predicted = track.predicted;
            d.validUntilMs = track.validUntilMs;
            auto* state = selectedStereo();
            if (state) {
                auto& depths = state->depths;
                auto depth = depths.find({model, track.id});
                if (depth != depths.end()) {
                    const qint64 age = now - depth->second.capturedMs;
                    if (age >= 0 && age <= 300 && nearBox(track.box, depth->second.box)) {
                        d.depthMeters = depth->second.meters; d.depthAgeMs = int(age);
                        d.depthCapturedMs = depth->second.capturedMs;
                    } else depths.erase(depth);
                }
            }
            result.push_back(d);
        }
        return result;
    }
    void publish(const QString& model, double ms, qint64 now) {
        if (currentCapturedMs < 0 || !live(active.epoch)) return;
        auto boxes = detectionsFor(model, std::max(currentCapturedMs, now), now);
        publishedCounts[model] = boxes.size();
        emit q->tracksReady(model, active.generation, currentFrame, std::move(boxes), ms);
    }
    void expireFrozenTracks(qint64 now) {
        if (!options.tracking || active.lane || currentCapturedMs < 0) return;
        for (const auto& item : trackers) {
            if (publishedCounts[item.first] > 0 &&
                item.second.tracks(std::max(currentCapturedMs, now)).empty())
                publish(item.first, 0, now);
        }
    }
    void acceptReply(const Reply& value, qint64 now) {
        if (value.request.epoch != active.epoch || !active.models.contains(value.model)) return;
        auto source = std::find_if(history.begin(), history.end(), [&](const History& h) {
            return h.frame.frameId == value.request.frameId;
        });
        if (source == history.end() || now - source->frame.capturedMs > 1000) return;
        if (!options.tracking || active.lane) {
            QVector<Detection> clean = value.detections;
            for (auto& d : clean) {
                d.trackId = 0; d.predicted = false; d.matchScore = 0;
                d.depthMeters = std::numeric_limits<double>::quiet_NaN(); d.depthAgeMs = 0;
                d.depthCapturedMs = 0;
                d.validUntilMs = source->frame.capturedMs + 2000;
            }
            if (live(active.epoch)) emit q->tracksReady(value.model, active.generation,
                value.request.frameId, clean, 0);
            return;
        }
        auto original = source->snapshots.find(value.model);
        auto target = trackers.find(value.model);
        if (original == source->snapshots.end() || target == trackers.end()) return;
        if (trackBudgets[value.model] == 0) { publish(value.model, 0, now); return; }
        QElapsedTimer elapsed; elapsed.start();
        tdm::TemplateTracker corrected = original->second; // deep clone
        std::vector<tdm::ObjectDetection> input;
        for (const auto& d : value.detections) input.push_back({d.cls, d.score, rawBox(d)});
        corrected.correct(source->gray, input, source->frame.capturedMs);
        source->snapshots.insert_or_assign(value.model, corrected);
        for (auto it = std::next(source); it != history.end(); ++it) {
            corrected.update(it->gray, it->frame.capturedMs);
            it->snapshots.insert_or_assign(value.model, corrected);
        }
        target->second = std::move(corrected);
        lost[value.model] = !value.detections.isEmpty() &&
            target->second.tracks(history.back().frame.capturedMs).empty();
        // A detection correction may change target identity/position; metric
        // values from before that correction must not survive it.
        for (auto& state : stereoStates)
            for (auto it = state->depths.begin(); it != state->depths.end();) {
                if (it->first.first == value.model) it = state->depths.erase(it); else ++it;
            }
        const double ms = elapsed.nsecsElapsed() / 1e6;
        matchTotalMs += ms; ++matchedFrames;
        publish(value.model, ms, now);
    }
    void processFrame(const VisionFrame& frame, qint64 now) {
        if (frame.camera != active.camera || frame.frameId <= currentFrame || frame.sourceGeneration != active.generation ||
            now < frame.capturedMs || now - frame.capturedMs > 1000) return;
        if (currentCapturedMs >= 0 && frame.capturedMs < currentCapturedMs) return;
        History h; h.frame = frame; h.gray = gray(frame);
        QElapsedTimer elapsed; elapsed.start();
        if (options.tracking && !active.lane) {
            for (auto& item : trackers) {
                const bool hadTracks = currentCapturedMs >= 0 &&
                    !item.second.tracks(currentCapturedMs).empty();
                const auto tracks = item.second.update(h.gray, frame.capturedMs);
                if (hadTracks && tracks.empty()) lost[item.first] = true;
            }
        }
        h.snapshots = trackers;
        history.push_back(std::move(h)); currentFrame = frame.frameId;
        currentCapturedMs = frame.capturedMs;
        prune(now);
        const double ms = elapsed.nsecsElapsed() / 1e6;
        if (options.tracking && !active.lane) {
            matchTotalMs += ms; ++matchedFrames;
            for (const auto& item : trackers) publish(item.first, ms, now);
        }
    }
    void request(qint64 now) {
        if (history.empty() || active.models.isEmpty()) return;
        const auto& frame = history.back().frame;
        if (now - frame.capturedMs > 1000) return;
        bool urgent = false;
        if (options.tracking && !active.lane) {
            for (const auto& item : trackers) {
                // Empty scenes refresh periodically. Weak/lost existing
                // targets can request sooner, with the same minimum limit.
                if (lost[item.first] || (item.second.needsDetection(frame.capturedMs) &&
                    !item.second.tracks(frame.capturedMs).empty())) urgent = true;
            }
        }
        const bool bypass = active.lane || !options.tracking;
        const qint64 interval = urgent ? std::max(1, options.minimumDetectionIntervalMs) :
            std::max({1, options.detectionIntervalMs, options.minimumDetectionIntervalMs});
        if (!bypass && lastRequestMs >= 0 && now - lastRequestMs < interval) return;
        {
            QMutexLocker lock(&mutex);
            if (stopping || config.epoch != active.epoch || pending) return;
            const auto latest = frameSlots.find(active.camera);
            if (latest != frameSlots.end() && !latest->second.empty() &&
                latest->second.back().frameId > frame.frameId) return;
            const auto submissionKey = std::make_pair(active.generation, active.camera);
            auto previous = submittedThrough.find(submissionKey);
            if (previous != submittedThrough.end() && frame.frameId <= previous->second) return;
            pending = Pending{active.epoch, frame.frameId, active.generation, now};
            submittedThrough[submissionKey] = frame.frameId;
            while (submittedThrough.size() > 24) submittedThrough.erase(submittedThrough.begin());
        }
        lastRequestMs = now; ++requests;
        if (live(active.epoch)) emit q->inferenceRequested(frame);
    }
    cv::Rect rectifiedRoi(const StereoState& state, const cv::Rect2f& box, const cv::Size& size) const {
        // Sample the central half of the original left ROI, then map it using
        // the exact rounded, scaled rectification geometry used by DepthEngine.
        std::vector<cv::Point2f> points;
        for (int y = 0; y < 3; ++y) for (int x = 0; x < 3; ++x)
            points.emplace_back(box.x + box.width * (0.25f + x * 0.25f),
                                box.y + box.height * (0.25f + y * 0.25f));
        std::vector<cv::Point2f> rectified;
        cv::undistortPoints(points, rectified, state.calibration.K1, state.calibration.D1,
                            state.roiRotation, state.roiProjection);
        for (auto p : rectified) if (!std::isfinite(p.x) || !std::isfinite(p.y)) return {};
        return cv::boundingRect(rectified) & cv::Rect(0, 0, size.width, size.height);
    }
    struct StereoFrames { const VisionFrame* left = nullptr; const VisionFrame* right = nullptr; };
    StereoFrames correspondingFrames(const StereoState& state,
            const std::map<int, std::deque<VisionFrame>>& frames, qint64 now) const {
        auto l = frames.find(state.options.left), r = frames.find(state.options.right);
        const bool sync = state.options.synchronizationConfirmed && state.options.hasTagOffset;
        StereoFrames pair;
        if (l != frames.end() && r != frames.end()) {
            for (const auto& a : l->second) for (const auto& b : r->second) {
                if (a.frameId <= state.pairedLeft || b.frameId <= state.pairedRight ||
                    a.sourceGeneration != active.generation || b.sourceGeneration != active.generation ||
                    now < a.capturedMs || now < b.capturedMs ||
                    now - a.capturedMs > 500 || now - b.capturedMs > 500) continue;
                if (sync && a.tag != b.tag + quint32(state.options.tagOffset)) continue;
                if (!pair.left || a.frameId > pair.left->frameId ||
                    (a.frameId == pair.left->frameId && b.frameId > pair.right->frameId))
                    pair = {&a, &b};
            }
        }
        return pair;
    }
    void stereoPreview(StereoState& state, quint64 id, const QImage& image, const QString& status) {
        if (&state == previewStereo() && live(active.epoch))
            emit q->stereoReady(active.generation, id, image,
                 QStringLiteral("C%1/C%2: %3").arg(state.options.left + 1).arg(state.options.right + 1).arg(status));
    }
    void reportStereoWindows(qint64 now) {
        if (stereoWindowStartMs < 0) { stereoWindowStartMs = now; return; }
        // Fixed, non-overlapping five-second windows; never emit per-frame logs.
        while (now - stereoWindowStartMs >= 5000) {
            for (auto& owned : stereoStates) {
                auto& state = *owned;
                const auto& window = state.window;
                const quint64 computes = window.computeSuccess + window.computeFailure;
                qint64 cacheAgeMs = -1;
                for (const auto& depth : state.depths)
                    cacheAgeMs = std::max(cacheAgeMs, now - depth.second.capturedMs);
                const qint64 pairAgeMs = state.lastPairCapturedMs < 0 ? -1 :
                    std::max(qint64(0), now - state.lastPairCapturedMs);
                const QString line = QStringLiteral(
                    "[stereo] window=[%1,%2) window_ms=5000 C%3/C%4 "
                    "pair_compute_ok=%5 pair_compute_failed=%6 no_fresh_pair_polls=%7 "
                    "(polls_not_dropped_frames) compute_mean_ms=%8 compute_max_ms=%9 "
                    "latest_host_pair_age_ms=%10 depth_cache_age_ms=%11 depth_cache_items=%12")
                    .arg(stereoWindowStartMs).arg(stereoWindowStartMs + 5000)
                    .arg(state.options.left + 1).arg(state.options.right + 1)
                    .arg(window.computeSuccess).arg(window.computeFailure).arg(window.noFreshPairPolls)
                    .arg(computes ? window.computeTotalMs / computes : 0, 0, 'f', 2)
                    .arg(window.computeMaxMs, 0, 'f', 2).arg(pairAgeMs).arg(cacheAgeMs)
                    .arg(state.depths.size());
                std::fprintf(stderr, "%s\n", line.toUtf8().constData());
                state.window = {};
            }
            stereoWindowStartMs += 5000;
        }
    }
    void stereoWork(const std::map<int, std::deque<VisionFrame>>& frames, qint64 now) {
        if (stereoStates.empty()) return;
        reportStereoWindows(now);
        // Expiry is independent per group and does not wait for compute slots.
        for (auto& owned : stereoStates) {
            auto& state = *owned;
            const auto pair = correspondingFrames(state, frames, now);
            // Count each worker poll without a fresh pair, including cooldown.
            // This is not a count of camera frames or mailbox replacements.
            if (!pair.left || !pair.right) ++state.window.noFreshPairPolls;
            const bool sync = state.options.synchronizationConfirmed && state.options.hasTagOffset;
            if ((!pair.left || !pair.right || !state.engine) && !state.staleReported &&
                (state.lastPreviewMs < 0 || now - state.lastPreviewMs > 1000)) {
                state.staleReported = true;
                stereoPreview(state, state.pairedLeft, QImage(),
                    QStringLiteral("Z/ROI invalid: %1; %2; no fresh corresponding pair")
                        .arg(state.calibrationStatus, sync ? QStringLiteral("sync confirmed") : QStringLiteral("sync unconfirmed")));
            }
        }
        const int interval = std::max(1, options.stereoIntervalMs);
        // Cool down after completion, even if compute itself exceeds interval.
        // At most one group computes here; a continuously ready group cannot
        // starve the other group or keep this worker in endless back-to-back SGBM.
        if (lastStereoFinishedMs >= 0 && now - lastStereoFinishedMs < interval) return;
        for (size_t attempt = 0; attempt < stereoStates.size(); ++attempt) {
            const size_t index = (nextStereo + attempt) % stereoStates.size();
            auto& state = *stereoStates[index];
            const int groupInterval = state.options.intervalMs == 0 ? interval : state.options.intervalMs;
            if (!state.engine || (state.lastAttemptMs >= 0 && now - state.lastAttemptMs < groupInterval)) continue;
            const auto pair = correspondingFrames(state, frames, now);
            if (!pair.left || !pair.right) continue;
            state.lastAttemptMs = now;
            state.lastPairCapturedMs = std::min(pair.left->capturedMs, pair.right->capturedMs);
            state.pairedLeft = pair.left->frameId; state.pairedRight = pair.right->frameId;
            nextStereo = (index + 1) % stereoStates.size();
            QElapsedTimer elapsed; elapsed.start();
            bool succeeded = false;
            try { computeStereo(state, *pair.left, *pair.right); succeeded = true; }
            catch (const std::exception& e) {
                state.depths.clear();
                stereoPreview(state, state.pairedLeft, QImage(),
                    QStringLiteral("Z/ROI invalid: stereo compute failed: %1").arg(QString::fromUtf8(e.what())));
            }
            const double computeMs = elapsed.nsecsElapsed() / 1e6;
            lastStereoFinishedMs = monotonicMs();
            // Attribute a compute to its completion window, including failures.
            reportStereoWindows(lastStereoFinishedMs);
            if (succeeded) ++state.window.computeSuccess; else ++state.window.computeFailure;
            state.window.computeTotalMs += computeMs;
            state.window.computeMaxMs = std::max(state.window.computeMaxMs, computeMs);
            return;
        }
    }
    void computeStereo(StereoState& state, const VisionFrame& left, const VisionFrame& right) {
        const bool sync = state.options.synchronizationConfirmed && state.options.hasTagOffset;
        const auto result = state.engine->compute(gray(left), gray(right));
        const qint64 finished = monotonicMs();
        state.lastPreviewMs = finished;
        state.staleReported = false;
        const bool fresh = finished >= left.capturedMs && finished >= right.capturedMs &&
                           finished - left.capturedMs <= 500 && finished - right.capturedMs <= 500;
        QImage preview(result.disparity.cols, result.disparity.rows, QImage::Format_RGB888);
        for (int y = 0; y < preview.height(); ++y) {
            auto* row = preview.scanLine(y);
            for (int x = 0; x < preview.width(); ++x) {
                const float v = result.disparity.at<float>(y, x);
                const uchar shade = std::isfinite(v) ? uchar(std::clamp(int(v * 255 / options.stereoDisparities), 0, 255)) : 0;
                row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = shade;
            }
        }
        QString status = QStringLiteral("Z/ROI invalid: %1; %2")
            .arg(state.calibrationStatus, sync ? QStringLiteral("sync confirmed") : QStringLiteral("sync unconfirmed"));
        if (!fresh) status += QStringLiteral("; host age >500ms");
        if (result.calibrated && state.calibrated && sync && fresh) {
            const cv::Rect center(result.left.cols * 3 / 8, result.left.rows * 3 / 8,
                                  result.left.cols / 4, result.left.rows / 4);
            const auto range = stereo::DepthEngine::estimate(result, center);
            if (range.valid) {
                status = QStringLiteral("Z/ROI center %1 m; calibrated; sync confirmed")
                    .arg(range.meters, 0, 'f', 2);
            } else status += QStringLiteral("; %1").arg(QString::fromStdString(range.reason));
            // Only boxes at this exact left frame may seed a short-lived cache.
            // Older disparity never samples a newer target's position.
            if (active.camera == state.options.left && !history.empty() &&
                history.back().frame.camera == state.options.left &&
                history.back().frame.frameId == left.frameId && options.tracking && !active.lane) {
                for (const auto& item : trackers) {
                    for (const auto& track : item.second.tracks(left.capturedMs)) {
                        if (track.predicted || track.weakFrames > 0) continue;
                        const auto rangeForTrack = stereo::DepthEngine::estimate(result,
                            rectifiedRoi(state, track.box, result.left.size()));
                        if (rangeForTrack.valid) state.depths[{item.first, track.id}] =
                            Depth{rangeForTrack.meters, left.capturedMs, track.box};
                    }
                    publish(item.first, 0, finished);
                }
            }
        }
        stereoPreview(state, left.frameId, preview, status);
    }
    void diagnose(qint64 now) {
        if (lastDiagnosticMs < 0) { lastDiagnosticMs = now; return; }
        if (now - lastDiagnosticMs < 1000) return;
        const double seconds = double(now - lastDiagnosticMs) / 1000;
        int count = 0;
        if (currentCapturedMs >= 0) for (const auto& item : trackers)
            count += int(item.second.tracks(std::max(currentCapturedMs, now)).size());
        QStringList stereoProgress;
        for (const auto& state : stereoStates)
            stereoProgress.push_back(QStringLiteral("C%1/C%2:%3/%4")
                .arg(state->options.left + 1).arg(state->options.right + 1)
                .arg(state->pairedLeft).arg(state->pairedRight));
        if (live(active.epoch)) emit q->diagnostics(
            QStringLiteral("vision tracks=%1 track/replay=%2 ms NPU requests=%3/s history=%4/8 stereo=[%5]")
                .arg(count).arg(matchedFrames ? matchTotalMs / matchedFrames : 0, 0, 'f', 2)
                .arg(requests / seconds, 0, 'f', 1).arg(history.size()).arg(stereoProgress.join(QStringLiteral(","))));
        requests = matchedFrames = 0; matchTotalMs = 0; lastDiagnosticMs = now;
    }
};

VisionPipeline::VisionPipeline(VisionOptions options, QObject* parent)
    : QThread(parent), d(new Impl(this, std::move(options))) {
    qRegisterMetaType<VisionFrame>("VisionFrame");
    qRegisterMetaType<QVector<Detection>>("QVector<Detection>");
}
VisionPipeline::~VisionPipeline() { stop(); if (QThread::currentThread() != this) wait(); }

void VisionPipeline::configure(int generation, int camera, bool lane, const QStringList& models) {
    QMutexLocker lock(&d->mutex);
    ++d->config.epoch;
    d->config.generation = generation; d->config.camera = camera; d->config.lane = lane;
    d->config.models = models; d->config.models.removeDuplicates();
    d->frameSlots.clear(); d->highWater.clear(); d->pending.reset(); d->reply.reset();
    d->changed.wakeOne();
}
void VisionPipeline::submitFrame(const VisionFrame& frame) {
    if (frame.image.size() != QSize(640, 480) || frame.image.format() != QImage::Format_RGB888 ||
        frame.frameId == 0 || frame.capturedMs < 0) return;
    QMutexLocker lock(&d->mutex);
    if (d->stopping || frame.sourceGeneration != d->config.generation ||
        (frame.camera != d->config.camera &&
         (frame.camera < 0 || frame.camera >= 6 || !(d->stereoMask & (quint32(1) << frame.camera))))) return;
    auto previous = d->highWater.find(frame.camera);
    if (previous != d->highWater.end() && frame.frameId <= previous->second) return;
    d->highWater[frame.camera] = frame.frameId;
    auto& slot = d->frameSlots[frame.camera];
    // VisionFrame contract guarantees an owned image; implicit QImage sharing
    // keeps ingress cheap and ownership alive while worker snapshots use it.
    slot.push_back(frame);
    while (slot.size() > 2) slot.pop_front();
    d->changed.wakeOne();
}
void VisionPipeline::submitDetections(QString model, int generation, quint64 frameId,
                                      QVector<Detection> values, double inferMs) {
    QMutexLocker lock(&d->mutex);
    if (d->stopping || !d->pending || d->reply ||
        d->pending->epoch != d->config.epoch || d->pending->generation != generation ||
        d->pending->frameId != frameId || monotonicMs() - d->pending->sentMs >= 2000) return;
    if (!d->config.models.contains(model)) { d->pending.reset(); d->changed.wakeOne(); return; }
    d->reply = Impl::Reply{*d->pending, std::move(model), std::move(values), inferMs};
    d->changed.wakeOne();
}
void VisionPipeline::inferenceFailed(int generation, quint64 frameId) {
    QMutexLocker lock(&d->mutex);
    if (d->pending && d->pending->epoch == d->config.epoch &&
        d->pending->generation == generation && d->pending->frameId == frameId && !d->reply) {
        d->pending.reset(); d->changed.wakeOne();
    }
}
void VisionPipeline::stop() {
    QMutexLocker lock(&d->mutex);
    d->stopping = true; d->pending.reset(); d->reply.reset(); d->frameSlots.clear();
    d->changed.wakeAll();
}
void VisionPipeline::run() {
    d->prepareStereo();
    for (;;) {
        Impl::Config config;
        std::map<int, std::deque<VisionFrame>> frames;
        std::optional<Impl::Reply> reply;
        {
            QMutexLocker lock(&d->mutex);
            if (d->stopping) break;
            config = d->config; frames = d->frameSlots;
            if (d->reply) { reply = std::move(d->reply); d->reply.reset(); d->pending.reset(); }
            else if (d->pending && monotonicMs() - d->pending->sentMs >= 2000) d->pending.reset();
        }
        const qint64 now = monotonicMs();
        try {
            if (config.epoch != d->active.epoch) d->reset(config);
            d->prune(now);
            if (reply) d->acceptReply(*reply, now);
            auto selected = frames.find(config.camera);
            if (selected != frames.end() && !selected->second.empty())
                d->processFrame(selected->second.back(), now);
            d->expireFrozenTracks(now);
            d->request(now);
            d->stereoWork(frames, now);
            d->diagnose(monotonicMs());
        } catch (const std::exception& e) {
            // Malformed calibration or a failed OpenCV operation cannot kill
            // capture threads or leave an NPU reservation permanently locked.
            if (d->live(config.epoch)) {
                const qint64 errorNow = monotonicMs();
                if (d->lastDiagnosticMs < 0 || errorNow - d->lastDiagnosticMs >= 1000) {
                    emit diagnostics(QStringLiteral("vision: %1").arg(QString::fromUtf8(e.what())));
                    d->lastDiagnosticMs = errorNow;
                }
            }
        }
        QMutexLocker lock(&d->mutex);
        if (!d->stopping && d->config.epoch == config.epoch && !d->reply)
            d->changed.wait(&d->mutex, 20);
    }
}
