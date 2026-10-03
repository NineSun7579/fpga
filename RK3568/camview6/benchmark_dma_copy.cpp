#include "dma_copy.h"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

struct DmaOp {
    uint32_t current_len, offset_addr, cmd, ddr3_addr, total_length;
    void *read_buf, *write_buf;
};
constexpr unsigned long command(int number) {
    return 0xC0000000u | (4u << 16) | (0x53u << 8) | number;
}
using Clock = std::chrono::steady_clock;
int main() {
    constexpr size_t bytes = 614400, mappingBytes = 4 * 1024 * 1024;
    int fd = open("/dev/pango_pci_driver", O_RDWR | O_SYNC);
    if (fd < 0) return 1;
    for (uint32_t mapping = 0; mapping < 2; ++mapping) {
        DmaOp op{}; op.cmd = mapping; op.total_length = mappingBytes;
        if (ioctl(fd, command(2), &op)) return 2;
    }
    auto *rx = static_cast<uint8_t *>(mmap(nullptr, mappingBytes, PROT_READ | PROT_WRITE,
                                         MAP_SHARED, fd, 1024 * 1024));
    if (rx == MAP_FAILED) return 3;
    std::vector<uint8_t> reference(bytes), copied(bytes);
    DmaOp op{}; op.ddr3_addr = 0x800000; op.total_length = bytes;
    if (ioctl(fd, command(5), &op)) return 4;
    std::memcpy(reference.data(), rx, bytes);
    // Exercise aligned/unaligned destinations and short tails against a stable
    // DMA buffer, without issuing another transfer between the two copies.
    for (size_t offset : {size_t(0), size_t(1), size_t(7), size_t(15)}) {
        for (size_t count : {size_t(1), size_t(63), size_t(64), size_t(65), bytes - offset}) {
            copyDmaPixels(copied.data() + offset, rx + offset, count);
            if (std::memcmp(copied.data() + offset, reference.data() + offset, count)) return 5;
        }
    }
    std::printf("copy_identity=pass bytes=%zu\n", bytes);
    for (int method = 0; method < 3; ++method) {
        double copyMs = 0, dmaMs = 0;
        constexpr int count = 240;
        auto start = Clock::now();
        for (int i = 0; i < count; ++i) {
            op.ddr3_addr = 0x800000 + (i % 6) * 0x400000;
            auto t = Clock::now();
            if (ioctl(fd, command(5), &op)) return 6;
            auto c = Clock::now();
            if (method == 1) std::memcpy(copied.data(), rx, bytes);
            if (method == 2) copyDmaPixels(copied.data(), rx, bytes);
            auto end = Clock::now();
            dmaMs += std::chrono::duration<double, std::milli>(c - t).count();
            copyMs += std::chrono::duration<double, std::milli>(end - c).count();
        }
        double seconds = std::chrono::duration<double>(Clock::now() - start).count();
        std::printf("method=%s frames=%d MBps=%.3f fps=%.3f dma_ms=%.3f copy_ms=%.3f\n",
                    method == 0 ? "no_copy" : method == 1 ? "memcpy" : "neon64",
                    count, bytes * count / seconds / 1e6, count / seconds, dmaMs / count, copyMs / count);
    }
    munmap(rx, mappingBytes); close(fd);
    return 0;
}
