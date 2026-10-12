/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef PANGO_ZC_UAPI_H
#define PANGO_ZC_UAPI_H
#include <linux/types.h>
#include <linux/ioctl.h>

#define PZ_BUFFER_BYTES 0x400000U
#define PZ_RX_MMAP_OFFSET 0x100000U
#define PZ_INPUT_BYTES 1228800U
/* Suggested reservation; metadata/register scratch remains at RX offset zero. */
#define PZ_INPUT_OFFSET 0x200000U
#define PZ_VERSION 1U

/* Legacy ioctl encodings specify sizeof(int), not sizeof(the argument).
 * Only this fixed 20-byte prefix is consumed; native pointer tails are unused. */
struct pz_dma_op {
    __u32 current_len, offset_addr, cmd, ddr3_addr, total_length;
};
#define PZ_MAP _IOWR(0x53, 2, int)
#define PZ_H2F _IOWR(0x53, 4, int)
#define PZ_F2H _IOWR(0x53, 5, int)
#define PZ_UNMAP _IOWR(0x53, 7, int)

/* All input fields except version must be zero. ioctl RETURNS the new
 * O_RDWR|O_CLOEXEC DMA-BUF fd (>=0), or -1/errno. No output usercopy. */
struct pz_export_rx {
    __u32 version, flags, reserved[2];
};
#define PZ_EXPORT_RX _IOW(0x53, 0x30, struct pz_export_rx)

/* BEGIN: version=1, flags=0, page-aligned offset>=PAGE_SIZE,
 * length=PZ_INPUT_BYTES, token=0, reserved=0. Returns a nonzero token.
 * END: return exactly the BEGIN fields/token after synchronous RKNN completion.
 * No implicit fences: kernel cannot prove the client's END assertion. */
struct pz_lease {
    __u32 version, flags, offset, length;
    __aligned_u64 token;
    __u32 reserved[4];
};
#define PZ_BEGIN _IOWR(0x53, 0x31, struct pz_lease)
#define PZ_END _IOW(0x53, 0x32, struct pz_lease)
#endif
