#include "driving_demo.h"

#include <algorithm>
#include <cmath>

namespace {
enum { Red = 1, Amber = 2, Green = 4, Off = 8 };

// Exact model vocabulary: no substring/color guessing, and U-turn never applies.
struct LightClass { const char* name; int direction; int color; };
const LightClass lights[] = {
    {"tlr_motor_red", 0, Red}, {"tly_motor_amber", 0, Amber},
    {"tlg_motor_green", 0, Green},
    {"tlra_left_red", 1, Red}, {"tlya_left_amber", 1, Amber},
    {"tlga_left_green", 1, Green},
    {"tsra_straight_red", 2, Red}, {"tsya_straight_amber", 2, Amber},
    {"tsga_straight_green", 2, Green},
    {"trra_right_red", 3, Red}, {"trya_right_amber", 3, Amber},
    {"trga_right_green", 3, Green},
    {"tura_uturn_red", 4, Red}, {"tuya_uturn_amber", 4, Amber},
    {"tuga_uturn_green", 4, Green}, {"tln_lamp_off", 0, Off}
};

const LightClass* lightClass(const QString& name) {
    for (const auto& light : lights)
        if (name == QLatin1String(light.name)) return &light;
    return nullptr;
}

int direction(DrivingLane lane) {
    switch (lane) {
    case DrivingLane::Left: return 1;
    case DrivingLane::Straight: return 2;
    case DrivingLane::Right: return 3;
    }
    return -1;
}

bool usable(const Detection& detection, const QStringList& classes, float threshold) {
    return !detection.predicted && detection.cls >= 0 && detection.cls < classes.size() &&
        std::isfinite(detection.score) && detection.score >= threshold && detection.score <= 1.0f;
}

bool isVehicle(const QString& name) {
    return name == QLatin1String("vehicle") || name == QLatin1String("car") ||
        name == QLatin1String("bus") || name == QLatin1String("truck") ||
        name == QLatin1String("motorcycle") || name == QLatin1String("bicycle");
}
} // namespace

DrivingDemo::DrivingDemo(const DrivingDemoConfig& config) : config_(config) {
    if (!std::isfinite(config_.confidenceThreshold) || config_.confidenceThreshold < 0.0f ||
        config_.confidenceThreshold > 1.0f) config_.confidenceThreshold = 0.4f;
    if (config_.staleMs <= 0) config_.staleMs = 1200;
    config_.greenSamples = std::max(2, config_.greenSamples);
    config_.greenHoldMs = std::max(qint64(200), config_.greenHoldMs);
}

void DrivingDemo::clearGreen() {
    greenFirstMs_ = greenLastMs_ = -1;
    greenSamples_ = 0;
}

void DrivingDemo::setEnabled(bool enabled) {
    if (enabled_ != enabled) clearGreen();
    enabled_ = enabled;
}

void DrivingDemo::setLane(DrivingLane lane) {
    if (lane_ != lane) clearGreen();
    lane_ = lane;
}

void DrivingDemo::setMode(DrivingMode mode) {
    if (mode_ != mode) clearGreen();
    mode_ = mode;
}

void DrivingDemo::resetPerception() {
    observations_.clear();
    clearGreen();
}

void DrivingDemo::setInputAvailable(bool available) {
    if (inputAvailable_ != available) resetPerception();
    inputAvailable_ = available;
}

int DrivingDemo::observationTier(const Observation& observation, int* mask) const {
    const int selected = direction(lane_);
    if (selected < 0) { *mask = 0; return 0; }
    bool supportsMotor = false, supportsDirection = false, supportsOff = false;
    for (const auto& name : observation.classes) {
        const auto* light = lightClass(name);
        if (!light) continue;
        supportsOff |= light->color == Off;
        supportsMotor |= light->direction == 0 && light->color != Off;
        supportsDirection |= light->direction == selected;
    }
    int motor = 0, directed = 0, off = 0;
    for (const auto& detection : observation.detections) {
        if (!usable(detection, observation.classes, config_.confidenceThreshold)) continue;
        const auto* light = lightClass(observation.classes.at(detection.cls));
        if (!light) continue;
        if (light->color == Off) off |= Off;
        else if (light->direction == selected) directed |= light->color;
        else if (light->direction == 0) motor |= light->color;
    }
    if (directed) { *mask = directed | off; return 2; }
    if (motor) { *mask = motor | off; return 1; }
    *mask = off;
    // A missing applicable head in a capable model is unknown evidence, not a
    // reason to keep that model's disappeared green. Nontraffic models are ignored.
    if (supportsDirection) return 2;
    if (supportsMotor || supportsOff) return 1;
    return 0;
}

DrivingDemo::Evidence DrivingDemo::evidence(qint64 nowMs) const {
    Evidence result;
    int mask = 0;
    bool unknown = false, staleRelevant = false;
    for (const auto& observation : observations_) {
        int observedMask = 0;
        const int tier = observationTier(observation, &observedMask);
        if (nowMs - observation.capturedMs > config_.staleMs) {
            staleRelevant |= tier != 0;
            continue;
        }
        for (const auto& detection : observation.detections) {
            if (!usable(detection, observation.classes, config_.confidenceThreshold)) continue;
            const auto& name = observation.classes.at(detection.cls);
            if (name == QLatin1String("person")) ++result.personCount;
            if (isVehicle(name)) ++result.vehicleCount;
            if (name == QLatin1String("zebra") || name == QLatin1String("zebra_crossing"))
                ++result.zebraCount;
        }
        if (tier == 0 || tier < result.tier) continue;
        if (tier > result.tier) { mask = 0; unknown = false; result.tier = tier; }
        mask |= observedMask;
        unknown |= observedMask == 0;
    }
    result.stale = result.tier == 0 && staleRelevant;
    result.conflict = mask && (mask & (mask - 1));
    if (mask & Red) result.signal = DrivingSignal::Red;
    else if (mask & Amber) result.signal = DrivingSignal::Amber;
    else if (mask == Green && !unknown) result.signal = DrivingSignal::Green;
    else if (mask == Off && !unknown) result.signal = DrivingSignal::Off;
    return result;
}

bool DrivingDemo::observe(const QStringList& classes, const QVector<Detection>& detections,
                           qint64 capturedMs, qint64 nowMs) {
    if (!inputAvailable_) return false;
    if (nowMs < 0 || nowMs < lastNowMs_) return false;
    lastNowMs_ = nowMs;
    // Age existing evidence even when the incoming capture is rejected.
    if (evidence(nowMs).signal != DrivingSignal::Green ||
        (greenLastMs_ >= 0 && nowMs - greenLastMs_ > config_.staleMs)) clearGreen();
    if (capturedMs < 0 || capturedMs > nowMs || nowMs - capturedMs > config_.staleMs ||
        capturedMs <= lastCapturedMs_ || classes.isEmpty()) return false;
    lastCapturedMs_ = capturedMs;

    int slot = -1;
    for (int i = 0; i < observations_.size(); ++i)
        if (observations_.at(i).classes == classes) { slot = i; break; }
    if (slot < 0) {
        if (observations_.size() == 4) {
            // Capture times increase globally, so smallest timestamp is the oldest model.
            slot = 0;
            for (int i = 1; i < observations_.size(); ++i)
                if (observations_.at(i).capturedMs < observations_.at(slot).capturedMs) slot = i;
        } else {
            observations_.push_back(Observation());
            slot = observations_.size() - 1;
        }
    }
    auto& observation = observations_[slot];
    observation.classes = classes;
    observation.detections = detections;
    observation.capturedMs = capturedMs;
    const auto current = evidence(nowMs);
    if (current.signal != DrivingSignal::Green) {
        clearGreen();
    } else {
        int mask = 0;
        const int tier = observationTier(observation, &mask);
        // Rotation through unrelated models or lower-priority generic models
        // cannot accumulate samples from a cached directional green.
        if (tier == current.tier && mask == Green && enabled_ && mode_ == DrivingMode::Auto) {
            if (greenFirstMs_ < 0) greenFirstMs_ = capturedMs;
            greenLastMs_ = capturedMs;
            if (greenSamples_ < config_.greenSamples) ++greenSamples_;
        }
    }
    return true;
}

bool DrivingDemo::greenConfirmed() const {
    return greenSamples_ >= config_.greenSamples && greenFirstMs_ >= 0 &&
        greenLastMs_ - greenFirstMs_ >= config_.greenHoldMs;
}

DrivingSnapshot DrivingDemo::snapshot(qint64 nowMs) {
    DrivingSnapshot result;
    result.enabled = enabled_;
    result.inputAvailable = inputAvailable_;
    result.lane = lane_;
    result.mode = mode_;
    result.modelCount = observations_.size();
    const bool validTime = nowMs >= 0 && nowMs >= lastNowMs_;
    Evidence current;
    if (validTime) {
        lastNowMs_ = nowMs;
        current = evidence(nowMs);
    }
    if (!validTime || current.signal != DrivingSignal::Green ||
        (greenLastMs_ >= 0 && nowMs - greenLastMs_ > config_.staleMs)) clearGreen();
    result.signal = current.signal;
    result.conflict = current.conflict;
    result.stale = current.stale;
    result.personCount = current.personCount;
    result.vehicleCount = current.vehicleCount;
    result.zebraCount = current.zebraCount;

    QString perception;
    if (!validTime) perception = QStringLiteral("invalid or backward timestamp");
    else if (current.stale) perception = QStringLiteral("source stale");
    else if (current.conflict) perception = QStringLiteral("conflicting applicable signal colors");
    else switch (current.signal) {
    case DrivingSignal::Red: perception = QStringLiteral("red signal"); break;
    case DrivingSignal::Amber: perception = QStringLiteral("amber signal"); break;
    case DrivingSignal::Off: perception = QStringLiteral("signal lamp off"); break;
    case DrivingSignal::Unknown: perception = QStringLiteral("selected signal unknown or missing"); break;
    case DrivingSignal::Green:
        perception = greenConfirmed() ? QStringLiteral("sustained green") :
            QStringLiteral("green awaiting distinct samples and hold time");
        break;
    }
    if (!inputAvailable_) result.reason = QStringLiteral("HDMI input unavailable; simulated motion inhibited");
    else if (!enabled_) result.reason = QStringLiteral("demo disabled; ") + perception;
    else if (mode_ == DrivingMode::Stop) result.reason = QStringLiteral("manual stop; ") + perception;
    else if (mode_ == DrivingMode::ForcedGo) {
        result.moving = true;
        result.alarm = current.signal == DrivingSignal::Red;
        result.warning = !result.alarm && current.signal != DrivingSignal::Green;
        result.reason = QStringLiteral("forced go; ") + perception;
    } else {
        result.moving = validTime && current.signal == DrivingSignal::Green && greenConfirmed();
        result.reason = (result.moving ? QStringLiteral("auto go; ") : QStringLiteral("auto stop; ")) + perception;
    }
    return result;
}
