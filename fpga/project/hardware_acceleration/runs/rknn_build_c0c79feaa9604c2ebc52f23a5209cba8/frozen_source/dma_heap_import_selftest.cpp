#include "dma_heap_import.h"
#include <algorithm>
#include <deque>
#include <iostream>
#include <map>

using namespace DmaHeapImport;
static void require(bool value, const char *message) { if (!value) throw std::runtime_error(message); }
template<class F> static void rejected(F action) {
    bool caught = false; try { action(); } catch (const std::runtime_error &) { caught = true; }
    require(caught, "expected rejection");
}
struct Mock final : Operations {
    struct Buffer { Identity id; bool open = true, mapped = false; std::vector<unsigned char> bytes; rknn_tensor_mem memory{}; };
    std::map<int, Buffer> storage;
    std::vector<std::string> calls;
    std::deque<int> syncResults;
    int nextFd = 10, failAllocateAt = -1, failImportAt = -1, failMapAt = -1;
    int contextRc = 0, importRc = 0;
    bool closeOnDestroy = false, reuseOnDestroy = false, unmapOnDestroy = false;
    long pageSize() override { return 4096; }
    int allocate(uint32_t bytes) override {
        calls.push_back("allocate");
        const int fd = nextFd++;
        if (fd == failAllocateAt) throw std::runtime_error("mock allocator failure");
        auto &b = storage[fd]; b.id = {42, uint64_t(fd)}; b.bytes.resize(bytes, 165);
        return fd;
    }
    void *map(int fd, uint32_t) override {
        calls.push_back("map");
        if (fd == failMapAt) throw std::runtime_error("mock mmap failure");
        auto &b = storage.at(fd); b.mapped = true; return b.bytes.data();
    }
    bool identity(int fd, Identity &id) noexcept override {
        auto it = storage.find(fd);
        if (it == storage.end() || !it->second.open) return false;
        id = it->second.id; return true;
    }
    bool mapped(void *address, uint32_t) noexcept override {
        for (const auto &pair : storage) if (pair.second.bytes.data() == address) return pair.second.mapped;
        return false;
    }
    int cpuSync(int, uint64_t flags) noexcept override {
        calls.push_back(std::string(flags & DMA_BUF_SYNC_END ? "END_" : "START_") +
                        (flags & DMA_BUF_SYNC_WRITE ? "WRITE" : "READ"));
        if (syncResults.empty()) return 0;
        const int rc = syncResults.front(); syncResults.pop_front(); return rc;
    }
    rknn_tensor_mem *import(rknn_context ctx, int fd, void *address, uint32_t bytes) override {
        require(ctx == 123, "wrong context for import"); calls.push_back("import");
        if (fd == failImportAt) return nullptr;
        auto &b = storage.at(fd); b.memory.virt_addr = address; b.memory.fd = fd; b.memory.size = bytes;
        b.memory.flags = RKNN_TENSOR_MEMORY_FLAGS_FROM_FD;
        return &b.memory;
    }
    int destroyImport(rknn_context ctx, rknn_tensor_mem *memory) noexcept override {
        if (ctx != 123) std::terminate();
        calls.push_back("destroy_import");
        auto &b = storage.at(memory->fd);
        if (closeOnDestroy) b.open = false;
        if (reuseOnDestroy) ++b.id.inode;
        if (unmapOnDestroy) b.mapped = false;
        return importRc;
    }
    int destroyContext(rknn_context ctx) noexcept override {
        if (ctx != 123) std::terminate();
        calls.push_back("destroy_context"); return contextRc;
    }
    int unmap(void *address, uint32_t) noexcept override {
        calls.push_back("munmap");
        for (auto &pair : storage) if (pair.second.bytes.data() == address) pair.second.mapped = false;
        return 0;
    }
    int closeFd(int fd) noexcept override { calls.push_back("close"); storage.at(fd).open = false; return 0; }
    void fullyReleased() {
        for (const auto &pair : storage) require(!pair.second.open && !pair.second.mapped, "owned resource leak");
    }
};
static void teardownOrder(const Mock &m) {
    const auto context = std::find(m.calls.begin(), m.calls.end(), "destroy_context");
    require(context != m.calls.end(), "context never destroyed");
    require(std::find(context, m.calls.end(), "destroy_import") == m.calls.end(), "destroy import after context");
    require(std::find(m.calls.begin(), context, "munmap") == context, "unmap before context retired");
    require(std::find(m.calls.begin(), context, "close") == context, "close before context retired");
}
static void frame(MemorySessionOwnedRAII &session, Mock &m, OwnedBuffer &input, OwnedBuffer &output, int runRc = 0) {
    { CpuAccess access(session, input, DMA_BUF_SYNC_WRITE); m.calls.push_back("full_copy"); access.finish(); }
    m.calls.push_back("RKNN_TO_DEVICE");
    session.beforeRun(); m.calls.push_back("run"); session.runReturned(runRc);
    if (runRc) return;
    { CpuAccess access(session, output, DMA_BUF_SYNC_READ);
      m.calls.push_back("RKNN_FROM_DEVICE"); m.calls.push_back("convert"); access.finish(); }
}
int main() {
    try {
        require(alignedBytes(1228800, 4096) == 1228800, "input alignment");
        require(alignedBytes(25600, 4096) == 28672, "classifier allocation rounding");
        require(alignedBytes(25600, 65536) == 65536, "queried non-4K page size");
        for (long page : {0L, -1L}) rejected([&] { alignedBytes(1, page); });
        rejected([] { alignedBytes(0, 4096); });
        rejected([] { alignedBytes(UINT32_MAX, 4096); });
        rejected([] { alignedBytes(size_t(UINT32_MAX) + 1, 4096); });
        {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx);
            auto &input = session.allocate(1228800, "input");
            auto &output = session.allocate(25600, "output");
            const size_t start = m.calls.size(); frame(session, m, input, output);
            const std::vector<std::string> expected = {"START_WRITE", "full_copy", "END_WRITE", "RKNN_TO_DEVICE", "run",
                "START_READ", "RKNN_FROM_DEVICE", "convert", "END_READ"};
            require(std::vector<std::string>(m.calls.begin() + start, m.calls.end()) == expected, "CPU/RKNN ordering");
            require(output.memory->size == 28672 && output.nativeBytes == 25600, "logical/allocation conflation");
            require(session.retire() && !ctx, "success retirement");
            require(input.afterImportFd && input.afterImportMap && input.afterContextFd && input.afterContextMap, "ownership snapshots");
            teardownOrder(m); m.fullyReleased();
            const size_t count = m.calls.size(); require(session.retire() && m.calls.size() == count, "non-idempotent cleanup");
        }
        // Partial allocator/mmap/import/bind failures: all acquired resources
        // retire after imports and context, including the not-imported last FD.
        for (int failure = 0; failure < 4; ++failure) {
            Mock m; rknn_context ctx = 123;
            if (failure == 0) m.failAllocateAt = 11;
            if (failure == 1) m.failMapAt = 11;
            if (failure == 2) m.failImportAt = 11;
            {
                MemorySessionOwnedRAII session(m, ctx); session.allocate(25600, "first");
                rejected([&] { session.allocate(25600, "second"); m.calls.push_back("bind"); throw std::runtime_error("bind failure"); });
            }
            require(!ctx, "partial failure context alive"); teardownOrder(m); m.fullyReleased();
        }
        for (const std::string stage : {"copy", "input_sync", "output_sync", "convert"}) {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx);
            auto &b = session.allocate(25600, stage);
            rejected([&] {
                CpuAccess access(session, b, stage == "copy" || stage == "input_sync" ? DMA_BUF_SYNC_WRITE : DMA_BUF_SYNC_READ);
                m.calls.push_back(stage); throw std::runtime_error(stage + " failed");
            });
            require(!b.cpuActive, "CPU END missing on exception");
            require(m.calls.back() == (stage == "copy" || stage == "input_sync" ? "END_WRITE" : "END_READ"), "wrong paired cleanup END");
            require(session.retire(), "exception cleanup failure"); teardownOrder(m); m.fullyReleased();
        }
        {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx);
            auto &b = session.allocate(25600, "eintr"); m.syncResults = {-EINTR, -EINTR, 0, -EINTR, 0};
            { CpuAccess access(session, b, DMA_BUF_SYNC_READ); access.finish(); }
            require(b.sync[0].attempts == 3 && b.sync[0].interrupted == 2 && b.sync[0].success == 1 &&
                    b.sync[1].attempts == 2 && b.sync[1].success == 1, "EINTR accounting");
            require(session.retire(), "EINTR retirement");
        }
        for (bool endFailure : {false, true}) {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx); auto &b = session.allocate(25600, "ioctl_failure");
            if (endFailure) m.syncResults = {0, -EIO, 0}; else m.syncResults = {-EIO};
            rejected([&] { CpuAccess access(session, b, DMA_BUF_SYNC_WRITE); access.finish(); });
            require(b.sync[2].success == (endFailure ? 1u : 0u), "START failure accounting");
            require(b.sync[3].attempts == (endFailure ? 2u : 0u), "paired cleanup END attempt sequence");
            rejected([&] { session.beforeRun(); }); session.retire(); teardownOrder(m); m.fullyReleased();
        }
        {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx); auto &b = session.allocate(25600, "bounded");
            m.syncResults.assign(MaxEintrAttempts, -EINTR);
            rejected([&] { CpuAccess access(session, b, DMA_BUF_SYNC_READ); });
            require(b.sync[0].attempts == MaxEintrAttempts && b.sync[1].attempts == 0, "unbounded/extra sync retry");
            session.retire(); m.fullyReleased();
        }
        {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx); auto &b = session.allocate(25600, "failed_end_cleanup");
            m.syncResults = {0, -EIO};
            for (unsigned i = 0; i < MaxEintrAttempts; ++i) m.syncResults.push_back(-EINTR);
            rejected([&] { CpuAccess access(session, b, DMA_BUF_SYNC_READ); access.finish(); });
            require(!b.cpuActive && b.sync[1].attempts == 1 + MaxEintrAttempts && b.sync[1].failures == 2,
                    "failed cleanup END was unbounded or lost");
            const uint64_t attempts = b.sync[1].attempts;
            require(!session.retire() && b.sync[1].attempts == attempts, "retirement retried failed END again");
            teardownOrder(m); m.fullyReleased();
        }
        {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx);
            auto &input = session.allocate(25600, "input"); auto &output = session.allocate(25600, "output");
            frame(session, m, input, output, -1);
            rejected([&] { CpuAccess access(session, output, DMA_BUF_SYNC_READ); });
            require(output.sync[0].attempts == 0, "CPU access after uncertain run failure");
            require(session.retire(), "run failure retirement"); teardownOrder(m); m.fullyReleased();
        }
        {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx); auto &b = session.allocate(25600, "active");
            { CpuAccess access(session, b, DMA_BUF_SYNC_WRITE); rejected([&] { session.beforeRun(); }); access.finish(); }
            session.retire(); m.fullyReleased();
        }
        for (int ownership = 0; ownership < 3; ++ownership) {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx); session.allocate(25600, "probe");
            m.closeOnDestroy = ownership == 0; m.reuseOnDestroy = ownership == 1; m.unmapOnDestroy = ownership == 2;
            require(!session.retire(), "unexpected ownership was accepted"); teardownOrder(m);
            require(std::count(m.calls.begin(), m.calls.end(), ownership == 2 ? "munmap" : "close") == 0,
                    "double-close/reused-FD close/unmap hazard");
        }
        {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx); session.allocate(25600, "context_failure");
            m.contextRc = -1; require(!session.retire(), "failed context retirement accepted");
            require(std::count(m.calls.begin(), m.calls.end(), "munmap") == 0 &&
                    std::count(m.calls.begin(), m.calls.end(), "close") == 0, "free while device completion uncertain");
        }
        {
            Mock m; rknn_context ctx = 123; MemorySessionOwnedRAII session(m, ctx); auto &b = session.allocate(25600, "short_import");
            b.memory->size = 25599; rejected([&] { session.validate(b); });
            b.memory->size = b.mappingBytes; m.importRc = -1;
            require(!session.retire(), "destroy import failure accepted"); teardownOrder(m); m.fullyReleased();
        }
        std::cout << "dma_heap_lifecycle_checks_passed=true; mocked_syscalls_only=true; hardware_compatibility=false\n";
        return 0;
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 1; }
}
