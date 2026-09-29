// ddr_scan - 找出 FPGA 当前正在写入的相机缓冲（用于位流换成多路后重新对地址）
// 做法：在 DDR 里按 2MB 分块各读两遍（间隔 40ms），比较哈希，变化的块就是活动帧缓冲；
//       对变化块再打印 +0x96000（既有布局里 tag 的位置）处的计数值，确认帧标签在递增。
// 用法: sudo ./ddr_scan [扫描MB数]
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <ctime>
#include <csignal>
#include <vector>

struct DmaOp {
    uint32_t current_len, offset_addr, cmd, ddr3_addr, total_length;
    void *read_buf, *write_buf;
};
static const unsigned long MAP_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 2;
static const unsigned long F2H_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 5;
static const uint32_t CAM_BLOCK = 2 * 1024 * 1024;   // 既有布局：每路占 2MB（帧 0x96000 + tag）
static const uint32_t TAG_OFF = 640 * 480 * 2;      // 0x96000

static double nowMs() {
    timespec ts{};
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}
static volatile sig_atomic_t alarmHit = 0;
static void onAlarm(int) { alarmHit = 1; }

static int g_fd = -1;
static uint8_t *g_rx = nullptr;
static std::vector<uint8_t> g_buf;

static bool ddrRead(uint32_t addr, uint32_t len, void *out) {
    DmaOp op{};
    op.offset_addr = 0;
    op.ddr3_addr = addr;
    op.total_length = len;
    alarmHit = 0;
    alarm(3);
    const int rc = ioctl(g_fd, F2H_CMD, &op);
    alarm(0);
    if (rc != 0 || alarmHit)
        return false;
    memcpy(out, g_rx, len);
    return true;
}

static uint64_t fnv(const uint8_t *p, size_t n) {
    uint64_t h = 1469598103934665603ull;
    for (size_t i = 0; i < n; i++) {
        h ^= p[i];
        h *= 1099511628211ull;
    }
    return h;
}

int main(int argc, char **argv) {
    const uint32_t scanMB = argc > 1 ? (uint32_t)atoi(argv[1]) : 64;
    struct sigaction sa{};
    sa.sa_handler = &onAlarm;
    sigaction(SIGALRM, &sa, nullptr);

    g_fd = ::open("/dev/pango_pci_driver", O_RDWR | O_SYNC);
    if (g_fd < 0) {
        fprintf(stderr, "open driver: %s\n", strerror(errno));
        return 1;
    }
    DmaOp b{};
    b.cmd = 1;
    b.total_length = 4 * 1024 * 1024;
    if (ioctl(g_fd, MAP_CMD, &b) < 0) {
        fprintf(stderr, "map rx: %s\n", strerror(errno));
        return 2;
    }
    g_rx = (uint8_t *)mmap(nullptr, 4 * 1024 * 1024, PROT_READ | PROT_WRITE, MAP_SHARED, g_fd,
                           1024 * 1024);
    if (g_rx == MAP_FAILED) {
        fprintf(stderr, "mmap rx: %s\n", strerror(errno));
        return 3;
    }
    g_buf.resize(4 * 1024 * 1024);

    const uint32_t blocks = scanMB * 1024 * 1024 / CAM_BLOCK;
    std::vector<uint64_t> hashA(blocks, 0), hashB(blocks, 0);
    std::vector<uint32_t> tagA(blocks, 0), tagB(blocks, 0);
    std::vector<bool> okA(blocks, false), okB(blocks, false);

    /* 每次只读一帧大小（614400B）：实测大块（2MB）读会把驱动挂住 */
    const double t0 = nowMs();
    for (uint32_t i = 0; i < blocks; i++) {
        const uint32_t addr = i * CAM_BLOCK;
        if (ddrRead(addr, TAG_OFF, g_buf.data())) {
            hashA[i] = fnv(g_buf.data(), TAG_OFF);
            okA[i] = true;
        }
        ddrRead(addr + TAG_OFF, 4, &tagA[i]);
    }
    usleep(40000);
    for (uint32_t i = 0; i < blocks; i++) {
        const uint32_t addr = i * CAM_BLOCK;
        if (ddrRead(addr, TAG_OFF, g_buf.data())) {
            hashB[i] = fnv(g_buf.data(), TAG_OFF);
            okB[i] = true;
        }
        ddrRead(addr + TAG_OFF, 4, &tagB[i]);
    }
    const double t1 = nowMs();
    printf("扫描 %u MB（%u 块，每块读一帧 %u B）两遍耗时 %.0f ms\n", scanMB, blocks, TAG_OFF,
           t1 - t0);

    int changed = 0;
    for (uint32_t i = 0; i < blocks; i++) {
        if (!okA[i] || !okB[i]) {
            printf("block %2u @0x%08x: 读失败\n", i, i * CAM_BLOCK);
            continue;
        }
        const bool frameChanged = hashA[i] != hashB[i];
        const bool tagChanged = tagA[i] != tagB[i];
        if (frameChanged || tagChanged) {
            changed++;
            printf("block %2u @0x%08x  frame变化=%d  tag=%u -> %u  (tag地址 0x%08x)\n", i,
                   i * CAM_BLOCK, frameChanged ? 1 : 0, tagA[i], tagB[i], i * CAM_BLOCK + TAG_OFF);
        }
    }
    printf("活动块: %d / %u\n", changed, blocks);
    printf("DDR_SCAN_DONE\n");
    return 0;
}
