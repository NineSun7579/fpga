"""Compile actual driver lease/transfer functions against host syscall stubs.

Tests admission/arithmetic/state transitions, not IRQ, DMA or hardware behavior.
Run with python3 on a host with gcc; no device access.
"""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
source = (root / 'pango_zc.c').read_bytes().decode('ascii')
def section(start, end):
    return source[source.index(start):source.index(end)]

prefix = r'''
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
'''
actual = section('static bool range_ok(', 'static int live(')
actual += section('static int transfer(', 'static int get_pages(')
actual += section('static bool lease_valid(', 'static long pz_ioctl(')
end_case = section('    case PZ_END:\n', '    }\nout:')
actual += 'static int end(struct pz_generation *g, struct pz_lease lease) {\n'
actual += 'int ret=0; struct { struct pz_lease lease; } q={lease}; mutex_lock(&pz.lock); switch(0) {\n'
actual += end_case.replace('case PZ_END:', 'case 0:')
actual += '} mutex_unlock(&pz.lock); return ret; }\n'
tests = r'''
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
'''
build = root / 'local_build'
build.mkdir(exist_ok=True)
unit = build / 'concurrency.c'
unit.write_text(prefix + actual + tests)
binary = build / 'concurrency_test'
subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Wno-misleading-indentation', str(unit), '-o', str(binary)], check=True)
subprocess.run([str(binary)], check=True)
