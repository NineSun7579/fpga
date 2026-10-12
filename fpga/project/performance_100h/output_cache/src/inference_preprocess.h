#pragma once
#include <QImage>
#include <QColor>
#include <cstring>

// Worker-only storage. Returned pointers stay valid until the next prepare().
// Square inputs bypass this storage, so they cannot disturb its constant padding.
class InferencePreprocessor {
public:
    const QImage* prepare(const QImage& source) {
        if (source.isNull() || source.format() != QImage::Format_RGB888 ||
            source.width() != 640 || (source.height() != 480 && source.height() != 640) ||
            source.bytesPerLine() < 640 * 3)
            return nullptr;
        if (source.height() == 640) return &source;
        if (m_letterbox.isNull()) {
            m_letterbox = QImage(640, 640, QImage::Format_RGB888);
            if (m_letterbox.isNull()) return nullptr;
            m_letterbox.fill(QColor(114, 114, 114));
        }
        for (int y = 0; y < 480; ++y)
            std::memcpy(m_letterbox.scanLine(y + 80), source.constScanLine(y), 640 * 3);
        return &m_letterbox;
    }
private:
    QImage m_letterbox;
};
