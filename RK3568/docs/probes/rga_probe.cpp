// rga_probe - 验证 RK3568 上 dma-heap + RGA 的“转换/缩放”链路是否可用于显示管线
// 用法: sudo ./rga_probe
// 依赖: /dev/dma_heap/system, /dev/rga, librga
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <ctime>

#include <rga/im2d.h>
#include <rga/rga.h>

// 直接内联 dma-heap 的 ABI，避免依赖内核头文件版本
struct dma_heap_allocation_data {
    uint64_t len;
    uint32_t fd;
    uint32_t fd_flags;
    uint64_t heap_flags;
};
#define DMA_HEAP_IOC_MAGIC 'H'
#define DMA_HEAP_IOCTL_ALLOC _IOWR(DMA_HEAP_IOC_MAGIC, 0x0, struct dma_heap_allocation_data)

struct DmaBuf {
    int fd = -1;
    void *p = nullptr;
    size_t size = 0;
};

static bool allocDma(DmaBuf &b, size_t size, const char *heap = "/dev/dma_heap/system") {
    int h = ::open(heap, O_RDWR | O_CLOEXEC);
    if (h < 0) {
        fprintf(stderr, "open %s: %s\n", heap, strerror(errno));
        return false;
    }
    dma_heap_allocation_data data{};
    data.len = size;
    data.fd_flags = O_RDWR | O_CLOEXEC;
    if (ioctl(h, DMA_HEAP_IOCTL_ALLOC, &data) < 0) {
        fprintf(stderr, "DMA_HEAP_IOCTL_ALLOC(%zu): %s\n", size, strerror(errno));
        ::close(h);
        return false;
    }
    ::close(h);
    b.fd = (int)data.fd;
    b.size = size;
    b.p = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, b.fd, 0);
    if (b.p == MAP_FAILED) {
        fprintf(stderr, "mmap(%zu): %s\n", size, strerror(errno));
        b.p = nullptr;
        return false;
    }
    return true;
}

static double nowMs() {
    timespec ts{};
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

int main() {
    const int SW = 1280, SH = 960;                 // 2x2 合成（RGB888）
    /* RGA 要求 RGB888 的行 stride 按 4 字节对齐：宽度向上取整到 4 的倍数，
       多出来的像素不显示（QImage 用同样的 stride） */
    const int DW = 1900, DH = 1006;                // 目标窗口内容区尺寸（RGB888）
    DmaBuf src, dst, src565;
    if (!allocDma(src, (size_t)SW * SH * 3)) return 1;
    if (!allocDma(dst, (size_t)DW * DH * 3)) return 1;
    if (!allocDma(src565, (size_t)640 * 480 * 2)) return 1;
    printf("dma-heap ok: src=%d(%zuB) dst=%d(%zuB) s565=%d(%zuB)\n", src.fd, src.size, dst.fd,
           dst.size, src565.fd, src565.size);

    // 源：横向渐变 + 四个象限不同色调，便于核对缩放位置
    uint8_t *s = (uint8_t *)src.p;
    for (int y = 0; y < SH; y++)
        for (int x = 0; x < SW; x++) {
            uint8_t *px = s + ((size_t)y * SW + x) * 3;
            px[0] = (uint8_t)(x & 0xFF);
            px[1] = (uint8_t)(y & 0xFF);
            px[2] = (uint8_t)(((x / 640) + 2 * (y / 480)) * 60);
        }
    memset(dst.p, 0, dst.size);

    rga_buffer_t rs = wrapbuffer_fd(src.fd, SW, SH, RK_FORMAT_RGB_888);
    rga_buffer_t rd = wrapbuffer_fd(dst.fd, DW, DH, RK_FORMAT_RGB_888);
    im_rect empty{};
    IM_STATUS chk = imcheck(rs, rd, empty, empty);
    printf("imcheck=%s (%d)\n", imStrError(chk), (int)chk);
    if (chk != IM_STATUS_NOERROR) {
        fprintf(stderr, "imcheck failed\n");
        return 2;
    }

    const int N = 50;
    const double t0 = nowMs();
    for (int i = 0; i < N; i++) {
        IM_STATUS st = imresize(rs, rd);
        if (st != IM_STATUS_SUCCESS) {
            fprintf(stderr, "imresize failed: %s\n", imStrError(st));
            return 3;
        }
    }
    const double t1 = nowMs();
    printf("imresize %dx%d -> %dx%d : %.3f ms/op\n", SW, SH, DW, DH, (t1 - t0) / N);

    // 抽查若干点：缩放后应当仍是“x 渐变、y 渐变”
    uint8_t *d = (uint8_t *)dst.p;
    for (int k = 1; k <= 4; k++) {
        const int x = DW * k / 5, y = DH * k / 5;
        const uint8_t *px = d + ((size_t)y * DW + x) * 3;
        printf("  dst(%4d,%4d)=(%3u,%3u,%3u)  期望≈(%3d,%3d)\n", x, y, px[0], px[1], px[2], x * SW / DW,
               y * SH / DH);
    }

    // RGB565 -> RGB888（备用路径：相机帧转 888）
    uint16_t *p565 = (uint16_t *)src565.p;
    for (int i = 0; i < 640 * 480; i++) p565[i] = (uint16_t)((i * 7) & 0xFFFF);
    rga_buffer_t r565 = wrapbuffer_fd(src565.fd, 640, 480, RK_FORMAT_RGB_565);
    DmaBuf c888;
    if (!allocDma(c888, (size_t)640 * 480 * 3)) return 4;
    rga_buffer_t r888 = wrapbuffer_fd(c888.fd, 640, 480, RK_FORMAT_RGB_888);
    const double c0 = nowMs();
    for (int i = 0; i < N; i++) {
        IM_STATUS st = imcvtcolor(r565, r888, RK_FORMAT_RGB_565, RK_FORMAT_RGB_888);
        if (st != IM_STATUS_SUCCESS) {
            fprintf(stderr, "imcvtcolor failed: %s\n", imStrError(st));
            return 5;
        }
    }
    const double c1 = nowMs();
    const uint16_t v = p565[12345];
    const uint8_t *q = (const uint8_t *)c888.p + (size_t)12345 * 3;
    printf("imcvtcolor 640x480 565->888 : %.3f ms/op\n", (c1 - c0) / N);
    printf("  src565[12345]=0x%04x -> rgb=(%u,%u,%u)  期望=(%u,%u,%u)\n", v, q[0], q[1], q[2],
           (uint8_t)((((v >> 11) & 0x1F) << 3) | (((v >> 11) & 0x1F) >> 2)),
           (uint8_t)((((v >> 5) & 0x3F) << 2) | (((v >> 5) & 0x3F) >> 4)),
           (uint8_t)(((v & 0x1F) << 3) | ((v & 0x1F) >> 2)));

    // 清屏代价（letterbox 黑边用）
    const double f0 = nowMs();
    for (int i = 0; i < N; i++) imfill(rd, empty, 0xFF000000);
    const double f1 = nowMs();
    printf("imfill 全幅: %.3f ms/op\n", (f1 - f0) / N);

    printf("RGA_PROBE_PASS\n");
    return 0;
}
