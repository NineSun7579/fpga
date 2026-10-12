/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef PANGO_DMA_UAPI_H
#define PANGO_DMA_UAPI_H

#include <linux/types.h>
#include <linux/ioctl.h>

/* Legacy command encoding is sizeof(int), NOT sizeof(the argument). */
#define PCI_MAP_ADDR_CMD       _IOWR('S', 2, int)
#define PCI_DMA_READ_CMD       _IOWR('S', 4, int) /* host TX -> FPGA */
#define PCI_DMA_WRITE_CMD      _IOWR('S', 5, int) /* FPGA -> host RX */
#define PCI_UMAP_ADDR_CMD      _IOWR('S', 7, int)
#define RX_MMAP_OFFSET         0x100000UL

typedef struct {
    void *read_buf;
    void *write_buf;
} DMA_DATA;

typedef struct {
    unsigned int current_len;
    unsigned int offset_addr;
    unsigned int cmd;
    unsigned int ddr3_addr;
    unsigned int total_length;
    DMA_DATA data;
} DMA_OPERATION;

#define PANGO_DMA_ABI_V1       1U
#define PANGO_RX_BYTES         0x400000U
#define PANGO_SLOT_COUNT       6U
#define PANGO_SLOT_STRIDE      0x97000U
#define PANGO_SLOT_BYTES       0x96000U

/* All fields must be initialized by the caller; no implicit capability probe. */
struct pango_export_slot_v1 {
    __u32 version;            /* in: 1 */
    __u32 slot;               /* in: 0..5 */
    __u32 flags;              /* in: 0 */
    __s32 fd;                 /* in: -1; out: CLOEXEC dma-buf FD */
    __u32 offset;             /* in: 0; out: slot * stride */
    __u32 length;             /* in: 0; out: pixel bytes only */
    __aligned_u64 generation; /* in: 0; out: allocation-session ID */
    __u32 reserved[4];        /* in/out: zero */
};

struct pango_slot_lease_v1 {
    __u32 version;            /* in: 1 */
    __u32 slot;               /* in: 0..5 */
    __aligned_u64 generation; /* in: export result */
    __aligned_u64 token;      /* BEGIN in: 0, out: nonzero; END in: same */
    __u32 flags;              /* in/out: 0 */
    __u32 reserved[5];        /* in/out: zero */
};

#define PANGO_EXPORT_SLOT_V1  _IOWR('S', 32, struct pango_export_slot_v1)
#define PANGO_SLOT_BEGIN_V1   _IOWR('S', 33, struct pango_slot_lease_v1)
#define PANGO_SLOT_END_V1     _IOW('S', 34, struct pango_slot_lease_v1)

#endif
