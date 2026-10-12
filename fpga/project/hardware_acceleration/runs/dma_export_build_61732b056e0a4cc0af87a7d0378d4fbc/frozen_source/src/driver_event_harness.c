/* SPDX-License-Identifier: GPL-2.0-only */
/* Executes byte-extracted candidate functions with event/lock/resource mocks.
 * Fake proof/backend switches exercise transactions ONLY, not kernel DMA. */
#define _GNU_SOURCE
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include "pango_dma_uapi.h"
#include "pango_policy.h"

_Static_assert(sizeof(struct pango_export_slot_v1) == 48, "export ABI size");
_Static_assert(sizeof(struct pango_slot_lease_v1) == 48, "lease ABI size");
_Static_assert(offsetof(struct pango_export_slot_v1, generation) == 24, "export ABI alignment");
_Static_assert(offsetof(struct pango_slot_lease_v1, token) == 16, "lease ABI alignment");
_Static_assert(PCI_MAP_ADDR_CMD == 0xc0045302U, "legacy command size");
_Static_assert(PANGO_EXPORT_SLOT_V1 == 0xc0305320U, "export command size");

typedef uint64_t u64;
typedef uint32_t u32;
typedef uint64_t dma_addr_t;
#define __user
#define GFP_KERNEL 0
#define PAGE_SIZE 4096UL
#define PAGE_ALIGN(x) (((x) + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1))
#define VM_SHARED 1UL
#define VM_DONTEXPAND 2UL
#define VM_DONTDUMP 4UL
#define U64_MAX UINT64_MAX
#define ERESTARTSYS 512
#define PANGO_DMA_TIMEOUT_MS 120U
#define PANGO_MAX_TLP 4096U
#define PANGO_CMD 0x100
#define PANGO_ADDR_LO 0x110
#define PANGO_ADDR_HI 0x120
#define PANGO_DDR 0x1e0
#define PANGO_TOTAL 0x200
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#define min(a, b) ((a) < (b) ? (a) : (b))
#define lower_32_bits(x) ((u32)(x))
#define check_add_overflow(a, b, result) __builtin_add_overflow(a, b, result)
#define READ_ONCE(x) (x)
#define WARN_ON(x) assert(!(x))
#define container_of(p, t, member) ((t *)((char *)(p) - offsetof(t, member)))
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define PTR_ERR(x) ((int)(intptr_t)(x))
#define IS_ERR(x) ((uintptr_t)(x) >= (uintptr_t)-4095)

struct mutex { int held; };
struct kref { int count; };
struct device { int dummy; unsigned long *dma_mask; };
struct pci_dev { int dummy; };
struct sg_table { unsigned int orig_nents; };
struct list_head { struct list_head *next, *prev; };
enum dma_data_direction { DMA_BIDIRECTIONAL, DMA_TO_DEVICE, DMA_FROM_DEVICE, DMA_NONE };
struct dma_buf;
struct file { void *private_data; struct dma_buf *buf; };
struct dma_buf { struct file *file; void *priv; };
struct dma_buf_attachment { struct dma_buf *dmabuf; struct device *dev; void *priv; unsigned long dma_map_attrs; };
struct vm_operations_struct { int dummy; };
struct vm_area_struct {
    unsigned long vm_flags, vm_pgoff, vm_end, vm_start;
    const struct vm_operations_struct *vm_ops;
    void *vm_private_data;
};
struct dma_buf_ops { int dummy; };
struct dma_buf_export_info { const struct dma_buf_ops *ops; size_t size; int flags; void *priv; };
#define DEFINE_DMA_BUF_EXPORT_INFO(name) struct dma_buf_export_info name = {0}

/* All resource-bearing structs below are extracted from the candidate bytes. */
#include "extracted_types.h"
static struct {
    struct mutex lock;
    struct pci_dev *pdev;
    unsigned char *bar;
    struct pango_generation *gen;
    bool dead, faulted;
    u64 next_token;
    int active, done;
} pango;
static const struct vm_operations_struct pango_vm_ops = {0};
static const struct dma_buf_ops pango_buf_ops = {0};
static struct device device;
static struct pci_dev pci;
static struct pango_generation generation;
static struct file owner;
static unsigned char bar[0x300];
static int proof, backend, input_fail, output_fail, export_fail, sync_fail, mutate_input;
static int core_event, output_event, reserved_fd, core_refs, writes, copies_in, copies_out;
static dma_addr_t allocation_address;
static struct dma_buf *installed;
#define PANGO_EXPORT_PROVEN proof /* mock TU ONLY; production source stays 0 */

static int pango_mmap(struct file *, struct vm_area_struct *);
static long pango_ioctl(struct file *, unsigned int, unsigned long);
static void pango_buf_release(struct dma_buf *);
static int pango_unmap_legacy(struct pango_generation *, unsigned int);
static int pango_transfer(struct pango_generation *, const DMA_OPERATION *, bool);
static void mutex_lock(struct mutex *m) { assert(!m->held); m->held = 1; }
static void mutex_unlock(struct mutex *m) { assert(m->held); m->held = 0; }
static int mutex_lock_interruptible(struct mutex *m) { mutex_lock(m); return 0; }
#define lockdep_assert_held(m) assert((m)->held)
static void kref_get(struct kref *ref) { assert(pango.lock.held); ++ref->count; }
static void pango_gen_put(struct pango_generation *g)
{
    assert(pango.lock.held && g->refs.count > 1);
    --g->refs.count; /* owner reference is deliberately kept by this harness */
}
static void pango_quarantine(struct pango_generation *g)
{
    assert(pango.lock.held);
    pango.faulted = true;
    if (!g->quarantined) { g->quarantined = true; kref_get(&g->refs); }
}
static int atomic_read(int *v) { return *v; }
static void atomic_set(int *v, int value) { *v = value; }
static int pci_irq_vector(struct pci_dev *p, int vector) { (void)p; return vector; }
static void synchronize_irq(int irq) { (void)irq; assert(pango.lock.held); }
static void reinit_completion(int *completion) { *completion = 0; }
static unsigned int msecs_to_jiffies(unsigned int ms) { return ms; }
static long wait_for_completion_interruptible_timeout(int *done, unsigned int ms)
{
    (void)ms;
    assert(pango.lock.held);
    *done = 1;
    pango.active = 0;
    return 1;
}
static void dma_wmb(void) { assert(pango.lock.held); }
static void dma_rmb(void) { assert(pango.lock.held); }
static void iowrite32(u32 value, void *address)
{
    assert(pango.lock.held);
    ++writes;
    memcpy(address, &value, sizeof(value));
}
static void *kzalloc(size_t bytes, int flags) { (void)flags; return calloc(1, bytes); }
static void kfree(void *p) { free(p); }
static void *dma_alloc_coherent(struct device *dev, size_t bytes, dma_addr_t *addr, int flags)
{
    (void)dev; (void)flags;
    assert(pango.lock.held);
    *addr = allocation_address;
    return calloc(1, bytes);
}
static void dma_free_coherent(struct device *dev, size_t bytes, void *cpu, dma_addr_t addr)
{
    (void)dev; (void)bytes; (void)addr;
    assert(pango.lock.held);
    free(cpu);
}
static void sg_free_table(struct sg_table *sgt) { sgt->orig_nents = 0; }
static void INIT_LIST_HEAD(struct list_head *head) { head->next = head->prev = head; }
static int list_empty(const struct list_head *head) { return head->next == head; }
static void list_add_tail(struct list_head *node, struct list_head *head)
{ node->next = head; node->prev = head->prev; head->prev->next = node; head->prev = node; }
static int pango_get_pages(struct pango_generation *g) { g->rx.pages_valid = true; return 0; }
static int pango_slice_pages(struct pango_buffer *b, unsigned int offset,
                             unsigned int length, struct sg_table *sgt)
{ (void)b; (void)offset; sgt->orig_nents = length / PAGE_SIZE; return 0; }
static int dma_mmap_coherent(struct device *dev, struct vm_area_struct *vma,
                              void *cpu, dma_addr_t addr, size_t bytes)
{ (void)dev; (void)vma; (void)cpu; (void)addr; (void)bytes; assert(pango.lock.held); return 0; }

/* Actual production readiness and handoff/map stubs are tested separately. */
#define pango_import_backend_ready pango_production_backend_ready
#define pango_sync_slot pango_production_sync_slot
#include "extracted_backend.h"
#undef pango_import_backend_ready
#undef pango_sync_slot
static bool pango_import_backend_ready(void) { return backend != 0; }
static int pango_sync_slot(struct pango_generation *g, unsigned int slot, bool gpu)
{ (void)g; (void)slot; (void)gpu; assert(pango.lock.held); return sync_fail ? -EOPNOTSUPP : 0; }

static void fault_mmap_probe(bool pending)
{
    struct vm_area_struct vma = {.vm_flags = VM_SHARED, .vm_pgoff = RX_MMAP_OFFSET / PAGE_SIZE,
                                .vm_start = PAGE_SIZE, .vm_end = 2 * PAGE_SIZE};
    int ret;
    /* Simulates a userfault/reclaim path acquiring mmap_lock before driverlock. */
    assert(!pango.lock.held);
    ret = pango_mmap(&owner, &vma);
    if (pending) {
        assert(ret == -EBUSY || ret == -ENODEV || ret == -EIO);
    } else if (!ret) {
        --generation.vmas;
        --generation.refs.count; /* end the mock VMA, balancing the actual mmap pin */
    }
    assert(!pango.lock.held);
}
static void pending_probe(void)
{
    DMA_OPERATION op = {.offset_addr = PANGO_SLOT_STRIDE, .total_length = 4};
    assert(!pango.lock.held && generation.refs.count >= 2);
    fault_mmap_probe(true);
    mutex_lock(&pango.lock);
    assert(pango_unmap_legacy(&generation, 3) == -EBUSY);
    assert(pango_transfer(&generation, &op, true) == -EBUSY);
    assert(pango_transfer(&generation, &op, false) == -EBUSY);
    mutex_unlock(&pango.lock);
}
static unsigned long copy_from_user(void *dst, const void *src, size_t bytes)
{
    assert(!pango.lock.held);
    ++copies_in;
    fault_mmap_probe(false);
    if (input_fail) return bytes;
    memcpy(dst, src, bytes);
    if (mutate_input && bytes == 5 * sizeof(unsigned int))
        ((DMA_OPERATION *)src)->total_length = 0; /* snapshot must stay immutable */
    return 0;
}
static unsigned long copy_to_user(void *dst, const void *src, size_t bytes)
{
    assert(!pango.lock.held);
    ++copies_out;
    pending_probe();
    if (output_event == 1) pango.dead = true;
    if (output_event == 2 && installed) {
        struct dma_buf *buf = installed;
        installed = NULL;
        assert(!pango.lock.held);
        pango_buf_release(buf);
        free(buf->file); free(buf); --core_refs;
    }
    if (output_fail) return bytes;
    memcpy(dst, src, bytes);
    return 0;
}
static int get_unused_fd_flags(int flags) { assert(!pango.lock.held && flags == O_CLOEXEC); assert(!reserved_fd); reserved_fd = 10; return 10; }
static void put_unused_fd(int fd) { assert(!pango.lock.held && fd == reserved_fd); reserved_fd = 0; }
static void fd_install(int fd, struct file *file)
{ assert(!pango.lock.held && fd == reserved_fd); assert(!generation.export_pending); installed = file->buf; reserved_fd = 0; }
static struct dma_buf *dma_buf_export(const struct dma_buf_export_info *info)
{
    struct dma_buf *buf;
    assert(!pango.lock.held); /* registry/debugfs/resv -> map -> driver lock */
    pending_probe();
    if (core_event == 1) pango.dead = true;
    if (export_fail) return ERR_PTR(-ENOMEM);
    buf = calloc(1, sizeof(*buf));
    buf->file = calloc(1, sizeof(*buf->file));
    buf->file->buf = buf; buf->priv = info->priv; ++core_refs;
    return buf;
}
static void dma_buf_put(struct dma_buf *buf)
{ assert(!pango.lock.held); pango_buf_release(buf); free(buf->file); free(buf); --core_refs; }

/* Tested ioctl/transfer/mmap/resource functions are extracted unchanged. */
#include "extracted_driver.h"

static void reset(void)
{
    assert(!pango.lock.held && !reserved_fd && !core_refs && !installed);
    free(generation.rx.cpu); free(generation.tx.cpu);
    memset(&generation, 0, sizeof(generation)); memset(&pango, 0, sizeof(pango));
    memset(bar, 0, sizeof(bar));
    generation.refs.count = 1; generation.id = 1; generation.owned = true;
    generation.alloc_dev = &device;
    generation.tx.cpu = calloc(1, PAGE_SIZE); generation.tx.size = PAGE_SIZE;
    generation.rx.cpu = calloc(1, PANGO_RX_BYTES); generation.rx.size = PANGO_RX_BYTES;
    generation.tx.dma = 0x1000000; generation.rx.dma = 0x2000000;
    pango.pdev = &pci; pango.gen = &generation; pango.bar = bar;
    owner.private_data = &generation;
    proof = backend = input_fail = output_fail = export_fail = sync_fail = mutate_input = 0;
    core_event = output_event = writes = copies_in = copies_out = 0;
    allocation_address = 0x1000000;
}
static struct pango_export_slot_v1 request(void)
{ struct pango_export_slot_v1 r = {.version = 1, .slot = 0, .fd = -1}; return r; }
static void close_installed(void)
{ struct dma_buf *buf = installed; installed = NULL; dma_buf_put(buf); }
static void fake_export(void)
{
    struct pango_export_slot_v1 r = request();
    proof = backend = 1;
    assert(pango_ioctl(&owner, PANGO_EXPORT_SLOT_V1, (unsigned long)&r) == 0);
    assert(r.fd == 10 && r.length == PANGO_SLOT_BYTES && r.generation == 1);
    assert(generation.exports == 1 && generation.refs.count == 2);
}

int main(void)
{
    unsigned int commands[] = {PCI_MAP_ADDR_CMD, PCI_DMA_READ_CMD, PCI_DMA_WRITE_CMD, PCI_UMAP_ADDR_CMD};
    unsigned int i, rx;
    DMA_OPERATION op;
    struct pango_export_slot_v1 r;
    struct pango_slot_lease_v1 lease;
    struct dma_buf_attachment att;
    struct pango_attachment attachment = {.dev = &device};

    reset();
    assert(!pango_production_backend_ready());
    assert(pango_backend_map(&device, &generation.rx.pages, DMA_TO_DEVICE) == -EOPNOTSUPP);
    assert(pango_production_sync_slot(&generation, 0, true) == -EOPNOTSUPP);
    assert(pango_production_sync_slot(&generation, 0, false) == -EOPNOTSUPP);
    for (i = 0; i < ARRAY_SIZE(commands); ++i) {
        memset(&op, 0, sizeof(op)); op.total_length = 4;
        input_fail = 1;
        assert(pango_ioctl(&owner, commands[i], (unsigned long)&op) == -EFAULT);
        assert(!pango.lock.held && !writes);
        input_fail = 0;
    }
    assert(copies_in == 4);
    assert(pango_ioctl(&owner, 0, 0) == -ENOTTY && copies_in == 4);
    memset(&op, 0, sizeof(op)); op.total_length = 4; mutate_input = 1;
    assert(pango_ioctl(&owner, PCI_DMA_READ_CMD, (unsigned long)&op) == 0);
    assert(op.total_length == 0 && *(u32 *)(bar + PANGO_TOTAL) == 4);
    mutate_input = 0; writes = 0;
    for (rx = 0; rx < 2; ++rx) {
        struct pango_buffer *b = rx ? &generation.rx : &generation.tx;
        unsigned int cmd = rx ? PCI_DMA_WRITE_CMD : PCI_DMA_READ_CMD;
        b->dma = 0x100000000ULL;
        memset(&op, 0, sizeof(op)); op.total_length = 4;
        assert(pango_ioctl(&owner, cmd, (unsigned long)&op) == -EOVERFLOW);
        b->dma = 0xfffffffcULL; op.total_length = 8;
        assert(pango_ioctl(&owner, cmd, (unsigned long)&op) == -EOVERFLOW);
        assert(!writes && !pango.active);
        op.total_length = 4;
        assert(pango_ioctl(&owner, cmd, (unsigned long)&op) == 0);
        assert(*(u32 *)(bar + PANGO_ADDR_HI) == 0);
        assert(!(*(u32 *)(bar + PANGO_CMD) & (1U << 16)));
        writes = 0;
    }
    reset();
    memset(&op, 0, sizeof(op)); op.cmd = 3;
    assert(pango_ioctl(&owner, PCI_UMAP_ADDR_CMD, (unsigned long)&op) == 0);
    op.cmd = 0; op.total_length = PAGE_SIZE;
    allocation_address = 0x100000000ULL;
    assert(pango_ioctl(&owner, PCI_MAP_ADDR_CMD, (unsigned long)&op) == -EOVERFLOW);
    assert(!generation.tx.cpu);
    allocation_address = 0xfffff000ULL;
    op.total_length = PAGE_SIZE + 4;
    assert(pango_ioctl(&owner, PCI_MAP_ADDR_CMD, (unsigned long)&op) == -EOVERFLOW);
    assert(!generation.tx.cpu);

    reset();
    r = request();
    assert(pango_ioctl(&owner, PANGO_EXPORT_SLOT_V1, (unsigned long)&r) == -EOPNOTSUPP);
    proof = 1;
    assert(pango_ioctl(&owner, PANGO_EXPORT_SLOT_V1, (unsigned long)&r) == -EOPNOTSUPP);
    backend = 1; export_fail = 1;
    assert(pango_ioctl(&owner, PANGO_EXPORT_SLOT_V1, (unsigned long)&r) == -ENOMEM);
    assert(!generation.export_pending && generation.refs.count == 1 && !reserved_fd);
    export_fail = 0; output_fail = 1;
    assert(pango_ioctl(&owner, PANGO_EXPORT_SLOT_V1, (unsigned long)&r) == -EFAULT);
    assert(!generation.export_pending && !generation.exports && generation.refs.count == 1 && !core_refs);
    output_fail = 0; core_event = 1;
    assert(pango_ioctl(&owner, PANGO_EXPORT_SLOT_V1, (unsigned long)&r) == -ENODEV);
    assert(!generation.export_pending && generation.refs.count == 1 && !core_refs);
    pango.dead = false; core_event = 0; output_event = 1;
    assert(pango_ioctl(&owner, PANGO_EXPORT_SLOT_V1, (unsigned long)&r) == -ENODEV);
    assert(!generation.export_pending && !generation.exports && !core_refs);

    reset(); fake_export();
    memset(&att, 0, sizeof(att)); att.dmabuf = installed; att.dev = &device;
    assert(PTR_ERR(pango_buf_map(&att, DMA_BIDIRECTIONAL)) == -EOPNOTSUPP);
    assert(PTR_ERR(pango_buf_map(&att, DMA_FROM_DEVICE)) == -EOPNOTSUPP);
    backend = 0;
    assert(PTR_ERR(pango_buf_map(&att, DMA_TO_DEVICE)) == -EOPNOTSUPP);
    backend = 1;
    att.priv = &attachment;
    assert(PTR_ERR(pango_buf_map(&att, DMA_TO_DEVICE)) == -EOPNOTSUPP);
    assert(!attachment.maps); /* even mock readiness cannot make production map succeed */
    lease = (struct pango_slot_lease_v1){.version = 1, .slot = 0, .generation = 1};
    output_fail = 1;
    assert(pango_ioctl(&owner, PANGO_SLOT_BEGIN_V1, (unsigned long)&lease) == -EFAULT);
    assert(!generation.begin_pending && !generation.lease_mask && generation.refs.count == 2);
    output_fail = 0;
    assert(pango_ioctl(&owner, PANGO_SLOT_BEGIN_V1, (unsigned long)&lease) == 0);
    assert(lease.token && !generation.begin_pending && generation.lease_mask == 1 && generation.refs.count == 2);
    sync_fail = 1;
    assert(pango_ioctl(&owner, PANGO_SLOT_END_V1, (unsigned long)&lease) == -EOPNOTSUPP);
    assert(generation.lease_mask == 1);
    sync_fail = 0;
    assert(pango_ioctl(&owner, PANGO_SLOT_END_V1, (unsigned long)&lease) == 0);
    close_installed();

    reset(); fake_export();
    lease = (struct pango_slot_lease_v1){.version = 1, .slot = 0, .generation = 1};
    output_event = 2;
    assert(pango_ioctl(&owner, PANGO_SLOT_BEGIN_V1, (unsigned long)&lease) == -ENXIO);
    assert(!generation.begin_pending && !generation.lease_mask && generation.refs.count == 1 && !core_refs);
    reset(); fake_export();
    lease = (struct pango_slot_lease_v1){.version = 1, .slot = 0, .generation = 1};
    output_event = 1;
    assert(pango_ioctl(&owner, PANGO_SLOT_BEGIN_V1, (unsigned long)&lease) == -ENODEV);
    assert(!generation.begin_pending && !generation.lease_mask && generation.refs.count == 2);
    close_installed();
    reset();
    free(generation.tx.cpu); free(generation.rx.cpu);
    puts("Extracted driver event checks passed: usercopy/publication unlocked; pending rollback; DMA32; backend rejection");
    return 0;
}
