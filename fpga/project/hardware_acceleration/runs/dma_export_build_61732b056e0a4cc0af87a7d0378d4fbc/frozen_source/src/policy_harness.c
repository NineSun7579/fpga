/* SPDX-License-Identifier: GPL-2.0-only */
/* Freestanding host test: no kernel headers, CRT, device, or module load. */
#include "pango_policy.h"
#define CHECK(expr) do { if (!(expr)) return __LINE__; } while (0)

int main(void)
{
    unsigned int slot;

    CHECK(pango_range_valid(0x400000, 0, 0x400000));
    CHECK(!pango_range_valid(0x400000, 0, 0));
    CHECK(!pango_range_valid(0x400000, 0x400000, 4));
    CHECK(!pango_range_valid(0x400000, ~0ULL, 1));
    CHECK(!pango_range_valid(~0ULL, ~0ULL - 1, 4));
    CHECK(pango_range_valid(~0ULL, ~0ULL - 1, 1));
    CHECK(pango_dma32_valid(0, 0x400000));
    CHECK(pango_dma32_valid(0xffffffffULL, 1));
    CHECK(pango_dma32_valid(0xfffff000ULL, 4096));
    CHECK(!pango_dma32_valid(0xfffff000ULL, 4100));
    CHECK(!pango_dma32_valid(0x100000000ULL, 1));
    CHECK(!pango_dma32_valid(~0ULL, 4));
    CHECK(!pango_dma32_valid(0, 0));
    for (slot = 0; slot < 6; ++slot) {
        unsigned int bit = 1U << slot;
        unsigned int start = slot * 0x97000U;

        CHECK(pango_rx_hits_lease(bit, start, 0x96000));
        CHECK(pango_rx_hits_lease(bit, start, 4));
        CHECK(pango_rx_hits_lease(bit, start + 0x96000 - 4, 8));
        CHECK(!pango_rx_hits_lease(bit, start + 0x96000, 16));
        CHECK(!pango_rx_hits_lease(bit, 0x3ff000, 16));
        if (slot)
            CHECK(!pango_rx_hits_lease(bit, start - 4, 4));
        if (slot < 5)
            CHECK(!pango_rx_hits_lease(bit, start + 0x97000, 0x96000));
    }
    CHECK(pango_rx_hits_lease(0x3f, 0, 0x400000));
    CHECK(!pango_rx_hits_lease(0, 0, 0x400000));
    CHECK(!pango_unmap_busy(0, 0, 0, 0, 0, 0));
    CHECK(pango_unmap_busy(1, 0, 0, 0, 0, 0));
    CHECK(pango_unmap_busy(0, 1, 0, 0, 0, 0));
    CHECK(pango_unmap_busy(0, 0, 1, 0, 0, 0));
    CHECK(pango_unmap_busy(0, 0, 0, 1, 0, 0));
    CHECK(pango_unmap_busy(0, 0, 0, 0, 1, 0));
    CHECK(pango_unmap_busy(0, 0, 0, 0, 0, 1));
    return 0;
}
