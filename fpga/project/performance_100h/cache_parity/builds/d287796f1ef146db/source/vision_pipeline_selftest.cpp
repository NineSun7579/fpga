#include "vision_pipeline.h"
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QMutex>
#include <QMutexLocker>
#include <QTextStream>
#include <QTemporaryFile>
#include <opencv2/imgproc.hpp>
#include <algorithm>
#include <cmath>
#include <functional>
#include <time.h>

namespace {
qint64 testNow() {
    timespec ts{};
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return qint64(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
}
bool until(const std::function<bool()>& predicate, int timeout = 1000) {
    QElapsedTimer timer; timer.start();
    while (!predicate()) {
        if (timer.elapsed() >= timeout) return false;
        QThread::msleep(2);
    }
    return true;
}
QImage fixture(int shift = 0, bool blank = false) {
    QImage image(640, 480, QImage::Format_RGB888);
    image.fill(Qt::black);
    if (blank) return image;
    // Stable, textured, distinctive target translated in original camera pixels.
    quint32 seed = 739391;
    for (int y = 150; y < 230; ++y) {
        auto* row = image.scanLine(y);
        for (int x = 200 + shift; x < 280 + shift; ++x) {
            seed = seed * 1664525U + 1013904223U;
            const uchar value = uchar(30 + (seed >> 24) % 210);
            row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = value;
        }
    }
    return image;
}
VisionFrame frame(quint64 id, int generation = 1, int camera = 0, int shift = 0, bool blank = false) {
    VisionFrame f;
    f.image = fixture(shift, blank); f.frameId = id; f.sourceGeneration = generation;
    f.camera = camera; f.tag = quint32(id); f.capturedMs = testNow();
    return f;
}
Detection target() {
    Detection d;
    d.cls = 3; d.score = 0.95f;
    d.x1 = 200; d.x2 = 280; d.y1 = 230; d.y2 = 310;
    return d;
}
void writeCalibration(const QString& path, double baseline) {
    const cv::Mat K = (cv::Mat_<double>(3, 3) << 400, 0, 320, 0, 400, 240, 0, 0, 1);
    cv::FileStorage file(path.toStdString(), cv::FileStorage::WRITE | cv::FileStorage::FORMAT_YAML);
    file << "image_width" << 640 << "image_height" << 480 << "length_unit" << "m"
         << "K1" << K << "K2" << K << "D1" << cv::Mat::zeros(1, 5, CV_64F)
         << "D2" << cv::Mat::zeros(1, 5, CV_64F) << "R" << cv::Mat::eye(3, 3, CV_64F)
         << "T" << (cv::Mat_<double>(3, 1) << -baseline, 0, 0);
}
struct Log {
    QMutex mutex;
    QVector<VisionFrame> requests;
    QVector<qint64> requestedAt;
    struct Output { QString model; int generation; quint64 id; QVector<Detection> boxes; };
    QVector<Output> outputs;
    QStringList stereo;
    struct StereoOutput { int generation; quint64 id; bool preview; QString status; qint64 at; };
    QVector<StereoOutput> stereoOutputs;
    QStringList diagnostics;
    int stereoPreviews = 0;
    void connect(VisionPipeline& p) {
        QObject::connect(&p, &VisionPipeline::inferenceRequested, &p, [this](VisionFrame f) {
            QMutexLocker lock(&mutex); requests.push_back(f); requestedAt.push_back(testNow());
        }, Qt::DirectConnection);
        QObject::connect(&p, &VisionPipeline::tracksReady, &p,
            [this](QString m, int gen, quint64 id, QVector<Detection> boxes, double) {
                QMutexLocker lock(&mutex); outputs.push_back({m, gen, id, boxes});
            }, Qt::DirectConnection);
        QObject::connect(&p, &VisionPipeline::stereoReady, &p,
            [this](int gen, quint64 id, QImage image, QString s) {
                QMutexLocker lock(&mutex); stereo.push_back(s);
                stereoOutputs.push_back({gen, id, !image.isNull(), s, testNow()});
                if (!image.isNull()) ++stereoPreviews;
            }, Qt::DirectConnection);
        QObject::connect(&p, &VisionPipeline::diagnostics, &p, [this](QString s) {
            QMutexLocker lock(&mutex); diagnostics.push_back(s);
        }, Qt::DirectConnection);
    }
    int count() { QMutexLocker lock(&mutex); return requests.size(); }
    VisionFrame request(int i) { QMutexLocker lock(&mutex); return requests[i]; }
    int outputCount() { QMutexLocker lock(&mutex); return outputs.size(); }
    bool hasOutput(const QString& model, int generation, quint64 id, bool requireTarget = false) {
        QMutexLocker lock(&mutex);
        for (const auto& o : outputs) if (o.model == model && o.generation == generation && o.id == id &&
            (!requireTarget || !o.boxes.isEmpty())) return true;
        return false;
    }
    bool hasDepth(int generation, quint64 id, double meters, qint64 captured) {
        QMutexLocker lock(&mutex);
        for (const auto& o : outputs) if (o.generation == generation && o.id == id)
            for (const auto& box : o.boxes)
                if (std::isfinite(box.depthMeters) && std::abs(box.depthMeters - meters) < 0.08 &&
                    box.depthCapturedMs == captured) return true;
        return false;
    }
    bool hasPreview(int generation, quint64 id) {
        QMutexLocker lock(&mutex);
        for (const auto& o : stereoOutputs)
            if (o.generation == generation && o.id == id && o.preview) return true;
        return false;
    }
};
}

bool VisionPipeline::selfTest() {
    QTextStream out(stdout), err(stderr);
    auto check = [&](bool condition, const char* name) {
        if (!condition) { err << "VISION_SELFTEST_FAIL: " << name << '\n'; err.flush(); }
        return condition;
    };
    bool ok = true;
    {
        VisionOptions options;
        ok &= check(!options.stereoEnabled() && options.stereoCameraMask() == 0 &&
                    options.primaryStereoLeft() == -1, "stereo requires explicit configuration");
        options.stereoLeft = 0; options.stereoRight = 1;
        options.calibrationPath = QStringLiteral("legacy.yml");
        options.synchronizationConfirmed = options.hasTagOffset = true; options.tagOffset = -2;
        const auto legacy = options.stereoPairs();
        ok &= check(legacy.size() == 1 && legacy.front().calibrationPath == options.calibrationPath &&
                    legacy.front().tagOffset == -2 && legacy.front().synchronizationConfirmed &&
                    legacy.front().hasTagOffset && legacy.front().intervalMs == 0,
                    "legacy pair retains calibration and synchronization with inherited interval");
        options.stereoGroups = {{0, 1, {}, false, false, 0}, {4, 5, {}, true, true, 3}};
        ok &= check(options.stereoPairs().size() == 2 && options.stereoCameraMask() == 0x33 &&
                    options.primaryStereoLeft() == 0 && options.stereoSummary().contains(QStringLiteral("C5/C6")) &&
                     options.stereoPairs().front().calibrationPath.isEmpty(), "explicit groups override legacy without leaking calibration");
        ok &= check(options.stereoGroups[0].intervalMs == 0 && options.stereoGroups[1].intervalMs == 0,
                    "six-field aggregate initialization inherits global interval");
        for (int invalid : {-1, 1, 99, 5001}) {
            options.stereoGroups[1].intervalMs = invalid;
            ok &= check(options.stereoConfigurationError().contains(QStringLiteral("intervalMs")) &&
                        options.stereoPairs().empty() && options.stereoCameraMask() == 0,
                        "invalid group interval rejects entire configuration");
        }
        for (int valid : {0, 100, 5000}) {
            options.stereoGroups[1].intervalMs = valid;
            ok &= check(options.stereoConfigurationError().isEmpty() && options.stereoPairs().size() == 2 &&
                        options.stereoPairs()[1].intervalMs == valid, "group interval boundaries accepted and retained");
        }
        options.stereoGroups[1].intervalMs = 0;
        options.stereoGroups[1].left = 1;
        ok &= check(!options.stereoConfigurationError().isEmpty() && !options.stereoEnabled(),
                    "overlapping stereo cameras rejected");
        options.stereoGroups[1].left = 6;
        ok &= check(!options.stereoConfigurationError().isEmpty() && options.stereoCameraMask() == 0,
                    "out of range stereo camera rejected before mask shift");
        options.stereoGroups = {{0, 1, {}, false, false, 0}, {2, 3, {}, false, false, 0}, {4, 5, {}, false, false, 0}};
        ok &= check(!options.stereoConfigurationError().isEmpty() && !options.stereoEnabled(),
                    "more than two stereo groups rejected");
    }
    {
        // A real worker, direct observation of Qt signals: no event loop, NPU,
        // display server, PCIe or model files are needed.
        VisionOptions options;
        options.detectionIntervalMs = 220; options.minimumDetectionIntervalMs = 80;
        Log log;
        VisionPipeline pipeline(options);
        log.connect(pipeline); pipeline.configure(1, 0, false, {QStringLiteral("a"), QStringLiteral("b")});
        pipeline.start();
        pipeline.submitFrame(frame(1));
        ok &= check(until([&] { return log.count() == 1; }), "initial request");
        if (log.count() != 1) { pipeline.stop(); pipeline.wait(); return false; }
        // Hold detection while later frames arrive. Only the source snapshot
        // can be corrected; replay must move the original x=200 target.
        for (int i = 2; i <= 4; ++i) {
            QThread::msleep(22); pipeline.submitFrame(frame(i, 1, 0, (i - 1) * 4));
        }
        ok &= check(log.count() == 1, "one outstanding request");
        pipeline.submitDetections(QStringLiteral("a"), 1, 1, {target()}, 12);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("a"), 1, 4, true); }), "frameId history replay");
        uint64_t id = 0;
        {
            QMutexLocker lock(&log.mutex);
            bool moved = false;
            for (const auto& o : log.outputs) if (o.model == QStringLiteral("a") && o.id == 4 && !o.boxes.isEmpty()) {
                const auto& d = o.boxes.front(); id = d.trackId;
                moved = d.x1 > 207 && d.x1 < 219 && d.y1 > 225 && d.y1 < 235 && d.matchScore >= 0.65f;
            }
            ok &= check(moved && id != 0, "replay moves box and restores model padding");
        }
        pipeline.submitFrame(frame(5, 1, 0, 16));
        QThread::msleep(30);
        ok &= check(log.count() == 1, "strong tracking low frequency");
        // Weak/lost tracking may request earlier, but never before minimum.
        pipeline.submitFrame(frame(6, 1, 0, 0, true));
        ok &= check(until([&] { return log.count() >= 2; }, 190), "weak early request");
        if (log.count() >= 2) {
            QMutexLocker lock(&log.mutex);
            ok &= check(log.requestedAt[1] - log.requestedAt[0] >= 80 &&
                        log.requestedAt[1] - log.requestedAt[0] < 220, "early minimum interval");
        }
        // A full empty detection result clears a model without stopping
        // periodic discovery of new objects.
        if (log.count() >= 2) {
            const auto req = log.request(1);
            pipeline.submitDetections(QStringLiteral("a"), 1, req.frameId, {}, 10);
            ok &= check(until([&] { return log.hasOutput(QStringLiteral("a"), 1, req.frameId); }), "empty correction");
        }
        QThread::msleep(90); pipeline.submitFrame(frame(7, 1, 0, 0, true));
        QThread::msleep(25);
        ok &= check(log.count() == 2, "empty scene uses periodic interval");
        QThread::msleep(130); pipeline.submitFrame(frame(8, 1, 0, 0, true));
        ok &= check(until([&] { return log.count() >= 3; }), "empty scene periodic discovery");
        pipeline.stop(); pipeline.wait();
    }
    {
        VisionOptions options; options.tracking = false;
        Log log; VisionPipeline pipeline(options);
        log.connect(pipeline); pipeline.configure(1, 0, false, {QStringLiteral("a")});
        pipeline.start(); pipeline.submitFrame(frame(1));
        ok &= check(until([&] { return log.count() == 1; }), "unthrottled first request");
        // Burst frames are overwritten in two slots. Once the ack arrives the
        // worker requests the newest frame, never drains a FIFO of 100 images.
        const QImage shared = fixture();
        for (quint64 i = 2; i <= 101; ++i) {
            auto f = frame(i); f.image = shared; pipeline.submitFrame(f);
        }
        ok &= check(log.count() == 1, "bounded mailbox while outstanding");
        pipeline.inferenceFailed(1, 1);
        ok &= check(until([&] { return log.count() == 2; }), "failed inference releases request");
        if (log.count() >= 2) ok &= check(log.request(1).frameId == 101, "latest frame replaces burst");
        // Source/model reconfiguration must reject the old callback even when
        // it arrives while another request is outstanding.
        pipeline.configure(2, 1, false, {QStringLiteral("b")});
        pipeline.submitFrame(frame(1, 2, 1));
        ok &= check(until([&] { return log.count() == 3; }), "source reset requests new camera");
        const int before = log.outputCount();
        pipeline.submitDetections(QStringLiteral("a"), 1, 101, {target()}, 10);
        pipeline.inferenceFailed(1, 101);
        QThread::msleep(30);
        ok &= check(log.outputCount() == before && log.count() == 3, "old source cannot release new request");
        pipeline.submitDetections(QStringLiteral("b"), 2, 1, {}, 10);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("b"), 2, 1); }), "new source result accepted");
        pipeline.submitFrame(frame(2, 2, 1));
        ok &= check(until([&] { return log.count() == 4; }), "no tracking bypasses interval");
        pipeline.configure(2, 1, false, {QStringLiteral("c")});
        pipeline.submitFrame(frame(3, 2, 1));
        ok &= check(until([&] { return log.count() == 5; }), "model reset within source");
        pipeline.submitDetections(QStringLiteral("b"), 2, 2, {target()}, 10);
        pipeline.inferenceFailed(2, 2);
        QThread::msleep(25);
        ok &= check(log.count() == 5, "old model frame does not unlock new frame");
        // Wait for the 2s watchdog, then prove an old frame cannot acknowledge
        // the newer request from this same epoch.
        pipeline.submitFrame(frame(4, 2, 1));
        QThread::msleep(2050);
        // Refresh host age; the old retained image is deliberately not reused.
        pipeline.submitFrame(frame(5, 2, 1));
        ok &= check(until([&] { return log.count() == 6; }), "timeout releases outstanding");
        pipeline.submitDetections(QStringLiteral("c"), 2, 3, {target()}, 10);
        pipeline.inferenceFailed(2, 3); pipeline.submitFrame(frame(6, 2, 1));
        QThread::msleep(30);
        ok &= check(log.count() == 6, "late timed out frame cannot unlock newer request");
        if (log.count() >= 6) {
            const auto req = log.request(5);
            pipeline.inferenceFailed(2, req.frameId);
            ok &= check(until([&] { return log.count() == 7; }), "current ack releases newer request");
        }
        pipeline.stop(); pipeline.wait();
    }
    {
        VisionOptions options;
        options.stereoLeft = 2; options.stereoRight = 4;
        options.stereoIntervalMs = 40;
        Log log; VisionPipeline pipeline(options);
        log.connect(pipeline); pipeline.configure(3, 2, true, {QStringLiteral("lane")});
        pipeline.start(); pipeline.submitFrame(frame(1, 3, 2)); pipeline.submitFrame(frame(1, 3, 4));
        ok &= check(until([&] {
            QMutexLocker lock(&log.mutex);
            return log.stereoPreviews > 0 && std::any_of(log.stereo.begin(), log.stereo.end(), [](const QString& s) {
                return s.contains(QStringLiteral("not calibrated")) && s.contains(QStringLiteral("sync unconfirmed"));
            });
        }), "uncalibrated and unconfirmed stereo forbids meters");
        {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.stereo) ok &= check(!s.contains(QStringLiteral(" m;")), "no metric status without calibration");
        }
        ok &= check(until([&] { return log.count() == 1; }), "lane request");
        pipeline.inferenceFailed(3, 1); pipeline.submitFrame(frame(2, 3, 2));
        ok &= check(until([&] { return log.count() == 2; }), "lane ack and unthrottled request");
        // Leaving lane mode must reset its history (which has no tracking gray/snapshots).
        pipeline.configure(30, 2, false, {QStringLiteral("tracked")});
        pipeline.submitFrame(frame(3, 30, 2));
        ok &= check(until([&] { return log.count() == 3; }), "lane to tracking request after reset");
        pipeline.submitDetections(QStringLiteral("tracked"), 30, 3, {target()}, 1);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("tracked"), 30, 3, true); }),
                    "tracking correction after lane history reset");
        pipeline.configure(31, 2, true, {QStringLiteral("lane")});
        pipeline.submitFrame(frame(4, 31, 2));
        ok &= check(until([&] { return log.count() == 4; }), "tracking to lane request after reset");
        pipeline.submitDetections(QStringLiteral("tracked"), 30, 3, {target()}, 1);
        pipeline.inferenceFailed(31, 4);
        pipeline.stop(); pipeline.wait();
    }
    {
        // Simulation only: fx=400px, baseline=0.1m, disparity=20px => Z=2m.
        // Two independent calibrations: identical pixels, baselines 0.1/0.2m
        // must produce 2/4m respectively. All calibration is synthetic.
        QTemporaryFile calibrationFile, secondCalibration;
        if (!check(calibrationFile.open() && secondCalibration.open(), "temporary simulated calibrations")) return false;
        calibrationFile.close(); secondCalibration.close();
        writeCalibration(calibrationFile.fileName(), 0.1);
        writeCalibration(secondCalibration.fileName(), 0.2);
        cv::Mat leftPixels(480, 640, CV_8UC1), rightPixels(480, 640, CV_8UC1);
        cv::RNG random(99271);
        random.fill(leftPixels, cv::RNG::UNIFORM, 0, 256);
        cv::GaussianBlur(leftPixels, leftPixels, {3, 3}, 0.7);
        rightPixels.setTo(0);
        leftPixels(cv::Rect(20, 0, 620, 480)).copyTo(rightPixels(cv::Rect(0, 0, 620, 480)));
        auto pixels = [](const cv::Mat& image) {
            cv::Mat rgb; cv::cvtColor(image, rgb, cv::COLOR_GRAY2RGB);
            return QImage(rgb.data, rgb.cols, rgb.rows, int(rgb.step), QImage::Format_RGB888).copy();
        };
        VisionOptions options;
        options.stereoGroups = {
            {0, 1, calibrationFile.fileName(), true, true, 0},
            {4, 5, secondCalibration.fileName(), true, true, 3}};
        options.stereoIntervalMs = 40;
        options.detectionIntervalMs = 500;
        Log log; VisionPipeline pipeline(options);
        log.connect(pipeline); pipeline.configure(4, 0, false, {QStringLiteral("sim")});
        auto left = frame(10, 4, 0); left.image = pixels(leftPixels); left.tag = 77;
        pipeline.start(); pipeline.submitFrame(left);
        ok &= check(until([&] { return log.count() == 1; }), "simulated left detection request");
        Detection d = target(); d.x1 = 200; d.x2 = 360; d.y1 = 240; d.y2 = 400;
        pipeline.submitDetections(QStringLiteral("sim"), 4, 10, {d}, 10);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("sim"), 4, 10, true); }), "simulated target initialized");
        auto right = frame(11, 4, 1); right.image = pixels(rightPixels); right.tag = 78;
        pipeline.submitFrame(right);
        QThread::msleep(30);
        {
            QMutexLocker lock(&log.mutex);
            ok &= check(log.stereoPreviews == 0, "mismatched exposure IDs do not produce calibrated depth");
        }
        right.frameId = 12; right.tag = 77; right.capturedMs = testNow();
        pipeline.submitFrame(right);
        ok &= check(until([&] {
            QMutexLocker lock(&log.mutex);
            for (const auto& o : log.outputs)
                for (const auto& box : o.boxes)
                    if (o.model == QStringLiteral("sim") && o.id == 10 && std::isfinite(box.depthMeters) &&
                        std::abs(box.depthMeters - 2.0) < 0.05 && box.depthCapturedMs == left.capturedMs)
                        return true;
            return false;
        }), "simulated 2m target depth and original capture timestamp");
        // C5/C6 use lower frame IDs than C1/C2, and a nonzero tag offset.
        // A shared pair watermark or group-1 offset would suppress this pair.
        auto secondLeft = frame(2, 4, 4); secondLeft.image = left.image; secondLeft.tag = 7;
        auto secondRight = frame(3, 4, 5); secondRight.image = right.image; secondRight.tag = 4;
        pipeline.submitFrame(secondLeft); pipeline.submitFrame(secondRight);
        ok &= check(until([&] {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.diagnostics)
                if (s.contains(QStringLiteral("C1/C2:10/12")) && s.contains(QStringLiteral("C5/C6:2/3"))) return true;
            return false;
        }, 1600), "both groups independently pair while only selected group previews");
        {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.stereoOutputs)
                ok &= check(s.status.startsWith(QStringLiteral("C1/C2:")), "background group cannot overwrite selected preview");
            for (const auto& req : log.requests)
                ok &= check(req.camera == 0, "background stereo cameras never enter selected tracker or NPU");
        }
        // Switch to the second left with frame IDs below its previous watermark.
        // No tracks or depth may cross cameras; old generation replies are stale.
        const int beforeSwitch = log.count();
        pipeline.configure(5, 4, false, {QStringLiteral("sim")});
        secondLeft = frame(1, 5, 4); secondLeft.image = left.image; secondLeft.tag = 1;
        pipeline.submitFrame(secondLeft);
        ok &= check(until([&] { return log.count() == beforeSwitch + 1; }), "camera switch resets selected tracking and request watermarks");
        {
            QMutexLocker lock(&log.mutex);
            bool empty = false;
            for (const auto& o : log.outputs) if (o.generation == 5) {
                empty = true;
                ok &= check(o.boxes.isEmpty(), "camera switch does not inherit previous tracks or depth");
            }
            ok &= check(empty, "new selected camera publishes empty tracker before detection");
        }
        pipeline.submitDetections(QStringLiteral("sim"), 4, 10, {d}, 10);
        pipeline.submitDetections(QStringLiteral("sim"), 5, 1, {d}, 10);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("sim"), 5, 1, true); }), "second camera target initialized independently");
        secondRight = frame(2, 5, 5); secondRight.image = right.image;
        secondRight.tag = 1; // group 1's offset would incorrectly accept this
        pipeline.submitFrame(secondRight);
        QThread::msleep(60);
        ok &= check(!log.hasPreview(5, 1), "second group refuses group-1 tag offset");
        secondRight.frameId = 3; secondRight.tag = 0xfffffffeU; // +3 wraps to 1
        secondRight.capturedMs = testNow(); pipeline.submitFrame(secondRight);
        ok &= check(until([&] { return log.hasDepth(5, 1, 4.0, secondLeft.capturedMs); }),
                    "second calibration produces 4m with its own wrapping tag offset");
        // A fresh first-group pair computes in the background without changing
        // the selected second-group preview or second-group target cache.
        auto backgroundLeft = frame(100, 5, 0); backgroundLeft.image = left.image; backgroundLeft.tag = 50;
        auto backgroundRight = frame(101, 5, 1); backgroundRight.image = right.image; backgroundRight.tag = 50;
        pipeline.submitFrame(backgroundLeft); pipeline.submitFrame(backgroundRight);
        ok &= check(until([&] {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.diagnostics)
                if (s.contains(QStringLiteral("C1/C2:100/101")) && s.contains(QStringLiteral("C5/C6:1/3"))) return true;
            return false;
        }, 1600), "switch resets all groups and background group continues fairly");
        {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.stereoOutputs) if (s.generation == 5)
                ok &= check(s.status.startsWith(QStringLiteral("C5/C6:")), "selected second group preview remains isolated");
            for (const auto& o : log.outputs) if (o.generation == 5)
                for (const auto& box : o.boxes) if (std::isfinite(box.depthMeters))
                    ok &= check(std::abs(box.depthMeters - 4.0) < 0.08, "group-1 calibration never seeds group-2 cache");
        }
        ok &= check(until([&] {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.stereoOutputs) if (s.generation == 5 && !s.preview &&
                    s.status.contains(QStringLiteral("no fresh corresponding pair")) &&
                    s.status.startsWith(QStringLiteral("C5/C6:")) && s.id == 1) return true;
            return false;
        }, 1400), "selected group independently expires preview when its pair freezes");
        // Selecting a right camera keeps its own boxes and can show that pair's
        // preview, but left-image ROI depths must never label its targets.
        const int beforeRight = log.count();
        pipeline.configure(6, 5, false, {QStringLiteral("sim")});
        auto selectedRight = frame(1, 6, 5); selectedRight.image = right.image; selectedRight.tag = 10;
        pipeline.submitFrame(selectedRight);
        ok &= check(until([&] { return log.count() == beforeRight + 1; }), "right camera inference stays on selected route");
        pipeline.submitDetections(QStringLiteral("sim"), 6, 1, {d}, 10);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("sim"), 6, 1, true); }), "right camera tracks its own targets");
        auto unselectedLeft = frame(2, 6, 4); unselectedLeft.image = left.image; unselectedLeft.tag = 13;
        pipeline.submitFrame(unselectedLeft);
        ok &= check(until([&] { return log.hasPreview(6, 2); }), "right selected camera displays its stereo group");
        {
            QMutexLocker lock(&log.mutex);
            for (const auto& o : log.outputs) if (o.generation == 6)
                for (const auto& box : o.boxes)
                    ok &= check(!std::isfinite(box.depthMeters), "right camera cannot inherit left ROI depth");
        }
        // Return to primary left with no paired image. Reset must clear both the
        // old targets and all disparity/depth state, even if track IDs restart.
        const int beforeReturn = log.count();
        pipeline.configure(7, 0, false, {QStringLiteral("sim")});
        left = frame(1, 7, 0); left.image = pixels(leftPixels); left.tag = 77;
        pipeline.submitFrame(left);
        ok &= check(until([&] { return log.count() == beforeReturn + 1; }), "return to primary left accepts lower frame IDs in new source");
        pipeline.submitDetections(QStringLiteral("sim"), 7, 1, {d}, 10);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("sim"), 7, 1, true); }), "returned camera target freshly initialized");
        {
            QMutexLocker lock(&log.mutex);
            for (const auto& o : log.outputs) if (o.generation == 7)
                for (const auto& box : o.boxes)
                    ok &= check(!std::isfinite(box.depthMeters), "switch clears cached depths before any new corresponding pair");
        }
        right = frame(2, 7, 1); right.image = pixels(rightPixels); right.tag = 77;
        pipeline.submitFrame(right);
        ok &= check(until([&] { return log.hasDepth(7, 1, 2.0, left.capturedMs); }), "primary calibration remains independent after round-trip camera switch");
        // Retain two left frames, track the newer one, then deliver a right
        // exposure matching only the older left. Center preview is allowed;
        // using that disparity for the newer target is forbidden.
        const int beforeOlder = log.count();
        pipeline.configure(8, 0, false, {QStringLiteral("sim")});
        auto olderLeft = frame(1, 8, 0); olderLeft.image = pixels(leftPixels); olderLeft.tag = 20;
        pipeline.submitFrame(olderLeft);
        ok &= check(until([&] { return log.count() == beforeOlder + 1; }), "older exposure request reserved");
        auto newerLeft = frame(2, 8, 0); newerLeft.image = olderLeft.image; newerLeft.tag = 21;
        pipeline.submitFrame(newerLeft);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("sim"), 8, 2); }), "newer left enters selected history");
        pipeline.submitDetections(QStringLiteral("sim"), 8, 1, {d}, 10);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("sim"), 8, 2, true); }), "target correction replays to newer exposure");
        auto olderRight = frame(3, 8, 1); olderRight.image = pixels(rightPixels); olderRight.tag = 20;
        pipeline.submitFrame(olderRight);
        ok &= check(until([&] { return log.hasPreview(8, 1); }), "older matching pair still has a stereo preview");
        {
            QMutexLocker lock(&log.mutex);
            for (const auto& o : log.outputs) if (o.generation == 8)
                for (const auto& box : o.boxes)
                    ok &= check(!std::isfinite(box.depthMeters), "older stereo frame never seeds newer target depth");
        }
        olderRight.frameId = 4; olderRight.tag = 21; olderRight.capturedMs = testNow();
        pipeline.submitFrame(olderRight);
        ok &= check(until([&] { return log.hasDepth(8, 2, 2.0, newerLeft.capturedMs); }), "only same-frame target and disparity seed cache");
        pipeline.stop(); pipeline.wait();
    }
    {
        // A slow selected group must not impose its attempt interval, frame IDs
        // or tag offset on a fast background group. Deliberately retain a slow
        // pair until its 500ms freshness expires before the next 2000ms attempt.
        VisionOptions options;
        options.stereoGroups = {{0, 1, {}, true, true, -2, 100}, {4, 5, {}, true, true, 3, 2000}};
        options.stereoIntervalMs = 40;
        Log log; VisionPipeline pipeline(options);
        log.connect(pipeline); pipeline.configure(12, 4, false, {}); pipeline.start();
        auto slowLeft = frame(100, 12, 4); slowLeft.tag = 13;
        auto slowRight = frame(101, 12, 5); slowRight.tag = 10;
        const qint64 firstSubmittedMs = testNow();
        pipeline.submitFrame(slowLeft); pipeline.submitFrame(slowRight);
        const bool firstPreview = until([&] { return log.hasPreview(12, 100); });
        ok &= check(firstPreview, "slow group initially computes its own matching pair");
        const qint64 firstObservedMs = testNow();
        slowLeft = frame(102, 12, 4); slowLeft.tag = 23;
        slowRight = frame(103, 12, 5); slowRight.tag = 20;
        pipeline.submitFrame(slowLeft); pipeline.submitFrame(slowRight);
        auto fastLeft = frame(1, 12, 0); fastLeft.tag = 7;
        auto fastRight = frame(2, 12, 1); fastRight.tag = 9;
        pipeline.submitFrame(fastLeft); pipeline.submitFrame(fastRight);
        ok &= check(until([&] {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.diagnostics)
                if (s.contains(QStringLiteral("C1/C2:1/2")) && s.contains(QStringLiteral("C5/C6:100/101")))
                    return true;
            return false;
        }, 1500), "fast group progresses while slow group interval holds its independent watermark");
        ok &= check(!log.hasPreview(12, 102), "slow group does not compute queued pair before its interval");
        fastLeft = frame(3, 12, 0); fastLeft.tag = 17;
        fastRight = frame(4, 12, 1); fastRight.tag = 19;
        pipeline.submitFrame(fastLeft); pipeline.submitFrame(fastRight);
        ok &= check(until([&] {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.diagnostics)
                if (s.contains(QStringLiteral("C1/C2:3/4")) && s.contains(QStringLiteral("C5/C6:100/101")))
                    return true;
            return false;
        }, 1600), "fast group repeats within slow interval without borrowing its offset or watermarks");
        if (firstPreview) {
            // Observing completion provides a conservative wait beyond the
            // attempt deadline. Submit newly captured frames only after that.
            ok &= check(until([&] { return testNow() - firstObservedMs >= 2000; }, 2200),
                        "slow group attempt interval elapses");
            slowLeft = frame(104, 12, 4); slowLeft.tag = 33;
            slowRight = frame(105, 12, 5); slowRight.tag = 30;
            pipeline.submitFrame(slowLeft); pipeline.submitFrame(slowRight);
            ok &= check(until([&] { return log.hasPreview(12, 104); }), "slow group resumes with a fresh own-offset pair");
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.stereoOutputs) if (s.preview) {
                ok &= check(s.status.startsWith(QStringLiteral("C5/C6:")), "different intervals retain selected preview isolation");
                ok &= check(s.id != 102, "interval never reuses an expired host pair");
                if (s.id == 104)
                    ok &= check(s.at - firstSubmittedMs >= 2000, "slow group honors configured attempt interval");
            }
        }
        pipeline.stop(); pipeline.wait();
    }
    {
        // Both groups have confirmed tags, but neither has a usable calibration.
        // A malformed file in group 2 must not turn group 1's preview into metric
        // depth, nor kill the worker or its independent matcher.
        QTemporaryFile malformed;
        if (!check(malformed.open(), "temporary malformed calibration")) return false;
        malformed.write("invalid calibration fixture\n"); malformed.close();
        VisionOptions options;
        options.stereoGroups = {{0, 1, {}, true, true, 0}, {4, 5, malformed.fileName(), true, true, -2}};
        options.stereoIntervalMs = 80;
        Log log; VisionPipeline pipeline(options);
        log.connect(pipeline); pipeline.configure(9, 0, false, {QStringLiteral("uncal")}); pipeline.start();
        pipeline.submitFrame(frame(10, 9, 0));
        ok &= check(until([&] { return log.count() == 1; }), "uncalibrated first group detection request");
        pipeline.submitDetections(QStringLiteral("uncal"), 9, 10, {target()}, 10);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("uncal"), 9, 10, true); }), "uncalibrated target initialized");
        pipeline.submitFrame(frame(10, 9, 1));
        ok &= check(until([&] { return log.hasPreview(9, 10); }), "uncalibrated synchronized pair has disparity preview");
        auto bgLeft = frame(1, 9, 4); bgLeft.tag = 20;
        auto bgRight = frame(2, 9, 5); bgRight.tag = 22;
        pipeline.submitFrame(bgLeft); pipeline.submitFrame(bgRight);
        pipeline.submitFrame(frame(11, 9, 0)); pipeline.submitFrame(frame(11, 9, 1));
        ok &= check(until([&] { return log.hasPreview(9, 11); }), "two groups respect aggregate throttle while progressing");
        {
            QMutexLocker lock(&log.mutex);
            qint64 firstAt = -1, secondAt = -1;
            for (const auto& s : log.stereoOutputs) if (s.generation == 9 && s.preview) {
                if (s.id == 10) firstAt = s.at;
                if (s.id == 11) secondAt = s.at;
                ok &= check(s.status.contains(QStringLiteral("not calibrated")) && !s.status.contains(QStringLiteral(" m;")),
                            "confirmed tags without calibration never advertise meters");
            }
            ok &= check(firstAt >= 0 && secondAt - firstAt >= options.stereoIntervalMs,
                        "stereo computation enforces cooldown after prior completion");
            for (const auto& o : log.outputs) if (o.generation == 9)
                for (const auto& box : o.boxes)
                    ok &= check(!std::isfinite(box.depthMeters), "uncalibrated target cache never contains trusted meters");
        }
        const int beforeMalformed = log.count();
        pipeline.configure(10, 4, false, {QStringLiteral("uncal")});
        bgLeft = frame(1, 10, 4); bgLeft.tag = 20; pipeline.submitFrame(bgLeft);
        ok &= check(until([&] { return log.count() == beforeMalformed + 1; }), "malformed group still tracks selected camera");
        pipeline.submitDetections(QStringLiteral("uncal"), 10, 1, {target()}, 10);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("uncal"), 10, 1, true); }), "malformed group target initialized");
        bgRight = frame(2, 10, 5); bgRight.tag = 22; pipeline.submitFrame(bgRight);
        ok &= check(until([&] { return log.hasPreview(10, 1); }), "malformed second calibration falls back to disparity only");
        {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.stereoOutputs) if (s.generation == 10)
                ok &= check(s.status.startsWith(QStringLiteral("C5/C6:")) &&
                            s.status.contains(QStringLiteral("not calibrated")) && !s.status.contains(QStringLiteral(" m;")),
                            "malformed calibration stays isolated and cannot report meters");
            for (const auto& o : log.outputs) if (o.generation == 10)
                for (const auto& box : o.boxes)
                    ok &= check(!std::isfinite(box.depthMeters), "malformed calibration cannot seed target depth");
        }
        // C3 belongs to neither pair: it tracks independently while the four
        // stereo camera slots stay active, with no unrelated preview exposed.
        const int beforeUnpaired = log.count();
        pipeline.configure(11, 2, false, {QStringLiteral("uncal")});
        pipeline.submitFrame(frame(1, 11, 2));
        ok &= check(until([&] { return log.count() == beforeUnpaired + 1; }), "camera outside stereo groups requests its own inference");
        pipeline.submitDetections(QStringLiteral("uncal"), 11, 1, {target()}, 10);
        ok &= check(until([&] { return log.hasOutput(QStringLiteral("uncal"), 11, 1, true); }), "camera outside stereo groups tracks independently");
        pipeline.submitFrame(frame(8, 11, 0)); pipeline.submitFrame(frame(8, 11, 1));
        bgLeft = frame(2, 11, 4); bgLeft.tag = 20;
        bgRight = frame(3, 11, 5); bgRight.tag = 22;
        pipeline.submitFrame(bgLeft); pipeline.submitFrame(bgRight);
        ok &= check(until([&] {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.diagnostics)
                if (s.contains(QStringLiteral("C1/C2:8/8")) && s.contains(QStringLiteral("C5/C6:2/3"))) return true;
            return false;
        }, 1600), "four stereo cameras continue bounded pairing with unrelated camera selected");
        {
            QMutexLocker lock(&log.mutex);
            for (const auto& s : log.stereoOutputs)
                ok &= check(s.generation != 11, "unrelated selected camera receives no other-group preview");
            for (const auto& o : log.outputs) if (o.generation == 11)
                for (const auto& box : o.boxes)
                    ok &= check(!std::isfinite(box.depthMeters), "unrelated selected camera has no stereo target cache");
            for (const auto& req : log.requests) if (req.sourceGeneration == 11)
                ok &= check(req.camera == 2, "unrelated selection never tracks a stereo input camera");
        }
        pipeline.stop(); pipeline.wait();
    }
    if (ok) { out << "VISION_SELFTEST_PASS\n"; out.flush(); }
    return ok;
}

#ifdef TDM_VISION_SELFTEST_MAIN
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    return VisionPipeline::selfTest() ? 0 : 1;
}
#endif
