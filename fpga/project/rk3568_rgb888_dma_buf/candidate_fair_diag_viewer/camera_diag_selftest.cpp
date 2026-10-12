#include "camera_diag.h"
#include <cassert>
#include <string>

static std::string contents(FILE* file) {
    fflush(file); rewind(file);
    std::string result; char buffer[4096];
    while (fgets(buffer, sizeof(buffer), file)) result += buffer;
    return result;
}
int main() {
    using namespace camera_diag;
    FILE* log = tmpfile(); assert(log);
    unsigned calls = 0;
    auto reader = [&](int camera, uint32_t (&v)[9]) {
        assert(camera == 1); ++calls;
        v[0] = 0xf1234567u;
        v[1] = calls == 1 ? 0xfffffffeu : 3;
        v[2] = 307200; // offered pixels is a per-frame gauge, not a counter
        v[3] = calls == 1 ? 0xfffeffffu : 0x00030002u;
        for (unsigned i = 4; i < 9; ++i) v[i] = calls == 1 ? 0xffffffffu : 2;
    };
    State off(false, true, 1, 0);
    off.result(0); off.result(2); off.result(-1);
    assert(!off.tick(1, 999999, false, false, reader, log));
    assert(calls == 0 && off.noNew == 0 && off.unstable == 0 && off.failed == 0);
    State enabled(true, true, 1, 0);
    enabled.result(0); enabled.result(0); enabled.result(2); enabled.result(-1); enabled.result(1);
    assert(!enabled.tick(1, 5199, false, false, reader, log));
    assert(enabled.tick(1, 5200, true, true, reader, log));
    assert(calls == 1 && enabled.noNew == 0);
    enabled.result(0);
    assert(!enabled.tick(1, 10199, false, false, reader, log));
    assert(enabled.tick(1, 10200, false, false, reader, log));
    assert(calls == 2);
    const std::string text = contents(log);
    assert(text.find("camera=2 interval_ms=5200 paused=1 disabled=1 result0=2 result2=1 result_negative=1 result1=1") != std::string::npos);
    assert(text.find("overflow=1 short=1 abort=1 tag_phase=1 accepted_pixels=19088743") != std::string::npos);
    assert(text.find("sof_delta=5 offered_pixels=307200") != std::string::npos);
    assert(text.find("overflow_delta=5 short_delta=3") != std::string::npos);
    assert(text.find("good_delta=3") != std::string::npos);
    assert(text.find("cdc_source=2 cdc_out=2 cdc_dropped=2") != std::string::npos);
    assert(text.find("source_delta=") == std::string::npos);
    assert(text.find("out_delta=") == std::string::npos);
    assert(text.find("dropped_delta=") == std::string::npos);
    assert(text.find("seq_delta=3") != std::string::npos);
    assert(delta32(0, 0xffffffffu) == 1 && delta16(0, 65535) == 1);
    const Fault zero(0); assert(zero.accepted == 0 && zero.overflow == 0);
    for (int cam = 0; cam < 6; ++cam) {
        State s(true, true, cam, 0);
        const auto due = 5000 + cam * 200;
        assert(!s.tick(cam, due - 1, false, false, reader, log));
        assert(s.tick(cam, due, false, true, reader, log));
    }
    assert(calls == 3); // six workers, only camera 2 has nine register reads
    unsigned allReads = 0;
    auto all = [&](int cam, uint32_t (&v)[9]) {
        assert(cam < 4); ++allReads;
        for (unsigned i = 0; i < 9; ++i) {
            const uint32_t address = bases[cam] + offsets[i];
            assert((address & 15) == 0); v[i] = address;
        }
    };
    for (int cam = 0; cam < 6; ++cam) {
        State s(true, false, cam, 0);
        assert(s.tick(cam, 10000, false, false, all, log));
        assert(!s.tick(cam, 10001, false, false, all, log));
    }
    assert(allReads == 4 && bases[1] == 0x20000200u);
    fclose(log);
    puts("CAMERA_DIAG_SELFTEST_PASS zero-off-IO cadence six-workers wrap parse map");
}
