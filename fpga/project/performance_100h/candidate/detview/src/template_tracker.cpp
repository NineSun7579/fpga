#include "template_tracker.h"

#include <opencv2/imgproc.hpp>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace tdm {
namespace {

std::atomic<uint64_t> nextId{1};

uint64_t allocateId() {
    uint64_t id = nextId.load(std::memory_order_relaxed);
    for (;;) {
        if (id == std::numeric_limits<uint64_t>::max())
            throw std::overflow_error("template tracker ID space exhausted");
        if (nextId.compare_exchange_weak(id, id + 1, std::memory_order_relaxed))
            return id;
    }
}

cv::Point2f center(const cv::Rect2f& box) {
    return {box.x + box.width * 0.5f, box.y + box.height * 0.5f};
}

cv::Rect2f clip(cv::Rect2f box, cv::Size size) {
    return box & cv::Rect2f(0, 0, static_cast<float>(size.width),
                          static_cast<float>(size.height));
}

bool validBox(const cv::Rect2f& b) {
    return std::isfinite(b.x) && std::isfinite(b.y) &&
           std::isfinite(b.width) && std::isfinite(b.height) &&
           std::isfinite(b.x + b.width) && std::isfinite(b.y + b.height) &&
           b.width > 0 && b.height > 0;
}

float iou(const cv::Rect2f& a, const cv::Rect2f& b) {
    const float intersection = (a & b).area();
    const float total = a.area() + b.area() - intersection;
    return total > 0 ? intersection / total : 0;
}

bool textured(const cv::Mat& patch, float minimum) {
    if (patch.empty() || patch.cols < 4 || patch.rows < 4) return false;
    cv::Scalar mean, deviation;
    cv::meanStdDev(patch, mean, deviation);
    // A nonzero floor is necessary even when the configured threshold is zero:
    // TM_CCOEFF_NORMED reports 1 for a constant template.
    return deviation[0] >= std::max(0.5f, minimum);
}

cv::Rect scaledRect(const cv::Rect2f& b, cv::Size original, cv::Size small) {
    const double sx = static_cast<double>(small.width) / original.width;
    const double sy = static_cast<double>(small.height) / original.height;
    const int x = std::clamp(static_cast<int>(std::floor(b.x * sx)), 0, small.width);
    const int y = std::clamp(static_cast<int>(std::floor(b.y * sy)), 0, small.height);
    const int r = std::clamp(static_cast<int>(std::ceil((b.x + b.width) * sx)), x, small.width);
    const int d = std::clamp(static_cast<int>(std::ceil((b.y + b.height) * sy)), y, small.height);
    return {x, y, r - x, d - y};
}

struct Peak {
    float score;
    cv::Rect box;
};

// Keep a distant runner-up from EACH scale so duplicate objects and periodic
// textures cannot pass simply by producing many equally good NCC peaks.
void addPeaks(const cv::Mat& image, cv::Rect window, const cv::Mat& appearance,
              cv::Size size, float minimumTexture, std::vector<Peak>& peaks) {
    if (size.width < 4 || size.height < 4 || size.width > window.width ||
        size.height > window.height) return;
    cv::Mat templ;
    cv::resize(appearance, templ, size, 0, 0, cv::INTER_LINEAR);
    if (!textured(templ, minimumTexture)) return;
    cv::Mat response;
    cv::matchTemplate(image(window), templ, response, cv::TM_CCOEFF_NORMED);
    cv::patchNaNs(response, -1);
    for (int n = 0; n < 2; ++n) {
        double score;
        cv::Point location;
        cv::minMaxLoc(response, nullptr, &score, nullptr, &location);
        if (!std::isfinite(score) || score < -0.5) break;
        peaks.push_back({static_cast<float>(score),
                         cv::Rect(location + window.tl(), size)});
        const int rx = std::max(2, size.width / 4);
        const int ry = std::max(2, size.height / 4);
        const cv::Rect suppress = cv::Rect(location.x - rx, location.y - ry,
                                           rx * 2 + 1, ry * 2 + 1) &
                                  cv::Rect(0, 0, response.cols, response.rows);
        response(suppress).setTo(-1);
    }
}

} // namespace

TemplateTracker::TemplateTracker(TrackerOptions options) : options_(options) {
    if (options.maxTracks <= 0 || options.maxTracks > 12 ||
        !std::isfinite(options.scale) || options.scale <= 0 || options.scale > 1 ||
        !std::isfinite(options.matchThreshold) || options.matchThreshold <= 0 ||
        options.matchThreshold > 1 || !std::isfinite(options.updateThreshold) ||
        options.updateThreshold < options.matchThreshold || options.updateThreshold > 1 ||
        !std::isfinite(options.minimumTextureStdDev) || options.minimumTextureStdDev < 0 ||
        options.maxWeakFrames < 0 || options.maxDetectionAgeMs <= 0)
        throw std::invalid_argument("invalid template tracker options");
}

TemplateTracker::TemplateTracker(const TemplateTracker& other)
    : options_(other.options_), states_(other.states_), imageSize_(other.imageSize_),
      lastFrameMs_(other.lastFrameMs_), lastDetectionMs_(other.lastDetectionMs_) {
    for (auto& state : states_) {
        state.appearance = state.appearance.clone();
        state.anchor = state.anchor.clone();
    }
}

TemplateTracker& TemplateTracker::operator=(const TemplateTracker& other) {
    if (this != &other) {
        TemplateTracker copy(other);
        *this = std::move(copy);
    }
    return *this;
}

void TemplateTracker::clear() {
    states_.clear();
    imageSize_ = {};
    lastFrameMs_ = lastDetectionMs_ = -1;
}

void TemplateTracker::validateTime(int64_t timeMs) const {
    if (timeMs < 0 || timeMs < lastFrameMs_)
        throw std::invalid_argument("template tracker time moved backwards");
}

cv::Mat TemplateTracker::prepare(const cv::Mat& gray, int64_t timeMs) {
    validateTime(timeMs);
    if (gray.empty() || gray.type() != CV_8UC1 || gray.dims != 2)
        throw std::invalid_argument("template tracker requires nonempty CV_8UC1");
    const cv::Size small(std::max(1, cvRound(gray.cols * options_.scale)),
                         std::max(1, cvRound(gray.rows * options_.scale)));
    cv::Mat result;
    cv::resize(gray, result, small, 0, 0, cv::INTER_AREA);
    if (imageSize_ != gray.size()) {
        states_.clear();
        lastDetectionMs_ = -1;
        imageSize_ = gray.size();
    }
    return result;
}

void TemplateTracker::correct(const cv::Mat& gray,
                              const std::vector<ObjectDetection>& detections,
                              int64_t timeMs) {
    const cv::Mat small = prepare(gray, timeMs);
    struct Candidate { ObjectDetection det; cv::Mat patch; };
    std::vector<ObjectDetection> ordered;
    ordered.reserve(detections.size());
    for (auto det : detections) {
        if (!validBox(det.box) || !std::isfinite(det.score)) continue;
        det.box = clip(det.box, imageSize_);
        if (det.box.area() > 0) ordered.push_back(det);
    }
    std::stable_sort(ordered.begin(), ordered.end(), [](const auto& a, const auto& b) {
        return a.score > b.score;
    });
    std::vector<Candidate> candidates;
    for (const auto& det : ordered) {
        const cv::Rect roi = scaledRect(det.box, imageSize_, small.size());
        if (!textured(small(roi), options_.minimumTextureStdDev)) continue;
        candidates.push_back({det, small(roi).clone()});
        if (candidates.size() >= static_cast<size_t>(options_.maxTracks)) break;
    }
    struct Pair { float overlap; size_t oldIndex; size_t newIndex; };
    std::vector<Pair> pairs;
    for (size_t old = 0; old < states_.size(); ++old) {
        const auto& s = states_[old];
        if (timeMs - s.detectionMs > options_.maxDetectionAgeMs) continue;
        cv::Rect2f predicted = s.track.box;
        const float dt = static_cast<float>(std::min<int64_t>(100, timeMs - lastFrameMs_));
        predicted.x += s.velocity.x * dt;
        predicted.y += s.velocity.y * dt;
        predicted = clip(predicted, imageSize_);
        for (size_t n = 0; n < candidates.size(); ++n) {
            if (s.track.cls != candidates[n].det.cls) continue;
            const float overlap = iou(predicted, candidates[n].det.box);
            if (overlap >= 0.2f) pairs.push_back({overlap, old, n});
        }
    }
    std::stable_sort(pairs.begin(), pairs.end(), [](const Pair& a, const Pair& b) {
        return a.overlap > b.overlap;
    });
    std::vector<int> associated(candidates.size(), -1);
    std::vector<bool> used(states_.size(), false);
    for (const auto& p : pairs) {
        if (used[p.oldIndex] || associated[p.newIndex] >= 0) continue;
        used[p.oldIndex] = true;
        associated[p.newIndex] = static_cast<int>(p.oldIndex);
    }
    std::vector<State> corrected;
    for (size_t n = 0; n < candidates.size(); ++n) {
        const auto& c = candidates[n];
        State s;
        if (associated[n] >= 0) s.track.id = states_[associated[n]].track.id;
        else s.track.id = allocateId();
        s.track.cls = c.det.cls;
        s.track.detectionScore = c.det.score;
        s.track.box = c.det.box;
        // A detector observation is not an NCC measurement: matchScore stays 0.
        s.appearance = c.patch;
        s.anchor = c.patch.clone();
        s.observedCenter = center(c.det.box);
        s.detectedSize = c.det.box.size();
        s.observedMs = s.detectionMs = timeMs;
        corrected.push_back(std::move(s));
    }
    states_ = std::move(corrected);
    lastFrameMs_ = lastDetectionMs_ = timeMs;
}

std::vector<Track> TemplateTracker::update(const cv::Mat& gray, int64_t timeMs) {
    const cv::Mat small = prepare(gray, timeMs);
    if (lastFrameMs_ == timeMs) return tracks(timeMs);
    const float sx = static_cast<float>(small.cols) / gray.cols;
    const float sy = static_cast<float>(small.rows) / gray.rows;
    const float dt = lastFrameMs_ < 0 ? 0 :
        static_cast<float>(std::min<int64_t>(100, timeMs - lastFrameMs_));
    for (auto& s : states_) {
        if (timeMs - s.detectionMs > options_.maxDetectionAgeMs) continue;
        const cv::Rect2f previous = s.track.box;
        cv::Rect2f predicted = previous;
        predicted.x += s.velocity.x * dt;
        predicted.y += s.velocity.y * dt;
        // Clamp the whole box rather than shrinking the prediction at edges.
        predicted.x = std::clamp(predicted.x, 0.f, gray.cols - predicted.width);
        predicted.y = std::clamp(predicted.y, 0.f, gray.rows - predicted.height);
        const cv::Rect expected = scaledRect(predicted, imageSize_, small.size());
        const int rx = cvRound(std::max(12.f, expected.width * 0.6f) +
                               std::min(s.track.weakFrames, 3) * 4);
        const int ry = cvRound(std::max(12.f, expected.height * 0.6f) +
                               std::min(s.track.weakFrames, 3) * 4);
        const cv::Rect window = cv::Rect(expected.x - rx, expected.y - ry,
                                         expected.width + rx * 2, expected.height + ry * 2) &
                                cv::Rect(0, 0, small.cols, small.rows);
        std::vector<Peak> peaks;
        for (float scale : {1.f, 0.95f, 1.05f}) {
            // Prediction can have subpixel coordinates. floor/ceil of its ROI
            // must not inflate the template size on each frame.
            const cv::Size size(cvRound(previous.width * sx * scale),
                                cvRound(previous.height * sy * scale));
            if (size.width / sx < s.detectedSize.width * 0.7f ||
                size.width / sx > s.detectedSize.width * 1.4f ||
                size.height / sy < s.detectedSize.height * 0.7f ||
                size.height / sy > s.detectedSize.height * 1.4f) continue;
            addPeaks(small, window, s.appearance, size, options_.minimumTextureStdDev, peaks);
        }
        std::stable_sort(peaks.begin(), peaks.end(), [](const Peak& a, const Peak& b) {
            return a.score > b.score;
        });
        bool accepted = !peaks.empty() && peaks[0].score >= options_.matchThreshold;
        if (accepted) {
            const auto& best = peaks[0];
            const cv::Point2f bestCenter = center(cv::Rect2f(best.box));
            for (size_t i = 1; i < peaks.size(); ++i) {
                const cv::Point2f difference = center(cv::Rect2f(peaks[i].box)) - bestCenter;
                if ((std::abs(difference.x) > std::max(2.f, best.box.width * 0.25f) ||
                     std::abs(difference.y) > std::max(2.f, best.box.height * 0.25f)) &&
                    peaks[i].score >= options_.matchThreshold &&
                    best.score - peaks[i].score < 0.05f) accepted = false;
            }
            accepted = accepted && textured(small(best.box), options_.minimumTextureStdDev);
        }
        s.track.matchScore = peaks.empty() ? 0.f : std::clamp(peaks[0].score, 0.f, 1.f);
        if (accepted) {
            const auto& best = peaks[0];
            s.track.box = clip({best.box.x / sx, best.box.y / sy,
                                best.box.width / sx, best.box.height / sy}, imageSize_);
            const cv::Point2f nowCenter = center(s.track.box);
            if (timeMs > s.observedMs) {
                const cv::Point2f measured = (nowCenter - s.observedCenter) *
                    (1.f / static_cast<float>(timeMs - s.observedMs));
                s.velocity = s.velocity * 0.5f + measured * 0.5f;
            }
            s.observedCenter = nowCenter;
            s.observedMs = timeMs;
            s.track.weakFrames = 0;
            s.track.predicted = false;
            s.stableFrames = best.score >= options_.updateThreshold ?
                std::min(3, s.stableFrames + 1) : 0;
            // Only adapt after stable strong matches that also agree with the
            // immutable detection anchor. Replace Mat storage, never alias pixels.
            if (s.stableFrames >= 3) {
                cv::Mat patch, anchorScore;
                cv::resize(small(best.box), patch, s.anchor.size(), 0, 0, cv::INTER_AREA);
                cv::matchTemplate(patch, s.anchor, anchorScore, cv::TM_CCOEFF_NORMED);
                if (anchorScore.at<float>(0, 0) >= options_.updateThreshold) {
                    cv::Mat adapted, old;
                    cv::resize(s.appearance, old, patch.size(), 0, 0, cv::INTER_LINEAR);
                    cv::addWeighted(old, 0.98, patch, 0.02, 0, adapted);
                    s.appearance = std::move(adapted);
                }
            }
        } else {
            s.track.box = predicted;
            s.track.predicted = true;
            ++s.track.weakFrames;
            s.stableFrames = 0;
        }
    }
    states_.erase(std::remove_if(states_.begin(), states_.end(), [&](const State& s) {
        return timeMs - s.detectionMs > options_.maxDetectionAgeMs ||
               s.track.weakFrames > options_.maxWeakFrames;
    }), states_.end());
    lastFrameMs_ = timeMs;
    return tracks(timeMs);
}

std::vector<Track> TemplateTracker::tracks(int64_t timeMs) const {
    validateTime(timeMs);
    std::vector<Track> result;
    for (const auto& s : states_) {
        if (timeMs - s.detectionMs <= options_.maxDetectionAgeMs &&
            s.track.weakFrames <= options_.maxWeakFrames) {
            Track value = s.track;
            value.validUntilMs = s.detectionMs + options_.maxDetectionAgeMs;
            result.push_back(value);
        }
    }
    return result;
}

bool TemplateTracker::needsDetection(int64_t timeMs) const {
    validateTime(timeMs);
    if (lastDetectionMs_ < 0 ||
        timeMs - lastDetectionMs_ >= std::min(500, options_.maxDetectionAgeMs)) return true;
    const auto live = tracks(timeMs);
    return live.empty() || std::any_of(live.begin(), live.end(), [](const Track& t) {
        return t.weakFrames > 0 || t.predicted;
    });
}

} // namespace tdm
