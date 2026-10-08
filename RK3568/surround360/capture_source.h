#pragma once

#include <QImage>
#include <QMutex>
#include <QThread>
#include <QString>
#include <array>
#include <cstddef>
#include <cstdint>

namespace surround {

constexpr int captureCameraCount = 6;
constexpr int captureWidth = 640;
constexpr int captureHeight = 480;
constexpr std::size_t captureFrameBytes = 640u * 480u * 2u;

struct CaptureSnapshot {
    std::array<QImage, 6> images;
    std::array<qint64, 6> capturedMs{};
    std::array<quint64, 6> sequences{};
    std::array<quint64, 6> errors{};
    std::array<double, 6> fps{};
    std::array<quint32, 6> tags{};
    QString error;
    qint64 producedMs = 0;
};

// All timestamps are CLOCK_MONOTONIC milliseconds (steady clock on other hosts).
qint64 captureMonotonicMs();
int captureNewestBank(quint32 a, quint32 b, bool delivered, quint32 last);
bool captureValidateFrame(const void* packet, std::size_t bytes,
                          quint32 selectedTag, quint32 tagAfterRead);
QImage captureRgb565Image(const void* pixels, std::size_t bytes);
int runCaptureSelfTest();

// Construct/start from the GUI thread. One worker polls all six inputs in order.
// A snapshot owns its RGB888 pixels and remains valid after later captures.
class CaptureSource : public QThread {
public:
    explicit CaptureSource(bool synthetic = false, QObject* parent = nullptr);
    ~CaptureSource() override;
    CaptureSnapshot snapshot() const;
    void stop();

protected:
    void run() override;

private:
    void setError(const QString& error);
    const bool synthetic_;
    mutable QMutex mutex_;
    CaptureSnapshot latest_;
};

} // namespace surround
