#include "driving_demo.h"

#include <iostream>
#include <limits>

// Host-only build, no application/display/hardware required:
// g++ -std=c++17 -fPIC -Wall -Wextra -pedantic -DTDM_DRIVING_DEMO_SELFTEST_MAIN driving_demo.cpp driving_demo_selftest.cpp $(pkg-config --cflags --libs Qt5Core Qt5Gui) -o driving_demo_selftest
namespace {
struct Checks {
    int total = 0;
    int failures = 0;
    void check(bool condition, const char* name) {
        ++total;
        if (!condition) {
            ++failures;
            std::cerr << "DRIVING_DEMO_SELFTEST_FAIL: " << name << '\n';
        }
    }
};

const QStringList allLights = {
    "tlr_motor_red", "tly_motor_amber", "tlg_motor_green",
    "tlra_left_red", "tlya_left_amber", "tlga_left_green",
    "tsra_straight_red", "tsya_straight_amber", "tsga_straight_green",
    "trra_right_red", "trya_right_amber", "trga_right_green",
    "tura_uturn_red", "tuya_uturn_amber", "tuga_uturn_green", "tln_lamp_off"
};
const QStringList motor = {"tlr_motor_red", "tly_motor_amber", "tlg_motor_green"};
const QStringList straight = {"tsra_straight_red", "tsya_straight_amber", "tsga_straight_green"};

Detection detection(const QStringList& classes, const char* name, float score = 0.9f) {
    Detection result;
    result.cls = classes.indexOf(QLatin1String(name));
    result.score = score;
    return result;
}

QVector<Detection> detections(const QStringList& classes, std::initializer_list<const char*> names) {
    QVector<Detection> result;
    for (const char* name : names) result.push_back(detection(classes, name));
    return result;
}

bool observe(DrivingDemo& demo, const QStringList& classes,
             std::initializer_list<const char*> names, qint64 capturedMs, qint64 nowMs = -1) {
    return demo.observe(classes, detections(classes, names), capturedMs,
                        nowMs < 0 ? capturedMs : nowMs);
}

void stableMotor(DrivingDemo& demo, qint64 start = 1000) {
    observe(demo, motor, {"tlg_motor_green"}, start);
    observe(demo, motor, {"tlg_motor_green"}, start + 200);
}
} // namespace

int runDrivingDemoSelfTest() {
    Checks c;
    {
        DrivingDemo demo;
        c.check(!demo.snapshot(0).moving, "disabled default is stationary");
        demo.setEnabled(true);
        c.check(!demo.snapshot(0).moving, "enabled unknown is stationary");
        c.check(observe(demo, motor, {"tlg_motor_green"}, 1000), "first green accepted");
        c.check(!demo.snapshot(1000).moving, "one green cannot authorize go");
        c.check(!demo.snapshot(1100).moving, "wall clock alone cannot confirm green");
        observe(demo, motor, {"tlg_motor_green"}, 1199);
        c.check(!demo.snapshot(1199).moving, "two samples before 200ms cannot go");
        observe(demo, motor, {"tlg_motor_green"}, 1200);
        c.check(demo.snapshot(1200).moving, "distinct samples spanning 200ms authorize go");
        observe(demo, motor, {"tlr_motor_red"}, 1201);
        auto state = demo.snapshot(1201);
        c.check(state.signal == DrivingSignal::Red && !state.moving && !state.alarm,
                "red immediately stops auto without manual alarm");
        observe(demo, motor, {"tlg_motor_green"}, 1401);
        c.check(!demo.snapshot(1401).moving, "red clears prior green confirmation");
        observe(demo, motor, {"tlg_motor_green"}, 1601);
        c.check(demo.snapshot(1601).moving, "green can recover with fresh confirmation");
        observe(demo, motor, {"tly_motor_amber"}, 1602);
        c.check(!demo.snapshot(1602).moving && demo.snapshot(1602).signal == DrivingSignal::Amber,
                "amber immediately stops auto");
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        demo.setMode(DrivingMode::ForcedGo);
        observe(demo, motor, {"tlr_motor_red"}, 1000);
        auto state = demo.snapshot(1000);
        c.check(state.moving && state.alarm && !state.warning, "forced red moves with red alarm");
        demo.setMode(DrivingMode::Stop);
        state = demo.snapshot(1000);
        c.check(!state.moving && !state.alarm && !state.warning, "manual stop overrides red and alarm");
        demo.setMode(DrivingMode::ForcedGo);
        observe(demo, motor, {"tly_motor_amber"}, 1001);
        state = demo.snapshot(1001);
        c.check(state.moving && !state.alarm && state.warning, "forced amber has warning only");
        observe(demo, motor, {}, 1002);
        state = demo.snapshot(1002);
        c.check(state.moving && !state.alarm && state.warning, "forced unknown has warning only");
        observe(demo, allLights, {"tln_lamp_off"}, 1003);
        state = demo.snapshot(1003);
        c.check(state.moving && !state.alarm && state.warning && state.signal == DrivingSignal::Off,
                "forced off has warning only");
        demo.resetPerception();
        observe(demo, motor, {"tlg_motor_green"}, 1004);
        state = demo.snapshot(1004);
        c.check(state.moving && !state.alarm && !state.warning, "forced green needs no warning");
        demo.setEnabled(false);
        state = demo.snapshot(1004);
        c.check(!state.moving && !state.alarm && !state.warning, "disabled overrides forced go");
    }
    {
        const DrivingLane lanes[] = {DrivingLane::Left, DrivingLane::Straight, DrivingLane::Right};
        const char* selectedGreen[] = {"tlga_left_green", "tsga_straight_green", "trga_right_green"};
        const char* selectedRed[] = {"tlra_left_red", "tsra_straight_red", "trra_right_red"};
        for (int lane = 0; lane < 3; ++lane) {
            DrivingDemo demo;
            demo.setEnabled(true);
            demo.setLane(lanes[lane]);
            observe(demo, allLights, {selectedGreen[lane]}, 1000);
            observe(demo, allLights, {selectedGreen[lane]}, 1200);
            c.check(demo.snapshot(1200).moving, "each selected direction can confirm green");
            for (int other = 0; other < 3; ++other) {
                if (other == lane) continue;
                demo.resetPerception();
                observe(demo, allLights, {selectedGreen[other]}, 1300 + other * 300);
                observe(demo, allLights, {selectedGreen[other]}, 1500 + other * 300);
                c.check(!demo.snapshot(1500 + other * 300).moving,
                        "green for either unrelated lane never authorizes selected lane");
            }
            // Reset does not rewind timestamp watermarks.
            demo.resetPerception();
            observe(demo, allLights, {"tuga_uturn_green"}, 2500);
            observe(demo, allLights, {"tuga_uturn_green"}, 2700);
            c.check(!demo.snapshot(2700).moving, "uturn green never authorizes selected lane");
            observe(demo, allLights, {"tlg_motor_green"}, 2900);
            observe(demo, allLights, {"tlg_motor_green"}, 3100);
            c.check(demo.snapshot(3100).moving, "generic motor fallback works for every lane");
            observe(demo, allLights, {selectedRed[lane], "tlg_motor_green"}, 3101);
            c.check(!demo.snapshot(3101).moving && demo.snapshot(3101).signal == DrivingSignal::Red,
                    "selected directional red overrides generic green");
            observe(demo, allLights, {selectedGreen[lane], "tlr_motor_red"}, 3301);
            observe(demo, allLights, {selectedGreen[lane], "tlr_motor_red"}, 3501);
            c.check(demo.snapshot(3501).moving, "selected directional green overrides generic red");
            observe(demo, allLights, {selectedGreen[(lane + 1) % 3]}, 3502);
            c.check(!demo.snapshot(3502).moving, "arriving mismatch clears held green immediately");
        }
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        stableMotor(demo);
        observe(demo, motor, {"tlr_motor_red", "tlg_motor_green"}, 1201);
        auto state = demo.snapshot(1201);
        c.check(state.signal == DrivingSignal::Red && state.conflict && !state.moving,
                "red dominates conflicting red and green");
        observe(demo, motor, {"tly_motor_amber", "tlg_motor_green"}, 1202);
        state = demo.snapshot(1202);
        c.check(state.conflict && !state.moving, "amber and green conflict fails stop");
        observe(demo, allLights, {"tln_lamp_off", "tlg_motor_green"}, 1203);
        c.check(demo.snapshot(1203).conflict && !demo.snapshot(1203).moving,
                "off and green cannot authorize movement");
        observe(demo, allLights, {"tln_lamp_off"}, 1204);
        c.check(demo.snapshot(1204).signal == DrivingSignal::Off && !demo.snapshot(1204).moving,
                "off signal stops auto");
        observe(demo, allLights, {}, 1205);
        c.check(demo.snapshot(1205).signal == DrivingSignal::Unknown && !demo.snapshot(1205).moving,
                "empty current result replaces disappeared green");
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        observe(demo, straight, {"tsra_straight_red"}, 1000);
        stableMotor(demo, 1001);
        c.check(demo.snapshot(1201).signal == DrivingSignal::Red && !demo.snapshot(1201).moving,
                "cached directional red beats newer generic green across models");
        observe(demo, straight, {"tsga_straight_green"}, 1401);
        const QStringList objects = {"person", "vehicle", "zebra"};
        observe(demo, objects, {"person"}, 1601);
        c.check(!demo.snapshot(1601).moving, "object model cannot count as a green sample");
        observe(demo, motor, {"tlg_motor_green"}, 1801);
        c.check(!demo.snapshot(1801).moving, "lower priority generic cannot confirm cached directional green");
        observe(demo, straight, {"tsga_straight_green"}, 1802);
        c.check(demo.snapshot(1802).moving, "directional green survives ordinary model rotation");
        observe(demo, straight, {}, 1803);
        c.check(!demo.snapshot(1803).moving, "missing directional head blocks cached generic green");
        observe(demo, motor, {"tlg_motor_green"}, 1804);
        c.check(!demo.snapshot(1804).moving, "generic refresh cannot override fresh missing directional head");
        observe(demo, motor, {"tlg_motor_green"}, 3004);
        c.check(!demo.snapshot(3004).moving, "expired direction needs new generic confirmation");
        observe(demo, motor, {"tlg_motor_green"}, 3204);
        c.check(demo.snapshot(3204).moving, "generic fallback recovers after directional stale budget");
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        stableMotor(demo);
        c.check(demo.snapshot(2400).moving, "evidence valid at exactly 1200ms age");
        auto state = demo.snapshot(2401);
        c.check(!state.moving && state.stale && state.reason.contains("stale"),
                "source age beyond 1200ms stops and exposes stale reason");
        demo.setMode(DrivingMode::ForcedGo);
        state = demo.snapshot(2401);
        c.check(state.moving && state.warning && !state.alarm && state.reason.contains("stale"),
                "forced go exposes stale source with warning");
        demo.setMode(DrivingMode::Auto);
        observe(demo, motor, {"tlg_motor_green"}, 2402);
        c.check(!demo.snapshot(2402).moving, "stale gap clears confirmation");
        observe(demo, motor, {"tlg_motor_green"}, 2602);
        c.check(demo.snapshot(2602).moving, "stale stream can recover with two new samples");
        demo.resetPerception();
        c.check(!demo.snapshot(2602).moving && demo.snapshot(2602).modelCount == 0,
                "generation reset removes cached signals and green hold");
        c.check(!observe(demo, motor, {"tlg_motor_green"}, 2601, 2602),
                "reset retains timestamp watermark against old replay");
        observe(demo, motor, {"tlg_motor_green"}, 2802);
        c.check(!demo.snapshot(2802).moving, "one post-reset sample cannot reuse old hold");
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        c.check(!observe(demo, motor, {"tlg_motor_green"}, -1, 0), "negative capture rejected");
        c.check(!observe(demo, motor, {"tlg_motor_green"}, 2001, 2000), "future capture rejected");
        c.check(!observe(demo, motor, {"tlg_motor_green"}, 799, 2000), "stale capture rejected");
        c.check(!demo.snapshot(2000).moving, "invalid captures never establish green evidence");
        observe(demo, motor, {"tlg_motor_green"}, 2000);
        c.check(!observe(demo, motor, {"tlg_motor_green"}, 2000, 2200), "duplicate capture rejected");
        c.check(!demo.snapshot(2200).moving, "duplicate with later delivery cannot satisfy hold");
        c.check(!observe(demo, motor, {"tlg_motor_green"}, 1999, 2200), "old capture rejected");
        c.check(!observe(demo, motor, {"tlg_motor_green"}, 2100, 2199), "backward delivery clock rejected");
        observe(demo, motor, {"tlg_motor_green"}, 2200);
        c.check(demo.snapshot(2200).moving, "valid sample recovers after rejected timestamps");
        c.check(!demo.snapshot(2199).moving, "backward snapshot fails stop");
        c.check(!demo.snapshot(2200).moving, "backward query clears green authorization");
        demo.resetPerception();
        observe(demo, motor, {"tlg_motor_green"}, 2300, 3000);
        observe(demo, motor, {"tlg_motor_green"}, 2301, 3200);
        c.check(!demo.snapshot(3200).moving, "delivery delay is not captured green duration");
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        stableMotor(demo);
        demo.setLane(DrivingLane::Left);
        c.check(!demo.snapshot(1200).moving, "lane switch cannot reuse generic green hold");
        stableMotor(demo, 1400);
        c.check(demo.snapshot(1600).moving, "new lane can independently confirm green");
        demo.setLane(DrivingLane::Straight);
        c.check(!demo.snapshot(1600).moving, "switching back cannot restore old lane hold");
        stableMotor(demo, 1800);
        demo.setMode(DrivingMode::Stop);
        c.check(!demo.snapshot(2000).moving, "stop overrides confirmed green");
        demo.setMode(DrivingMode::Auto);
        c.check(!demo.snapshot(2000).moving, "leaving stop requires fresh confirmation");
        stableMotor(demo, 2200);
        demo.setEnabled(false);
        demo.setEnabled(true);
        c.check(!demo.snapshot(2400).moving, "reenabling cannot reuse prior green hold");
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        auto green = detection(motor, "tlg_motor_green", 0.399f);
        demo.observe(motor, {green}, 1000, 1000);
        demo.observe(motor, {green}, 1200, 1200);
        c.check(!demo.snapshot(1200).moving, "scores below confidence threshold ignored");
        green.score = 0.4f;
        demo.observe(motor, {green}, 1400, 1400);
        demo.observe(motor, {green}, 1600, 1600);
        c.check(demo.snapshot(1600).moving, "score exactly at confidence threshold accepted");
        green.predicted = true;
        demo.observe(motor, {green}, 1601, 1601);
        c.check(!demo.snapshot(1601).moving, "tracker prediction cannot keep trafficlight green alive");
        green.predicted = false;
        green.score = std::numeric_limits<float>::quiet_NaN();
        demo.observe(motor, {green}, 1602, 1602);
        c.check(!demo.snapshot(1602).moving, "NaN confidence cannot authorize green");
        green.score = 0.9f;
        green.cls = 100;
        demo.observe(motor, {green}, 1603, 1603);
        c.check(!demo.snapshot(1603).moving, "out-of-range class index ignored");
        const QStringList misleading = {"green", "trafficlight_green", "TLG_MOTOR_GREEN"};
        demo.resetPerception();
        observe(demo, misleading, {"green", "trafficlight_green", "TLG_MOTOR_GREEN"}, 1800);
        observe(demo, misleading, {"green", "trafficlight_green", "TLG_MOTOR_GREEN"}, 2000);
        c.check(!demo.snapshot(2000).moving, "trafficlight raw names matched exactly");
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        const QStringList objects = {"zebra", "vehicle", "person"};
        observe(demo, objects, {"zebra", "person", "vehicle", "person"}, 1000);
        auto state = demo.snapshot(1000);
        c.check(state.personCount == 2 && state.vehicleCount == 1 && state.zebraCount == 1,
                "counts use explicit per-model vocabulary");
        c.check(!state.moving, "objects alone cannot authorize movement");
        state = demo.snapshot(2201);
        c.check(state.personCount == 0 && state.vehicleCount == 0 && state.zebraCount == 0,
                "object counts expire on capture timestamps");
        for (int i = 0; i < 10; ++i) {
            const QStringList classes = {QStringLiteral("model_%1").arg(i), "person"};
            observe(demo, classes, {"person"}, 2300 + i);
            c.check(demo.snapshot(2300 + i).modelCount <= 4, "model cache remains bounded");
        }
        c.check(demo.snapshot(2309).modelCount == 4 && demo.snapshot(2309).personCount == 4,
                "eviction retains only four latest model result sets");
        const QStringList lastClasses = {"model_9", "person"};
        observe(demo, lastClasses, {}, 2310);
        c.check(demo.snapshot(2310).modelCount == 4 && demo.snapshot(2310).personCount == 3,
                "same vocabulary replaces previous model result");
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        const QStringList alternateStraight = {"person", "tsga_straight_green", "tsra_straight_red"};
        observe(demo, straight, {"tsga_straight_green"}, 1000);
        observe(demo, straight, {"tsga_straight_green"}, 1200);
        c.check(demo.snapshot(1200).moving, "directional green initially confirmed");
        observe(demo, alternateStraight, {"tsra_straight_red"}, 1201);
        auto state = demo.snapshot(1201);
        c.check(state.signal == DrivingSignal::Red && state.conflict && !state.moving,
                "directional red in different model immediately vetoes held green");
        observe(demo, straight, {"tsga_straight_green"}, 1401);
        c.check(!demo.snapshot(1401).moving, "refreshing directional green cannot mask cached directional red");
        demo.setMode(DrivingMode::ForcedGo);
        state = demo.snapshot(1401);
        c.check(state.moving && state.alarm && state.conflict, "cross-model red conflict alarms forced go");
        demo.setMode(DrivingMode::Auto);
        observe(demo, alternateStraight, {}, 1402);
        c.check(!demo.snapshot(1402).moving, "disappeared red is unknown rather than permission from old green");
        observe(demo, alternateStraight, {"tsga_straight_green"}, 1602);
        observe(demo, straight, {"tsga_straight_green"}, 1802);
        c.check(demo.snapshot(1802).moving, "agreement across directional models confirms fresh green");
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        stableMotor(demo);
        for (int i = 0; i < 4; ++i) {
            const QStringList classes = {QStringLiteral("object_model_%1").arg(i), "person"};
            observe(demo, classes, {"person"}, 1300 + i);
        }
        c.check(!demo.snapshot(1303).moving, "eviction of only traffic model clears permission");
        c.check(!observe(demo, motor, {"tlg_motor_green"}, 1200, 1303),
                "evicted model cannot replay old capture to regain a cache slot");
        c.check(demo.snapshot(1303).signal == DrivingSignal::Unknown, "replayed evicted green stays unknown");
        observe(demo, motor, {"tlg_motor_green"}, 1503);
        c.check(!demo.snapshot(1503).moving, "reintroduced model requires new green hold");
        observe(demo, motor, {"tlg_motor_green"}, 1703);
        c.check(demo.snapshot(1703).moving, "reintroduced model can confirm with fresh captures");
        c.check(!observe(demo, motor, {"tlr_motor_red"}, 1704, 1703), "future red capture is rejected");
        c.check(demo.snapshot(1703).signal == DrivingSignal::Green, "future result does not replace current evidence");
        c.check(!observe(demo, motor, {"tlg_motor_green"}, 1705, 3000), "stale result rejected after stream gap");
        c.check(!demo.snapshot(3000).moving && demo.snapshot(3000).stale,
                "rejecting stale result still ages and stops previous green");
    }
    {
        DrivingDemoConfig config;
        config.confidenceThreshold = 0.8f;
        config.greenSamples = 3;
        config.greenHoldMs = 300;
        DrivingDemo demo(config);
        demo.setEnabled(true);
        stableMotor(demo);
        c.check(!demo.snapshot(1200).moving, "configured sample and hold requirements respected");
        observe(demo, motor, {"tlg_motor_green"}, 1300);
        c.check(demo.snapshot(1300).moving, "three samples across configured duration authorize go");
        demo.observe(motor, {detection(motor, "tlg_motor_green", 0.79f)}, 1301, 1301);
        c.check(!demo.snapshot(1301).moving, "configured confidence threshold respected");
    }
    {
        DrivingDemo demo;
        demo.setEnabled(true);
        stableMotor(demo, 1000);
        c.check(demo.snapshot(1200).moving, "fresh HDMI begins with confirmed green motion");
        demo.setInputAvailable(false);
        auto state = demo.snapshot(1201);
        c.check(!state.inputAvailable && !state.moving && state.signal == DrivingSignal::Unknown,
                "lost HDMI half clears perception and stops automatic motion");
        demo.setMode(DrivingMode::ForcedGo);
        state = demo.snapshot(1202);
        c.check(!state.moving && !state.alarm, "forced movement cannot bypass missing HDMI input");
        c.check(!observe(demo, motor, {"tlr_motor_red"}, 1300),
                "late inference cannot restore unavailable HDMI input");
        demo.setInputAvailable(true);
        demo.setMode(DrivingMode::Auto);
        observe(demo, motor, {"tlg_motor_green"}, 1400);
        c.check(!demo.snapshot(1400).moving, "recovered HDMI needs fresh green confirmation");
        observe(demo, motor, {"tlg_motor_green"}, 1600);
        c.check(demo.snapshot(1600).moving, "recovered input can resume after confirmation");
        observe(demo, motor, {"tlr_motor_red"}, 1601);
        demo.setMode(DrivingMode::ForcedGo);
        c.check(demo.snapshot(1601).alarm, "forced red still alarms with valid HDMI input");
        demo.setInputAvailable(false);
        c.check(!demo.snapshot(1602).moving && !demo.snapshot(1602).alarm,
                "input loss clears stale red alarm and simulated movement");
    }
    if (c.failures) {
        std::cerr << "DRIVING_DEMO_SELFTEST_FAILED: " << c.failures << '/' << c.total << '\n';
        return 1;
    }
    std::cout << "DRIVING_DEMO_SELFTEST_PASS: " << c.total << " checks\n";
    return 0;
}

#ifdef TDM_DRIVING_DEMO_SELFTEST_MAIN
int main() { return runDrivingDemoSelfTest(); }
#endif
