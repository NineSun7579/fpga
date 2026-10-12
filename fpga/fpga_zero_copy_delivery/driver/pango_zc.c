// SPDX-License-Identifier: GPL-2.0-only
/* Cooperative RX input sharing for the completion-fixed FPGA image. */
#include <linux/module.h>
#include <linux/pci.h>
#include <linux/cdev.h>
#include <linux/fs.h>
#include <linux/file.h>
#include <linux/fdtable.h>
#include <linux/compat.h>
#include <linux/uaccess.h>
#include <linux/mm.h>
#include <linux/slab.h>
#include <linux/kref.h>
#include <linux/mutex.h>
#include <linux/completion.h>
#include <linux/interrupt.h>
#include <linux/dma-buf.h>
#include <linux/dma-mapping.h>
#include <linux/dma-map-ops.h>
#include <linux/dma-direct.h>
#include <linux/iommu.h>
#include <linux/scatterlist.h>
#include "pango_zc_uapi.h"

#define PZ_NAME "pango_pci_driver"
#define PZ_BAR 1
#define PZ_CMD 0x100
#define PZ_ADDR_LO 0x110
#define PZ_ADDR_HI 0x120
#define PZ_DDR 0x1e0
#define PZ_TOTAL 0x200
#define PZ_TIMEOUT_MS 1000
#define PZ_MAP_ATTRS DMA_ATTR_SKIP_CPU_SYNC

static unsigned int vendor_id = 0x0755, device_id = 0x0755;
module_param(vendor_id, uint, 0444);
module_param(device_id, uint, 0444);
MODULE_PARM_DESC(vendor_id, "Verified endpoint PCI vendor (default 0755)");
MODULE_PARM_DESC(device_id, "Verified endpoint PCI device (default 0755)");

struct pz_buffer { void *cpu; dma_addr_t dma; size_t size; };
struct pz_generation {
    struct kref refs;
    struct device *allocator;
    struct pz_buffer tx, rx;
    struct sg_table pages;
    bool pages_valid, owned, quarantined, exported, pending, mapped;
    unsigned int cpu_access[3];
    u64 token;
    u32 lease_offset, lease_length, ready_offset, ready_length;
};
struct pz_mapping {
    struct sg_table table;
    enum dma_data_direction dir;
};
/* IRQ touches only active/done. No IRQ launches camera/legacy NPU DMA.
 * Lock order is mmap_lock or DMA-BUF core -> lock. NEVER usercopy or
 * dma_buf_export/put/fd_install under lock. Allocation generations pin module. */
static struct {
    struct mutex lock;
    struct pci_dev *pdev;
    void __iomem *bar;
    bool dead, faulted;
    struct pz_generation *gen;
    u64 next_token;
    atomic_t active;
    struct completion done;
    dev_t devt;
    struct cdev cdev;
    struct class *class;
    struct device *node;
} pz;

static bool range_ok(size_t size, u32 off, u32 bytes)
{
    return bytes && off <= size && bytes <= size - off;
}
static bool overlap(u32 a, u32 n, u32 b, u32 m)
{
    return n && m && (u64)a < (u64)b + m && (u64)b < (u64)a + n;
}
static bool cpu_busy(struct pz_generation *g)
{
    return g->cpu_access[0] || g->cpu_access[1] || g->cpu_access[2];
}
static int live(struct pz_generation *g)
{
    if (READ_ONCE(pz.dead) || !pz.pdev)
        return -ENODEV;
    if (pz.faulted || g->quarantined)
        return -EIO;
    return g->owned && pz.gen == g ? 0 : -EBADF;
}
static void free_buffer(struct pz_generation *g, struct pz_buffer *b)
{
    if (b->cpu)
        dma_free_coherent(g->allocator, b->size, b->cpu, b->dma);
    memset(b, 0, sizeof(*b));
}
static void gen_release(struct kref *ref)
{
    struct pz_generation *g = container_of(ref, struct pz_generation, refs);

    lockdep_assert_held(&pz.lock);
    WARN_ON(g->owned || g->exported || g->pending || g->token ||
            g->quarantined || cpu_busy(g));
    if (g->pages_valid)
        sg_free_table(&g->pages);
    free_buffer(g, &g->rx);
    free_buffer(g, &g->tx);
    pz.gen = NULL;
    put_device(g->allocator);
    kfree(g);
    module_put(THIS_MODULE);
}
static void gen_put(struct pz_generation *g) { kref_put(&g->refs, gen_release); }

/* A failed DMA or abandoned consumer lease has no proven cancellation.
 * Keep one permanent RAM/device/module reference; reboot is recovery. */
static void quarantine(struct pz_generation *g)
{
    pz.faulted = true;
    if (!g->quarantined) {
        g->quarantined = true;
        kref_get(&g->refs);
        pr_err(PZ_NAME ": uncertain DMA/consumer lifetime; reboot required\n");
    }
    if (pz.pdev)
        pci_clear_master(pz.pdev);
}

static int alloc_buffer(struct pz_generation *g, const struct pz_dma_op *op)
{
    struct pz_buffer *b;
    size_t bytes;

    if (op->cmd > 1 || !op->total_length || op->total_length > PZ_BUFFER_BYTES)
        return -EINVAL;
    if (g->pending || g->token || cpu_busy(g))
        return -EBUSY;
    b = op->cmd ? &g->rx : &g->tx;
    if (b->cpu)
        return -EBUSY;
    bytes = PAGE_ALIGN(op->total_length);
    b->cpu = dma_alloc_coherent(g->allocator, bytes, &b->dma, GFP_KERNEL);
    if (!b->cpu)
        return -ENOMEM;
    b->size = bytes;
    if ((u64)b->dma + bytes > (1ULL << 32)) {
        free_buffer(g, b);
        return -EOVERFLOW;
    }
    memset(b->cpu, 0, bytes);
    return 0;
}

static irqreturn_t dma_irq(int irq, void *data)
{
    if (atomic_xchg(&pz.active, 0))
        complete(&pz.done);
    return IRQ_HANDLED;
}
static irqreturn_t event_irq(int irq, void *data) { return IRQ_HANDLED; }

static int transfer(struct pz_generation *g, const struct pz_dma_op *op, bool rx)
{
    struct pz_buffer *b = rx ? &g->rx : &g->tx;
    dma_addr_t addr;
    u32 cmd;
    long waited;

    if (!b->cpu)
        return -ENXIO;
    if (!range_ok(b->size, op->offset_addr, op->total_length) ||
        ((op->offset_addr | op->total_length | op->ddr3_addr) & 3) ||
        (u64)op->ddr3_addr + op->total_length > (1ULL << 32))
        return -EINVAL;
    if (g->pending || (rx && (cpu_busy(g) ||
        overlap(op->offset_addr, op->total_length, g->lease_offset,
                g->token ? g->lease_length : 0))))
        return -EBUSY;
    addr = b->dma + op->offset_addr;
    if ((u64)addr + op->total_length > (1ULL << 32))
        return -EOVERFLOW;
    if (rx && overlap(op->offset_addr, op->total_length,
                      g->ready_offset, g->ready_length))
        g->ready_length = 0;
    synchronize_irq(pci_irq_vector(pz.pdev, 0));
    reinit_completion(&pz.done);
    atomic_set(&pz.active, 1);
    cmd = (min_t(u32, op->total_length, 4096) / 4) & 0x3ff;
    if (rx)
        cmd |= 1U << 24;
    /* Explicit 32-bit host-address mode, 4096-byte chunk encodes DW length 0.
     * The fixed integrated image retires final TX payload BEFORE final MSI. */
    dma_wmb();
    iowrite32(op->ddr3_addr, pz.bar + PZ_DDR);
    iowrite32(lower_32_bits(addr), pz.bar + PZ_ADDR_LO);
    iowrite32(0, pz.bar + PZ_ADDR_HI);
    iowrite32(op->total_length, pz.bar + PZ_TOTAL);
    iowrite32(cmd, pz.bar + PZ_CMD);
    /* Once submitted, userspace termination cannot cancel hardware DMA.
     * Finish the bounded wait before delivering pending task signals. */
    waited = wait_for_completion_timeout(&pz.done,
                                            msecs_to_jiffies(PZ_TIMEOUT_MS));
    if (READ_ONCE(pz.dead) || waited <= 0) {
        quarantine(g);
        return READ_ONCE(pz.dead) ? -ENODEV : waited ? -ERESTARTSYS : -ETIMEDOUT;
    }
    dma_rmb();
    if (rx && op->total_length == PZ_INPUT_BYTES && op->offset_addr >= PAGE_SIZE &&
        !(op->offset_addr & (PAGE_SIZE - 1))) {
        g->ready_offset = op->offset_addr;
        g->ready_length = op->total_length;
    }
    return 0;
}

static int get_pages(struct pz_generation *g)
{
    struct scatterlist *sg;
    unsigned int i;
    size_t bytes = 0;
    int ret;

    if (g->pages_valid)
        return 0;
    ret = dma_get_sgtable(g->allocator, &g->pages, g->rx.cpu, g->rx.dma, g->rx.size);
    if (ret)
        return ret;
    for_each_sg(g->pages.sgl, sg, g->pages.orig_nents, i) {
        if (!sg_page(sg) || sg->offset || !sg->length ||
            (sg->length & (PAGE_SIZE - 1)) || sg->length > g->rx.size - bytes) {
            ret = -EOPNOTSUPP;
            goto fail;
        }
        bytes += sg->length;
    }
    if (bytes != g->rx.size) {
        ret = -EOPNOTSUPP;
        goto fail;
    }
    g->pages_valid = true;
    return 0;
fail:
    sg_free_table(&g->pages);
    memset(&g->pages, 0, sizeof(g->pages));
    return ret;
}

/* Prove every mapped DMA page reaches the original page, excluding SWIOTLB
 * staging. Persistent bounce maps are invalid for independently refilled RX.
 * IOMMU translation checks use the ATTACHMENT domain, never the PCI address.
 * Custom non-IOMMU DMA ops have no generic inverse and are unsupported. */
static bool mapping_is_original(struct device *dev, struct sg_table *mapped,
                                struct sg_table *original)
{
    struct iommu_domain *domain = iommu_get_domain_for_dev(dev);
    struct scatterlist *dma_sg, *page_sg = original->sgl;
    unsigned int i;
    size_t page_pos = 0, total = 0;

    if (!domain && get_dma_ops(dev))
        return false;
    for_each_sg(mapped->sgl, dma_sg, mapped->nents, i) {
        size_t pos;
        if (!sg_dma_len(dma_sg) ||
            ((sg_dma_address(dma_sg) | sg_dma_len(dma_sg)) & (PAGE_SIZE - 1)))
            return false;
        for (pos = 0; pos < sg_dma_len(dma_sg); pos += PAGE_SIZE) {
            dma_addr_t dma = sg_dma_address(dma_sg) + pos;
            phys_addr_t phys;
            if (!page_sg || total >= PZ_BUFFER_BYTES)
                return false;
            phys = domain ? iommu_iova_to_phys(domain, dma) : dma_to_phys(dev, dma);
            if (phys != sg_phys(page_sg) + page_pos)
                return false;
            total += PAGE_SIZE;
            page_pos += PAGE_SIZE;
            if (page_pos == page_sg->length) {
                page_sg = sg_next(page_sg);
                page_pos = 0;
            }
        }
    }
    return total == PZ_BUFFER_BYTES;
}

static int buf_attach(struct dma_buf *buf, struct dma_buf_attachment *att)
{
    struct pz_generation *g = buf->priv;
    int ret;
    mutex_lock(&pz.lock);
    ret = live(g);
    if (!ret && (!att->dev->dma_mask || dma_get_max_seg_size(att->dev) < PAGE_SIZE))
        ret = -EOPNOTSUPP;
    mutex_unlock(&pz.lock);
    return ret;
}
static struct sg_table *buf_map(struct dma_buf_attachment *att,
                                enum dma_data_direction dir)
{
    struct pz_generation *g = att->dmabuf->priv;
    struct pz_mapping *m;
    struct scatterlist *src, *dst;
    unsigned int i;
    int ret;

    /* Some RKNN importers request BIDIRECTIONAL even for input tensors.
     * This grants addressability, not permission to use RX as an output. */
    if (dir != DMA_TO_DEVICE && dir != DMA_BIDIRECTIONAL)
        return ERR_PTR(-EOPNOTSUPP);
    m = kzalloc(sizeof(*m), GFP_KERNEL);
    if (!m)
        return ERR_PTR(-ENOMEM);
    mutex_lock(&pz.lock);
    ret = live(g);
    if (ret)
        goto unlock;
    ret = sg_alloc_table(&m->table, PZ_BUFFER_BYTES / PAGE_SIZE, GFP_KERNEL);
    if (ret)
        goto unlock;
    dst = m->table.sgl;
    for_each_sg(g->pages.sgl, src, g->pages.orig_nents, i) {
        size_t pos;
        for (pos = 0; pos < src->length; pos += PAGE_SIZE) {
            sg_set_page(dst, nth_page(sg_page(src), pos / PAGE_SIZE), PAGE_SIZE, 0);
            dst = sg_next(dst);
        }
    }
    /* Only the allocator's coherent CPU alias is accessible. Skip streaming
     * maintenance of the cached linear alias. No bounce map is publishable. */
    ret = dma_map_sgtable(att->dev, &m->table, dir, PZ_MAP_ATTRS);
    if (ret)
        goto table;
    if (!mapping_is_original(att->dev, &m->table, &g->pages)) {
        dma_unmap_sgtable(att->dev, &m->table, dir, PZ_MAP_ATTRS);
        ret = -EOPNOTSUPP;
        goto table;
    }
    m->dir = dir;
    mutex_unlock(&pz.lock);
    return &m->table;
table:
    sg_free_table(&m->table);
unlock:
    mutex_unlock(&pz.lock);
    kfree(m);
    return ERR_PTR(ret);
}
static void buf_unmap(struct dma_buf_attachment *att, struct sg_table *table,
                      enum dma_data_direction dir)
{
    struct pz_mapping *m = container_of(table, struct pz_mapping, table);
    WARN_ON(dir != m->dir);
    /* No CPU alias maintenance and no bounce copyback, including after close. */
    dma_unmap_sgtable(att->dev, table, m->dir, PZ_MAP_ATTRS);
    sg_free_table(table);
    kfree(m);
}
static int buf_begin_cpu(struct dma_buf *buf, enum dma_data_direction dir)
{
    struct pz_generation *g = buf->priv;
    int ret;
    if (dir > DMA_FROM_DEVICE)
        return -EINVAL;
    mutex_lock(&pz.lock);
    ret = live(g);
    if (!ret && (g->pending || g->token || atomic_read(&pz.active)))
        ret = -EBUSY;
    if (!ret) {
        if (g->cpu_access[dir] == UINT_MAX)
            ret = -EOVERFLOW;
        else {
            g->cpu_access[dir]++;
            dma_rmb();
        }
    }
    mutex_unlock(&pz.lock);
    return ret;
}
static int buf_end_cpu(struct dma_buf *buf, enum dma_data_direction dir)
{
    struct pz_generation *g = buf->priv;
    int ret = 0;
    if (dir > DMA_FROM_DEVICE)
        return -EINVAL;
    mutex_lock(&pz.lock);
    if (!g->cpu_access[dir])
        ret = -EINVAL;
    else {
        dma_wmb();
        g->cpu_access[dir]--;
        /* A CPU writer invalidates kernel-recorded producer completion. */
        if (dir != DMA_FROM_DEVICE)
            g->ready_length = 0;
    }
    mutex_unlock(&pz.lock);
    return ret;
}

static int map_coherent(struct pz_generation *g, struct pz_buffer *b,
                         struct vm_area_struct *vma, struct file *backing_file)
{
    unsigned long bytes = vma->vm_end - vma->vm_start;
    int ret;
    if (vma->vm_file != backing_file || !b->cpu || !(vma->vm_flags & VM_SHARED) ||
        vma->vm_pgoff > b->size / PAGE_SIZE ||
        bytes > b->size - vma->vm_pgoff * PAGE_SIZE)
        return -EINVAL;
    if (g->pending || g->token)
        return -EBUSY;
    ret = dma_mmap_coherent(g->allocator, vma, b->cpu, b->dma, b->size);
    if (ret)
        return ret;
    /* The VMA's file reference pins either pz_fops' owner reference or the
     * DMA-BUF export reference until the last VMA/file/attachment retires.
     * Fork/split/mremap retain file references through the MM core. Leave
     * allocator vm_ops AND vm_private_data untouched (ARM64 installs access).
     * Without private VMA counting, explicit UNMAP stays blocked permanently
     * after the first successful mapping; final reference retirement frees RAM.
     */
    if (vma->vm_file != backing_file)
        return -EOPNOTSUPP;
    g->mapped = true;
    return 0;
}
static int buf_mmap(struct dma_buf *buf, struct vm_area_struct *vma)
{
    struct pz_generation *g = buf->priv;
    int ret;
    mutex_lock(&pz.lock);
    ret = live(g);
    if (!ret)
        ret = map_coherent(g, &g->rx, vma, buf->file);
    if (ret)
        dev_err_ratelimited(g->allocator, "RX DMA-BUF mmap failed: %d\n", ret);
    mutex_unlock(&pz.lock);
    return ret;
}
static void buf_release(struct dma_buf *buf)
{
    struct pz_generation *g = buf->priv;
    mutex_lock(&pz.lock);
    if (cpu_busy(g))
        quarantine(g);
    g->exported = false;
    gen_put(g);
    mutex_unlock(&pz.lock);
}
static const struct dma_buf_ops buf_ops = {
    .attach = buf_attach, .map_dma_buf = buf_map, .unmap_dma_buf = buf_unmap,
    .begin_cpu_access = buf_begin_cpu, .end_cpu_access = buf_end_cpu,
    .mmap = buf_mmap, .release = buf_release,
};

static long export_rx(struct pz_generation *g)
{
    DEFINE_DMA_BUF_EXPORT_INFO(info);
    struct dma_buf *buf;
    int fd, ret;

    fd = get_unused_fd_flags(O_CLOEXEC);
    if (fd < 0)
        return fd;
    mutex_lock(&pz.lock);
    ret = live(g);
    if (!ret && (g->pending || g->exported || g->token || cpu_busy(g)))
        ret = -EBUSY;
    if (!ret && (!g->rx.cpu || g->rx.size != PZ_BUFFER_BYTES || PAGE_SIZE != 4096))
        ret = -EINVAL;
    if (!ret)
        ret = get_pages(g);
    if (ret) {
        mutex_unlock(&pz.lock);
        put_unused_fd(fd);
        return ret;
    }
    g->pending = true;
    g->exported = true;
    kref_get(&g->refs);
    mutex_unlock(&pz.lock);
    info.exp_name = "pango-rx";
    info.owner = THIS_MODULE;
    info.ops = &buf_ops;
    info.size = PZ_BUFFER_BYTES;
    info.flags = O_RDWR;
    info.priv = g;
    buf = dma_buf_export(&info);
    mutex_lock(&pz.lock);
    ret = IS_ERR(buf) ? PTR_ERR(buf) : live(g);
    g->pending = false;
    if (IS_ERR(buf)) {
        g->exported = false;
        gen_put(g);
    }
    mutex_unlock(&pz.lock);
    if (ret) {
        if (!IS_ERR(buf))
            dma_buf_put(buf);
        put_unused_fd(fd);
        return ret;
    }
    /* A concurrent removal after revalidation returns a pinned but dead fd;
     * all later map/lease operations fail. Publication never dereferences BAR. */
    fd_install(fd, buf->file);
    return fd;
}

static bool lease_valid(const struct pz_lease *q)
{
    return q->version == PZ_VERSION && !q->flags &&
        !memchr_inv(q->reserved, 0, sizeof(q->reserved)) &&
        q->offset >= PAGE_SIZE && !(q->offset & (PAGE_SIZE - 1)) &&
        q->length == PZ_INPUT_BYTES && range_ok(PZ_BUFFER_BYTES, q->offset, q->length);
}
static long lease_begin(struct pz_generation *g, struct pz_lease *q, void __user *arg)
{
    int ret;
    if (!lease_valid(q) || q->token)
        return -EINVAL;
    mutex_lock(&pz.lock);
    ret = live(g);
    if (!ret && (g->pending || g->token || !g->exported || cpu_busy(g)))
        ret = -EBUSY;
    if (!ret && (g->ready_offset != q->offset || g->ready_length != q->length))
        ret = -ENODATA;
    if (!ret && pz.next_token == U64_MAX)
        ret = -EOVERFLOW;
    if (ret) {
        mutex_unlock(&pz.lock);
        return ret;
    }
    q->token = ++pz.next_token;
    g->token = q->token;
    g->lease_offset = q->offset;
    g->lease_length = q->length;
    g->pending = true;
    dma_wmb();
    mutex_unlock(&pz.lock);
    ret = copy_to_user(arg, q, sizeof(*q)) ? -EFAULT : 0;
    mutex_lock(&pz.lock);
    if (!ret)
        ret = live(g);
    if (!ret && !g->exported)
        ret = -EBADF;
    g->pending = false;
    if (ret)
        g->token = 0;
    mutex_unlock(&pz.lock);
    return ret;
}

static long pz_ioctl(struct file *file, unsigned int cmd, unsigned long value)
{
    struct pz_generation *g = file->private_data;
    void __user *arg = (void __user *)value;
    union { struct pz_dma_op op; struct pz_export_rx exp; struct pz_lease lease; } q;
    int ret;

    memset(&q, 0, sizeof(q));
    /* All faultable input/output usercopy is outside pz.lock. */
    switch (cmd) {
    case PZ_MAP: case PZ_H2F: case PZ_F2H:
        if (copy_from_user(&q.op, arg, sizeof(q.op)))
            return -EFAULT;
        break;
    case PZ_UNMAP:
        if (get_user(q.op.cmd, &((struct pz_dma_op __user *)arg)->cmd))
            return -EFAULT;
        break;
    case PZ_EXPORT_RX:
        if (copy_from_user(&q.exp, arg, sizeof(q.exp)))
            return -EFAULT;
        if (q.exp.version != PZ_VERSION || q.exp.flags ||
            memchr_inv(q.exp.reserved, 0, sizeof(q.exp.reserved)))
            return -EINVAL;
        return export_rx(g);
    case PZ_BEGIN: case PZ_END:
        if (copy_from_user(&q.lease, arg, sizeof(q.lease)))
            return -EFAULT;
        if (cmd == PZ_BEGIN)
            return lease_begin(g, &q.lease, arg);
        if (!lease_valid(&q.lease) || !q.lease.token)
            return -EINVAL;
        break;
    default:
        return -ENOTTY;
    }
    mutex_lock(&pz.lock);
    ret = live(g);
    if (ret)
        goto out;
    switch (cmd) {
    case PZ_MAP: ret = alloc_buffer(g, &q.op); break;
    case PZ_H2F: case PZ_F2H:
        ret = transfer(g, &q.op, cmd == PZ_F2H);
        break;
    case PZ_UNMAP:
        if (q.op.cmd != 0 && q.op.cmd != 1 && q.op.cmd != 3) {
            ret = -EINVAL;
            break;
        }
        if (g->pending || g->exported || g->mapped || g->token || cpu_busy(g)) {
            ret = -EBUSY;
            break;
        }
        if (q.op.cmd == 1 || q.op.cmd == 3) {
            if (g->pages_valid) {
                sg_free_table(&g->pages);
                g->pages_valid = false;
            }
            free_buffer(g, &g->rx);
            g->ready_length = 0;
        }
        if (q.op.cmd == 0 || q.op.cmd == 3)
            free_buffer(g, &g->tx);
        break;
    case PZ_END:
        if (g->pending || g->token != q.lease.token ||
            g->lease_offset != q.lease.offset || g->lease_length != q.lease.length) {
            ret = -EINVAL;
            break;
        }
        dma_rmb();
        g->token = 0;
        g->ready_length = 0;
        break;
    }
out:
    if (ret && (cmd == PZ_MAP || cmd == PZ_H2F || cmd == PZ_F2H))
        dev_err_ratelimited(g->allocator, "ioctl=%#x selector=%u bytes=%u failed: %d\n",
                            cmd, q.op.cmd, q.op.total_length, ret);
    mutex_unlock(&pz.lock);
    return ret;
}
#ifdef CONFIG_COMPAT
static long pz_compat_ioctl(struct file *f, unsigned int cmd, unsigned long arg)
{
    return pz_ioctl(f, cmd, (unsigned long)compat_ptr(arg));
}
#endif
static int pz_open(struct inode *inode, struct file *file)
{
    struct pz_generation *g;
    int ret = 0;
    mutex_lock(&pz.lock);
    if (pz.dead || !pz.pdev || pz.faulted) { ret = -ENODEV; goto out; }
    if (pz.gen) { ret = -EBUSY; goto out; }
    g = kzalloc(sizeof(*g), GFP_KERNEL);
    if (!g) { ret = -ENOMEM; goto out; }
    kref_init(&g->refs);
    __module_get(THIS_MODULE);
    g->allocator = get_device(&pz.pdev->dev);
    g->owned = true;
    pz.gen = g;
    file->private_data = g;
out:
    mutex_unlock(&pz.lock);
    return ret;
}
static int pz_release(struct inode *inode, struct file *file)
{
    struct pz_generation *g = file->private_data;
    mutex_lock(&pz.lock);
    if (g->token || g->pending || cpu_busy(g) || atomic_read(&pz.active))
        quarantine(g);
    g->owned = false;
    gen_put(g);
    mutex_unlock(&pz.lock);
    return 0;
}
static int pz_mmap(struct file *file, struct vm_area_struct *vma)
{
    struct pz_generation *g = file->private_data;
    struct pz_buffer *b;
    int ret;
    mutex_lock(&pz.lock);
    ret = live(g);
    if (ret)
        goto out;
    if (vma->vm_pgoff == 0)
        b = &g->tx;
    else if (vma->vm_pgoff == PZ_RX_MMAP_OFFSET / PAGE_SIZE)
        b = &g->rx;
    else { ret = -EINVAL; goto out; }
    vma->vm_pgoff = 0;
    ret = map_coherent(g, b, vma, file);
out:
    if (ret)
        dev_err_ratelimited(g->allocator, "device mmap bytes=%lu failed: %d\n",
                            vma->vm_end - vma->vm_start, ret);
    mutex_unlock(&pz.lock);
    return ret;
}
static const struct file_operations pz_fops = {
    .owner = THIS_MODULE, .open = pz_open, .release = pz_release,
    .unlocked_ioctl = pz_ioctl, .mmap = pz_mmap, .llseek = no_llseek,
#ifdef CONFIG_COMPAT
    .compat_ioctl = pz_compat_ioctl,
#endif
};

static int pz_probe(struct pci_dev *dev, const struct pci_device_id *id)
{
    void __iomem *bar;
    int ret, irqs = 0;
    mutex_lock(&pz.lock);
    if (pz.pdev || pz.gen || pz.faulted) { ret = -EBUSY; goto out; }
    ret = pci_enable_device_mem(dev);
    if (ret)
        goto out;
    ret = dma_set_mask_and_coherent(&dev->dev, DMA_BIT_MASK(32));
    if (ret)
        goto disable;
    if (!(pci_resource_flags(dev, PZ_BAR) & IORESOURCE_MEM) ||
        pci_resource_len(dev, PZ_BAR) < PZ_TOTAL + sizeof(u32)) {
        ret = -ENODEV;
        goto disable;
    }
    ret = pci_request_region(dev, PZ_BAR, PZ_NAME);
    if (ret)
        goto disable;
    bar = pci_iomap(dev, PZ_BAR, 0);
    if (!bar) { ret = -ENOMEM; goto region; }
    /* Conventional MSI allocates a power of two: vectors 0..2 need four. */
    ret = pci_alloc_irq_vectors(dev, 3, 4, PCI_IRQ_MSI);
    if (ret < 0)
        goto iomap;
    ret = request_irq(pci_irq_vector(dev, 0), dma_irq, 0, PZ_NAME, dev);
    if (ret)
        goto vectors;
    irqs++;
    ret = request_irq(pci_irq_vector(dev, 1), event_irq, 0, PZ_NAME, dev);
    if (ret)
        goto irq;
    irqs++;
    ret = request_irq(pci_irq_vector(dev, 2), event_irq, 0, PZ_NAME, dev);
    if (ret)
        goto irq;
    pci_set_master(dev);
    pz.pdev = dev;
    pz.bar = bar;
    WRITE_ONCE(pz.dead, false);
    ret = 0;
    goto out;
irq:
    while (irqs)
        free_irq(pci_irq_vector(dev, --irqs), dev);
vectors:
    pci_free_irq_vectors(dev);
iomap:
    pci_iounmap(dev, bar);
region:
    pci_release_region(dev, PZ_BAR);
disable:
    pci_disable_device(dev);
out:
    mutex_unlock(&pz.lock);
    return ret;
}
static void pz_remove(struct pci_dev *dev)
{
    WRITE_ONCE(pz.dead, true);
    complete_all(&pz.done);
    mutex_lock(&pz.lock);
    pci_clear_master(dev);
    if (pz.gen && (pz.gen->rx.cpu || pz.gen->tx.cpu))
        quarantine(pz.gen); /* allocator domain may disappear; retain RAM */
    free_irq(pci_irq_vector(dev, 2), dev);
    free_irq(pci_irq_vector(dev, 1), dev);
    free_irq(pci_irq_vector(dev, 0), dev);
    pci_free_irq_vectors(dev);
    pci_iounmap(dev, pz.bar);
    pz.bar = NULL;
    pci_release_region(dev, PZ_BAR);
    pci_disable_device(dev);
    pz.pdev = NULL;
    mutex_unlock(&pz.lock);
}
static struct pci_device_id pz_ids[] = {
    { .subvendor = PCI_ANY_ID, .subdevice = PCI_ANY_ID }, { 0 },
};
static struct pci_driver pz_driver = {
    .name = "pango_zc", .id_table = pz_ids, .probe = pz_probe, .remove = pz_remove,
};
static int __init pz_init(void)
{
    int ret;
    BUILD_BUG_ON(sizeof(struct pz_dma_op) != 20);
    BUILD_BUG_ON(sizeof(struct pz_export_rx) != 16);
    BUILD_BUG_ON(sizeof(struct pz_lease) != 40);
    if (!vendor_id || !device_id || vendor_id >= 0xffff || device_id >= 0xffff)
        return -EINVAL;
    pz_ids[0].vendor = vendor_id;
    pz_ids[0].device = device_id;
    mutex_init(&pz.lock);
    init_completion(&pz.done);
    atomic_set(&pz.active, 0);
    pz.dead = true;
    ret = alloc_chrdev_region(&pz.devt, 0, 1, PZ_NAME);
    if (ret)
        return ret;
    cdev_init(&pz.cdev, &pz_fops);
    pz.cdev.owner = THIS_MODULE;
    ret = cdev_add(&pz.cdev, pz.devt, 1);
    if (ret)
        goto devt;
    pz.class = class_create(THIS_MODULE, PZ_NAME);
    if (IS_ERR(pz.class)) { ret = PTR_ERR(pz.class); goto cdev; }
    pz.node = device_create(pz.class, NULL, pz.devt, NULL, PZ_NAME);
    if (IS_ERR(pz.node)) { ret = PTR_ERR(pz.node); goto class; }
    ret = pci_register_driver(&pz_driver);
    if (!ret)
        return 0;
    device_destroy(pz.class, pz.devt);
class:
    class_destroy(pz.class);
cdev:
    cdev_del(&pz.cdev);
devt:
    unregister_chrdev_region(pz.devt, 1);
    return ret;
}
static void __exit pz_exit(void)
{
    pci_unregister_driver(&pz_driver);
    device_destroy(pz.class, pz.devt);
    class_destroy(pz.class);
    cdev_del(&pz.cdev);
    unregister_chrdev_region(pz.devt, 1);
}
module_init(pz_init);
module_exit(pz_exit);
MODULE_IMPORT_NS(DMA_BUF);
MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("Pango coherent RX DMA-BUF for completion-fixed FPGA and RKNN input");
MODULE_VERSION("1.0");
