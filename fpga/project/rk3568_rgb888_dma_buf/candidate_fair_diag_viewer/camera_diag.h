#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace camera_diag {
inline bool envOne(const char* name) {
    const char* value = std::getenv(name);
    return value && std::strcmp(value, "1") == 0;
}
// Copied integrated_six_batch RTL: physical DVP cameras only. SFP 5/6
// have no ov5640_reg page, and must never be read through guessed addresses.
constexpr uint32_t bases[4] = {0x20000000u, 0x20000200u, 0x20000400u, 0x20000600u};
constexpr uint32_t offsets[9] = {0x00, 0x20, 0x30, 0xa0, 0xf0, 0x190, 0x1a0, 0x1b0, 0x1c0};
inline uint32_t delta32(uint32_t now, uint32_t before) { return now - before; }
inline unsigned delta16(unsigned now, unsigned before) { return (now - before) & 0xffffu; }
struct Fault {
    unsigned overflow, shortFrame, abort, tagPhase;
    uint32_t accepted;
    explicit Fault(uint32_t value) : overflow(value >> 31), shortFrame((value >> 30) & 1),
        abort((value >> 29) & 1), tagPhase((value >> 28) & 1), accepted(value & 0x0fffffffu) {}
};
struct State {
    const bool enabled;
    const bool cam2Only;
    int64_t nextMs, intervalMs;
    uint64_t noNew = 0, unstable = 0, failed = 0, delivered = 0;
    bool havePrevious = false;
    uint32_t previous[9] = {};
    State(bool on, bool only, int cameraIndex, int64_t now)
        : enabled(on), cam2Only(only), nextMs(now + 5000 + cameraIndex * 200), intervalMs(now) {}
    void result(int code) {
        if (!enabled) return;
        if (code == 0) ++noNew;
        else if (code == 2) ++unstable;
        else if (code < 0) ++failed;
        else if (code == 1) ++delivered;
    }
    // Called at the top of every worker loop, before pause/mode/result continues.
    // Reader is the existing owner PangoDev helper; disabled means zero reads.
    template<class Reader>
    bool tick(int cameraIndex, int64_t now, bool paused, bool disabled, Reader read,
              FILE* out = stderr) {
        if (!enabled || now < nextMs) return false;
        nextMs = now + 5000; // no catch-up bursts after a slow DMA
        const bool registers = cameraIndex >= 0 && cameraIndex < 4 && (!cam2Only || cameraIndex == 1);
        uint32_t values[9] = {};
        if (registers) read(cameraIndex, values); // quarantine before logging any partial sample
        fprintf(out, "[camera-diag] camera=%d interval_ms=%lld paused=%d disabled=%d result0=%llu result2=%llu result_negative=%llu result1=%llu",
            cameraIndex + 1, static_cast<long long>(now - intervalMs), int(paused), int(disabled),
            (unsigned long long)noNew, (unsigned long long)unstable,
            (unsigned long long)failed, (unsigned long long)delivered);
        if (registers) {
            const Fault fault(values[0]);
            // Offered and CDC source/output/drop are previous-frame gauges;
            // only SOF, reject totals, publication and sequence are counters.
            fprintf(out, " regs=sampled delta_valid=%d fault=0x%08x overflow=%u short=%u abort=%u tag_phase=%u accepted_pixels=%u sof=%u sof_delta=%u offered_pixels=%u overflow_count=%u short_count=%u overflow_delta=%u short_delta=%u good_publication=%u good_delta=%u cdc_source=%u cdc_out=%u cdc_dropped=%u cdc_seq=%u seq_delta=%u",
                int(havePrevious), values[0], fault.overflow, fault.shortFrame, fault.abort, fault.tagPhase, fault.accepted,
                values[1], havePrevious ? delta32(values[1], previous[1]) : 0, values[2],
                values[3] >> 16, values[3] & 0xffffu,
                havePrevious ? delta16(values[3] >> 16, previous[3] >> 16) : 0,
                havePrevious ? delta16(values[3] & 0xffffu, previous[3] & 0xffffu) : 0,
                values[4], havePrevious ? delta32(values[4], previous[4]) : 0,
                values[5], values[6], values[7],
                values[8], havePrevious ? delta32(values[8], previous[8]) : 0);
            std::memcpy(previous, values, sizeof(values));
            havePrevious = true;
        } else fprintf(out, " regs=%s", cameraIndex >= 4 ? "unsupported_sfp_map" : "cam2_only");
        fprintf(out, "\n");
        fflush(out);
        noNew = unstable = failed = delivered = 0;
        intervalMs = now;
        return true;
    }
};
} // namespace camera_diag
