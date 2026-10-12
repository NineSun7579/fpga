/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef PANGO_POLICY_H
#define PANGO_POLICY_H

/* Pure arithmetic helpers shared with the offline policy harness. */
static inline int pango_range_valid(unsigned long long size,
                                    unsigned long long offset,
                                    unsigned long long length)
{
    return length && offset <= size && length <= size - offset;
}

/* This candidate programs the verified 32-bit DMA address mode (CMD bit16=0).
 * Validate the complete interval, not only the first byte/high register word. */
static inline int pango_dma32_valid(unsigned long long address,
                                   unsigned long long length)
{
    return pango_range_valid(1ULL << 32, address, length);
}

static inline int pango_ranges_overlap(unsigned long long a,
                                       unsigned long long a_len,
                                       unsigned long long b,
                                       unsigned long long b_len)
{
    /* Callers first validate both ranges against bounded allocations. */
    return a < b + b_len && b < a + a_len;
}

static inline int pango_rx_hits_lease(unsigned int mask,
                                     unsigned int offset,
                                     unsigned int length)
{
    unsigned int slot;

    for (slot = 0; slot < 6; ++slot)
        if ((mask & (1U << slot)) &&
            pango_ranges_overlap(offset, length, slot * 0x97000U, 0x96000U))
            return 1;
    return 0;
}

static inline int pango_unmap_busy(unsigned int exports, unsigned int vmas,
                                   unsigned int leases, unsigned int pending, int active,
                                   int quarantined)
{
    return exports || vmas || leases || pending || active || quarantined;
}

#endif
