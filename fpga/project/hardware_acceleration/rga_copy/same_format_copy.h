#pragma once
// Fixed full-frame same-format copy. No PCIe/exporter ABI or producer leasing.
#include <cstddef> // retained RGA declarations use NULL without including it
#include <cstdio>
#include <cstring>
#include <rga/im2d.h>
#include <rga/rga.h>
#include <linux/dma-buf.h>
#include <linux/dma-heap.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace rga_copy {
constexpr int Width = 640, Height = 480, RowBytes = Width * 2;
constexpr size_t FrameBytes = size_t(RowBytes) * Height; // 0x96000
constexpr const char *SystemHeap = "/dev/dma_heap/system";

inline void require(bool ok, const char *why) { if (!ok) throw std::runtime_error(why); }
inline std::runtime_error systemError(const char *action) {
    return std::runtime_error(std::string(action) + ": " + std::strerror(errno));
}
inline void checkStatus(IM_STATUS status, const char *action, bool capabilityCheck = false) {
    if (status != IM_STATUS_SUCCESS && !(capabilityCheck && status == IM_STATUS_NOERROR))
        throw std::runtime_error(std::string(action) + ": " + imStrError(status));
}
inline double milliseconds(clockid_t clock) {
    timespec time{};
    if (clock_gettime(clock, &time) != 0) throw systemError("clock_gettime");
    return double(time.tv_sec) * 1000.0 + double(time.tv_nsec) / 1e6;
}
struct Stamp { double wall = milliseconds(CLOCK_MONOTONIC), cpu = milliseconds(CLOCK_THREAD_CPUTIME_ID); };
struct Duration { double wall_ms = 0, thread_cpu_ms = 0; };
inline Duration elapsed(const Stamp &s) {
    return {milliseconds(CLOCK_MONOTONIC) - s.wall, milliseconds(CLOCK_THREAD_CPUTIME_ID) - s.cpu};
}
struct Measurement {
    Duration total, rga_copy, cpu_begin_read, snapshot_memcpy, cpu_end_read, cpu_access_and_snapshot;
};

inline void validateLength(size_t length) {
    require(length == FrameBytes, "source FD must describe one full packed RGB565 640x480 slot of exactly0x96000 bytes");
}
inline void validateSnapshot(void *out, size_t size, const void *mappedDestination) {
    require(out && size == FrameBytes, "snapshot must be an owned full614400-byte CPU buffer");
    const uintptr_t output = reinterpret_cast<uintptr_t>(out), mapped = reinterpret_cast<uintptr_t>(mappedDestination);
    require(output <= std::numeric_limits<uintptr_t>::max() - FrameBytes &&
            mapped <= std::numeric_limits<uintptr_t>::max() - FrameBytes, "snapshot pointer range overflow");
    require(!mappedDestination || !(output < mapped + FrameBytes && mapped < output + FrameBytes),
            "snapshot must not alias the private DMA-heap mapping");
}

class UniqueFd {
    int fd_ = -1;
public:
    explicit UniqueFd(int fd = -1) : fd_(fd) {}
    UniqueFd(const UniqueFd &) = delete;
    UniqueFd &operator=(const UniqueFd &) = delete;
    ~UniqueFd() { if (fd_ >= 0) ::close(fd_); }
    int get() const { return fd_; }
    void adopt(int fd) { require(fd_ < 0, "FD already owned"); fd_ = fd; }
};

inline void bufferSync(int fd, uint64_t flags) {
    dma_buf_sync sync{}; sync.flags = flags;
    int rc;
    do { rc = ioctl(fd, DMA_BUF_IOCTL_SYNC, &sync); } while (rc < 0 && (errno == EINTR || errno == EAGAIN));
    if (rc < 0) throw systemError("DMA_BUF_IOCTL_SYNC");
}
class CpuAccess {
    int fd_;
    uint64_t direction_;
    bool active_ = false;
public:
    CpuAccess(int fd, uint64_t direction) : fd_(fd), direction_(direction) {
        require(direction == DMA_BUF_SYNC_READ || direction == DMA_BUF_SYNC_WRITE || direction == DMA_BUF_SYNC_RW,
                "invalid CPU access direction");
        bufferSync(fd_, DMA_BUF_SYNC_START | direction_); active_ = true;
    }
    CpuAccess(const CpuAccess &) = delete;
    CpuAccess &operator=(const CpuAccess &) = delete;
    void finish() {
        require(active_, "CPU access already ended");
        bufferSync(fd_, DMA_BUF_SYNC_END | direction_); active_ = false;
    }
    ~CpuAccess() {
        if (active_) { try { finish(); } catch (...) {} } // best effort only; never certifies output
    }
};

// Uses official Linux UAPI. Standard system heap is selected for a cache-mapped
// CPU destination; actual target cache policy is not proven by mmap or its name.
class HeapSlot {
    UniqueFd fd_;
    uint8_t *data_ = nullptr;
    size_t mappedBytes_ = 0, pageSize_ = 0;
public:
    HeapSlot() {
        const long page = sysconf(_SC_PAGESIZE);
        require(page > 0, "invalid actual page size"); pageSize_ = size_t(page);
        require(FrameBytes <= std::numeric_limits<size_t>::max() - (pageSize_ - 1), "page rounding overflow");
        mappedBytes_ = (FrameBytes + pageSize_ - 1) / pageSize_ * pageSize_;
        // Never silently enlarge the packed slot imported below.
        require(mappedBytes_ == FrameBytes, "frame size not aligned to actual DMA-heap page size");
        UniqueFd heap(open(SystemHeap, O_RDWR | O_CLOEXEC));
        if (heap.get() < 0) throw systemError("open /dev/dma_heap/system");
        dma_heap_allocation_data allocation{};
        allocation.len = mappedBytes_; allocation.fd_flags = O_RDWR | O_CLOEXEC;
        allocation.heap_flags = 0;
        int rc;
        do { rc = ioctl(heap.get(), DMA_HEAP_IOCTL_ALLOC, &allocation); } while (rc < 0 && errno == EINTR);
        if (rc < 0) throw systemError("DMA_HEAP_IOCTL_ALLOC");
        require(allocation.fd <= uint32_t(std::numeric_limits<int>::max()), "invalid returned DMA-BUF descriptor");
        fd_.adopt(int(allocation.fd));
        void *mapping = mmap(nullptr, mappedBytes_, PROT_READ | PROT_WRITE, MAP_SHARED, fd_.get(), 0);
        if (mapping == MAP_FAILED) throw systemError("mmap DMA-heap slot");
        data_ = static_cast<uint8_t *>(mapping);
    }
    HeapSlot(const HeapSlot &) = delete;
    HeapSlot &operator=(const HeapSlot &) = delete;
    ~HeapSlot() { if (data_) munmap(data_, mappedBytes_); }
    int fd() const { return fd_.get(); }
    uint8_t *data() const { return data_; }
    size_t size() const { return mappedBytes_; }
    size_t pageSize() const { return pageSize_; }
};

class ImportedBuffer {
    rga_buffer_handle_t handle_ = 0;
public:
    explicit ImportedBuffer(int fd) : handle_(importbuffer_fd(fd, int(FrameBytes))) {
        require(handle_ != 0, "RGA importbuffer_fd(fd,614400) failed");
    }
    ImportedBuffer(const ImportedBuffer &) = delete;
    ImportedBuffer &operator=(const ImportedBuffer &) = delete;
    ~ImportedBuffer() { reset(); }
    void reset() noexcept {
        if (handle_) { releasebuffer_handle(handle_); handle_ = 0; }
    }
    rga_buffer_handle_t get() const { return handle_; }
};

inline int duplicateSlotFd(int externalFd, size_t declaredLength) {
    validateLength(declaredLength);
    if (externalFd < 0) throw std::runtime_error("invalid external DMA-BUF FD");
    int duplicate;
    do { duplicate = fcntl(externalFd, F_DUPFD_CLOEXEC, 0); } while (duplicate < 0 && errno == EINTR);
    if (duplicate < 0) throw systemError("duplicate external DMA-BUF FD");
    // DMA-BUF supports size discovery by SEEK_END/0 and reset by SEEK_SET/0.
    // A slab FD larger than one slot or an exporter lacking this query declines.
    const off_t size = lseek(duplicate, 0, SEEK_END);
    const int saved = errno;
    const off_t reset = lseek(duplicate, 0, SEEK_SET);
    if (size != off_t(FrameBytes) || reset != 0) {
        ::close(duplicate); errno = saved;
        throw std::runtime_error("external DMA-BUF size query must equal614400 with base offset0; suballocations unsupported");
    }
    return duplicate;
}

// One fixed external slot + one private destination per instance/camera.
// Caller keeps the exporter generation pinned for this object's lifetime and
// the producer slot leased/stable for the entire copy() call. dup is not a lease.
// No source mmap, source CPU cache sync, address reinterpretation or exporter ABI.
class SameFormatCopy {
    UniqueFd sourceFd_;
    HeapSlot destination_;
    ImportedBuffer sourceImport_;
    ImportedBuffer destinationImport_;
    rga_buffer_t sourceImage_{}, destinationImage_{};
    bool failed_ = false;
public:
    explicit SameFormatCopy(int externalFd, size_t declaredLength)
        : sourceFd_(duplicateSlotFd(externalFd, declaredLength)), destination_(),
          sourceImport_(sourceFd_.get()), destinationImport_(destination_.fd()) {
        try {
            sourceImage_ = wrapbuffer_handle(sourceImport_.get(), Width, Height, RK_FORMAT_RGB_565, Width, Height);
            destinationImage_ = wrapbuffer_handle(destinationImport_.get(), Width, Height, RK_FORMAT_RGB_565, Width, Height);
            const im_rect full{0, 0, Width, Height};
            checkStatus(imcheck(sourceImage_, destinationImage_, full, full, IM_SYNC), "imcheck same-format full frame", true);
        } catch (...) { sourceImport_.reset(); destinationImport_.reset(); throw; }
    }
    SameFormatCopy(const SameFormatCopy &) = delete;
    SameFormatCopy &operator=(const SameFormatCopy &) = delete;
    ~SameFormatCopy() {
        // Release both device imports before either owned mapping or FD goes.
        sourceImport_.reset(); destinationImport_.reset();
    }
    size_t destinationPageSize() const { return destination_.pageSize(); }
    // On exception, out may contain bytes but is invalid and MUST NOT be
    // published. Device/sync failure poisons the instance; recover externally.
    Measurement copy(void *out, size_t size) {
        validateSnapshot(out, size, destination_.data());
        require(!failed_, "copy instance invalid after previous device/synchronization failure");
        try {
            Measurement result; const Stamp total;
            { const Stamp t; checkStatus(imcopy(sourceImage_, destinationImage_, 1), "imcopy synchronous RGB565");
              result.rga_copy = elapsed(t); }
            const Stamp cpuPhase, begin;
            CpuAccess read(destination_.fd(), DMA_BUF_SYNC_READ);
            result.cpu_begin_read = elapsed(begin);
            { const Stamp t; std::memcpy(out, destination_.data(), FrameBytes); result.snapshot_memcpy = elapsed(t); }
            { const Stamp t; read.finish(); result.cpu_end_read = elapsed(t); }
            result.cpu_access_and_snapshot = elapsed(cpuPhase);
            result.total = elapsed(total);
            return result; // END_READ and synchronous device completion succeeded
        } catch (...) { failed_ = true; throw; }
    }
    // Transactional owned snapshot: previous output survives all failures.
    // Allocation and swap are outside the returned internal copy timings.
    Measurement copy(std::vector<uint8_t> &out) {
        std::vector<uint8_t> next(FrameBytes);
        const Measurement timing = copy(next.data(), next.size());
        out.swap(next); return timing;
    }
};
} // namespace rga_copy
