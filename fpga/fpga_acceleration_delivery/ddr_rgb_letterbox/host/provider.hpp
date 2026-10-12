#pragma once
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace delivery {
struct Lease {
    std::uint32_t generation, sequence, camera, source_ddr;
};
// Implement against the coordinated board's actual driver ownership protocol.
// There is deliberately no synthetic or software provider implementation.
class Provider {
public:
    virtual ~Provider() = default;
    // Actual MMIO signature; a bitstream file hash alone cannot prove programming.
    virtual std::uint32_t rtl_signature() const = 0;
    // Claim a completed camera frame; hold it immutable until release.
    virtual Lease claim() = 0;
    // Copy EXACTLY 640*480*2 RGB565 bytes, little-endian, no in-band metadata.
    virtual std::vector<std::uint8_t> read_raw(const Lease&) = 0;
    // Submit source DDR address to delivery_rgb_ddr, wait for successful final
    // B completion, DMA EXACTLY 640*640*3 bytes, then return owned CPU bytes.
    // Never upload raw pixels via H2F or return CPU-generated RGB.
    virtual std::vector<std::uint8_t> preprocess_and_read_rgb(const Lease&) = 0;
    // Consume ownership before attempting release; failures must not retry.
    virtual void release(const Lease&) = 0;
    // Faults/uncertain DMA completion quarantine the session and held buffers.
    // No automatic reset, DMA replay, or ownership release on this path.
    virtual void quarantine() noexcept = 0;
    virtual void finish() = 0;
};
std::unique_ptr<Provider> bind_provider();
}
