#pragma once
#include <cstddef>
#include <cstdint>

namespace sixdma {
constexpr uint32_t Allocation = 4u * 1024u * 1024u;
constexpr uint32_t RawSlot = 0;
constexpr uint32_t Metadata = 1024u * 1024u;
constexpr uint32_t SharedInput = 2u * 1024u * 1024u;
constexpr uint32_t SharedInputBytes = 640u * 640u * 3u;
constexpr uint32_t RawBytes = 640u * 480u * 2u;
// Always reserve this region, even before the parent installs shared RKNN.
constexpr bool scratchRange(uint32_t offset, uint32_t length) {
    return length && offset < SharedInput && length <= SharedInput - offset;
}
static_assert(RawSlot + RawBytes + 16 <= Metadata, "RAW/tag scratch must not overlap MMIO");
static_assert(Metadata + 4096 <= SharedInput, "MMIO scratch below input reservation");
static_assert(SharedInput + SharedInputBytes <= Allocation, "RKNN slot fits mapping");
struct BorrowedSession {
    int fd; // borrowed: never close, mmap again or change device ownership
    uint8_t* rx;
    size_t rxBytes;
    uint32_t inputOffset;
    uint32_t inputBytes;
};
// A callback receives BorrowedSession only while PangoDev's DMA mutex is held.
// Never retain RX scratch pointers or call locking PangoDev methods inside it.
// Shared-input token/lifetime and RKNN binding remain the parent's responsibility.
} // namespace sixdma
