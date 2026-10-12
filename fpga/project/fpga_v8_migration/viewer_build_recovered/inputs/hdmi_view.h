#pragma once
#include <QByteArray>
#include <QImage>
#include <cstring>

namespace tdm {
// The optical transport splits a 1280x480 frame into C5/C6. Both camera
// and HDMI modes use this protocol; freshness cannot identify the source mode.
// HDMI selection is explicit (F or --prefer-hdmifull on).
constexpr int hdmiLeftCamera = 4;
constexpr int hdmiRightCamera = 5;
constexpr int hdmiInferenceCamera = 6; // virtual, full HDMI image; never a DMA index
constexpr int hdmiAnalyticsWidth = 640;
constexpr int hdmiAnalyticsHeight = 360;
constexpr int hdmiAnalyticsPad = 60; // existing pipeline expects 640x480
constexpr int hdmiModelPad = 80 + hdmiAnalyticsPad;

inline bool hdmiPairReady(qint64 now, qint64 left, qint64 right,
                          int generation, int leftGeneration, int rightGeneration) {
    // Latest-buffer pairing is bounded by time, not claimed to be tag-exact.
    return left > 0 && right > 0 && now >= left && now >= right &&
           now - left <= 100 && now - right <= 100 && qAbs(left - right) <= 40 &&
           leftGeneration == generation && rightGeneration == generation;
}

inline QImage hdmiAnalyticsImage(const QByteArray &left, const QByteArray &right) {
    constexpr int halfWidth = 640, height = 480, rowBytes = halfWidth * 2;
    if (left.size() != rowBytes * height || right.size() != rowBytes * height) return {};
    QImage joined(halfWidth * 2, height, QImage::Format_RGB16);
    for (int y = 0; y < height; ++y) {
        std::memcpy(joined.scanLine(y), left.constData() + y * rowBytes, rowBytes);
        std::memcpy(joined.scanLine(y) + rowBytes, right.constData() + y * rowBytes, rowBytes);
    }
    // Restore the source's 16:9 aspect before inference, then letterbox.
    const QImage rgb = joined.scaled(hdmiAnalyticsWidth, hdmiAnalyticsHeight,
                                    Qt::IgnoreAspectRatio, Qt::SmoothTransformation)
                              .convertToFormat(QImage::Format_RGB888);
    QImage result(640, 480, QImage::Format_RGB888);
    result.fill(qRgb(114, 114, 114));
    for (int y = 0; y < rgb.height(); ++y)
        std::memcpy(result.scanLine(y + hdmiAnalyticsPad), rgb.constScanLine(y), rgb.width() * 3);
    return result;
}

int runHdmiViewSelfTest();
} // namespace tdm
