#include "vision_pipeline.h"
#include "stereo_async_worker.h"
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QTemporaryFile>
#include <opencv2/imgproc.hpp>
#include <atomic>
#include <condition_variable>
#include <cmath>
#include <cstdio>
#include <functional>
#include <mutex>
#include <thread>
#include <time.h>

namespace {
qint64 nowMs() {
    timespec ts{}; clock_gettime(CLOCK_MONOTONIC, &ts);
    return qint64(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
}
bool until(const std::function<bool()>& predicate, int limit = 2000) {
    QElapsedTimer elapsed; elapsed.start();
    while (!predicate()) {
        if (elapsed.elapsed() >= limit) return false;
        QThread::msleep(2);
    }
    return true;
}
bool check(bool value, const char* name) {
    std::fprintf(value ? stdout : stderr, "%s: %s\n", value ? "PASS" : "FAIL", name); return value;
}
void calibration(const QString& path, double baseline) {
    const cv::Mat K = (cv::Mat_<double>(3, 3) << 400, 0, 320, 0, 400, 240, 0, 0, 1);
    cv::FileStorage file(path.toStdString(), cv::FileStorage::WRITE | cv::FileStorage::FORMAT_YAML);
    file << "image_width" << 640 << "image_height" << 480 << "length_unit" << "m"
         << "K1" << K << "K2" << K << "D1" << cv::Mat::zeros(1, 5, CV_64F)
         << "D2" << cv::Mat::zeros(1, 5, CV_64F) << "R" << cv::Mat::eye(3, 3, CV_64F)
         << "T" << (cv::Mat_<double>(3, 1) << -baseline, 0, 0);
}
std::pair<QImage, QImage> images(int disparity = 20) {
    cv::Mat left(480, 640, CV_8UC1), right(480, 640, CV_8UC1, cv::Scalar(0));
    cv::RNG random(99271); random.fill(left, cv::RNG::UNIFORM, 0, 256);
    cv::GaussianBlur(left, left, {3, 3}, 0.7);
    left(cv::Rect(disparity, 0, 640 - disparity, 480)).copyTo(right(cv::Rect(0, 0, 640 - disparity, 480)));
    auto rgb = [](const cv::Mat& gray) {
        cv::Mat pixels; cv::cvtColor(gray, pixels, cv::COLOR_GRAY2RGB);
        return QImage(pixels.data, pixels.cols, pixels.rows, int(pixels.step), QImage::Format_RGB888).copy();
    };
    return {rgb(left), rgb(right)};
}
VisionFrame frame(const QImage& image, quint64 id, int camera = 0, int generation = 1, quint32 tag = 77) {
    VisionFrame value; value.image = image; value.frameId = id; value.camera = camera;
    value.sourceGeneration = generation; value.tag = tag; value.capturedMs = nowMs(); return value;
}
Detection target() {
    Detection d; d.cls = 3; d.score = 0.95f; d.x1 = 200; d.x2 = 360; d.y1 = 240; d.y2 = 400; return d;
}
VisionOptions options(const QString& path = {}) {
    VisionOptions value; value.stereoGroups = {{0, 1, path, true, true, 0}, {4, 5, path, true, true, 3}};
    value.stereoScale = 0.5; value.stereoDisparities = 64; value.stereoIntervalMs = 250;
    value.detectionIntervalMs = 10000; return value;
}
struct Log {
    std::mutex mutex;
    std::vector<VisionFrame> requests;
    struct Preview { int generation; quint64 id; QImage image; QString status; };
    std::vector<Preview> previews;
    struct Output { QString model; int generation; quint64 id; QVector<Detection> boxes; };
    std::vector<Output> outputs;
    void connect(VisionPipeline& p) {
        QObject::connect(&p, &VisionPipeline::inferenceRequested, &p, [this](VisionFrame f) {
            std::lock_guard<std::mutex> lock(mutex); requests.push_back(f);
        }, Qt::DirectConnection);
        QObject::connect(&p, &VisionPipeline::stereoReady, &p, [this](int gen, quint64 id, QImage image, QString status) {
            std::lock_guard<std::mutex> lock(mutex); previews.push_back({gen, id, image, status});
        }, Qt::DirectConnection);
        QObject::connect(&p, &VisionPipeline::tracksReady, &p, [this](QString model, int gen, quint64 id, QVector<Detection> boxes, double) {
            std::lock_guard<std::mutex> lock(mutex); outputs.push_back({model, gen, id, boxes});
        }, Qt::DirectConnection);
    }
    size_t requestCount() { std::lock_guard<std::mutex> lock(mutex); return requests.size(); }
    bool targetOutput(quint64 id, const QString& model = QStringLiteral("model")) {
        std::lock_guard<std::mutex> lock(mutex);
        for (const auto& o : outputs) if (o.id == id && o.model == model && !o.boxes.empty()) return true;
        return false;
    }
    bool preview(int gen, quint64 id) {
        std::lock_guard<std::mutex> lock(mutex);
        for (const auto& p : previews) if (p.generation == gen && p.id == id && !p.image.isNull()) return true;
        return false;
    }
    bool anyDepth() {
        std::lock_guard<std::mutex> lock(mutex);
        for (const auto& o : outputs) for (const auto& d : o.boxes) if (std::isfinite(d.depthMeters)) return true;
        return false;
    }
};
struct Gate {
    std::mutex mutex;
    std::condition_variable changed;
    bool released = false;
    std::vector<stereo_async::Stamp> entered;
    void hold(const stereo_async::Stamp& stamp) {
        std::unique_lock<std::mutex> lock(mutex); entered.push_back(stamp); changed.notify_all();
        changed.wait(lock, [&] { return released; });
    }
    size_t count() { std::lock_guard<std::mutex> lock(mutex); return entered.size(); }
    void release() { std::lock_guard<std::mutex> lock(mutex); released = true; changed.notify_all(); }
    ~Gate() { release(); }
};

bool parity(const QString& path, bool sync, int disparity, double expected) {
    const auto fixed = images(disparity);
    Log logs[2]; qint64 captures[2]{};
    bool ok = true;
    for (int mode = 0; mode < 2; ++mode) {
        if (mode) qputenv("DETVIEW_STEREO_ASYNC", "1"); else qunsetenv("DETVIEW_STEREO_ASYNC");
        auto value = options(path); value.stereoGroups.resize(1); value.stereoGroups[0].synchronizationConfirmed = sync;
        VisionPipeline p(value); logs[mode].connect(p); p.configure(1, 0, false, {QStringLiteral("model")}); p.start();
        auto left = frame(fixed.first, 10); captures[mode] = left.capturedMs; p.submitFrame(left);
        ok &= check(until([&] { return logs[mode].requestCount() == 1; }), "parity initial request");
        p.submitDetections(QStringLiteral("model"), 1, 10, {target()}, 1);
        ok &= check(until([&] { return logs[mode].targetOutput(10); }), "parity exact-left target initialized");
        p.submitFrame(frame(fixed.second, 12, 1));
        ok &= check(until([&] { return logs[mode].preview(1, 10); }), "parity paired preview");
        p.stop(); p.wait();
    }
    std::vector<Log::Preview> valid[2];
    for (int mode = 0; mode < 2; ++mode) for (const auto& p : logs[mode].previews) if (!p.image.isNull()) valid[mode].push_back(p);
    if (valid[0].size() != 1 || valid[1].size() != 1) return check(false, "exactly one fixed-pair preview per mode");
    ok &= check(valid[0][0].image == valid[1][0].image && valid[0][0].status == valid[1][0].status &&
        valid[0][0].id == 10 && valid[1][0].id == 10, "actual sync/async preview pixels, status and frame tuple parity");
    double meters[2]{};
    for (int mode = 0; mode < 2; ++mode) {
        for (const auto& o : logs[mode].outputs) for (const auto& d : o.boxes) if (std::isfinite(d.depthMeters)) {
            ok &= check(o.model == QStringLiteral("model") && o.generation == 1 && o.id == 10 &&
                d.depthCapturedMs == captures[mode] && d.trackId != 0, "depth model/generation/frame/track/capture association");
            meters[mode] = d.depthMeters;
        }
    }
    if (expected > 0) ok &= check(std::abs(meters[0] - expected) < 0.08 && meters[0] == meters[1], "actual calibrated track depth parity");
    else ok &= check(meters[0] == 0 && meters[1] == 0, "invalid calibration/sync emits no track meters in either mode");
    return ok;
}

stereo_async::Job job(const std::pair<QImage, QImage>& pixels, quint64 epoch = 1, int gen = 1, size_t pair = 0) {
    stereo_async::Job value;
    value.left = frame(pixels.first, 10, pair ? 4 : 0, gen, 77);
    value.right = frame(pixels.second, 12, pair ? 5 : 1, gen, pair ? 74 : 77);
    value.stamp = {epoch, gen, value.left.camera, pair, value.left.camera, value.right.camera,
        10, 12, value.left.tag, value.right.tag, value.left.capturedMs, value.right.capturedMs};
    return value;
}
bool mailbox(const QString& path) {
    bool ok = true; const auto pixels = images();
    Gate gate; stereo_async::setComputeGate([&](const auto& stamp) { gate.hold(stamp); });
    stereo_async::Worker worker(options(path)); worker.invalidate(1, 1); worker.start();
    ok &= check(until([&] { return worker.pairStatus()[0].available; }), "worker owns and prepares engines");
    auto input = job(pixels);
    auto wrong = input; ++wrong.stamp.rightId;
    ok &= check(!worker.submit(wrong), "reject mismatched job frame stamp");
    wrong = input; wrong.stamp.leftCamera = 4;
    ok &= check(!worker.submit(wrong), "reject wrong pair camera identity");
    wrong = input; ++wrong.right.tag; wrong.stamp.rightTag = wrong.right.tag;
    ok &= check(!worker.submit(wrong), "reject wrong synchronization tuple");
    ok &= check(worker.submit(input) && until([&] { return gate.count() == 1; }), "one owned job enters dedicated worker");
    input.left.image.fill(Qt::white); input.left.frameId = 900; // producer detaches, cannot overwrite job pixels
    ok &= check(!worker.submit(job(pixels, 1, 1, 1)) && worker.occupied(), "running job prevents a second job/result");
    gate.release();
    std::optional<stereo_async::Result> result;
    ok &= check(until([&] { result = worker.takeResult(); return bool(result); }), "bounded result delivered");
    if (result) ok &= check(result->succeeded && result->stamp.leftId == 10 &&
        result->status.contains(QStringLiteral("2.00 m")), "owned pixels survive producer replacement; original tuple retained");
    const qint64 finished = worker.lastFinishedMs();
    ok &= check(!worker.submit(job(pixels)), "completion cooldown rejects immediate dispatch");
    ok &= check(until([&] { return nowMs() - finished >= 250; }), "completion cooldown elapses");
    ok &= check(worker.submit(job(pixels, 1, 1, 1)), "other pair admitted after real completion cooldown");
    ok &= check(until([&] { result = worker.takeResult(); return bool(result); }), "other pair completes independently");
    if (result) ok &= check(result->stamp.pairIndex == 1 && result->stamp.leftCamera == 4 &&
        result->stamp.rightCamera == 5 && result->stamp.leftTag == result->stamp.rightTag + 3,
        "result retains independent pair cameras and tag offset");
    worker.stop(); worker.join(); stereo_async::setComputeGate({});
    ok &= check(!worker.submit(job(pixels)), "shutdown refuses new work");

    Gate staleGate; stereo_async::setComputeGate([&](const auto& stamp) { staleGate.hold(stamp); });
    stereo_async::Worker stale(options(path)); stale.invalidate(7, 3); stale.start();
    ok &= check(until([&] { return stale.pairStatus()[0].available; }), "stale worker initialized");
    stale.setMetricOrigin(nowMs());
    ok &= check(stale.submit(job(pixels, 7, 3)) && until([&] { return staleGate.count() == 1; }), "old generation computation in flight");
    stale.invalidate(8, 4);
    ok &= check(!stale.submit(job(pixels, 8, 4)), "generation invalidation retains occupied compute bound");
    staleGate.release();
    ok &= check(until([&] { return !stale.occupied(); }), "stale result dropped instead of queued");
    ok &= check(!stale.takeResult(), "old epoch/generation never delivers a result");
    ok &= check(!stale.submit(job(pixels, 8, 4)), "invalidated completion still enforces cooldown");
    stale.stop(); stale.join(); stereo_async::setComputeGate({});

    Gate stopGate; stereo_async::setComputeGate([&](const auto& stamp) { stopGate.hold(stamp); });
    stereo_async::Worker stopping(options(path)); stopping.invalidate(1, 1); stopping.start();
    ok &= check(until([&] { return stopping.pairStatus()[0].available; }), "shutdown worker initialized");
    ok &= check(stopping.submit(job(pixels)) && until([&] { return stopGate.count() == 1; }), "shutdown job in flight");
    stopping.stop(); std::atomic<bool> joined{false};
    std::thread joiner([&] { stopping.join(); joined = true; });
    QThread::msleep(20);
    ok &= check(!joined && !stopping.takeResult(), "join waits for engine-owned compute and cancels publication");
    stopGate.release(); joiner.join(); stereo_async::setComputeGate({});
    ok &= check(joined && !stopping.takeResult(), "shutdown joins before owned buffers/engines are destroyed");
    return ok;
}
bool association() {
    stereo_async::Depth depth; depth.target.model = QStringLiteral("a"); depth.target.revision = 9;
    depth.target.track.id = 42; depth.target.track.cls = 3; depth.target.track.box = {200, 160, 160, 160};
    auto current = depth.target.track;
    bool ok = check(stereo_async::associated(depth, 9, current, 100, 400), "same target accepts at 300ms age boundary");
    ok &= check(!stereo_async::associated(depth, 10, current, 100, 200), "detection correction revision rejects former target");
    ++current.id; ok &= check(!stereo_async::associated(depth, 9, current, 100, 200), "different track rejects former disparity");
    current = depth.target.track; current.box.x += 100;
    ok &= check(!stereo_async::associated(depth, 9, current, 100, 200), "moved target rejects old ROI");
    current = depth.target.track; current.predicted = true;
    ok &= check(!stereo_async::associated(depth, 9, current, 100, 200), "predicted target rejects metric depth");
    current.predicted = false; current.weakFrames = 1;
    ok &= check(!stereo_async::associated(depth, 9, current, 100, 200), "weak target rejects metric depth");
    current = depth.target.track;
    ok &= check(!stereo_async::associated(depth, 9, current, 100, 401) &&
        !stereo_async::associated(depth, 9, current, 100, 99), "expired/future capture rejects result");
    return ok;
}

bool scheduling(const QString& path, bool correction) {
    qputenv("DETVIEW_STEREO_ASYNC", "1");
    bool ok = true; const auto pixels = images();
    Gate gate; stereo_async::setComputeGate([&](const auto& stamp) { gate.hold(stamp); });
    auto value = options(path); value.stereoGroups.resize(1); value.detectionIntervalMs = 1; value.minimumDetectionIntervalMs = 1;
    Log log; VisionPipeline p(value); log.connect(p); p.configure(1, 0, false, {QStringLiteral("model")}); p.start();
    p.submitFrame(frame(pixels.first, 10));
    ok &= check(until([&] { return log.requestCount() == 1; }), "scheduler initial inference reservation");
    if (correction) {
        p.submitDetections(QStringLiteral("model"), 1, 10, {target()}, 1);
        ok &= check(until([&] { return log.targetOutput(10); }), "old target initialized before stereo");
    }
    p.submitFrame(frame(pixels.second, 12, 1));
    ok &= check(until([&] { return gate.count() == 1; }), "stereo compute held outside scheduler");
    if (correction) {
        p.submitFrame(frame(pixels.first, 11));
        ok &= check(until([&] { return log.requestCount() == 2; }), "next inference admitted while stereo blocked");
        auto changed = target(); changed.x1 += 100; changed.x2 += 100;
        p.submitDetections(QStringLiteral("model"), 1, 11, {changed}, 1);
        ok &= check(until([&] { return log.targetOutput(11); }), "authoritative target correction consumed during stereo");
    } else {
        p.submitFrame(frame(pixels.first, 11));
        QThread::msleep(20); ok &= check(log.requestCount() == 1, "pending inference stays reserved until its own reply");
        p.submitDetections(QStringLiteral("model"), 1, 999, {}, 1);
        QThread::msleep(20); ok &= check(log.requestCount() == 1, "wrong reply cannot release pending inference");
        p.submitDetections(QStringLiteral("model"), 1, 10, {target()}, 1);
        ok &= check(until([&] { return log.targetOutput(11) && log.requestCount() == 2; }),
            "own reply consumed/replayed and next inference admitted during blocked stereo");
    }
    gate.release();
    ok &= check(until([&] { return log.preview(1, 10); }), "original left-frame preview delivered after scheduler progress");
    ok &= check(!log.anyDepth(), correction ? "correction invalidates in-flight target depth" : "later detection cannot attach to job with no original target");
    p.stop(); p.wait(); stereo_async::setComputeGate({}); return ok;
}
bool configuration(const QString& path) {
    qputenv("DETVIEW_STEREO_ASYNC", "1");
    const auto pixels = images(); bool ok = true;
    Gate gate; stereo_async::setComputeGate([&](const auto& stamp) { gate.hold(stamp); });
    Log log; VisionPipeline p(options(path)); log.connect(p);
    p.configure(1, 0, false, {QStringLiteral("old")}); p.start();
    p.submitFrame(frame(pixels.first, 10)); p.submitFrame(frame(pixels.second, 12, 1));
    ok &= check(until([&] { return gate.count() == 1; }), "configuration test compute in flight");
    // Same generation and reused frame IDs: epoch, model and selected pair must
    // still invalidate the old result and leave only new camera inference.
    p.configure(1, 4, false, {QStringLiteral("new")});
    p.submitFrame(frame(pixels.first, 1, 4, 1, 13)); p.submitFrame(frame(pixels.second, 2, 5, 1, 10));
    ok &= check(until([&] { return log.requestCount() == 2; }), "same-generation configuration progresses during old compute");
    gate.release();
    ok &= check(until([&] { return log.preview(1, 1); }), "new selected pair resumes after stale completion cooldown");
    ok &= check(!log.preview(1, 10), "configuration epoch drops old pair preview");
    p.stop(); p.wait(); stereo_async::setComputeGate({}); return ok;
}
bool laterFrame(const QString& path) {
    qputenv("DETVIEW_STEREO_ASYNC", "1");
    const auto pixels = images(); bool ok = true;
    Gate gate; stereo_async::setComputeGate([&](const auto& stamp) { gate.hold(stamp); });
    auto value = options(path); value.stereoGroups.resize(1);
    Log log; VisionPipeline p(value); log.connect(p); p.configure(1, 0, false, {QStringLiteral("model")}); p.start();
    auto left = frame(pixels.first, 10); p.submitFrame(left);
    ok &= check(until([&] { return log.requestCount() == 1; }), "later-frame source inference request");
    p.submitDetections(QStringLiteral("model"), 1, 10, {target()}, 1);
    ok &= check(until([&] { return log.targetOutput(10); }), "later-frame original target corrected");
    p.submitFrame(frame(pixels.second, 12, 1));
    ok &= check(until([&] { return gate.count() == 1; }), "later-frame stereo holds exact source target snapshot");
    p.submitFrame(frame(pixels.first, 11));
    ok &= check(until([&] { return log.targetOutput(11); }), "later-frame tracker progresses during compute");
    gate.release(); ok &= check(until([&] { return log.preview(1, 10); }), "later-frame original disparity preview identity");
    {
        std::lock_guard<std::mutex> lock(log.mutex); bool found = false;
        for (const auto& o : log.outputs) for (const auto& d : o.boxes) if (std::isfinite(d.depthMeters)) {
            found = true;
            ok &= check(o.id == 11 && d.depthCapturedMs == left.capturedMs && std::abs(d.depthMeters - 2.0) < 0.08,
                "current track publication retains original disparity capture time and optical depth");
        }
        ok &= check(found, "unchanged associated current target receives short-lived source measurement");
    }
    p.stop(); p.wait(); stereo_async::setComputeGate({}); return ok;
}
bool continuousMetrics() {
    qputenv("DETVIEW_STEREO_ASYNC", "1");
    auto value = options(); const auto pixels = images();
    std::mutex mutex; std::vector<stereo_async::Stamp> starts;
    stereo_async::setComputeGate([&](const auto& stamp) { std::lock_guard<std::mutex> lock(mutex); starts.push_back(stamp); });
    VisionPipeline p(value); p.configure(1, 0, false, {}); p.start();
    QElapsedTimer elapsed; elapsed.start(); quint64 id = 1;
    while (elapsed.elapsed() < 10500) {
        p.submitFrame(frame(pixels.first, id, 0, 1, quint32(id)));
        p.submitFrame(frame(pixels.second, id, 1, 1, quint32(id)));
        p.submitFrame(frame(pixels.first, id, 4, 1, quint32(id + 3)));
        p.submitFrame(frame(pixels.second, id, 5, 1, quint32(id)));
        ++id; QThread::msleep(20);
    }
    p.stop(); p.wait(); stereo_async::setComputeGate({});
    bool ok = check(starts.size() >= 6, "continuous configured pairs execute jobs");
    size_t counts[2]{};
    for (size_t i = 0; i < starts.size(); ++i) {
        ++counts[starts[i].pairIndex];
        if (i) ok &= check(starts[i].pairIndex != starts[i - 1].pairIndex, "ready pairs rotate fairly without starvation");
    }
    ok &= check(counts[0] >= 3 && counts[1] >= 3, "each pair makes independent repeated progress");
    // Raw stderr windows are independently checked by local_checks.sh/Python.
    return ok;
}
}

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv); cv::setNumThreads(1);
    if (argc > 1 && QByteArray(argv[1]) == "--metrics") return continuousMetrics() ? 0 : 1;
    QTemporaryFile file; if (!file.open()) return 2; file.close(); calibration(file.fileName(), 0.1);
    QTemporaryFile second; if (!second.open()) return 2; second.close(); calibration(second.fileName(), 0.2);
    QTemporaryFile malformed; if (!malformed.open()) return 2; malformed.write("invalid calibration\n"); malformed.close();
    bool ok = parity(file.fileName(), true, 20, 2.0);
    ok &= parity(second.fileName(), true, 32, 2.5);
    ok &= parity(file.fileName(), false, 20, 0);
    ok &= parity({}, true, 20, 0);
    ok &= parity(malformed.fileName(), true, 20, 0);
    ok &= mailbox(file.fileName()); ok &= association();
    ok &= scheduling(file.fileName(), false); ok &= scheduling(file.fileName(), true); ok &= configuration(file.fileName());
    ok &= laterFrame(file.fileName());
    std::fprintf(ok ? stdout : stderr, "STEREO_ASYNC_SELFTEST_%s\n", ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}
