#include "inference_cadence.h"
#include "fpga_infer_input.h"
#include <cassert>
#include <cstdio>
#include <thread>

using tdm::InferenceCadence;

// Virtual clock models a busy acquisition thread, conversion readiness and
// synchronous worker completion. It uses the production cadence decisions and
// production single-slot Admission; it does not model Qt or board latency.
static void clockFixture(int acquisitionDelay, bool prefetch) {
    scheme2::Admission gate;
    gate.publish({480, "raw", 1});
    int64_t last = -1, readyAt = -1, finishedAt = -1;
    int submitted = 0, conversions = 0;
    bool pending = false, ready = false;
    for (int64_t now = 0; now <= 2000; ++now) {
        if (pending && now == finishedAt) {
            pending = false;
            gate.retire(scheme2::Selection{480, "raw", 1});
        }
        if (!pending && (prefetch ? InferenceCadence::mayArm(now, last, 250, false) :
                                    InferenceCadence::due(now, last, 250, false))) {
            gate.arm(2, 7);
            if (gate.claim(2, 7)) {
                assert(!ready && readyAt < 0);
                readyAt = now + acquisitionDelay;
                ++conversions;
            }
        }
        if (now == readyAt) { ready = true; readyAt = -1; }
        if (!pending && ready && InferenceCadence::due(now, last, 250, false)) {
            if (last >= 0) {
                assert(now - last >= 250);
                assert(now - last == (prefetch ? 250 : 250 + acquisitionDelay));
            }
            last = now; // same submission clock as original, never capture time
            pending = true; ready = false; finishedAt = now + 45; ++submitted;
        }
    }
    assert(conversions >= submitted && conversions <= submitted + 1);
    assert(submitted == (2000 - acquisitionDelay) / (250 + (prefetch ? 0 : acquisitionDelay)) + 1);
}

int main() {
    for (int delay : {40, 60, 100, 120}) {
        clockFixture(delay, false);
        clockFixture(delay, true);
    }
    assert(!InferenceCadence::mayArm(1129, 1000, 250, false));
    assert(InferenceCadence::mayArm(1130, 1000, 250, false));
    assert(!InferenceCadence::due(1249, 1000, 250, false));
    assert(InferenceCadence::due(1250, 1000, 250, false));
    assert(!InferenceCadence::due(1099, 1000, 100, false)); // urgent still bounded
    assert(InferenceCadence::due(1100, 1000, 100, false));
    assert(InferenceCadence::due(1001, 1000, 250, true)); // lane/no tracking

    // Source switches disarm an unclaimed preparation. Occupied old input
    // prevents a new claim until it retires, even across model publication.
    auto& gate = scheme2::admission();
    gate.publish({480, "unclaimed-old", 9}); gate.arm(2, 7);
    gate.publish({480, "raw-old", 10}); assert(!gate.claim(2, 7));
    gate.publish({480, "raw-old", 10}); gate.arm(2, 7);
    assert(!gate.claim(3, 7) && !gate.claim(2, 8));
    gate.disarm(); assert(!gate.claim(2, 7));
    gate.arm(3, 8); auto selected = gate.claim(3, 8); assert(selected);
    int begins = 0, ends = 0;
    auto backing = std::make_shared<int>(123);
    std::weak_ptr<int> lifetime = backing;
    auto queued = std::make_shared<scheme2::Input>();
    queued->selection = selected; queued->backing = backing;
    queued->begin = [&] { ++begins; }; queued->end = [&] { ++ends; };
    backing.reset();
    gate.publish({640, "raw-new", 11});
    gate.arm(3, 8); assert(!gate.claim(3, 8));
    queued->nextSelection = scheme2::Selection{480, "stale", 10};
    queued.reset(); // never consumed: no BEGIN/END and stale rotation ignored
    assert(lifetime.expired() && begins == 0 && ends == 0);
    gate.arm(3, 8); selected = gate.claim(3, 8);
    assert(selected.model == "raw-new" && selected.revision == 11 && selected.height == 640);
    queued = std::make_shared<scheme2::Input>();
    queued->begin = [&] { ++begins; }; queued->end = [&] { ++ends; };
    queued->backing = std::make_shared<int>(456); lifetime = std::static_pointer_cast<int>(queued->backing);
    auto importBacking = queued->backing;
    queued->consume(); queued->start();
    std::thread a([&] { queued->complete(); });
    std::thread b([&] { queued->complete(); }); a.join(); b.join();
    assert(begins == 1 && ends == 1);
    queued.reset(); assert(!lifetime.expired());
    importBacking.reset(); assert(lifetime.expired());
    std::puts("PREFETCH_CLOCK_SWITCH_LIFETIME_PASS (host fixtures only)");
}
