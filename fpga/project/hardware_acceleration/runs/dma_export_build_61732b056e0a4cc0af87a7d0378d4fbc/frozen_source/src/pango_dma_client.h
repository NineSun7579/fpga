/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef PANGO_DMA_CLIENT_H
#define PANGO_DMA_CLIENT_H

/* POSIX userspace helpers only; they submit no RGA work and perform no DMA. */
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include "pango_dma_uapi.h"

static inline int pango_client_zero(const __u32 *p, unsigned int count)
{
    unsigned int i;

    for (i = 0; i < count; ++i)
        if (p[i])
            return 0;
    return 1;
}

/* Returns zero with a fully checked result, or -1 with errno. */
static inline int pango_export_checked(int device_fd, unsigned int slot,
                                      struct pango_export_slot_v1 *result)
{
    struct pango_export_slot_v1 req;
    int ret, fd_flags;

    if (!result || slot >= PANGO_SLOT_COUNT) {
        errno = EINVAL;
        return -1;
    }
    memset(result, 0, sizeof(*result));
    result->fd = -1;
    memset(&req, 0, sizeof(req));
    req.version = PANGO_DMA_ABI_V1;
    req.slot = slot;
    req.fd = -1;
    ret = ioctl(device_fd, PANGO_EXPORT_SLOT_V1, &req);
    if (ret < 0)
        return -1;
    if (ret || req.version != PANGO_DMA_ABI_V1 || req.slot != slot || req.flags ||
        req.fd < 0 || req.offset != slot * PANGO_SLOT_STRIDE ||
        req.length != PANGO_SLOT_BYTES || !req.generation ||
        !pango_client_zero(req.reserved, 4)) {
        if (req.fd >= 0)
            close(req.fd);
        errno = EPROTO;
        return -1;
    }
    fd_flags = fcntl(req.fd, F_GETFD);
    if (fd_flags < 0 || !(fd_flags & FD_CLOEXEC)) {
        close(req.fd);
        errno = EPROTO;
        return -1;
    }
    *result = req;
    return 0;
}

static inline int pango_lease_begin_checked(int device_fd,
                                           const struct pango_export_slot_v1 *slot,
                                           struct pango_slot_lease_v1 *lease)
{
    struct pango_slot_lease_v1 req;
    int ret;

    if (!slot || !lease || slot->slot >= PANGO_SLOT_COUNT || !slot->generation) {
        errno = EINVAL;
        return -1;
    }
    memset(lease, 0, sizeof(*lease));
    memset(&req, 0, sizeof(req));
    req.version = PANGO_DMA_ABI_V1;
    req.slot = slot->slot;
    req.generation = slot->generation;
    ret = ioctl(device_fd, PANGO_SLOT_BEGIN_V1, &req);
    if (ret < 0)
        return -1;
    if (ret || req.version != PANGO_DMA_ABI_V1 || req.slot != slot->slot ||
        req.generation != slot->generation || !req.token || req.flags ||
        !pango_client_zero(req.reserved, 5)) {
        errno = EPROTO;
        return -1; /* stop work; never submit RGA on an unchecked response */
    }
    *lease = req;
    return 0;
}

/* Call ONLY after successful blocking RGA completion or a verified never-
 * submitted request. On ambiguous RGA errors keep the lease and stop work. */
static inline int pango_lease_end_checked(int device_fd,
                                         struct pango_slot_lease_v1 *lease)
{
    int ret;

    if (!lease || lease->version != PANGO_DMA_ABI_V1 ||
        lease->slot >= PANGO_SLOT_COUNT || !lease->generation || !lease->token ||
        lease->flags || !pango_client_zero(lease->reserved, 5)) {
        errno = EINVAL;
        return -1;
    }
    ret = ioctl(device_fd, PANGO_SLOT_END_V1, lease);
    if (ret < 0)
        return -1;
    if (ret) {
        errno = EPROTO;
        return -1;
    }
    memset(lease, 0, sizeof(*lease));
    return 0;
}

#endif
