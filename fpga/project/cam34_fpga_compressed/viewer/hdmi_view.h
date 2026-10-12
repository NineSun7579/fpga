#pragma once
#include <QByteArray>
#include <QImage>
#include <cstring>
#include "cam34_six.h"

namespace tdm {
// Isolated C3/C4 composite mode. The existing virtual-camera interface
// owns one combined recognition region. F can return to six-camera view.
constexpr int hdmiLeftCamera = 2;
constexpr int hdmiRightCamera = 3;
constexpr int hdmiInferenceCamera = 6; // virtual, full HDMI image; never a DMA index
constexpr int hdmiAnalyticsWidth = 640;
constexpr int hdmiAnalyticsHeight = 240;
constexpr int hdmiAnalyticsPad = 120; // existing pipeline expects 640x480
constexpr int hdmiModelPad = 80 + hdmiAnalyticsPad;

inline bool hdmiPairReady(qint64 now, qint64 left, qint64 right,
                          int generation, int leftGeneration, int rightGeneration) {
    // Latest-buffer pairing is bounded by time, not claimed to be tag-exact.
    return left > 0 && right > 0 && now >= left && now >= right &&
           now - left <= 100 && now - right <= 100 && qAbs(left - right) <= 40 &&
           leftGeneration == generation && rightGeneration == generation;
}

// One 2:1 horizontal box filter per source. The complete vertical field
// is retained. RAW DMA transfer remains two 640x480 RGB565 frames.
inline void rgb565RowToRgb888(const char* src, uchar* dst, int pixels) {
    const auto* p = reinterpret_cast<const uchar*>(src);
    for (int i = 0; i < pixels; ++i) {
        const quint16 v = quint16(p[i * 2]) | (quint16(p[i * 2 + 1]) << 8);
        dst[i * 3 + 0] = uchar((((v >> 11) & 31) << 3) | (((v >> 11) & 31) >> 2));
        dst[i * 3 + 1] = uchar((((v >> 5) & 63) << 2) | (((v >> 5) & 63) >> 4));
        dst[i * 3 + 2] = uchar(((v & 31) << 3) | ((v & 31) >> 2));
    }
}

inline QImage hdmiAnalyticsImage(const QByteArray& left, const QByteArray& right) {
    constexpr int width = 320, height = 240, rowBytes = width * 2;
    if (left.size() != rowBytes * height || right.size() != rowBytes * height) return {};
    QImage result(640, 480, QImage::Format_RGB888);
    result.fill(qRgb(114, 114, 114));
    for (int y = 0; y < height; ++y) {
        rgb565RowToRgb888(left.constData() + y * rowBytes, result.scanLine(y + 120), width);
        rgb565RowToRgb888(right.constData() + y * rowBytes, result.scanLine(y + 120) + width * 3, width);
    }
    return result;
}

int runHdmiViewSelfTest();
} // namespace tdm
