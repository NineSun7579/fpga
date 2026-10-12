#pragma once
#include "prepared/sdk/rknn_api.h"
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <functional>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include <fcntl.h>
#include <linux/dma-buf.h>
#if __has_include(<linux/dma-heap.h>)
#include <linux/dma-heap.h>
#else
// Stable Linux DMA-heap UAPI for vendor kernels with older userspace headers.
// This describes only the kernel ioctl; all RKNN types come from its SDK.
struct dma_heap_allocation_data { uint64_t len; uint32_t fd; uint32_t fd_flags; uint64_t heap_flags; };
#define DMA_HEAP_IOCTL_ALLOC _IOWR('H', 0x0, struct dma_heap_allocation_data)
#endif
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

// External DMA-BUF ownership is not specified by the retained SDK. No flags or
// priv_data are modified. A separate, unused import must pass teardown ownership
// inspection before inference allocations are made. Hooks are for lifecycle
// tests only; they cannot establish DMA-heap/RKNN compatibility.
namespace DmaHeapImport {
constexpr unsigned MaxEintrAttempts = 8;
inline uint32_t alignedBytes(size_t bytes, long pageSize) {
    if (!bytes || pageSize <= 0 || bytes > UINT32_MAX)
        throw std::runtime_error("invalid DMA-heap size/page size");
    const uint64_t page = uint64_t(pageSize), value = uint64_t(bytes);
    if (page > UINT32_MAX || value > std::numeric_limits<uint64_t>::max() - (page - 1))
        throw std::runtime_error("DMA-heap page alignment overflow");
    const uint64_t rounded = ((value + page - 1) / page) * page;
    if (rounded < value || rounded > UINT32_MAX)
        throw std::runtime_error("page-aligned import exceeds uint32 SDK size");
    return uint32_t(rounded);
}
struct Identity {
    uint64_t device = 0, inode = 0;
    bool operator==(const Identity &other) const { return device == other.device && inode == other.inode; }
};
struct Operations {
    virtual ~Operations() = default;
    virtual long pageSize() = 0;
    virtual int allocate(uint32_t bytes) = 0;
    virtual void *map(int fd, uint32_t bytes) = 0;
    virtual bool identity(int fd, Identity &id) noexcept = 0;
    virtual bool mapped(void *address, uint32_t bytes) noexcept = 0;
    virtual int cpuSync(int fd, uint64_t flags) noexcept = 0; // 0 or negative errno
    virtual rknn_tensor_mem *import(rknn_context ctx, int fd, void *address, uint32_t bytes) = 0;
    virtual int destroyImport(rknn_context ctx, rknn_tensor_mem *memory) noexcept = 0;
    virtual int destroyContext(rknn_context ctx) noexcept = 0;
    virtual int unmap(void *address, uint32_t bytes) noexcept = 0;
    virtual int closeFd(int fd) noexcept = 0;
};
struct LinuxOperations final : Operations {
    decltype(&rknn_create_mem_from_fd) importer;
    decltype(&rknn_destroy_mem) destroyMemory;
    decltype(&rknn_destroy) destroy;
    LinuxOperations(decltype(importer) i, decltype(destroyMemory) m, decltype(destroy) d)
        : importer(i), destroyMemory(m), destroy(d) {}
    long pageSize() override { return sysconf(_SC_PAGESIZE); }
    int allocate(uint32_t bytes) override {
        const int heap = open("/dev/dma_heap/system", O_RDWR | O_CLOEXEC);
        if (heap < 0) throw std::runtime_error("open /dev/dma_heap/system errno=" + std::to_string(errno));
        dma_heap_allocation_data data{};
        data.len = bytes; data.fd_flags = O_RDWR | O_CLOEXEC; // heap_flags stays zero
        int rc = -1, saved = 0;
        for (unsigned attempt = 0; attempt < MaxEintrAttempts; ++attempt) {
            rc = ioctl(heap, DMA_HEAP_IOCTL_ALLOC, &data); saved = errno;
            if (!rc || saved != EINTR) break;
        }
        close(heap); // Never retry close: Linux may already have retired the FD.
        if (rc) throw std::runtime_error("DMA_HEAP_IOCTL_ALLOC errno=" + std::to_string(saved));
        if (data.fd > uint32_t(std::numeric_limits<int>::max()))
            throw std::runtime_error("DMA heap returned invalid FD");
        return int(data.fd);
    }
    void *map(int fd, uint32_t bytes) override {
        void *address = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        if (address == MAP_FAILED) throw std::runtime_error("DMA-heap mmap errno=" + std::to_string(errno));
        return address;
    }
    bool identity(int fd, Identity &id) noexcept override {
        struct stat st{};
        if (fcntl(fd, F_GETFD) < 0 || fstat(fd, &st)) return false;
        id = {uint64_t(st.st_dev), uint64_t(st.st_ino)}; return true;
    }
    bool mapped(void *address, uint32_t bytes) noexcept override {
        const long page = pageSize();
        if (!address || page <= 0) return false;
        // mincore checks presence without dereferencing a possibly removed map.
        try {
            std::vector<unsigned char> resident((uint64_t(bytes) + uint64_t(page) - 1) / uint64_t(page));
            return mincore(address, bytes, resident.data()) == 0;
        } catch (...) { return false; }
    }
    int cpuSync(int fd, uint64_t flags) noexcept override {
        dma_buf_sync sync{}; sync.flags = flags;
        return ioctl(fd, DMA_BUF_IOCTL_SYNC, &sync) == 0 ? 0 : -errno;
    }
    rknn_tensor_mem *import(rknn_context ctx, int fd, void *address, uint32_t bytes) override {
        return importer(ctx, int32_t(fd), address, bytes, int32_t(0));
    }
    int destroyImport(rknn_context ctx, rknn_tensor_mem *memory) noexcept override { return destroyMemory(ctx, memory); }
    int destroyContext(rknn_context ctx) noexcept override { return destroy(ctx); }
    int unmap(void *address, uint32_t bytes) noexcept override { return munmap(address, bytes); }
    int closeFd(int fd) noexcept override { return close(fd); }
};
struct SyncCount {
    uint64_t attempts = 0, success = 0, failures = 0, interrupted = 0;
    int lastRc = 0;
};
// Api and its imported sessions share this guard. A deferred runtime handle is
// intentionally never dlclosed; only process teardown releases it.
struct RuntimeLibraryLifetime {
    bool retainedUntilProcessTeardown = false;
    void defer() noexcept { retainedUntilProcessTeardown = true; }
    bool unload(void *library, int (*closeLibrary)(void *)) noexcept {
        if (!library || retainedUntilProcessTeardown) return false;
        closeLibrary(library);
        return true;
    }
};
struct OwnedBuffer {
    std::string role;
    int fd = -1;
    void *mapping = nullptr;
    uint32_t mappingBytes = 0;
    size_t nativeBytes = 0;
    Identity original{};
    bool identityKnown = false;
    rknn_tensor_mem *memory = nullptr;
    bool cpuActive = false;
    uint64_t cpuDirection = 0;
    SyncCount sync[4]; // START_READ, END_READ, START_WRITE, END_WRITE
    bool beforeFd = false, beforeMap = false, afterImportFd = false, afterImportMap = false;
    bool afterContextFd = false, afterContextMap = false;
    bool beforeInspected = false, afterImportInspected = false, afterContextInspected = false;
    bool destroyAttempted = false, unmapAttempted = false, closeAttempted = false;
    int destroyRc = 0, unmapRc = 0, closeRc = 0;
};
class MemorySessionOwnedRAII {
    Operations &ops;
    rknn_context &context;
    RuntimeLibraryLifetime &runtime;
    bool retired = false, cleanupOK = true, runUncertain = false, poisoned = false;
    void deferToProcessTeardown(const char *branch) noexcept {
        cleanupOK = false; poisoned = true; processTeardownOnly = true;
        retirementBranch = branch;
        retainedContext = context;
        context = 0; // Detach from generic Session: its destructor must do nothing.
        runtime.defer();
    }
    bool sameFd(const OwnedBuffer &b) noexcept {
        Identity current{};
        return b.identityKnown && ops.identity(b.fd, current) && current == b.original;
    }
    int sync(OwnedBuffer &b, uint64_t flags) noexcept {
        const bool write = (flags & DMA_BUF_SYNC_WRITE) != 0, end = (flags & DMA_BUF_SYNC_END) != 0;
        auto &count = b.sync[(write ? 2 : 0) + (end ? 1 : 0)];
        int rc = 0;
        for (unsigned attempt = 0; attempt < MaxEintrAttempts; ++attempt) {
            ++count.attempts; rc = ops.cpuSync(b.fd, flags); count.lastRc = rc;
            if (rc != -EINTR) break;
            ++count.interrupted;
        }
        if (rc == 0) ++count.success; else ++count.failures;
        return rc;
    }
public:
    std::vector<std::unique_ptr<OwnedBuffer>> buffers;
    bool processTeardownOnly = false, contextDestroyAttempted = false;
    rknn_context retainedContext = 0;
    const char *retirementBranch = "not_retired";
    int contextDestroyRc = 0;
    MemorySessionOwnedRAII(Operations &operations, rknn_context &ctx, RuntimeLibraryLifetime &lifetime)
        : ops(operations), context(ctx), runtime(lifetime) {}
    MemorySessionOwnedRAII(const MemorySessionOwnedRAII &) = delete;
    MemorySessionOwnedRAII &operator=(const MemorySessionOwnedRAII &) = delete;
    ~MemorySessionOwnedRAII() { retire(); }
    OwnedBuffer &allocate(size_t bytes, const std::string &role) {
        if (!context || retired || poisoned) throw std::runtime_error("DMA-heap session unavailable");
        buffers.push_back(std::make_unique<OwnedBuffer>());
        auto &b = *buffers.back(); b.role = role; b.nativeBytes = bytes;
        b.mappingBytes = alignedBytes(bytes, ops.pageSize());
        b.fd = ops.allocate(b.mappingBytes);
        if (!ops.identity(b.fd, b.original)) throw std::runtime_error("DMA-heap fcntl/fstat identity unavailable");
        b.identityKnown = true;
        b.mapping = ops.map(b.fd, b.mappingBytes);
        b.memory = ops.import(context, b.fd, b.mapping, b.mappingBytes);
        if (!b.memory) throw std::runtime_error("rknn_create_mem_from_fd returned null for " + role);
        validate(b);
        return b;
    }
    void validate(const OwnedBuffer &b) const {
        if (retired || poisoned || runUncertain)
            throw std::runtime_error("FD descriptor validation prohibited after retirement/failure/uncertain run");
        if (!b.mapping || !b.memory || b.memory->virt_addr != b.mapping || b.memory->fd != b.fd || b.memory->offset != 0 ||
            b.memory->size < b.nativeBytes || b.memory->size > b.mappingBytes)
            throw std::runtime_error("FD import pointer/fd/offset/size contract changed for " + b.role);
    }
    OwnedBuffer &find(rknn_tensor_mem *memory) {
        for (auto &b : buffers) if (b->memory == memory) return *b;
        throw std::runtime_error("unknown FD import memory");
    }
    void begin(OwnedBuffer &b, uint64_t direction) {
        if (retired || poisoned || runUncertain || b.cpuActive ||
            (direction != DMA_BUF_SYNC_READ && direction != DMA_BUF_SYNC_WRITE))
            throw std::runtime_error("unsafe DMA-BUF CPU START for " + b.role);
        const int rc = sync(b, DMA_BUF_SYNC_START | direction);
        if (rc) { poisoned = true; throw std::runtime_error("DMA-BUF START " + b.role + " rc=" + std::to_string(rc)); }
        b.cpuActive = true; b.cpuDirection = direction;
    }
    void end(OwnedBuffer &b) {
        if (!b.cpuActive) return;
        const int rc = sync(b, DMA_BUF_SYNC_END | b.cpuDirection);
        // A failed END remains active; retirement makes one bounded paired END
        // cleanup attempt. No subsequent run or fallback is allowed.
        if (rc) { poisoned = true; throw std::runtime_error("DMA-BUF END " + b.role + " rc=" + std::to_string(rc)); }
        b.cpuActive = false;
    }
    void cleanupEnd(OwnedBuffer &b) noexcept {
        if (!b.cpuActive) return;
        if (sync(b, DMA_BUF_SYNC_END | b.cpuDirection)) { cleanupOK = false; poisoned = true; }
        b.cpuActive = false; // bounded cleanup: never attempt another implicit END
    }
    void beforeRun() {
        if (poisoned || retired || runUncertain) throw std::runtime_error("DMA-heap session cannot run");
        for (const auto &b : buffers) if (b->cpuActive) throw std::runtime_error("CPU access session spans NPU run");
        runUncertain = true;
    }
    void runReturned(int rc) noexcept {
        if (retired || poisoned) return; // A late success cannot undo failed-run uncertainty.
        if (rc == RKNN_SUCC) runUncertain = false;
        else poisoned = true; // No SDK quiescence API is proven for failed blocking runs.
    }
    bool retire() noexcept {
        if (retired) return cleanupOK;
        retired = true;
        if (runUncertain) {
            // Do not inspect/dereference imports or call runtime destruction:
            // bindings can still be used by the NPU. Caller FD retention alone
            // is insufficient. Even context destroy is not proven to quiesce a
            // failed run. Process exit is the sole release boundary, never a
            // certificate of hardware quiescence or permission to continue.
            deferToProcessTeardown("uncertain_run_process_teardown");
            return false;
        }
        retirementBranch = "normal";
        for (auto &b : buffers) cleanupEnd(*b);
        // No FD creation, buffer reuse, mmap or reporting occurs between these
        // inspections and context retirement. Identity guards prevent double
        // close if the runtime unexpectedly closes/reuses an owned descriptor.
        for (auto &ptr : buffers) {
            auto &b = *ptr;
            b.beforeInspected = true;
            b.beforeFd = b.fd >= 0 && sameFd(b);
            b.beforeMap = b.mapping && ops.mapped(b.mapping, b.mappingBytes);
            if (b.memory && context) {
                b.destroyAttempted = true;
                b.destroyRc = ops.destroyImport(context, b.memory);
                b.memory = nullptr;
                if (b.destroyRc != RKNN_SUCC) cleanupOK = false;
            }
            b.afterImportInspected = true;
            b.afterImportFd = b.fd >= 0 && sameFd(b);
            b.afterImportMap = b.mapping && ops.mapped(b.mapping, b.mappingBytes);
            if (b.identityKnown && (!b.beforeFd || !b.afterImportFd)) cleanupOK = false;
            if (b.mapping && (!b.beforeMap || !b.afterImportMap)) cleanupOK = false;
        }
        if (context) {
            contextDestroyAttempted = true;
            contextDestroyRc = ops.destroyContext(context);
            if (contextDestroyRc != RKNN_SUCC) {
                // No subsequent descriptor inspection or external release.
                // Preserve the failed context identity and runtime until exit.
                deferToProcessTeardown("context_destroy_failed_process_teardown");
                return false;
            }
            context = 0;
        }
        for (auto &ptr : buffers) {
            auto &b = *ptr;
            b.afterContextInspected = true;
            b.afterContextFd = b.fd >= 0 && sameFd(b);
            b.afterContextMap = b.mapping && ops.mapped(b.mapping, b.mappingBytes);
            if (b.identityKnown && !b.afterContextFd) cleanupOK = false;
            if (b.mapping && !b.afterContextMap) cleanupOK = false;
            if (b.afterContextMap) {
                b.unmapAttempted = true; b.unmapRc = ops.unmap(b.mapping, b.mappingBytes); if (b.unmapRc) cleanupOK = false;
            }
            if (b.afterContextFd) {
                b.closeAttempted = true; b.closeRc = ops.closeFd(b.fd); if (b.closeRc) cleanupOK = false;
            }
            b.mapping = nullptr; b.fd = -1;
        }
        return cleanupOK;
    }
};
class CpuAccess {
    MemorySessionOwnedRAII &session;
    OwnedBuffer &buffer;
public:
    CpuAccess(MemorySessionOwnedRAII &s, OwnedBuffer &b, uint64_t direction) : session(s), buffer(b) { session.begin(buffer, direction); }
    ~CpuAccess() { session.cleanupEnd(buffer); }
    CpuAccess(const CpuAccess &) = delete;
    CpuAccess &operator=(const CpuAccess &) = delete;
    void finish() { session.end(buffer); }
};
} // namespace DmaHeapImport
