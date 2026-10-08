#include "capture_source.h"

#include <QCoreApplication>
#include <QGuiApplication>
#include <algorithm>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace surround {
int runCaptureSelfTest() {
    try {
        const auto check = [](bool condition, const char* message) {
            if (!condition) throw std::runtime_error(message);
        };
        check(captureNewestBank(0, 0, false, 0) == -1, "uninitialized banks");
        check(captureNewestBank(17, 16, false, 0) == 0, "newest ping");
        check(captureNewestBank(17, 18, true, 17) == 1, "newest pong");
        check(captureNewestBank(18, 18, false, 0) == 1, "equal banks have deterministic selection");
        check(captureNewestBank(18, 18, true, 18) == -1, "equal banks must not duplicate a frame");
        check(captureNewestBank(17, 18, true, 18) == -1, "unchanged tag");
        check(captureNewestBank(0xffffffffu, 0, true, 0xffffffffu) == 1, "wrap to zero");
        check(captureNewestBank(1, 0xffffffffu, true, 0) == 0, "wrap ordering");
        check(captureNewestBank(3, 4, true, 100) == -1, "old tags after reset");

        std::vector<unsigned char> packet(captureFrameBytes + 16, 0);
        quint32 tag = 42;
        std::memcpy(packet.data() + captureFrameBytes, &tag, sizeof(tag));
        check(captureValidateFrame(packet.data(), packet.size(), 42, 42), "stable commit rejected");
        check(!captureValidateFrame(packet.data(), packet.size(), 41, 42), "changed embedded tag accepted");
        check(!captureValidateFrame(packet.data(), packet.size(), 42, 43), "changed post-read tag accepted");
        check(!captureValidateFrame(packet.data(), captureFrameBytes + 3, 42, 42), "truncated frame accepted");
        check(!captureValidateFrame(nullptr, packet.size(), 42, 42), "null frame accepted");
        tag = 0;
        std::memcpy(packet.data() + captureFrameBytes, &tag, sizeof(tag));
        check(captureValidateFrame(packet.data(), packet.size(), 0, 0), "valid wrapped commit rejected");

        const quint16 rgb[3] = {0xf800, 0x07e0, 0x001f};
        std::memcpy(packet.data(), rgb, sizeof(rgb));
        QImage converted = captureRgb565Image(packet.data(), captureFrameBytes);
        check(converted.size() == QSize(640, 480) && converted.format() == QImage::Format_RGB888,
              "incorrect converted image layout");
        check(converted.pixelColor(0, 0) == QColor(255, 0, 0), "RGB565 red conversion");
        check(converted.pixelColor(1, 0) == QColor(0, 255, 0), "RGB565 green conversion");
        check(converted.pixelColor(2, 0) == QColor(0, 0, 255), "RGB565 blue conversion");
        std::fill(packet.begin(), packet.end(), 0);
        check(converted.pixelColor(0, 0) == QColor(255, 0, 0), "converted image aliases DMA storage");
        QImage detached = converted;
        detached.fill(Qt::black);
        check(converted.pixelColor(0, 0) == QColor(255, 0, 0), "image copies lack value semantics");
        check(captureRgb565Image(nullptr, captureFrameBytes).isNull(), "null pixels accepted");
        check(captureRgb565Image(packet.data(), captureFrameBytes - 1).isNull(), "short RGB565 frame accepted");

        check(qobject_cast<QGuiApplication*>(QCoreApplication::instance()) != nullptr,
              "capture self-test needs QGuiApplication (use QT_QPA_PLATFORM=offscreen on a host)");
        CaptureSource capture(true);
        capture.start();
        CaptureSnapshot first;
        const qint64 deadline = captureMonotonicMs() + 2500;
        while (captureMonotonicMs() < deadline) {
            first = capture.snapshot();
            if (std::all_of(first.sequences.begin(), first.sequences.end(),
                            [](quint64 count) { return count >= 2; })) break;
            QThread::msleep(10);
        }
        for (int camera = 0; camera < 6; ++camera) {
            check(first.sequences[camera] >= 2, "synthetic camera missing or starved");
            check(first.images[camera].format() == QImage::Format_RGB888, "synthetic RGB888 layout");
            check(first.capturedMs[camera] > 0 && first.errors[camera] == 0, "synthetic capture metadata");
            if (camera) check(first.images[camera].pixelColor(639, 479) != first.images[0].pixelColor(639, 479),
                              "synthetic cameras need distinct colors");
        }
        const QImage frozen = first.images[5].copy();
        const quint64 frozenSequence = first.sequences[5];
        CaptureSnapshot next;
        while (captureMonotonicMs() < deadline) {
            next = capture.snapshot();
            if (next.sequences[5] >= frozenSequence + 3) break;
            QThread::msleep(10);
        }
        capture.stop();
        check(!capture.isRunning(), "capture stop did not join worker");
        check(next.sequences[5] >= frozenSequence + 3, "camera six did not continue advancing");
        check(first.images[5] == frozen, "held snapshot mutated on subsequent capture");
        check(next.images[5] != frozen, "synthetic pattern is static");
        CaptureSnapshot altered = capture.snapshot();
        altered.images[0].fill(Qt::black);
        check(capture.snapshot().images[0].pixelColor(639, 479) != QColor(Qt::black),
              "caller mutation escaped snapshot mutex/value semantics");
        check(capture.snapshot().error.isEmpty(), "synthetic capture reported an error");
        std::cout << "CAPTURE_SELFTEST_PASS\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "CAPTURE_SELFTEST_FAIL: " << error.what() << '\n';
        return 1;
    }
}
} // namespace surround
