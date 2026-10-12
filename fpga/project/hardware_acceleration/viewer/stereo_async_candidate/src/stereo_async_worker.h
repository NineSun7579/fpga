#pragma once

#include "vision_types.h"
#include "template_tracker.h"
#include <functional>
#include <memory>
#include <optional>

namespace stereo_async {

// Values only: no references into scheduler history, frame slots or trackers.
struct Target {
    QString model;
    quint64 revision = 0; // increments on authoritative detection correction
    tdm::Track track;
};
struct Stamp {
    quint64 epoch = 0;
    int generation = 0, selectedCamera = -1;
    size_t pairIndex = 0;
    int leftCamera = -1, rightCamera = -1;
    quint64 leftId = 0, rightId = 0;
    quint32 leftTag = 0, rightTag = 0;
    qint64 leftCapturedMs = -1, rightCapturedMs = -1;
};
struct Job {
    Stamp stamp;
    VisionFrame left, right;
    std::vector<Target> targets;
};
struct Depth {
    Target target;
    double meters = 0;
};
struct Result {
    Stamp stamp;
    bool succeeded = false;
    qint64 finishedMs = -1;
    double computeMs = 0;
    QImage preview;
    QString status;
    std::vector<Depth> depths;
};
struct PairStatus { bool available = false; QString calibrationStatus; };
struct ComputeWindow {
    quint64 success = 0, failure = 0;
    double totalMs = 0, maxMs = 0;
};

// Public methods synchronize only the bounded mailbox and completion counters.
// Calibration, rectification maps and both SGBM matchers live on the worker's
// stack and are created, used and destroyed on that same thread.
class Worker {
public:
    explicit Worker(VisionOptions options, std::function<void()> wake = {});
    ~Worker();
    void start();
    void invalidate(quint64 epoch, int generation);
    bool submit(Job job);
    bool occupied() const;
    qint64 lastFinishedMs() const;
    std::vector<PairStatus> pairStatus() const;
    std::optional<Result> takeResult();
    void setMetricOrigin(qint64 startMs);
    std::vector<ComputeWindow> takeMetricWindow(qint64 startMs);
    void stop();
    void join();
private:
    struct Impl;
    std::unique_ptr<Impl> d;
};

// The original measurement belongs to the copied left-frame target; a later
// tracker correction or a different/currently weak target cannot inherit it.
bool associated(const Depth& depth, quint64 revision, const tdm::Track& current,
                qint64 capturedMs, qint64 now);

#ifdef STEREO_ASYNC_TESTING
// Standalone local tests only; excluded from the viewer build. Install before
// creating a worker, remove after join. Enables deterministic in-flight events.
void setComputeGate(std::function<void(const Stamp&)> gate);
#endif

} // namespace stereo_async
