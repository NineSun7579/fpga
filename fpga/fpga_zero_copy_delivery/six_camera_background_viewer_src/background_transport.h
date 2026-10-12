#pragma once
#include "background_thumbnail_reader.hpp"
#include "six_dma_layout.h"
#include <cstring>
#include <functional>

namespace background_thumbnail {
constexpr std::uint32_t Base = 0x40020000u;
constexpr std::uint32_t Control = Base + 0x180u;
constexpr std::uint32_t Destinations[6][2] = {
    {0x0a280000,0x0a2c0000},{0x0a300000,0x0a340000},
    {0x0a380000,0x0a3c0000},{0x0a400000,0x0a440000},
    {0x0a200000,0x0a240000},{0x0a480000,0x0a4c0000}};
constexpr std::uint32_t TagDelta = ((kFrameBytes + 255u) / 256u) * 256u;
static_assert(kFrameBytes % 256 == 0 && TagDelta == 153600, "HMIC tag stride");
static_assert(sixdma::scratchRange(sixdma::RawSlot,kTransferBytes), "owned payload scratch");

template<class Op> bool checkedCopy(const Op& op,std::uint32_t address,std::uint32_t offset,
                                   std::size_t count,const std::uint8_t* rx,void* out,std::size_t copy) {
    if (!rx || !out || !copy || copy>count || count>sixdma::SharedInput ||
        !sixdma::scratchRange(offset,std::uint32_t(count)) || op.cmd != 0 ||
        op.ddr3_addr != address || op.offset_addr != offset || op.total_length != count) return false;
    std::memcpy(out,rx+offset,copy); return true;
}

// Callback holds DMA through ioctl, strict op validation and complete owned copy.
// It never holds the endpoint lease or writes any selector/control register.
class Adapter final : public Transport {
public:
    using Read = std::function<bool(std::uint32_t,std::uint32_t,std::size_t,void*)>;
    explicit Adapter(Read read) : read_(std::move(read)) {}
    bool readGuard(unsigned camera,unsigned bank,std::uint32_t& value) override {
        if (!valid(camera,bank)) return false;
        std::array<std::uint32_t,4> half{};
        if (!read_(record(camera,bank),sixdma::Metadata,16,half.data())) return false;
        if (half[1] != camera+1 || half[2] != bank || half[3] != Destinations[camera][bank])
            return false;
        value=half[0]; return true;
    }
    bool readSequence(unsigned camera,unsigned bank,std::uint32_t& value) override {
        if (!valid(camera,bank)) return false;
        std::array<std::uint32_t,4> half{};
        if (!read_(record(camera,bank)+16,sixdma::Metadata,16,half.data())) return false;
        if (half[1] != kFrameBytes || half[2] != (320u | (240u<<16)) ||
            half[3] != Destinations[camera][bank]+TagDelta) return false;
        value=half[0]; return true;
    }
    bool readPayloadOwned(unsigned camera,unsigned bank,OwnedPayload& payload) override {
        if (!valid(camera,bank)) return false;
        std::vector<std::uint8_t> owned(kTransferBytes);
        if (!read_(Destinations[camera][bank],sixdma::RawSlot,kTransferBytes,owned.data())) return false;
        std::memcpy(&payload.tag,owned.data()+kFrameBytes,4);
        owned.resize(kFrameBytes); payload.bytes=std::move(owned);
        payload.transferredBytes=kTransferBytes; payload.contiguousMappingConfirmed=true;
        return true;
    }
    static bool valid(unsigned camera,unsigned bank) { return camera<6 && bank<2; }
    static std::uint32_t record(unsigned camera,unsigned bank) {
        return Base+0x200u+32u*(2u*camera+bank);
    }
private:
    Read read_;
};
int runAdapterSelfTest();
}
