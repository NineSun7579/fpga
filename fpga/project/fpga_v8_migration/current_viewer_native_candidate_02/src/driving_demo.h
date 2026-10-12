#pragma once

#include "vision_types.h"

enum class DrivingLane { Left, Straight, Right };
enum class DrivingMode { Auto, Stop, ForcedGo };
enum class DrivingSignal { Unknown, Red, Amber, Green, Off };

struct DrivingDemoConfig {
    float confidenceThreshold = 0.4f;
    qint64 staleMs = 1200;
    int greenSamples = 2;       // Clamped to at least two distinct captures.
    qint64 greenHoldMs = 200;   // Clamped to at least 200ms of captured observations.
};

struct DrivingSnapshot {
    bool enabled = false;
    DrivingLane lane = DrivingLane::Straight;
    DrivingMode mode = DrivingMode::Auto;
    DrivingSignal signal = DrivingSignal::Unknown;
    bool moving = false;
    bool alarm = false;       // ForcedGo against red only.
    bool warning = false;     // ForcedGo against amber/off/unknown.
    bool conflict = false;
    bool stale = false;
    QString reason;
    int personCount = 0;
    int vehicleCount = 0;
    int zebraCount = 0;
    int modelCount = 0;        // Retained result sets, never greater than four.
};

// Single-threaded, coordinate-independent simulation. No actuator or image access.
// All timestamps are milliseconds from the same nonnegative monotonic clock.
// The ordered class list identifies a model; identical vocabularies share a slot.
class DrivingDemo {
public:
    explicit DrivingDemo(const DrivingDemoConfig& config = DrivingDemoConfig());
    void setEnabled(bool enabled);
    void setLane(DrivingLane lane);
    void setMode(DrivingMode mode);
    // Returns false for negative/future/stale/duplicate/out-of-order timestamps.
    // Accepted captures must increase globally, including across model rotation.
    bool observe(const QStringList& classes, const QVector<Detection>& detections,
                 qint64 capturedMs, qint64 nowMs);
    // Ages evidence and clears green confirmation on expiry. Must use monotonic nowMs.
    DrivingSnapshot snapshot(qint64 nowMs);
    // Discards evidence and green hold; retains clock watermarks to reject old replay.
    void resetPerception();

private:
    struct Observation {
        QStringList classes;
        QVector<Detection> detections;
        qint64 capturedMs = 0;
    };
    struct Evidence {
        DrivingSignal signal = DrivingSignal::Unknown;
        bool conflict = false;
        bool stale = false;
        int tier = 0;
        int personCount = 0;
        int vehicleCount = 0;
        int zebraCount = 0;
    };
    Evidence evidence(qint64 nowMs) const;
    int observationTier(const Observation& observation, int* mask) const;
    void clearGreen();
    bool greenConfirmed() const;

    DrivingDemoConfig config_;
    bool enabled_ = false;
    DrivingLane lane_ = DrivingLane::Straight;
    DrivingMode mode_ = DrivingMode::Auto;
    QVector<Observation> observations_;
    qint64 lastNowMs_ = -1;
    qint64 lastCapturedMs_ = -1;
    qint64 greenFirstMs_ = -1;
    qint64 greenLastMs_ = -1;
    int greenSamples_ = 0;
};

int runDrivingDemoSelfTest();
