#include "stereo_async_worker.h"
#include "stereo_demo/stereo_depth.h"
#include <QElapsedTimer>
#include <opencv2/imgproc.hpp>
#include <algorithm>
#include <cmath>
#include <condition_variable>
#include <map>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <thread>
#include <time.h>

namespace stereo_async {
namespace {
#ifdef STEREO_ASYNC_TESTING
std::function<void(const Stamp&)> computeGate;
#endif
qint64 nowMs() {
    timespec ts{}; clock_gettime(CLOCK_MONOTONIC, &ts);
    return qint64(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
}
cv::Mat gray(const VisionFrame& f) {
    cv::Mat rgb(f.image.height(), f.image.width(), CV_8UC3,
                const_cast<uchar*>(f.image.constBits()), f.image.bytesPerLine());
    cv::Mat result; cv::cvtColor(rgb, result, cv::COLOR_RGB2GRAY); return result;
}
struct Engine {
    StereoPairOptions options;
    stereo::Calibration calibration;
    std::unique_ptr<stereo::DepthEngine> engine;
    cv::Mat roiRotation, roiProjection;
    bool calibrated = false;
    QString status = QStringLiteral("not calibrated");
    Engine(const StereoPairOptions& pair, const VisionOptions& options) : options(pair) {
        stereo::MatcherOptions matcher;
        matcher.scale = options.stereoScale; matcher.numDisparities = options.stereoDisparities;
        try {
            if (!pair.calibrationPath.isEmpty()) {
                calibration = stereo::Calibration::load(pair.calibrationPath.toStdString());
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
                    calibration.R, calibration.T, roiRotation, r2, roiProjection, p2, Q, 0, 0.0, size);
                calibrated = true; status = QStringLiteral("calibrated"); return;
            }
        } catch (const std::exception& e) {
            status = QStringLiteral("not calibrated: %1").arg(QString::fromUtf8(e.what()));
        }
        try { engine.reset(new stereo::DepthEngine(matcher)); }
        catch (const std::exception& e) {
            engine.reset(); status = QStringLiteral("stereo unavailable: %1").arg(QString::fromUtf8(e.what()));
        }
    }
    cv::Rect roi(const cv::Rect2f& box, const cv::Size& size) const {
        std::vector<cv::Point2f> points, rectified;
        for (int y = 0; y < 3; ++y) for (int x = 0; x < 3; ++x)
            points.emplace_back(box.x + box.width * (0.25f + x * 0.25f),
                                box.y + box.height * (0.25f + y * 0.25f));
        cv::undistortPoints(points, rectified, calibration.K1, calibration.D1, roiRotation, roiProjection);
        for (auto p : rectified) if (!std::isfinite(p.x) || !std::isfinite(p.y)) return {};
        return cv::boundingRect(rectified) & cv::Rect(0, 0, size.width, size.height);
    }
    Result compute(const Job& job, int disparities) {
        Result output; output.stamp = job.stamp;
        const bool sync = options.synchronizationConfirmed && options.hasTagOffset;
        const auto result = engine->compute(gray(job.left), gray(job.right));
        const qint64 finished = nowMs();
        const bool fresh = finished >= job.left.capturedMs && finished >= job.right.capturedMs &&
            finished - job.left.capturedMs <= 500 && finished - job.right.capturedMs <= 500;
        output.preview = QImage(result.disparity.cols, result.disparity.rows, QImage::Format_RGB888);
        for (int y = 0; y < output.preview.height(); ++y) {
            auto* row = output.preview.scanLine(y);
            for (int x = 0; x < output.preview.width(); ++x) {
                const float v = result.disparity.at<float>(y, x);
                const uchar shade = std::isfinite(v) ? uchar(std::clamp(int(v * 255 / disparities), 0, 255)) : 0;
                row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = shade;
            }
        }
        output.status = QStringLiteral("Z/ROI invalid: %1; %2")
            .arg(status, sync ? QStringLiteral("sync confirmed") : QStringLiteral("sync unconfirmed"));
        if (!fresh) output.status += QStringLiteral("; host age >500ms");
        if (result.calibrated && calibrated && sync && fresh) {
            const cv::Rect center(result.left.cols * 3 / 8, result.left.rows * 3 / 8,
                                  result.left.cols / 4, result.left.rows / 4);
            const auto range = stereo::DepthEngine::estimate(result, center);
            if (range.valid) output.status = QStringLiteral("Z/ROI center %1 m; calibrated; sync confirmed")
                .arg(range.meters, 0, 'f', 2);
            else output.status += QStringLiteral("; %1").arg(QString::fromStdString(range.reason));
            for (const auto& target : job.targets) {
                if (target.track.predicted || target.track.weakFrames > 0) continue;
                const auto rangeForTrack = stereo::DepthEngine::estimate(result, roi(target.track.box, result.left.size()));
                if (rangeForTrack.valid) output.depths.push_back({target, rangeForTrack.meters});
            }
        }
        output.succeeded = true; return output;
    }
};
}

struct Worker::Impl {
    VisionOptions options;
    const std::vector<StereoPairOptions> pairs;
    std::function<void()> wake;
    mutable std::mutex mutex;
    std::condition_variable changed;
    std::thread thread;
    bool stopping = false, running = false;
    quint64 epoch = 0;
    int generation = 0;
    std::optional<Job> job;
    std::optional<Result> result;
    std::vector<PairStatus> status;
    qint64 metricOrigin = -1;
    qint64 lastFinished = -1;
    std::map<qint64, std::vector<ComputeWindow>> windows;
    Impl(VisionOptions value, std::function<void()> callback)
        : options(std::move(value)), pairs(options.stereoPairs()), wake(std::move(callback)), status(pairs.size()) {}
    void run() {
        // No scheduler/controller code ever accesses these engines.
        std::vector<std::unique_ptr<Engine>> engines;
        for (const auto& pair : pairs) engines.emplace_back(new Engine(pair, options));
        {
            std::lock_guard<std::mutex> lock(mutex);
            for (size_t i = 0; i < engines.size(); ++i)
                status[i] = {bool(engines[i]->engine), engines[i]->status};
        }
        if (wake) wake();
        for (;;) {
            Job value;
            {
                std::unique_lock<std::mutex> lock(mutex);
                changed.wait(lock, [&] { return stopping || job.has_value(); });
                if (stopping) break;
                value = std::move(*job); job.reset(); running = true;
            }
            QElapsedTimer elapsed; elapsed.start();
            Result output; output.stamp = value.stamp;
#ifdef STEREO_ASYNC_TESTING
            if (computeGate) computeGate(value.stamp);
#endif
            try { output = engines.at(value.stamp.pairIndex)->compute(value, options.stereoDisparities); }
            catch (const std::exception& e) {
                output.status = QStringLiteral("Z/ROI invalid: stereo compute failed: %1").arg(QString::fromUtf8(e.what()));
            }
            output.computeMs = elapsed.nsecsElapsed() / 1e6;
            {
                std::lock_guard<std::mutex> lock(mutex);
                // Timestamp and counters commit under the same lock as window
                // extraction: a closed five-second window cannot receive a late event.
                output.finishedMs = nowMs();
                lastFinished = output.finishedMs;
                if (metricOrigin >= 0) {
                    const qint64 start = metricOrigin + ((output.finishedMs - metricOrigin) / 5000) * 5000;
                    auto& counters = windows[start];
                    if (counters.empty()) counters.resize(status.size());
                    auto& counter = counters.at(value.stamp.pairIndex);
                    if (output.succeeded) ++counter.success; else ++counter.failure;
                    counter.totalMs += output.computeMs; counter.maxMs = std::max(counter.maxMs, output.computeMs);
                }
                running = false;
                // Even invalidated computations contribute real completion metrics.
                // Their buffers are destroyed here, with no queued signal/result.
                if (!stopping && output.stamp.epoch == epoch && output.stamp.generation == generation)
                    result = std::move(output);
            }
            if (wake) wake();
        }
    }
};
Worker::Worker(VisionOptions options, std::function<void()> wake)
    : d(new Impl(std::move(options), std::move(wake))) {}
Worker::~Worker() { stop(); join(); }
void Worker::start() { d->thread = std::thread([this] { d->run(); }); }
void Worker::invalidate(quint64 epoch, int generation) {
    std::lock_guard<std::mutex> lock(d->mutex);
    d->epoch = epoch; d->generation = generation; d->job.reset(); d->result.reset();
}
bool Worker::submit(Job job) {
    std::lock_guard<std::mutex> lock(d->mutex);
    const auto& stamp = job.stamp;
    if (d->stopping || d->running || d->job || d->result || stamp.epoch != d->epoch ||
        stamp.generation != d->generation || stamp.pairIndex >= d->status.size() ||
        !d->status[stamp.pairIndex].available) return false;
    if (d->lastFinished >= 0 && nowMs() - d->lastFinished < std::max(1, d->options.stereoIntervalMs)) return false;
    const auto& pair = d->pairs.at(stamp.pairIndex);
    if (stamp.leftCamera != pair.left || stamp.rightCamera != pair.right ||
        job.left.camera != pair.left || job.right.camera != pair.right ||
        job.left.sourceGeneration != stamp.generation || job.right.sourceGeneration != stamp.generation ||
        job.left.frameId != stamp.leftId || job.right.frameId != stamp.rightId ||
        job.left.tag != stamp.leftTag || job.right.tag != stamp.rightTag ||
        job.left.capturedMs != stamp.leftCapturedMs || job.right.capturedMs != stamp.rightCapturedMs ||
        job.left.image.size() != QSize(640, 480) || job.right.image.size() != QSize(640, 480) ||
        job.left.image.format() != QImage::Format_RGB888 || job.right.image.format() != QImage::Format_RGB888 ||
        (pair.synchronizationConfirmed && pair.hasTagOffset && job.left.tag != job.right.tag + quint32(pair.tagOffset))) return false;
    d->job = std::move(job); d->changed.notify_one(); return true;
}
bool Worker::occupied() const {
    std::lock_guard<std::mutex> lock(d->mutex); return d->running || d->job || d->result;
}
qint64 Worker::lastFinishedMs() const { std::lock_guard<std::mutex> lock(d->mutex); return d->lastFinished; }
std::vector<PairStatus> Worker::pairStatus() const { std::lock_guard<std::mutex> lock(d->mutex); return d->status; }
std::optional<Result> Worker::takeResult() {
    std::lock_guard<std::mutex> lock(d->mutex);
    auto result = std::move(d->result); d->result.reset(); return result;
}
void Worker::setMetricOrigin(qint64 startMs) {
    std::lock_guard<std::mutex> lock(d->mutex); if (d->metricOrigin < 0) d->metricOrigin = startMs;
}
std::vector<ComputeWindow> Worker::takeMetricWindow(qint64 startMs) {
    std::lock_guard<std::mutex> lock(d->mutex);
    auto found = d->windows.find(startMs);
    if (found == d->windows.end()) return std::vector<ComputeWindow>(d->status.size());
    auto result = std::move(found->second); d->windows.erase(found); return result;
}
void Worker::stop() {
    std::lock_guard<std::mutex> lock(d->mutex);
    d->stopping = true; ++d->epoch; d->job.reset(); d->result.reset(); d->changed.notify_all();
}
void Worker::join() { if (d->thread.joinable()) d->thread.join(); }
bool associated(const Depth& depth, quint64 revision, const tdm::Track& current, qint64 capturedMs, qint64 now) {
    if (depth.target.revision != revision || depth.target.track.id != current.id ||
        depth.target.track.cls != current.cls || current.predicted || current.weakFrames > 0 ||
        now < capturedMs || now - capturedMs > 300) return false;
    const auto& a = depth.target.track.box; const auto& b = current.box;
    const float area = (a & b).area(); const float combined = a.area() + b.area() - area;
    return combined > 0 && area / combined >= 0.7f &&
        cv::norm((a.tl() + a.br()) * 0.5f - (b.tl() + b.br()) * 0.5f) <=
            std::max(4.0f, std::min(a.width, a.height) * 0.15f);
}
#ifdef STEREO_ASYNC_TESTING
void setComputeGate(std::function<void(const Stamp&)> gate) { computeGate = std::move(gate); }
#endif
} // namespace stereo_async
