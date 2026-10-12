#pragma once
#include "../capture_host/capture_host_protocol.hpp"
#include "../raw_preprocess/raw_input_reference.h"
#include <algorithm>

// Certification utility only: no transport, release, reset or inference effects.
// Run outside timing, or explicitly include its cost in both measured profiles.
namespace paired_input {
enum class Error { None, Identity, Bytes };
struct Check { Error error=Error::Identity; std::size_t mismatch_offset=0; };
inline Check certify(const capture_host::OwnedRawFrame& raw,
                     const coop_host::OwnedFrame& prepared,
                     std::uint32_t expected_generation) {
    const auto& r=raw.descriptor;
    const auto& p=prepared.descriptor;
    if (!expected_generation || r.generation!=expected_generation || !r.sequence || !r.token ||
        r.camera!=4 || r.bank>1 || p.bank>1 ||
        r.address!=(r.bank ? 0x01a00000u : 0x01800000u) ||
        p.address!=(p.bank ? 0x08200000u : 0x08000000u) ||
        !capture_host::same_source(raw,prepared)) return {Error::Identity,0};
    const auto software=fpga_v8_raw::prepare(raw.bytes.data(),raw.bytes.size());
    const auto different=std::mismatch(software.begin(),software.end(),prepared.bytes.begin());
    if (different.first!=software.end())
        return {Error::Bytes,static_cast<std::size_t>(different.first-software.begin())};
    return {Error::None,0};
}
}
