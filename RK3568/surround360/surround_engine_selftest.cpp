#include "surround_engine.h"
#include "stereo_selection.h"

#include <QCoreApplication>
#include <QFile>
#include <QTemporaryDir>
#include <QTextStream>
#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <stdexcept>

namespace surround {
namespace {
void require(bool condition, const char *message) {
    if (!condition) throw std::runtime_error(message);
}
QImage solid(int r, int g, int b) {
    QImage image(SourceWidth, SourceHeight, QImage::Format_RGB888);
    for (int y = 0; y < SourceHeight; ++y) {
        uchar *row = image.scanLine(y);
        for (int x = 0; x < SourceWidth; ++x) {
            row[3 * x] = uchar(r); row[3 * x + 1] = uchar(g); row[3 * x + 2] = uchar(b);
        }
    }
    return image;
}
QImage grid() {
    QImage image(SourceWidth, SourceHeight, QImage::Format_RGB888);
    for (int y = 0; y < SourceHeight; ++y) {
        uchar *row = image.scanLine(y);
        for (int x = 0; x < SourceWidth; ++x) {
            row[3 * x] = uchar(x * 255 / (SourceWidth - 1));
            row[3 * x + 1] = uchar(y * 255 / (SourceHeight - 1));
            row[3 * x + 2] = uchar(x % 80 < 3 || y % 60 < 3 ? 220 : 40);
        }
    }
    return image;
}
FrameInput colors(qint64 captured = 1000) {
    FrameInput frames;
    const int rgb[CameraCount][3] = {{230, 20, 20}, {20, 230, 20}, {20, 20, 230},
                                   {230, 230, 20}, {230, 20, 230}, {20, 230, 230}};
    for (int i = 0; i < CameraCount; ++i) {
        frames.images[i] = solid(rgb[i][0], rgb[i][1], rgb[i][2]);
        frames.capturedMs[i] = captured;
        frames.sequence[i] = 1;
    }
    return frames;
}
cv::Vec3i pixel(const QImage &image, int x, int y) {
    const uchar *p = image.constScanLine(y) + 3 * x;
    return {p[0], p[1], p[2]};
}
int yawPixel(const Configuration &cfg, double yaw) {
    return std::min(cfg.panoramaWidth - 1, int((yaw / 360.0 + .5) * cfg.panoramaWidth));
}
bool near(const cv::Vec3i &a, const cv::Vec3i &b, int tolerance) {
    for (int c = 0; c < 3; ++c) if (std::abs(a[c] - b[c]) > tolerance) return false;
    return true;
}
QString rgbText(const cv::Vec3i &rgb) {
    return QString("(%1,%2,%3)").arg(rgb[0]).arg(rgb[1]).arg(rgb[2]);
}
void requireColor(const cv::Vec3i &actual, const cv::Vec3i &expected,
                  int tolerance, int camera, const char *context) {
    if (near(actual, expected, tolerance)) return;
    throw std::runtime_error(QString("%1 C%2: actual RGB %3, expected %4, tolerance %5")
        .arg(QString::fromLatin1(context)).arg(camera + 1).arg(rgbText(actual))
        .arg(rgbText(expected)).arg(tolerance).toStdString());
}
void writeJson(const QString &path, const QByteArray &bytes) {
    QFile file(path);
    require(file.open(QIODevice::WriteOnly), "Unable to create temporary JSON");
    require(file.write(bytes) == bytes.size(), "Unable to write temporary JSON");
}
} // namespace

int runEngineSelfTest() {
    QTextStream report(stdout);
    int failures = 0;
    const auto test = [&](const char *name, const std::function<void()> &body) {
        try {
            body();
            report << "PASS " << name << '\n';
        } catch (const std::exception &exception) {
            ++failures;
            report << "FAIL " << name << ": " << exception.what() << '\n';
        }
        report.flush();
    };

    Configuration cfg;
    cfg.exposureBalance = false;
    Engine engine(cfg);
    const FrameInput frames = colors();

    test("honest defaults and configuration validation", [&] {
        QString error;
        require(cfg.validate(&error), "Default configuration is invalid");
        const double expected[] = {0, 0, -90, 90, 180, 180};
        for (int i = 0; i < CameraCount; ++i) {
            require(cfg.cameras[i].id == i + 1 && cfg.cameras[i].yawDeg == expected[i],
                    "Camera topology/order changed");
            require(!cfg.cameras[i].intrinsicCalibrated && !cfg.cameras[i].yawCalibrated &&
                    !cfg.cameras[i].groundCalibrated, "Defaults imply nonexistent calibration");
        }
        Configuration bad = cfg;
        bad.cameras[0].yawDeg = std::numeric_limits<double>::quiet_NaN();
        require(!bad.validate(&error) && !error.isEmpty(), "Non-finite angle accepted");
        bad = cfg; bad.cameras[1].id = 1;
        require(!bad.validate(), "Camera reorder accepted");
        bad = cfg; bad.staleMs = bad.freshMs;
        require(!bad.validate(), "Zero stale interval accepted");
        bad = cfg; bad.panoramaWidth = 32768;
        require(!bad.validate(), "Unbounded allocation accepted");
        bad = cfg; bad.cameras[0].intrinsicCalibrated = true;
        require(!bad.validate(), "Zero focal length accepted as calibrated");
        bad = cfg; bad.cameras[0].groundCalibrated = true;
        bad.cameras[0].groundSrc[2] = bad.cameras[0].groundSrc[1];
        require(!bad.validate(), "Degenerate source quad accepted");
        bad = cfg; bad.cameras[0].groundCalibrated = true;
        bad.cameras[0].groundDst[2] = bad.cameras[0].groundDst[1];
        require(!bad.validate(), "Degenerate destination quad accepted");
        require(!engine.setConfig(bad, &error) && engine.config().panoramaWidth == cfg.panoramaWidth,
                "Invalid configuration replaced working maps");
    });

    test("four physical directions, stereo primaries and rear seam", [&] {
        // Stereo partners share an optical direction, never two separate sectors.
        Configuration isolated = cfg;
        for (auto &camera : isolated.cameras) camera.hfovDeg = 80;
        Engine isolatedEngine(isolated);
        const ProcessResult isolatedResult = isolatedEngine.composePanorama(frames, 1000);
        for (int i : {0, 2, 3, 4})
            requireColor(pixel(isolatedResult.output, yawPixel(isolated, isolated.cameras[i].yawDeg), 240),
                         pixel(frames.images[i], 320, 240), 2, i, "Isolated optical-axis direction");

        const ProcessResult result = engine.composePanorama(frames, 1000);
        require(!result.output.isNull() && result.output.format() == QImage::Format_RGB888,
                "Panorama is not owned RGB888 output");
        require(result.output.size() == QSize(1536, 480), "Unexpected panorama dimensions");
        require(result.approximateGeometry && result.status.contains("uncalibrated"),
                "Missing calibration warning");
        for (int i = 0; i < CameraCount; ++i) require(result.active[i], "Raw fresh camera omitted");
        require(result.projectionSelected == std::array<bool, 6>{{true, false, true, true, true, false}},
                "Fresh stereo pairs must project only C1/C5 primaries");
        for (int i : {0, 2, 3, 4})
            requireColor(pixel(result.output, yawPixel(cfg, cfg.cameras[i].yawDeg), 240),
                         pixel(frames.images[i], 320, 240), 2, i, "Four-direction optical axis");
        require(near(pixel(result.output, 0, 240), pixel(result.output, 1535, 240), 5),
                "Rear panorama seam discontinuity");
        require(near(pixel(result.output, yawPixel(cfg, 45), 240), cv::Vec3i(230, 125, 20), 4),
                "Front/right physical-direction overlap does not feather");
        const QImage owned = result.output;
        engine.composePanorama(FrameInput{}, 1000);
        require(pixel(owned, yawPixel(cfg, -90), 240)[2] > 200,
                "Later render overwrote previously returned image");
    });

    test("stereo eye freshness, fallback, field of view and bird selection", [&] {
        const auto none = selectStereoEyes(std::array<double, 6>{});
        require(none == std::array<bool, 6>{{true, false, true, true, true, false}},
                "Dead modules must retain primary geometric support");
        const auto ties = selectStereoEyes({{.6, .6, 1, 1, .4, .7}});
        require(ties[0] && !ties[1] && !ties[4] && ties[5] &&
                std::count(ties.begin(), ties.end(), true) == 4, "Freshness tie/greater backup policy failed");
        FrameInput input = frames;
        input.images[0] = QImage(); input.images[4] = QImage();
        const auto fallback = engine.composePanorama(input, 1000);
        require(!fallback.projectionSelected[0] && fallback.projectionSelected[1] &&
                !fallback.projectionSelected[4] && fallback.projectionSelected[5],
                "Missing primary did not select its stereo backup");
        requireColor(pixel(fallback.output, yawPixel(cfg, 0), 240), cv::Vec3i(20, 230, 20), 2, 1, "Front backup");
        requireColor(pixel(fallback.output, 0, 240), cv::Vec3i(20, 230, 230), 2, 5, "Rear backup");
        FrameInput replacement = frames;
        replacement.images[0] = frames.images[1]; replacement.images[4] = frames.images[5];
        require(engine.composeBird(input, 1000).output == engine.composeBird(replacement, 1000).output,
                "Bird maps did not use exactly the chosen stereo eye");
        input = frames; input.capturedMs[0] = 750;
        require(engine.composePanorama(input, 1000).projectionSelected[0],
                "Primary at the fresh boundary must remain preferred");
        input.capturedMs[0] = 749; input.capturedMs[4] = 0;
        const auto recovered = engine.composePanorama(input, 1000);
        require(recovered.active[0] && recovered.projectionSelected[1] && recovered.projectionSelected[5],
                "Fading/stale primaries did not yield to fresh backups without hiding raw activity");
        requireColor(pixel(recovered.output, yawPixel(cfg, 0), 240), cv::Vec3i(20, 230, 20), 2, 1, "Fresh backup beats fading primary");
        input = frames; input.capturedMs[0] = 500; input.capturedMs[1] = 600;
        const auto fading = engine.composePanorama(input, 1000);
        require(fading.projectionSelected[1], "Higher freshness must win when both stereo eyes fade");
        requireColor(pixel(fading.output, yawPixel(cfg, 0), 240), cv::Vec3i(16, 184, 16), 2, 1, "Fading backup preserves attenuation");
        input = frames; input.capturedMs[0] = input.capturedMs[1] = 0;
        const auto dead = engine.composePanorama(input, 1000);
        require(dead.projectionSelected[0] && !dead.projectionSelected[1] &&
                pixel(dead.output, yawPixel(cfg, 0), 240) == cv::Vec3i(0, 0, 0),
                "Dead stereo module must contribute primary geometry and black pixels");
        FrameInput onlyFront;
        onlyFront.images[0] = frames.images[0]; onlyFront.images[1] = frames.images[1];
        onlyFront.capturedMs.fill(1000);
        require(pixel(engine.composePanorama(onlyFront, 1000).output, yawPixel(cfg, 60), 240) == cv::Vec3i(0, 0, 0),
                "Uncalibrated stereo eyes widened the module's 110-degree field of view");
    });

    test("age fade, stale exclusion, clock errors and missing images", [&] {
        FrameInput input = frames;
        input.capturedMs[2] = 375; // 625 ms old: exactly halfway through the fade.
        const ProcessResult half = engine.composePanorama(input, 1000);
        require(half.active[2] && half.ageMs[2] == 625 && half.status.contains("Fading C3"),
                "Age diagnostics are incorrect");
        require(near(pixel(half.output, yawPixel(cfg, -90), 240), cv::Vec3i(10, 10, 115), 2),
                "Normalization cancelled stale-camera fade");
        input.capturedMs[2] = 0;
        ProcessResult expired = engine.composePanorama(input, 1000);
        require(!expired.active[2] && expired.status.contains("Stale C3"), "Expired camera remains active");
        require(pixel(expired.output, yawPixel(cfg, -90), 240) == cv::Vec3i(0, 0, 0),
                "Expired image is still displayed");
        input = frames; input.capturedMs[2] = 1001;
        expired = engine.composePanorama(input, 1000);
        require(!expired.active[2] && expired.ageMs[2] == -1, "Future capture time accepted");
        input = frames; input.images[2] = QImage(320, 240, QImage::Format_RGB888);
        expired = engine.composePanorama(input, 1000);
        require(!expired.active[2] && expired.status.contains("Invalid size/image C3"),
                "Wrong resolution silently resized");
        const ProcessResult empty = engine.composePanorama(FrameInput{}, 1000);
        require(empty.status.contains("Missing C1,C2,C3,C4,C5,C6"), "Missing feed diagnostics incomplete");
        cv::Mat black(empty.output.height(), empty.output.width(), CV_8UC3,
                      const_cast<uchar *>(empty.output.constBits()), empty.output.bytesPerLine());
        require(cv::countNonZero(black.reshape(1)) == 0, "No-input render fabricates pixels");
        input = frames; input.capturedMs[0] = 800;
        require(engine.composePanorama(input, 1000).captureSkewMs == 200, "Capture skew is incorrect");
    });

    test("JSON round trip, minimal defaults and failure transaction", [&] {
        QTemporaryDir temp;
        require(temp.isValid(), "Temporary directory unavailable");
        const QString path = temp.filePath("engine.json");
        QString error;
        require(cfg.save(path, &error), "JSON save failed");
        Configuration loaded;
        loaded.cameras[0].yawDeg = 73;
        require(Configuration::load(path, loaded, &error), "Saved JSON failed to load");
        require(loaded.cameras[0].yawDeg == 0 && loaded.birdSize == 512 && !loaded.exposureBalance,
                "Configuration values did not round-trip");
        for (const auto &c : loaded.cameras)
            require(!c.intrinsicCalibrated && !c.groundCalibrated && !c.yawCalibrated,
                    "Round-trip fabricated calibration");
        require(!Configuration::load(temp.filePath("missing.json"), loaded, &error) &&
                loaded.cameras[0].yawDeg == 0, "Missing-file load replaced the caller configuration");
        writeJson(path, "{\"version\":1}");
        require(Configuration::load(path, loaded, &error) && loaded.exposureBalance,
                "Minimal JSON should preserve defaults");
        const QByteArray invalid[] = {
            "{\"version\":2}", "{\"version\":1,\"birdSize\":12.5}",
            "{\"version\":1,\"exposureBalance\":\"true\"}",
            "{\"version\":1,\"cameras\":[{\"id\":1}]}", "[1,2,3]", "{broken"
        };
        for (const auto &bytes : invalid) {
            writeJson(path, bytes);
            require(!Configuration::load(path, loaded, &error) && !error.isEmpty(),
                    "Malformed JSON accepted or missing error");
            require(loaded.cameras[0].yawDeg == 0, "Failed JSON parse changed configuration");
        }
        Configuration calibrated = cfg;
        for (auto &c : calibrated.cameras) {
            c.K = {{320, 0, 320, 0, 320, 240, 0, 0, 1}};
            c.intrinsicCalibrated = c.groundCalibrated = c.yawCalibrated = true;
        }
        calibrated.cameras[0].lens = LensModel::Fisheye;
        calibrated.cameras[0].D[0] = .01;
        require(calibrated.save(path, &error) && Configuration::load(path, loaded, &error),
                "Calibrated configuration failed round-trip");
        require(loaded.cameras[0].lens == LensModel::Fisheye && loaded.cameras[0].D[0] == .01 &&
                loaded.cameras[0].groundSrc == calibrated.cameras[0].groundSrc &&
                loaded.cameras[0].groundDst == calibrated.cameras[0].groundDst,
                "Lens/quad values did not round-trip");
    });

    test("rectified ground homography and vehicle footprint", [&] {
        Configuration ground = cfg;
        const std::array<QPointF, 4> source{{QPointF(40, 40), QPointF(599, 40),
                                           QPointF(599, 439), QPointF(40, 439)}};
        const std::array<QPointF, 4> destination{{QPointF(20, 20), QPointF(190, 20),
                                                QPointF(190, 180), QPointF(20, 180)}};
        FrameInput input;
        const QImage image = grid();
        for (int i = 0; i < CameraCount; ++i) {
            auto &c = ground.cameras[i];
            c.K = {{320, 0, 320, 0, 320, 240, 0, 0, 1}};
            c.intrinsicCalibrated = c.groundCalibrated = true;
            c.groundSrc = source; c.groundDst = destination;
            input.images[i] = image; input.capturedMs[i] = 1000;
        }
        Engine groundEngine(ground);
        const ProcessResult result = groundEngine.composeBird(input, 1000);
        require(!result.approximateGeometry && result.status.contains("Calibrated ground warp"),
                "Calibrated bird mode does not report its calibration");
        cv::Point2f a[4], b[4];
        for (int i = 0; i < 4; ++i) {
            a[i] = cv::Point2f(float(source[i].x()), float(source[i].y()));
            b[i] = cv::Point2f(float(destination[i].x()), float(destination[i].y()));
        }
        cv::Mat raw(SourceHeight, SourceWidth, CV_8UC3,
                    const_cast<uchar *>(image.constBits()), image.bytesPerLine()), reference;
        cv::warpPerspective(raw, reference, cv::getPerspectiveTransform(a, b), cv::Size(512, 512));
        for (const cv::Point sample : {cv::Point(75, 85), cv::Point(130, 130), cv::Point(100, 100)}) {
            const cv::Vec3b ref = reference.at<cv::Vec3b>(sample);
            require(near(pixel(result.output, sample.x, sample.y), cv::Vec3i(ref[0], ref[1], ref[2]), 2),
                    "Cached inverse homography does not match perspective reference");
        }
        require(pixel(result.output, 256, 256) == cv::Vec3i(0, 0, 0), "Vehicle footprint contains camera pixels");
        const ProcessResult demo = engine.composeBird(frames, 1000);
        require(demo.approximateGeometry && demo.status.contains("DEMO bird view"),
                "Default bird view is presented as measured geometry");
        cv::Mat demoPixels(512, 512, CV_8UC3, const_cast<uchar *>(demo.output.constBits()), demo.output.bytesPerLine());
        require(cv::countNonZero(demoPixels.reshape(1)) > 20000, "Default ground sectors have no visible pixels");
    });

    test("pitch direction and calibrated equidistant lens projection", [&] {
        FrameInput input;
        input.images.fill(grid()); input.capturedMs.fill(1000);
        const int x = yawPixel(cfg, -90);
        const int baseGreen = pixel(engine.composePanorama(input, 1000).output, x, 240)[1];
        Configuration tilted = cfg;
        tilted.cameras[2].pitchDeg = 15;
        Engine tiltEngine(tilted);
        require(pixel(tiltEngine.composePanorama(input, 1000).output, x, 240)[1] > baseGreen + 20,
                "Positive pitch should place the horizon below image center");

        Configuration fish = cfg;
        for (auto &c : fish.cameras) {
            c.K = {{300, 0, 320, 0, 300, 240, 0, 0, 1}};
            c.lens = LensModel::Fisheye;
            c.intrinsicCalibrated = true;
        }
        Engine fishEngine(fish);
        const ProcessResult output = fishEngine.composePanorama(input, 1000);
        const cv::Vec3i actual = pixel(output.output, yawPixel(cfg, -90), 240);
        require(std::abs(actual[0] - 128) <= 3 && std::abs(actual[1] - 128) <= 3,
                "Equidistant optical center projection incorrect");
        require(!output.output.isNull() && !output.status.contains("Processing failed"),
                "Fisheye maps produced invalid output");
    });

    test("overlap exposure stays bounded and preserves equal cameras", [&] {
        Configuration balanced = cfg;
        balanced.exposureBalance = true;
        Engine balancedEngine(balanced);
        FrameInput input;
        for (int i = 0; i < CameraCount; ++i) {
            input.images[i] = solid(100, 100, 100); input.capturedMs[i] = 1000;
        }
        require(near(pixel(balancedEngine.composePanorama(input, 1000).output,
                           yawPixel(cfg, -90), 240), cv::Vec3i(100, 100, 100), 1),
                 "Exposure matching changed equal cameras");
        input.images[1] = solid(230, 230, 230); input.images[5] = solid(30, 30, 30);
        for (quint64 sequence = 1; sequence <= 10; ++sequence) {
            input.sequence.fill(sequence);
            const auto ignoredEyes = balancedEngine.composePanorama(input, 1000);
            require(near(pixel(ignoredEyes.output, yawPixel(cfg, 0), 240), cv::Vec3i(100, 100, 100), 1),
                    "Unselected stereo backup changed front exposure");
            require(near(pixel(ignoredEyes.output, 0, 240), cv::Vec3i(100, 100, 100), 1),
                    "Unselected stereo backup changed rear exposure");
        }
        input.images[2] = solid(70, 70, 70);
        ProcessResult result;
        for (quint64 sequence = 1; sequence <= 20; ++sequence) {
            input.sequence.fill(sequence);
            result = balancedEngine.composePanorama(input, 1000);
        }
        const int brightness = pixel(result.output, yawPixel(cfg, -90), 240)[0];
        require(brightness > 70 && brightness <= 81, "Exposure gain failed or exceeded 1.15 clamp");
        const ProcessResult repeated = balancedEngine.composePanorama(input, 1000);
        require(pixel(repeated.output, yawPixel(cfg, -90), 240) == pixel(result.output, yawPixel(cfg, -90), 240),
                "Repeated frame advanced exposure filter");
    });

    report << "Engine self-test: " << (failures ? "FAILED" : "PASSED")
           << " (" << failures << " failures)\n";
    report.flush();
    return failures ? 1 : 0;
}
} // namespace surround

#ifdef SURROUND_ENGINE_SELFTEST_MAIN
int main(int argc, char **argv) {
    QCoreApplication application(argc, argv);
    return surround::runEngineSelfTest();
}
#endif
