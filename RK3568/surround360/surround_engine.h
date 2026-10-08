#pragma once

#include <QImage>
#include <QPointF>
#include <QString>
#include <QtGlobal>
#include <array>
#include <memory>

namespace surround {

constexpr int CameraCount = 6;
constexpr int SourceWidth = 640;
constexpr int SourceHeight = 480;

enum class LensModel { Pinhole, Fisheye };
enum class ViewMode { Panorama, Birdseye };

struct CameraCalibration {
    int id = 1; // Stable physical identity: C1..C6, never reordered by yaw.
    double yawDeg = 0.0; // Positive yaw points right; zero is forward.
    double pitchDeg = 0.0; // Positive pitch points up.
    double rollDeg = 0.0;
    double hfovDeg = 110.0;
    LensModel lens = LensModel::Pinhole;
    std::array<double, 9> K{{0, 0, 0, 0, 0, 0, 0, 0, 1}};
    // OpenCV order. Pinhole accepts 4/5/8 coefficients; fisheye uses 4.
    std::array<double, 8> D{};
    int distortionCount = 4;
    bool intrinsicCalibrated = false;
    bool yawCalibrated = false;
    bool groundCalibrated = false;
    // TL, TR, BR, BL in the rectified 640x480 image and bird output pixels.
    // When groundCalibrated is false, generated illustrative quads are used.
    std::array<QPointF, 4> groundSrc{};
    std::array<QPointF, 4> groundDst{};
};

struct Configuration {
    int version = 1;
    std::array<CameraCalibration, CameraCount> cameras;
    int panoramaWidth = 1536;
    int panoramaHeight = 480;
    int birdSize = 512;
    double verticalFovDeg = 70.0;
    bool exposureBalance = true;
    qint64 freshMs = 250;
    qint64 staleMs = 1000;

    Configuration();
    bool validate(QString *error = nullptr) const;
    bool save(const QString &path, QString *error = nullptr) const;
    // Failure leaves out unchanged; missing files do not imply calibration.
    static bool load(const QString &path, Configuration &out, QString *error = nullptr);
};

struct FrameInput {
    std::array<QImage, CameraCount> images;
    // Monotonic milliseconds, from the same clock as nowMs. Zero is valid.
    std::array<qint64, CameraCount> capturedMs{};
    std::array<quint64, CameraCount> sequence{};
    std::array<quint64, CameraCount> generation{};
};

struct ProcessResult {
    QImage output; // Owned RGB888 pixels, safe after the next render.
    QString status;
    std::array<bool, CameraCount> active{};
    // Projection choices, independent of the raw six-camera availability.
    std::array<bool, CameraCount> projectionSelected{{true, false, true, true, true, false}};
    std::array<qint64, CameraCount> ageMs{}; // -1 for missing/future/invalid input.
    qint64 captureSkewMs = 0;
    bool approximateGeometry = true;
};

class Engine {
public:
    explicit Engine(const Configuration &config = Configuration());
    ~Engine();
    Engine(const Engine &) = delete;
    Engine &operator=(const Engine &) = delete;
    const Configuration &config() const;
    // Builds maps before replacing the current valid configuration.
    bool setConfig(const Configuration &config, QString *error = nullptr);
    ProcessResult render(const FrameInput &frames, ViewMode mode, qint64 nowMs);
    ProcessResult composePanorama(const FrameInput &frames, qint64 nowMs);
    ProcessResult composeBird(const FrameInput &frames, qint64 nowMs);
    // Convenience entry points for capture/UI code with separate arrays.
    QImage panorama(const std::array<QImage, CameraCount> &images,
                    const std::array<qint64, CameraCount> &capturedMs, qint64 nowMs);
    QImage birdseye(const std::array<QImage, CameraCount> &images,
                   const std::array<qint64, CameraCount> &capturedMs, qint64 nowMs);

private:
    struct Impl;
    std::unique_ptr<Impl> d;
};

// CPU only; no QApplication, window, capture device or board required.
int runEngineSelfTest();

} // namespace surround
