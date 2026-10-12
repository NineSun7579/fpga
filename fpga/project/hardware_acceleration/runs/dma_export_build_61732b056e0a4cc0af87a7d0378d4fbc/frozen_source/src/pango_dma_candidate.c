// SPDX-License-Identifier: GPL-2.0-only
/* Independent offline candidate; see README.md for proof gates and limits. */
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/pci.h>
#include <linux/io.h>
#include <linux/jiffies.h>
#include <linux/cdev.h>
#include <linux/fs.h>
#include <linux/device.h>
#include <linux/file.h>
#include <linux/fdtable.h>
#include <linux/uaccess.h>
#include <linux/compat.h>
#include <linux/mm.h>
#include <linux/slab.h>
#include <linux/kref.h>
#include <linux/mutex.h>
#include <linux/completion.h>
#include <linux/interrupt.h>
#include <linux/dma-buf.h>
#include <linux/dma-mapping.h>
#include <linux/scatterlist.h>
#include <linux/overflow.h>
#include "pango_dma_uapi.h"
#include "pango_policy.h"

/* The retained source supplies no verified abort/drain or RGA completion ABI.
 * A later audited source revision must change this gate. No runtime override. */
#define PANGO_EXPORT_PROVEN 0
#define PANGO_NAME "pango_pci_driver"
#define PANGO_BAR 1
#define PANGO_CMD 0x100
#define PANGO_ADDR_LO 0x110
#define PANGO_ADDR_HI 0x120
#define PANGO_DDR 0x1e0
#define PANGO_TOTAL 0x200
#define PANGO_MAX_TLP 4096U
#define PANGO_DMA_TIMEOUT_MS 120U

static unsigned int vendor_id;
static unsigned int device_id;
module_param(vendor_id, uint, 0444);
module_param(device_id, uint, 0444);
MODULE_PARM_DESC(vendor_id, "Explicit independently verified PCI vendor ID");
MODULE_PARM_DESC(device_id, "Explicit independently verified PCI device ID");

struct pango_buffer {
    void *cpu;
    dma_addr_t dma;
    size_t size;
    struct sg_table pages;
    bool pages_valid;
};

struct pango_generation {
    struct kref refs;
    struct device *alloc_dev; /* actual allocator; get_device, not devm */
    u64 id;
    struct pango_buffer tx;
    struct pango_buffer rx;
    unsigned int exports;
    unsigned int vmas;
    unsigned int lease_mask;
    unsigned int export_pending; /* slot reservations, includes output delivery */
    unsigned int begin_pending;  /* lease reservations awaiting copyout/commit */
    u64 lease[PANGO_SLOT_COUNT];
    struct pango_view *view[PANGO_SLOT_COUNT];
    bool owned;
    bool quarantined;
};

struct pango_attachment {
    struct device *dev;
    unsigned int maps;
};

struct pango_mapping {
    struct sg_table sgt;
    struct list_head node;
    struct pango_attachment *attachment;
    enum dma_data_direction dir;
};

struct pango_view {
    struct pango_generation *gen;
    unsigned int slot;
    struct list_head mappings;
    bool published;
};

union pango_ioctl_request {
    DMA_OPERATION op;
    struct pango_export_slot_v1 export;
    struct pango_slot_lease_v1 lease;
};

/* One board and one open file description. lock covers ALL process paths.
 * IRQs only update active/completion; they never touch buffers or program DMA.
 * mmap/VMA callbacks enter with mmap_lock held, so usercopy NEVER holds lock.
 * dma_buf_export/put also run unlocked (core registry/reservation lock order). */
static struct {
    struct mutex lock;
    struct pci_dev *pdev; /* binding owns a separate device reference */
    void __iomem *bar;
    struct pango_generation *gen; /* cleared only by final gen_put */
    bool dead;
    bool faulted;
    bool owner;
    u64 next_generation;
    u64 next_token;
    atomic_t active;
    struct completion done;
    dev_t devt;
    struct cdev cdev;
    struct class *class;
    struct device *node;
} pango;

static void pango_free_buffer(struct pango_generation *g,
                              struct pango_buffer *b)
{
    if (b->pages_valid)
        sg_free_table(&b->pages); /* original table, orig_nents unchanged */
    if (b->cpu)
        dma_free_coherent(g->alloc_dev, b->size, b->cpu, b->dma);
    memset(b, 0, sizeof(*b));
}

/* Every get/put of this kref runs under pango.lock, including VMA callbacks. */
static void pango_generation_release(struct kref *ref)
{
    struct pango_generation *g = container_of(ref, struct pango_generation, refs);

    lockdep_assert_held(&pango.lock);
    WARN_ON(g->owned || g->exports || g->vmas || g->lease_mask ||
            g->export_pending || g->begin_pending || g->quarantined);
    pango_free_buffer(g, &g->tx);
    pango_free_buffer(g, &g->rx);
    WARN_ON(pango.gen != g);
    pango.gen = NULL;
    put_device(g->alloc_dev);
    kfree(g);
    module_put(THIS_MODULE); /* allocation generation's independent pin */
}

static void pango_gen_put(struct pango_generation *g)
{
    kref_put(&g->refs, pango_generation_release);
}

/* BME clear and Transactions Pending are containment, NOT a posted-write
 * drain proof. A fault/removal retains one permanent reference and blocks
 * reopen. This deliberate leak is safer than reuse/free of uncertain DMA. */
static void pango_quarantine(struct pango_generation *g)
{
    lockdep_assert_held(&pango.lock);
    pango.faulted = true;
    if (!g->quarantined) {
        g->quarantined = true;
        kref_get(&g->refs);
        pr_err(PANGO_NAME ": DMA generation quarantined; reboot required\n");
    }
    if (pango.pdev) {
        pci_clear_master(pango.pdev);
        /* Return value cannot prove host-bound posted writes have drained. */
        pci_wait_for_pending_transaction(pango.pdev);
    }
}

static int pango_live(struct pango_generation *g)
{
    if (READ_ONCE(pango.dead) || !pango.pdev)
        return -ENODEV;
    if (pango.faulted || g->quarantined)
        return -EIO;
    if (!g->owned || pango.gen != g)
        return -EBADF;
    return 0;
}

static int pango_map_legacy(struct pango_generation *g, const DMA_OPERATION *op)
{
    struct pango_buffer *b;
    size_t size;

    if (op->cmd > 1 || !op->total_length || op->total_length > PANGO_RX_BYTES)
        return -EINVAL;
    b = op->cmd ? &g->rx : &g->tx;
    if (b->cpu)
        return -EBUSY;
    if (atomic_read(&pango.active) || g->export_pending || g->begin_pending)
        return -EBUSY;
    size = PAGE_ALIGN((size_t)op->total_length);
    b->cpu = dma_alloc_coherent(g->alloc_dev, size, &b->dma, GFP_KERNEL);
    if (!b->cpu)
        return -ENOMEM;
    b->size = size;
    if (!pango_dma32_valid((u64)b->dma, size)) {
        pango_free_buffer(g, b);
        return -EOVERFLOW;
    }
    memset(b->cpu, 0, size);
    /* SG extraction is deferred until export; legacy MAP still works if the
     * platform cannot expose allocation pages through dma_get_sgtable. */
    return 0;
}

static int pango_unmap_legacy(struct pango_generation *g, unsigned int which)
{
    if (which != 0 && which != 1 && which != 3)
        return -EINVAL;
    if (pango_unmap_busy(g->exports, g->vmas, g->lease_mask,
                         g->export_pending | g->begin_pending,
                         atomic_read(&pango.active), g->quarantined))
        return -EBUSY;
    if (which == 0 || which == 3)
        pango_free_buffer(g, &g->tx);
    if (which == 1 || which == 3)
        pango_free_buffer(g, &g->rx);
    return 0;
}

static irqreturn_t pango_dma_irq(int irq, void *dev_id)
{
    if (atomic_xchg(&pango.active, 0))
        complete(&pango.done);
    return IRQ_HANDLED;
}

static irqreturn_t pango_event_irq(int irq, void *dev_id)
{
    /* Deliberately no read_img/read_npu IRQ-launched host writes. */
    return IRQ_HANDLED;
}

static int pango_transfer(struct pango_generation *g, const DMA_OPERATION *op,
                          bool rx)
{
    struct pango_buffer *b = rx ? &g->rx : &g->tx;
    dma_addr_t addr;
    unsigned int cmd_word;
    long waited;

    if (!b->cpu)
        return -ENXIO;
    if (g->export_pending || g->begin_pending)
        return -EBUSY;
    if (!pango_range_valid(b->size, op->offset_addr, op->total_length) ||
        ((op->offset_addr | op->total_length | op->ddr3_addr) & 3) ||
        (u64)op->ddr3_addr + op->total_length > (1ULL << 32))
        return -EINVAL;
    if (rx && pango_rx_hits_lease(g->lease_mask, op->offset_addr, op->total_length))
        return -EBUSY;
    if (check_add_overflow(b->dma, (dma_addr_t)op->offset_addr, &addr))
        return -EOVERFLOW;
    /* Both H2F/F2H use the fixed 32-bit mode; reject any boundary crossing. */
    if (!pango_dma32_valid((u64)addr, op->total_length))
        return -EOVERFLOW;
    if (atomic_read(&pango.active))
        return -EBUSY;
    synchronize_irq(pci_irq_vector(pango.pdev, 0));
    reinit_completion(&pango.done);
    atomic_set(&pango.active, 1);
    /* Preserve the frozen source's 10-bit DW command encoding, including
     * 4096 / 4 truncating to zero in the 10-bit field. Do not invent RTL. */
    cmd_word = (min(op->total_length, PANGO_MAX_TLP) / 4) & 0x3ff;
    if (rx)
        cmd_word |= 1U << 24;
    dma_wmb();
    iowrite32(op->ddr3_addr, pango.bar + PANGO_DDR);
    iowrite32(lower_32_bits(addr), pango.bar + PANGO_ADDR_LO);
    /* CMD bit16 stays zero. Never invent 64-bit mode without RTL proof. */
    iowrite32(0, pango.bar + PANGO_ADDR_HI);
    iowrite32(op->total_length, pango.bar + PANGO_TOTAL);
    iowrite32(cmd_word, pango.bar + PANGO_CMD);
    /* Mutex stays held until completion or quarantine: BEGIN cannot race a
     * live F2H. A signal is not an abort, and a timeout is not completion. */
    waited = wait_for_completion_interruptible_timeout(&pango.done,
                                msecs_to_jiffies(PANGO_DMA_TIMEOUT_MS));
    if (READ_ONCE(pango.dead)) {
        pango_quarantine(g);
        return -ENODEV;
    }
    if (waited <= 0) {
        /* Even if MSI raced timeout, the return path has no verified drain. */
        pango_quarantine(g);
        return waited ? -ERESTARTSYS : -ETIMEDOUT;
    }
    dma_rmb();
    return 0;
}

/* Build a page-only bounded view, never copying PCI DMA addresses. A page per
 * entry avoids physical-contiguity assumptions across source SG boundaries. */
static int pango_slice_pages(struct pango_buffer *b, unsigned int offset,
                             unsigned int length, struct sg_table *out)
{
    struct scatterlist *src, *dst;
    unsigned int i, copied = 0;
    size_t skip = offset;
    int ret;

    if (!b->pages_valid || !pango_range_valid(b->size, offset, length) ||
        ((offset | length) & (PAGE_SIZE - 1)))
        return -EOPNOTSUPP;
    ret = sg_alloc_table(out, length / PAGE_SIZE, GFP_KERNEL);
    if (ret)
        return ret;
    dst = out->sgl;
    for_each_sg(b->pages.sgl, src, b->pages.orig_nents, i) {
        size_t pos, available;

        if (!sg_page(src) || src->offset || !src->length ||
            (src->length & (PAGE_SIZE - 1))) {
            ret = -EOPNOTSUPP;
            goto fail;
        }
        if (skip >= src->length) {
            skip -= src->length;
            continue;
        }
        pos = skip;
        skip = 0;
        available = min_t(size_t, src->length - pos, length - copied);
        while (available) {
            sg_set_page(dst, nth_page(sg_page(src), pos / PAGE_SIZE),
                        PAGE_SIZE, 0);
            copied += PAGE_SIZE;
            pos += PAGE_SIZE;
            available -= PAGE_SIZE;
            dst = sg_next(dst);
        }
        if (copied == length)
            return 0;
    }
    ret = -EOPNOTSUPP;
fail:
    sg_free_table(out);
    return ret;
}

static int pango_get_pages(struct pango_generation *g)
{
    struct pango_buffer *b = &g->rx;
    struct scatterlist *sg;
    size_t total = 0;
    unsigned int i;
    int ret;

    if (b->pages_valid)
        return 0;
    ret = dma_get_sgtable(g->alloc_dev, &b->pages, b->cpu, b->dma, b->size);
    if (ret)
        return ret;
    for_each_sg(b->pages.sgl, sg, b->pages.orig_nents, i) {
        if (!sg_page(sg) || sg->offset || !sg->length ||
            (sg->length & (PAGE_SIZE - 1)) || sg->length > b->size - total) {
            ret = -EOPNOTSUPP;
            goto fail;
        }
        total += sg->length;
    }
    if (total != b->size) {
        ret = -EOPNOTSUPP;
        goto fail;
    }
    b->pages_valid = true;
    return 0;
fail:
    sg_free_table(&b->pages);
    memset(&b->pages, 0, sizeof(b->pages));
    return ret;
}

/* No audited coherent-allocation -> importer DMA backend exists. Page aliases
 * from dma_get_sgtable must not undergo generic streaming cache maintenance.
 * These are source-code proof boundaries, not module parameters/compiler gates.
 * A future backend must also prove no stale bounce copy/copyback across refill.
 * Neither attributes=0 nor blindly setting SKIP_CPU_SYNC establishes that. */
static bool pango_import_backend_ready(void)
{
    return false;
}

static int pango_backend_map(struct device *dev, struct sg_table *sgt,
                             enum dma_data_direction dir)
{
    (void)dev;
    (void)sgt;
    (void)dir;
    return -EOPNOTSUPP;
}

static void pango_backend_unmap(struct device *dev, struct sg_table *sgt,
                                enum dma_data_direction dir)
{
    WARN_ON(1); /* No map can succeed with this backend. No cache alias access. */
}

static int pango_buf_attach(struct dma_buf *buf, struct dma_buf_attachment *att)
{
    struct pango_view *view = buf->priv;
    struct pango_attachment *a;
    int ret;

    if (!pango_import_backend_ready())
        return -EOPNOTSUPP;
    a = kzalloc(sizeof(*a), GFP_KERNEL);
    if (!a)
        return -ENOMEM;
    mutex_lock(&pango.lock);
    ret = pango_live(view->gen);
    if (!ret && (!att->dev->dma_mask || dma_get_max_seg_size(att->dev) < PAGE_SIZE))
        ret = -EOPNOTSUPP;
    if (!ret) {
        a->dev = get_device(att->dev);
        att->priv = a;
    }
    mutex_unlock(&pango.lock);
    if (ret)
        kfree(a);
    return ret;
}

static void pango_buf_detach(struct dma_buf *buf, struct dma_buf_attachment *att)
{
    struct pango_attachment *a = att->priv;

    mutex_lock(&pango.lock);
    WARN_ON(a->maps); /* core/importer must return mappings before detach */
    mutex_unlock(&pango.lock);
    put_device(a->dev);
    kfree(a);
    att->priv = NULL;
}

static struct sg_table *pango_buf_map(struct dma_buf_attachment *att,
                                     enum dma_data_direction dir)
{
    struct pango_view *view = att->dmabuf->priv;
    struct pango_attachment *a = att->priv;
    struct pango_mapping *map;
    int ret;

    /* Source only. BIDIRECTIONAL can copy stale SWIOTLB data back on unmap
     * after END/PCI refill. Reject it even if the importer expects it. */
    if (dir != DMA_TO_DEVICE)
        return ERR_PTR(-EOPNOTSUPP);
    if (att->dma_map_attrs)
        return ERR_PTR(-EOPNOTSUPP); /* no unchecked SKIP_CPU_SYNC */
    if (!pango_import_backend_ready())
        return ERR_PTR(-EOPNOTSUPP);
    map = kzalloc(sizeof(*map), GFP_KERNEL);
    if (!map)
        return ERR_PTR(-ENOMEM);
    mutex_lock(&pango.lock);
    ret = pango_live(view->gen);
    if (!ret && (atomic_read(&pango.active) || view->gen->export_pending ||
                 view->gen->begin_pending ||
                 (view->gen->lease_mask & (1U << view->slot))))
        ret = -EBUSY;
    if (!ret)
        ret = pango_slice_pages(&view->gen->rx, view->slot * PANGO_SLOT_STRIDE,
                                PANGO_SLOT_BYTES, &map->sgt);
    if (ret)
        goto fail;
    map->attachment = a;
    map->dir = dir;
    ret = pango_backend_map(a->dev, &map->sgt, dir);
    if (ret) {
        sg_free_table(&map->sgt);
        goto fail;
    }
    list_add_tail(&map->node, &view->mappings);
    a->maps++;
    mutex_unlock(&pango.lock);
    return &map->sgt;
fail:
    mutex_unlock(&pango.lock);
    kfree(map);
    return ERR_PTR(ret);
}

static void pango_buf_unmap(struct dma_buf_attachment *att, struct sg_table *sgt,
                            enum dma_data_direction dir)
{
    struct pango_mapping *map = container_of(sgt, struct pango_mapping, sgt);

    mutex_lock(&pango.lock);
    WARN_ON(map->attachment != att->priv || map->dir != dir);
    pango_backend_unmap(map->attachment->dev, sgt, map->dir);
    list_del(&map->node);
    map->attachment->maps--;
    sg_free_table(sgt); /* uses orig_nents, never the DMA-merged nents */
    mutex_unlock(&pango.lock);
    kfree(map);
}

static int pango_buf_cpu_access(struct dma_buf *buf, enum dma_data_direction dir)
{
    /* No CPU mmap/vmap of the dma-buf is supported. A successful cache-sync
     * callback must never be presented as RGA or PCIe completion. */
    return -EOPNOTSUPP;
}

static int pango_buf_cpu_partial(struct dma_buf *buf, enum dma_data_direction dir,
                                unsigned int offset, unsigned int len)
{
    return -EOPNOTSUPP;
}

static int pango_buf_mmap(struct dma_buf *buf, struct vm_area_struct *vma)
{
    return -EOPNOTSUPP;
}

static void pango_buf_release(struct dma_buf *buf)
{
    struct pango_view *view = buf->priv;
    struct pango_generation *g = view->gen;

    mutex_lock(&pango.lock);
    WARN_ON(!list_empty(&view->mappings));
    /* A lease outlives an accidentally closed FD until explicit END or owner
     * close. Never infer GPU completion from last FD release. */
    if (view->published) {
        WARN_ON(g->view[view->slot] != view);
        g->view[view->slot] = NULL;
        g->exports--;
    } else {
        WARN_ON(!(g->export_pending & (1U << view->slot)));
        g->export_pending &= ~(1U << view->slot);
    }
    pango_gen_put(g);
    mutex_unlock(&pango.lock);
    kfree(view);
}

static const struct dma_buf_ops pango_buf_ops = {
    .cache_sgt_mapping = false,
    .attach = pango_buf_attach,
    .detach = pango_buf_detach,
    .map_dma_buf = pango_buf_map,
    .unmap_dma_buf = pango_buf_unmap,
    .release = pango_buf_release,
    .begin_cpu_access = pango_buf_cpu_access,
    .end_cpu_access = pango_buf_cpu_access,
    .begin_cpu_access_partial = pango_buf_cpu_partial,
    .end_cpu_access_partial = pango_buf_cpu_partial,
    .mmap = pango_buf_mmap,
};

static bool pango_reserved_zero(const __u32 *words, unsigned int count)
{
    unsigned int i;

    for (i = 0; i < count; i++)
        if (words[i])
            return false;
    return true;
}

static long pango_export_ioctl(struct file *file,
                               const struct pango_export_slot_v1 *input,
                               void __user *arg)
{
    struct pango_export_slot_v1 req = *input;
    struct pango_generation *g = file->private_data;
    struct pango_view *view;
    struct dma_buf *buf;
    DEFINE_DMA_BUF_EXPORT_INFO(info);
    unsigned int bit;
    int fd, ret, copied;

    if (req.version != PANGO_DMA_ABI_V1 || req.slot >= PANGO_SLOT_COUNT ||
        req.flags || req.fd != -1 || req.offset || req.length || req.generation ||
        !pango_reserved_zero(req.reserved, ARRAY_SIZE(req.reserved)))
        return -EINVAL;
    if (!PANGO_EXPORT_PROVEN || !pango_import_backend_ready())
        return -EOPNOTSUPP;
    bit = 1U << req.slot;
    /* Reserve but do not publish an FD until copy_to_user succeeds. */
    fd = get_unused_fd_flags(O_CLOEXEC);
    if (fd < 0)
        return fd;
    view = kzalloc(sizeof(*view), GFP_KERNEL);
    if (!view) {
        put_unused_fd(fd);
        return -ENOMEM;
    }
    mutex_lock(&pango.lock);
    ret = pango_live(g);
    if (!ret && (!g->rx.cpu || g->rx.size != PANGO_RX_BYTES || PAGE_SIZE != 4096))
        ret = -EOPNOTSUPP;
    if (!ret && (g->view[req.slot] || (g->lease_mask & bit) ||
                 g->export_pending || g->begin_pending || atomic_read(&pango.active)))
        ret = -EBUSY;
    if (!ret)
        ret = pango_get_pages(g);
    if (ret)
        goto fail_locked;
    view->gen = g;
    view->slot = req.slot;
    INIT_LIST_HEAD(&view->mappings);
    info.ops = &pango_buf_ops;
    info.size = PANGO_SLOT_BYTES;
    info.flags = O_RDWR;
    info.priv = view;
    /* Reserve uniqueness and backing under lock, then enter DMA-BUF core with
     * no driver mutex held. Pending blocks DMA/UNMAP/mmap and pins generation. */
    g->export_pending |= bit;
    kref_get(&g->refs);
    mutex_unlock(&pango.lock);
    buf = dma_buf_export(&info); /* info.owner explicitly THIS_MODULE via macro */
    if (IS_ERR(buf)) {
        ret = PTR_ERR(buf);
        mutex_lock(&pango.lock);
        g->export_pending &= ~bit;
        pango_gen_put(g);
        goto fail_locked;
    }
    mutex_lock(&pango.lock);
    ret = pango_live(g); /* removal/owner loss during core publication */
    mutex_unlock(&pango.lock);
    if (ret)
        goto fail_buf;
    req.fd = fd;
    req.offset = req.slot * PANGO_SLOT_STRIDE;
    req.length = PANGO_SLOT_BYTES;
    req.generation = g->id;
    copied = copy_to_user(arg, &req, sizeof(req));
    mutex_lock(&pango.lock);
    ret = copied ? -EFAULT : pango_live(g);
    if (!ret) {
        g->export_pending &= ~bit;
        g->exports++;
        g->view[req.slot] = view;
        view->published = true;
    }
    mutex_unlock(&pango.lock);
    if (ret)
        goto fail_buf;
    fd_install(fd, buf->file); /* transfers the export file reference */
    return 0;
fail_buf:
    /* Release clears an unpublished reservation and drops its gen ref. Core
     * registry/resv/release locking must NEVER be entered under pango.lock. */
    dma_buf_put(buf);
    put_unused_fd(fd);
    return ret;
fail_locked:
    mutex_unlock(&pango.lock);
    kfree(view);
    put_unused_fd(fd);
    return ret;
}

static int pango_sync_slot(struct pango_generation *g, unsigned int slot, bool gpu)
{
    /* Generic dma_sync_sgtable_* on aliases of dma_alloc_coherent is unsafe.
     * No valid cache/bounce backend has been audited; never report success. */
    (void)g;
    (void)slot;
    (void)gpu;
    return -EOPNOTSUPP;
}

static int pango_lease_ioctl(struct pango_generation *g, unsigned int cmd,
                             const struct pango_slot_lease_v1 *input,
                             void __user *arg)
{
    struct pango_slot_lease_v1 req = *input;
    unsigned int bit;
    int ret, copied;

    if (req.version != PANGO_DMA_ABI_V1 || req.slot >= PANGO_SLOT_COUNT ||
        req.flags ||
        !pango_reserved_zero(req.reserved, ARRAY_SIZE(req.reserved)))
        return -EINVAL;
    if (!PANGO_EXPORT_PROVEN || !pango_import_backend_ready())
        return -EOPNOTSUPP;
    bit = 1U << req.slot;
    mutex_lock(&pango.lock);
    ret = pango_live(g);
    if (ret)
        goto out;
    if (req.generation != g->id) {
        ret = -EINVAL;
        goto out;
    }
    if (g->export_pending || g->begin_pending) {
        ret = -EBUSY;
        goto out;
    }
    if (cmd == PANGO_SLOT_BEGIN_V1) {
        if (req.token) {
            ret = -EINVAL;
            goto out;
        }
        if (!g->view[req.slot]) {
            ret = -ENXIO;
            goto out;
        }
        if ((g->lease_mask & bit) || atomic_read(&pango.active)) {
            ret = -EBUSY;
            goto out;
        }
        if (pango.next_token == U64_MAX) {
            ret = -EOVERFLOW;
            goto out;
        }
        ret = pango_sync_slot(g, req.slot, true);
        if (ret)
            goto out;
        req.token = ++pango.next_token;
        g->lease[req.slot] = req.token;
        g->lease_mask |= bit;
        g->begin_pending |= bit;
        kref_get(&g->refs); /* delivery transaction pin, beyond owning file ref */
        mutex_unlock(&pango.lock);
        copied = copy_to_user(arg, &req, sizeof(req));
        mutex_lock(&pango.lock);
        ret = copied ? -EFAULT : pango_live(g);
        if (!ret && !g->view[req.slot])
            ret = -ENXIO;
        if (ret) {
            /* No GPU submission is permitted before ioctl returns success.
             * Keep containment if a future backend cannot undo the handoff. */
            if (pango_sync_slot(g, req.slot, false))
                pango_quarantine(g);
            g->lease_mask &= ~bit;
            g->lease[req.slot] = 0;
        }
        g->begin_pending &= ~bit;
        pango_gen_put(g);
        goto out;
    }
    if (!(g->lease_mask & bit) || !req.token || g->lease[req.slot] != req.token) {
        ret = -EINVAL;
        goto out;
    }
    /* END is the trusted client's assertion of blocking RGA completion.
     * No external asynchronous/fence protocol is claimed by this candidate. */
    ret = pango_sync_slot(g, req.slot, false);
    if (ret)
        goto out; /* Keep lease on an unproven backend handback. */
    g->lease_mask &= ~bit;
    g->lease[req.slot] = 0;
out:
    mutex_unlock(&pango.lock);
    return ret;
}

static long pango_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct pango_generation *g = file->private_data;
    void __user *user = (void __user *)arg;
    union pango_ioctl_request req = {0};
    void *dest = &req;
    const void __user *input = user;
    size_t bytes;
    int ret;

    /* One immutable kernel snapshot BEFORE any driver mutex. User faults can
     * enter mmap/VMA paths under mmap_lock; no lock->usercopy inversion. */
    switch (cmd) {
    case PCI_MAP_ADDR_CMD:
    case PCI_DMA_READ_CMD:
    case PCI_DMA_WRITE_CMD:
        bytes = 5 * sizeof(unsigned int); /* legacy pointer-free prefix */
        break;
    case PCI_UMAP_ADDR_CMD:
        input = (char __user *)user + offsetof(DMA_OPERATION, cmd);
        dest = &req.op.cmd;
        bytes = sizeof(req.op.cmd);
        break;
    case PANGO_EXPORT_SLOT_V1:
        bytes = sizeof(req.export);
        break;
    case PANGO_SLOT_BEGIN_V1:
    case PANGO_SLOT_END_V1:
        bytes = sizeof(req.lease);
        break;
    default:
        return -ENOTTY;
    }
    if (copy_from_user(dest, input, bytes))
        return -EFAULT;
    if (cmd == PANGO_EXPORT_SLOT_V1)
        return pango_export_ioctl(file, &req.export, user);
    if (cmd == PANGO_SLOT_BEGIN_V1 || cmd == PANGO_SLOT_END_V1)
        return pango_lease_ioctl(g, cmd, &req.lease, user);
    if (mutex_lock_interruptible(&pango.lock))
        return -ERESTARTSYS;
    ret = pango_live(g);
    if (ret)
        goto out;
    switch (cmd) {
    case PCI_MAP_ADDR_CMD:
    case PCI_DMA_READ_CMD:
    case PCI_DMA_WRITE_CMD:
        if (cmd == PCI_MAP_ADDR_CMD)
            ret = pango_map_legacy(g, &req.op);
        else
            ret = pango_transfer(g, &req.op, cmd == PCI_DMA_WRITE_CMD);
        break;
    case PCI_UMAP_ADDR_CMD:
        ret = pango_unmap_legacy(g, req.op.cmd);
        break;
    default:
        ret = -ENOTTY; /* includes old auto-camera/NPU and performance paths */
        break;
    }
out:
    mutex_unlock(&pango.lock);
    return ret;
}

#ifdef CONFIG_COMPAT
static long pango_compat_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    /* New ABI uses aligned u64; consumed legacy prefix has no pointers. */
    return pango_ioctl(file, cmd, (unsigned long)compat_ptr(arg));
}
#endif

static void pango_vma_open(struct vm_area_struct *vma)
{
    struct pango_generation *g = vma->vm_private_data;

    mutex_lock(&pango.lock);
    kref_get(&g->refs);
    g->vmas++;
    mutex_unlock(&pango.lock);
}

static void pango_vma_close(struct vm_area_struct *vma)
{
    struct pango_generation *g = vma->vm_private_data;

    mutex_lock(&pango.lock);
    g->vmas--;
    pango_gen_put(g);
    mutex_unlock(&pango.lock);
}

static const struct vm_operations_struct pango_vm_ops = {
    .open = pango_vma_open,
    .close = pango_vma_close,
};

static int pango_mmap(struct file *file, struct vm_area_struct *vma)
{
    struct pango_generation *g = file->private_data;
    struct pango_buffer *b;
    unsigned long pgoff = vma->vm_pgoff;
    size_t size = vma->vm_end - vma->vm_start;
    int ret;

    if (!(vma->vm_flags & VM_SHARED))
        return -EINVAL;
    /* Compare page offsets without shifting untrusted values. */
    if (pgoff != 0 && pgoff != RX_MMAP_OFFSET / PAGE_SIZE)
        return -EINVAL;
    mutex_lock(&pango.lock);
    ret = pango_live(g);
    if (ret)
        goto out;
    if (g->export_pending || g->begin_pending || g->lease_mask) {
        ret = -EBUSY; /* no new CPU views during handoff/GPU access */
        goto out;
    }
    b = pgoff ? &g->rx : &g->tx;
    if (!b->cpu || !pango_range_valid(b->size, 0, size)) {
        ret = -EINVAL;
        goto out;
    }
    vma->vm_pgoff = 0;
    ret = dma_mmap_coherent(g->alloc_dev, vma, b->cpu, b->dma, b->size);
    if (ret) {
        vma->vm_pgoff = pgoff;
        goto out;
    }
    /* dma_mmap_coherent must leave vm_ops unused on the audited platform;
     * candidate refuses custom DMA mmap implementations with callbacks. */
    if (vma->vm_ops) {
        ret = -EOPNOTSUPP;
        goto out;
    }
    vma->vm_flags |= VM_DONTEXPAND | VM_DONTDUMP;
    vma->vm_ops = &pango_vm_ops;
    vma->vm_private_data = g;
    kref_get(&g->refs); /* initial VMA does not call vm_ops.open */
    g->vmas++;
out:
    mutex_unlock(&pango.lock);
    return ret;
}

static int pango_open(struct inode *inode, struct file *file)
{
    struct pango_generation *g;
    int ret = 0;

    mutex_lock(&pango.lock);
    if (READ_ONCE(pango.dead) || !pango.pdev) {
        ret = -ENODEV;
        goto out;
    }
    if (pango.owner || pango.gen || pango.faulted) {
        ret = -EBUSY;
        goto out;
    }
    if (pango.next_generation == U64_MAX) {
        ret = -EOVERFLOW;
        goto out;
    }
    g = kzalloc(sizeof(*g), GFP_KERNEL);
    if (!g) {
        ret = -ENOMEM;
        goto out;
    }
    if (!try_module_get(THIS_MODULE)) {
        kfree(g);
        ret = -ENODEV;
        goto out;
    }
    kref_init(&g->refs);
    g->alloc_dev = get_device(&pango.pdev->dev);
    g->id = ++pango.next_generation;
    g->owned = true;
    pango.owner = true;
    pango.gen = g;
    file->private_data = g;
out:
    mutex_unlock(&pango.lock);
    return ret;
}

static int pango_release(struct inode *inode, struct file *file)
{
    struct pango_generation *g = file->private_data;

    mutex_lock(&pango.lock);
    /* Kernel file references serialize final release after in-flight syscalls.
     * If completion remains outstanding, retain backing; never reset active. */
    if (atomic_read(&pango.active)) {
        if (!wait_for_completion_timeout(&pango.done,
                              msecs_to_jiffies(PANGO_DMA_TIMEOUT_MS)) ||
            atomic_read(&pango.active) || READ_ONCE(pango.dead))
            pango_quarantine(g);
        else
            dma_rmb();
    }
    /* remove's complete_all is a wakeup, never an MSI completion proof. BAR/
     * DMA-domain teardown cannot pass this mutex until release is contained. */
    if (READ_ONCE(pango.dead) && (g->tx.cpu || g->rx.cpu))
        pango_quarantine(g);
    /* Owner death with a GPU lease is not proof that GPU work has finished. */
    if (g->lease_mask || g->begin_pending || g->export_pending)
        pango_quarantine(g);
    g->owned = false;
    pango.owner = false;
    file->private_data = NULL;
    /* Exports/VMA refs keep BOTH TX and RX plus PCI device/module alive.
     * Reopen remains blocked by pango.gen until its final reference is gone. */
    pango_gen_put(g);
    mutex_unlock(&pango.lock);
    return 0;
}

static const struct file_operations pango_fops = {
    .owner = THIS_MODULE,
    .open = pango_open,
    .release = pango_release,
    .unlocked_ioctl = pango_ioctl,
#ifdef CONFIG_COMPAT
    .compat_ioctl = pango_compat_ioctl,
#endif
    .mmap = pango_mmap,
    .llseek = no_llseek,
};

static int pango_probe(struct pci_dev *pdev, const struct pci_device_id *id)
{
    void __iomem *bar;
    int ret, requested = 0;

    mutex_lock(&pango.lock);
    if (pango.pdev || pango.gen || pango.faulted) {
        ret = -EBUSY;
        goto out;
    }
    ret = pci_enable_device_mem(pdev);
    if (ret)
        goto out;
    /* Verified controller address mode is 32 bit (CMD bit16=0). */
    ret = dma_set_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(32));
    if (ret)
        goto disable;
    if (!(pci_resource_flags(pdev, PANGO_BAR) & IORESOURCE_MEM) ||
        pci_resource_len(pdev, PANGO_BAR) < PANGO_TOTAL + sizeof(u32)) {
        ret = -ENODEV;
        goto disable;
    }
    ret = pci_request_region(pdev, PANGO_BAR, PANGO_NAME);
    if (ret)
        goto disable;
    bar = pci_iomap(pdev, PANGO_BAR, 0);
    if (!bar) {
        ret = -ENOMEM;
        goto region;
    }
    /* Exactly three MSI vectors are required, never index unallocated ones. */
    ret = pci_alloc_irq_vectors(pdev, 3, 3, PCI_IRQ_MSI);
    if (ret < 0)
        goto iomap;
    ret = request_irq(pci_irq_vector(pdev, 0), pango_dma_irq, 0, PANGO_NAME, pdev);
    if (ret)
        goto vectors;
    requested++;
    ret = request_irq(pci_irq_vector(pdev, 1), pango_event_irq, 0, PANGO_NAME, pdev);
    if (ret)
        goto irqs;
    requested++;
    ret = request_irq(pci_irq_vector(pdev, 2), pango_event_irq, 0, PANGO_NAME, pdev);
    if (ret)
        goto irqs;
    pci_set_master(pdev);
    pango.pdev = pdev;
    get_device(&pdev->dev);
    pango.bar = bar;
    WRITE_ONCE(pango.dead, false);
    ret = 0;
    goto out;
irqs:
    while (requested)
        free_irq(pci_irq_vector(pdev, --requested), pdev);
vectors:
    pci_free_irq_vectors(pdev);
iomap:
    pci_iounmap(pdev, bar);
region:
    pci_release_region(pdev, PANGO_BAR);
disable:
    pci_disable_device(pdev);
out:
    mutex_unlock(&pango.lock);
    return ret;
}

static void pango_remove(struct pci_dev *pdev)
{
    /* Wake a transfer before waiting for the ioctl mutex. Completion is not
     * success once dead is set. Existing importer refs retain quarantined RAM. */
    WRITE_ONCE(pango.dead, true);
    complete_all(&pango.done);
    mutex_lock(&pango.lock);
    pci_clear_master(pdev);
    pci_wait_for_pending_transaction(pdev);
    if (pango.gen && (pango.gen->tx.cpu || pango.gen->rx.cpu))
        pango_quarantine(pango.gen);
    free_irq(pci_irq_vector(pdev, 2), pdev);
    free_irq(pci_irq_vector(pdev, 1), pdev);
    free_irq(pci_irq_vector(pdev, 0), pdev);
    pci_free_irq_vectors(pdev);
    pci_iounmap(pdev, pango.bar);
    pango.bar = NULL;
    pci_release_region(pdev, PANGO_BAR);
    pci_disable_device(pdev);
    pango.pdev = NULL;
    put_device(&pdev->dev);
    mutex_unlock(&pango.lock);
}

/* IDs are explicit module parameters; no guessed default or wildcard binding. */
static struct pci_device_id pango_ids[] = {
    { .subvendor = PCI_ANY_ID, .subdevice = PCI_ANY_ID },
    { 0 },
};

static struct pci_driver pango_driver = {
    .name = "pango_dma_candidate",
    .id_table = pango_ids,
    .probe = pango_probe,
    .remove = pango_remove,
};

static int __init pango_init(void)
{
    int ret;

    BUILD_BUG_ON(sizeof(struct pango_export_slot_v1) != 48);
    BUILD_BUG_ON(sizeof(struct pango_slot_lease_v1) != 48);
    BUILD_BUG_ON(offsetof(DMA_OPERATION, total_length) != 16);
    if (!vendor_id || !device_id || vendor_id >= 0xffff || device_id >= 0xffff)
        return -EINVAL;
    pango_ids[0].vendor = vendor_id;
    pango_ids[0].device = device_id;
    mutex_init(&pango.lock);
    init_completion(&pango.done);
    atomic_set(&pango.active, 0);
    pango.dead = true;
    ret = alloc_chrdev_region(&pango.devt, 0, 1, PANGO_NAME);
    if (ret)
        return ret;
    cdev_init(&pango.cdev, &pango_fops);
    pango.cdev.owner = THIS_MODULE;
    ret = cdev_add(&pango.cdev, pango.devt, 1);
    if (ret)
        goto devt;
    pango.class = class_create(THIS_MODULE, PANGO_NAME); /* 6.1 interface */
    if (IS_ERR(pango.class)) {
        ret = PTR_ERR(pango.class);
        goto cdev;
    }
    pango.node = device_create(pango.class, NULL, pango.devt, NULL, PANGO_NAME);
    if (IS_ERR(pango.node)) {
        ret = PTR_ERR(pango.node);
        goto class;
    }
    ret = pci_register_driver(&pango_driver);
    if (ret)
        goto node;
    return 0;
node:
    device_destroy(pango.class, pango.devt);
class:
    class_destroy(pango.class);
cdev:
    cdev_del(&pango.cdev);
devt:
    unregister_chrdev_region(pango.devt, 1);
    return ret;
}

static void __exit pango_exit(void)
{
    pci_unregister_driver(&pango_driver);
    device_destroy(pango.class, pango.devt);
    class_destroy(pango.class);
    cdev_del(&pango.cdev);
    unregister_chrdev_region(pango.devt, 1);
}

module_init(pango_init);
module_exit(pango_exit);
MODULE_IMPORT_NS(DMA_BUF);
MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("Offline fail-closed bounded Pango PCIe dma-buf candidate");
