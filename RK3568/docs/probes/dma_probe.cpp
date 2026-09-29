// dma_probe - 量 RK3568 上 PCIe DDR 读的真实代价（一帧 614400B 与 16B 标签）
// 用法: sudo ./dma_probe [帧数]
// 依赖: /dev/pango_pci_driver（需先停掉 detview/camview 之类占用者）
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <algorithm>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <ctime>
#include <csignal>

struct DmaOp {
    uint32_t current_len, offset_addr, cmd, ddr3_addr, total_length;
    void *read_buf, *write_buf;
};

static const unsigned long MAP_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 2;
static const unsigned long F2H_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 5;

static const uint32_t CAM1 = 0x00800000u;      // C1 帧缓冲（640x480 RGB565）
static const uint32_t TAG1 = CAM1 + 640 * 480 * 2;

static double nowMs() {
    timespec ts{};
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

static volatile sig_atomic_t alarmHit = 0;
static void onAlarm(int) { alarmHit = 1; }

int main(int argc, char **argv) {
    const int loops = argc > 1 ? atoi(argv[1]) : 100;
    struct sigaction sa{};
    sa.sa_handler = &onAlarm;
    sigaction(SIGALRM, &sa, nullptr);

    int fd = ::open("/dev/pango_pci_driver", O_RDWR | O_SYNC);
    if (fd < 0) {
        fprintf(stderr, "open driver: %s\n", strerror(errno));
        return 1;
    }
    DmaOp a{};
    a.cmd = 0;
    a.total_length = 4 * 1024 * 1024;
    if (ioctl(fd, MAP_CMD, &a) < 0) {
        fprintf(stderr, "map tx: %s\n", strerror(errno));
        return 2;
    }
    DmaOp b{};
    b.cmd = 1;
    b.total_length = 4 * 1024 * 1024;
    if (ioctl(fd, MAP_CMD, &b) < 0) {
        fprintf(stderr, "map rx: %s\n", strerror(errno));
        return 3;
    }
    uint8_t *rx = (uint8_t *)mmap(nullptr, 4 * 1024 * 1024, PROT_READ | PROT_WRITE, MAP_SHARED, fd,
                                  1024 * 1024);
    if (rx == MAP_FAILED) {
        fprintf(stderr, "mmap: %s\n", strerror(errno));
        return 4;
    }
    static uint8_t out[1024 * 1024];

    auto readOnce = [&](uint32_t addr, uint32_t len, void *dst) -> double {
        DmaOp op{};
        op.offset_addr = 0;
        op.ddr3_addr = addr;
        op.total_length = len;
        alarmHit = 0;
        alarm(3);
        const double t0 = nowMs();
        const int rc = ioctl(fd, F2H_CMD, &op);
        const double t1 = nowMs();
        alarm(0);
        if (rc != 0 || alarmHit)
            return -1.0;
        memcpy(dst, rx, len);
        return t1 - t0;
    };

    const uint32_t frameLen = 640 * 480 * 2;
    // 预热
    for (int i = 0; i < 5; i++) readOnce(CAM1, frameLen, out);

    double sum = 0, mn = 1e9, mx = 0;
    for (int i = 0; i < loops; i++) {
        const double ms = readOnce(CAM1, frameLen, out);
        if (ms < 0) {
            fprintf(stderr, "read timed out at %d\n", i);
            break;
        }
        sum += ms;
        mn = std::min(mn, ms);
        mx = std::max(mx, ms);
    }
    printf("读整帧 %u B x %d: 平均 %.3f ms (min %.3f max %.3f) -> %.1f MB/s（单笔）\n",
           frameLen, loops, sum / loops, mn, mx, frameLen / 1024.0 / 1024.0 / (sum / loops / 1000.0));

    // 16B 标签读（采集线程每 10ms 轮询的正是这个）
    sum = 0;
    mn = 1e9;
    mx = 0;
    for (int i = 0; i < loops; i++) {
        const double ms = readOnce(TAG1, 16, out);
        if (ms < 0)
            break;
        sum += ms;
        mn = std::min(mn, ms);
        mx = std::max(mx, ms);
    }
    printf("读标签 16 B x %d: 平均 %.3f ms (min %.3f max %.3f)\n", loops, sum / loops, mn, mx);

    // 分块读：同样一帧，拆成 4 笔
    sum = 0;
    for (int i = 0; i < loops; i++) {
        double t = 0;
        bool ok = true;
        for (int k = 0; k < 4; k++) {
            const double ms = readOnce(CAM1 + (uint32_t)k * frameLen / 4, frameLen / 4, out);
            if (ms < 0) { ok = false; break; }
            t += ms;
        }
        if (!ok)
            break;
        sum += t;
    }
    printf("读整帧分 4 笔 x %d: 平均合计 %.3f ms（每笔 %.3f ms）\n", loops, sum / loops,
           sum / loops / 4);

    // 4 路各读一帧（当前采集线程的顺序）
    static const uint32_t bases[4] = {0x00800000u, 0x00C00000u, 0x01000000u, 0x01400000u};
    sum = 0;
    for (int i = 0; i < loops / 4 + 1; i++) {
        double t = 0;
        for (int c = 0; c < 4; c++) {
            const double ms = readOnce(bases[c], frameLen, out);
            if (ms < 0) { t = -1; break; }
            t += ms;
        }
        if (t < 0)
            break;
        sum += t;
    }
    const int groups = loops / 4 + 1;
    printf("四路各读一帧 x %d: 平均 %.3f ms/轮 -> 上限 %.1f fps（仅 DMA，不含解码/显示）\n", groups,
           sum / groups, 1000.0 / (sum / groups));

    munmap(rx, 4 * 1024 * 1024);
    ::close(fd);
    printf("DMA_PROBE_DONE\n");
    return 0;
}
