#pragma once

#include <opencv2/core.hpp>
#include <cstdint>
#include <vector>

namespace tdm {

struct ObjectDetection {
    int cls = 0;
    float score = 0;
    cv::Rect2f box;
};

struct Track {
    uint64_t id = 0;
    int cls = 0;
    float detectionScore = 0;
    float matchScore = 0;
    cv::Rect2f box;
    int weakFrames = 0;
    bool predicted = false;
    int64_t validUntilMs = 0;
};

struct TrackerOptions {
    int maxTracks = 12;
    double scale = 0.5;
    float matchThreshold = 0.65f;
    float updateThreshold = 0.85f;
    float minimumTextureStdDev = 5;
    int maxWeakFrames = 3;
    int maxDetectionAgeMs = 2000;
};

// One instance per camera/source AND detector model; externally synchronized.
// All boxes use input image pixels (normally the original 640x480 camera image),
// never padded model pixels. Images must be nonempty CV_8UC1; time is nonnegative
// monotonic milliseconds. Invalid options/images/time throw std::invalid_argument.
class TemplateTracker {
public:
    explicit TemplateTracker(TrackerOptions options = {});
    // Owned templates are cloned: history snapshots share no mutable pixels.
    TemplateTracker(const TemplateTracker& other);
    TemplateTracker& operator=(const TemplateTracker& other);
    TemplateTracker(TemplateTracker&&) noexcept = default;
    TemplateTracker& operator=(TemplateTracker&&) noexcept = default;

    // Reset source, time and tracks; process-global IDs are never reused.
    void clear();
    // Authoritative full detection result for this instance's model. Same-class
    // IoU >= 0.2 pairs associate one-to-one; unmatched old tracks are removed.
    // Nonfinite/empty/textureless detections are ignored; highest scores fill the
    // bound. Templates and detection TTL are reset only here, not by update().
    // timeMs == current frame is allowed; timeMs < current frame throws BEFORE
    // mutation. Delayed results require restoring the source-frame snapshot,
    // correcting with source gray/time, then update() on later history frames.
    void correct(const cv::Mat& gray,
                 const std::vector<ObjectDetection>& detections, int64_t timeMs);
    // Local NCC search at three modest scales around a velocity prediction.
    // Failed/ambiguous matches produce at most maxWeakFrames predicted frames.
    // Same-time calls are idempotent (image validation still applies). A changed
    // input size clears tracks and detection age, preserving global ID uniqueness.
    std::vector<Track> update(const cv::Mat& gray, int64_t timeMs);
    // Read-only TTL filtering; no extrapolation or mutation. Queries before the
    // current state time throw. Age > maxDetectionAgeMs hides a track, even if
    // every template match succeeds. Returned boxes are clipped inside the image.
    std::vector<Track> tracks(int64_t timeMs) const;
    // True for no live tracks, weak tracking, or elapsed detection age >=
    // min(500ms, maxDetectionAgeMs). Periodic NPU scheduling is the caller's job;
    // strong matches/template adaptation cannot postpone this refresh request.
    bool needsDetection(int64_t timeMs) const;

private:
    struct State {
        Track track;
        cv::Mat appearance;
        cv::Mat anchor;
        cv::Point2f velocity;
        cv::Point2f observedCenter;
        cv::Size2f detectedSize;
        int64_t observedMs = 0;
        int64_t detectionMs = 0;
        int stableFrames = 0;
    };
    TrackerOptions options_;
    std::vector<State> states_;
    cv::Size imageSize_;
    int64_t lastFrameMs_ = -1;
    int64_t lastDetectionMs_ = -1;

    void validateTime(int64_t timeMs) const;
    cv::Mat prepare(const cv::Mat& gray, int64_t timeMs);
};

// Returns 0 on success and prints TRACKER_SELFTEST_PASS; no Qt, NPU or hardware.
// Define TDM_TRACKER_SELFTEST_MAIN to build a standalone host executable.
int runTrackerSelfTest();
int runTrackerBenchmark(); // Synthetic CPU matching only, no camera or NPU access.

} // namespace tdm
