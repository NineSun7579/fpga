
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
typedef uint32_t u32; typedef uint64_t u64; typedef uint64_t dma_addr_t;
#define __user
#define PAGE_SIZE 4096
#define U64_MAX UINT64_MAX
#define PZ_VERSION 1
#define PZ_BUFFER_BYTES 0x800000
#define PZ_INPUT_OFFSET 0x400000
#define PZ_INPUT_BYTES 1228800
#define PZ_MVP_INPUT_BYTES 921600
#define PZ_TIMEOUT_MS 1000
#define PZ_DDR 0
#define PZ_ADDR_LO 4
#define PZ_ADDR_HI 8
#define PZ_TOTAL 12
#define PZ_CMD 16
#define ERESTARTSYS 512
#define READ_ONCE(x) (x)
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define lower_32_bits(x) ((u32)(x))
struct pz_dma_op { u32 cmd, offset_addr, ddr3_addr, total_length, unused; };
struct pz_lease { u32 version, flags, offset, length; u64 token; u32 reserved[4]; };
struct pz_buffer { void *cpu; dma_addr_t dma; size_t size; };
struct pz_generation {
 struct pz_buffer tx,rx; bool pending,exported; u64 token;
 u32 lease_offset,lease_length,ready_offset,ready_length,cpu_access[3];
};
static struct { int lock,active,done; bool dead; void *pdev; char *bar; u64 next_token; } pz;
static int writes, copy_fault, completion_result=1;
static int live(struct pz_generation *g) { (void)g; return 0; }
static void mutex_lock(int *x) { assert(!*x); *x=1; }
static void mutex_unlock(int *x) { assert(*x); *x=0; }
static void dma_wmb(void) {} static void dma_rmb(void) {}
static int pci_irq_vector(void *p,int n) { (void)p; return n; }
static void synchronize_irq(int n) { (void)n; assert(pz.lock); }
static void reinit_completion(int *x) { *x=0; }
static void atomic_set(int *x,int n) { *x=n; }
static int msecs_to_jiffies(int x) { return x; }
static void iowrite32(u32 x,void *p) { (void)x;(void)p; assert(pz.lock); ++writes; }
static long wait_for_completion_interruptible_timeout(int *x,int n) {
 (void)x;(void)n; assert(pz.lock); pz.active=0; return completion_result;
}
static void quarantine(struct pz_generation *g) { (void)g; }
static void *memchr_inv(const void *p,int c,size_t n) {
 const unsigned char *s=p; while(n--) { if(*s++ != c) return (void *)(s-1); } return NULL;
}
static int copy_to_user(void *dst,const void *src,size_t n) {
 if(copy_fault) return 1; memcpy(dst,src,n); return 0;
}
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
    /* pz.lock remains held through completion: BEGIN/END cannot cross DMA.
     * The NPU reads only its reserved RX slot. TX is a separate allocation;
     * disjoint RX writes preserve both that slot and producer readiness.
     * pending still excludes export/BEGIN usercopy publication windows. */
    if (g->pending || (rx && cpu_busy(g)) ||
        (rx && g->token && overlap(op->offset_addr, op->total_length,
                                  g->lease_offset, g->lease_length)))
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
    waited = wait_for_completion_interruptible_timeout(&pz.done,
                                            msecs_to_jiffies(PZ_TIMEOUT_MS));
    if (READ_ONCE(pz.dead) || waited <= 0) {
        quarantine(g);
        return READ_ONCE(pz.dead) ? -ENODEV : waited ? -ERESTARTSYS : -ETIMEDOUT;
    }
    dma_rmb();
    if (rx && op->offset_addr == PZ_INPUT_OFFSET &&
        (op->total_length == PZ_INPUT_BYTES ||
         op->total_length == PZ_MVP_INPUT_BYTES)) {
        g->ready_offset = op->offset_addr;
        /* MVP consumer reads only 921600 bytes; lease reserves the full slot. */
        g->ready_length = PZ_INPUT_BYTES;
    }
    return 0;
}

static bool lease_valid(const struct pz_lease *q)
{
    return q->version == PZ_VERSION && !q->flags &&
        !memchr_inv(q->reserved, 0, sizeof(q->reserved)) &&
        q->offset == PZ_INPUT_OFFSET && !(q->offset & (PAGE_SIZE - 1)) &&
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

static int end(struct pz_generation *g, struct pz_lease lease) {
int ret=0; struct { struct pz_lease lease; } q={lease}; mutex_lock(&pz.lock); switch(0) {
    case 0:
        if (g->pending || g->token != q.lease.token ||
            g->lease_offset != q.lease.offset || g->lease_length != q.lease.length) {
            ret = -EINVAL;
            break;
        }
        dma_rmb();
        g->token = 0;
        g->ready_length = 0;
        break;
} mutex_unlock(&pz.lock); return ret; }

static int dma(struct pz_generation *g,u32 off,u32 n,bool rx) {
 struct pz_dma_op op={.offset_addr=off,.total_length=n};
 mutex_lock(&pz.lock); int r=transfer(g,&op,rx); mutex_unlock(&pz.lock); return r;
}
int main(void) {
 char bar[32]; pz.bar=bar;
 struct pz_generation g={.tx={(void*)1,0x1000,4096},
 .rx={(void*)1,0x100000,0x800000},.exported=true};
 struct pz_lease q={.version=1,.offset=PZ_INPUT_OFFSET,.length=PZ_INPUT_BYTES}, out;
 assert(lease_begin(&g,&q,&out)==-ENODATA);
 assert(dma(&g,PZ_INPUT_OFFSET,PZ_MVP_INPUT_BYTES,true)==0);
 assert(g.ready_length==PZ_INPUT_BYTES);
 assert(dma(&g,0x3ff000,16,true)==0 && g.ready_length==PZ_INPUT_BYTES);
 assert(lease_begin(&g,&q,&out)==0 && out.token && !g.pending); q.token=0;
 for(int c=0;c<6;c++) assert(dma(&g,c*0x97000,614416,true)==0);
 assert(dma(&g,0,PZ_INPUT_OFFSET,true)==0);
 assert(dma(&g,PZ_INPUT_OFFSET+PZ_INPUT_BYTES,4,true)==0);
 assert(dma(&g,0,16,false)==0);
 assert(g.ready_length==PZ_INPUT_BYTES);
 int before=writes;
 assert(dma(&g,PZ_INPUT_OFFSET-4,8,true)==-EBUSY);
 assert(dma(&g,PZ_INPUT_OFFSET,4,true)==-EBUSY);
 assert(dma(&g,PZ_INPUT_OFFSET+PZ_MVP_INPUT_BYTES,4,true)==-EBUSY);
 assert(dma(&g,PZ_INPUT_OFFSET+PZ_INPUT_BYTES-4,8,true)==-EBUSY);
 assert(dma(&g,0,0x800000,true)==-EBUSY && writes==before);
 g.pending=true;
 assert(dma(&g,0,16,false)==-EBUSY && dma(&g,0,16,true)==-EBUSY);
 assert(end(&g,out)==-EINVAL && g.token==out.token); g.pending=false;
 struct pz_lease wrong=out; wrong.token++;
 assert(end(&g,wrong)==-EINVAL && g.token==out.token);
 wrong=out; wrong.length-=4;
 assert(end(&g,wrong)==-EINVAL && g.token==out.token);
 assert(end(&g,out)==0 && !g.token && !g.ready_length);
 assert(end(&g,out)==-EINVAL);
 assert(lease_begin(&g,&q,&out)==-ENODATA);
 assert(dma(&g,PZ_INPUT_OFFSET,PZ_INPUT_BYTES,true)==0);
 assert(dma(&g,PZ_INPUT_OFFSET-4,8,true)==0 && !g.ready_length);
 assert(lease_begin(&g,&q,&out)==-ENODATA);
 assert(dma(&g,PZ_INPUT_OFFSET,PZ_MVP_INPUT_BYTES,true)==0);
 g.cpu_access[0]=1;
 assert(dma(&g,0,16,true)==-EBUSY);
 assert(lease_begin(&g,&q,&out)==-EBUSY); g.cpu_access[0]=0;
 copy_fault=1;
 assert(lease_begin(&g,&q,&out)==-EFAULT && !g.token && !g.pending);
 puts("actual driver transfer/BEGIN/END: disjoint boundaries, full reserve, pending, wrong lease, readiness, CPU guard PASS");
}
