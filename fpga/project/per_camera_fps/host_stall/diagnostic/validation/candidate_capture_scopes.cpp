#include <QByteArray>
#include <QElapsedTimer>
#include <QMutex>
#include <QThread>
#include <algorithm>
#include <atomic>
#include <csignal>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <fcntl.h>
#include <functional>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include "camera_dma.h"
#include "frame_metrics.h"
#include "vision_types.h"
#include "stall_timing.h"
static const int IMG_W = 640;
static const int IMG_H = 480;
static const size_t FRAME_BYTES = (size_t)IMG_W * IMG_H * 2;
/* 六路相机 DDR 乒乓缓冲（与运行版 camview 6 路版一致）；帧标签在 base + FRAME_BYTES */
static const int CAM_COUNT = 6;
static const int GRID_COLS = 3;
static const int GRID_ROWS = 2;
static const uint32_t CAM_BASE[CAM_COUNT][2] = {
    {0x00800000u, 0x00A00000u}, {0x00C00000u, 0x00E00000u}, {0x01000000u, 0x01200000u},
    {0x01400000u, 0x01600000u}, {0x01800000u, 0x01A00000u}, {0x01C00000u, 0x01E00000u}};
static const uint32_t REG_BASE = 0x20000000u;
static const uint32_t R_ACK = REG_BASE + 0x00;
static const uint32_t R_I2C_ID = REG_BASE + 0x3C;
static const uint32_t R_CAM_EN = REG_BASE + 0x40;
static const uint32_t R_ADDR1 = REG_BASE + 0x80;
static const uint32_t R_ADDR2 = REG_BASE + 0xC0;

static const unsigned long MAP_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 2;
static const unsigned long H2F_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 4;
static const unsigned long F2H_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 5;

static const int MODEL_W = 640;
static const int MODEL_H = 640;
static const size_t MODEL_SIZE = (size_t)MODEL_W * MODEL_H * 3;
static const float CONF_THRESH = 0.25f;
static const float IOU_THRESH = 0.45f;

static qint64 monotonicMs() {
    timespec stamp{};
    clock_gettime(CLOCK_MONOTONIC, &stamp);
    return stamp.tv_sec * 1000LL + stamp.tv_nsec / 1000000;
}

struct DmaOp {
    uint32_t current_len, offset_addr, cmd, ddr3_addr, total_length;
    void *read_buf, *write_buf;
};

class PangoDev {
public:
    ~PangoDev() { close(); }

    bool openDev() {
        StallTiming::IoctlDrain diagnosticDrain;
        struct sigaction sa{};
        sa.sa_handler = &PangoDev::alarmHandler;
        sigaction(SIGALRM, &sa, nullptr);  // 只装一次，避免每次 ioctl 的 sigaction 开销
        fd_ = ::open("/dev/pango_pci_driver", O_RDWR | O_SYNC);
        if (fd_ < 0) {
            err_ = "open driver failed";
            return false;
        }
        DmaOp a{};
        a.cmd = 0;
        a.total_length = 4 * 1024 * 1024;
        if (ioctlTmo(MAP_CMD, &a, 3) != 0) {
            err_ = "map tx failed";
            return false;
        }
        DmaOp b{};
        b.cmd = 1;
        b.total_length = 4 * 1024 * 1024;
        if (ioctlTmo(MAP_CMD, &b, 3) != 0) {
            err_ = "map rx failed";
            return false;
        }
        tx_ = (uint8_t *)mmap(nullptr, 4 * 1024 * 1024, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
        rx_ = (uint8_t *)mmap(nullptr, 4 * 1024 * 1024, PROT_READ | PROT_WRITE, MAP_SHARED, fd_,
                              1024 * 1024);
        if (tx_ == MAP_FAILED || rx_ == MAP_FAILED) {
            err_ = "mmap failed";
            return false;
        }
        return true;
    }

    static void alarmHandler(int) { timeoutHit_ = true; }
    static volatile sig_atomic_t timeoutHit_;

    bool regWrite(uint32_t addr, uint32_t val) {
        StallTiming::IoctlDrain diagnosticDrain;
        QMutexLocker dmaLock(&dmaMutex_);
        if (!tx_)
            return false;
        memcpy(tx_, &val, 4);
        DmaOp op{};
        op.offset_addr = 0;
        op.ddr3_addr = addr;
        op.total_length = 16;
        return ioctlTmo(H2F_CMD, &op, 3) == 0;
    }

    bool regRead(uint32_t addr, uint32_t &val) {
        StallTiming::IoctlDrain diagnosticDrain;
        QMutexLocker dmaLock(&dmaMutex_);
        DmaOp op{};
        op.offset_addr = tdm::cameraScratchOffset;
        op.ddr3_addr = addr;
        op.total_length = 16;
        if (ioctlTmo(F2H_CMD, &op, 3) != 0)
            return false;
        memcpy(&val, rx_ + op.offset_addr, 4);
        return true;
    }

    /* 六路采集线程共用一条 DMA 通道与同一对 tx/rx 缓冲，必须串行化。
       单次等待上限取 2s（与 camview 一致）：丢 MSI 时不能让整块卡住几十秒，
       上层线程会保留上一帧并在下一次帧标签变化时重试。 */
    bool ddrRead(uint32_t addr, uint32_t len, void *out) {
        StallTiming::IoctlDrain diagnosticDrain;
        if (len > tdm::cameraAllocationBytes || (!out && len)) return false;
        QMutexLocker dmaLock(&dmaMutex_);
        uint8_t* destination = static_cast<uint8_t*>(out);
        for (uint32_t copied = 0; copied < len;) {
            const uint32_t bytes = std::min(len - copied,
                tdm::cameraAllocationBytes - tdm::cameraScratchOffset);
            DmaOp op{};
            op.offset_addr = tdm::cameraScratchOffset;
            op.ddr3_addr = addr + copied;
            op.total_length = std::max(16u, bytes);
            if (ioctlTmo(F2H_CMD, &op, 2) != 0) return false;
            memcpy(destination + copied, rx_ + op.offset_addr, bytes);
            copied += bytes;
        }
        return true;
    }

    /* 帧标签：FPGA 每写完一帧就把 tag 递增，据此判断乒乓缓冲是否更新（参考 camview） */
    bool readTag(uint32_t addr, uint32_t &val) {
        uint8_t raw[16] = {0};
        if (!ddrRead(addr, sizeof(raw), raw))
            return false;
        memcpy(&val, raw, sizeof(val));
        return true;
    }

    // One worker per camera owns its RX slot until the CPU copy is complete.
    // All DMA submissions remain serialized; metadata uses a separate scratch.
    int cameraRead(int camera, uint32_t ping, uint32_t pong, bool delivered, uint32_t last,
                   void* output, uint32_t& selected, qint64& dmaNs, qint64& copyNs,
                   qint64& capturedMs, StallTiming::CameraAttempt& diagnostic) {
        StallTiming::IoctlDrain diagnosticDrain;
        if (camera < 0 || camera >= CAM_COUNT) return -1;
        const auto waitBegin = StallTiming::Stamp::now();
        QMutexLocker lock(&dmaMutex_);
        const auto holdBegin = StallTiming::Stamp::now();
        diagnostic.add(StallTiming::DmaWait, waitBegin, holdBegin);
        auto diagnosticReturn = [&](int result) {
            lock.unlock();
            diagnostic.add(StallTiming::DmaHold, holdBegin, StallTiming::Stamp::now());
            return result;
        };
        uint32_t a = 0, b = 0;
        if (!cameraTagLocked(ping + FRAME_BYTES, a) || !cameraTagLocked(pong + FRAME_BYTES, b)) return diagnosticReturn(-1);
        const int bank = tdm::newestCameraBank(a, b, delivered, last);
        if (bank < 0) return diagnosticReturn(0);
        selected = bank == 0 ? a : b;
        DmaOp op{};
        op.offset_addr = tdm::cameraSlotOffset(camera);
        op.ddr3_addr = bank == 0 ? ping : pong;
        op.total_length = FRAME_BYTES + 16;
        QElapsedTimer timer; timer.start();
        if (ioctlTmo(F2H_CMD, &op, 2) != 0) return diagnosticReturn(-1);
        dmaNs = timer.nsecsElapsed();
        capturedMs = monotonicMs();
        const uint8_t* pixels = rx_ + op.offset_addr;
        uint32_t actual = 0;
        memcpy(&actual, pixels + FRAME_BYTES, sizeof(actual));
        if (actual != selected) return diagnosticReturn(2);
        diagnosticReturn(1);
        timer.restart();
        const auto copyBegin = StallTiming::Stamp::now();
        tdm::copyCameraPixels(output, pixels, FRAME_BYTES);
        const auto copyEnd = StallTiming::Stamp::now();
        copyNs = timer.nsecsElapsed();
        diagnostic.add(StallTiming::Copy, copyBegin, copyEnd);
        return 1;
    }

    const char *lastErr() const { return err_; }

private:
    bool cameraTagLocked(uint32_t address, uint32_t& tag) {
        DmaOp op{};
        op.offset_addr = tdm::cameraScratchOffset;
        op.ddr3_addr = address;
        op.total_length = 16;
        if (ioctlTmo(F2H_CMD, &op, 2) != 0) return false;
        memcpy(&tag, rx_ + op.offset_addr, sizeof(tag));
        return true;
    }
    int ioctlTmo(unsigned long cmd, DmaOp *op, unsigned sec) {
        const uint32_t requestedAddress = op ? op->ddr3_addr : 0;
        const uint32_t requestedOffset = op ? op->offset_addr : 0;
        const uint32_t requestedBytes = op ? op->total_length : 0;
        timeoutHit_ = false;
        struct timespec ts0{}, ts1{};
        clock_gettime(CLOCK_MONOTONIC, &ts0);
        alarm(sec);
        const auto syscallBegin = StallTiming::Stamp::now();
        int r = ::ioctl(fd_, cmd, op);
        const int ioctlErrno = errno;
        const auto syscallEnd = StallTiming::Stamp::now();
        alarm(0);
        clock_gettime(CLOCK_MONOTONIC, &ts1);
        const double ms = (ts1.tv_sec - ts0.tv_sec) * 1000.0 +
                          (ts1.tv_nsec - ts0.tv_nsec) / 1e6;
        StallTiming::Span legacyLog;
        if (ms >= 30.0) {
            const auto logBegin = StallTiming::Stamp::now();
            fprintf(stderr, "[diag] t=%lld.%03ld pango_ioctl cmd=%lx addr=0x%08x len=%u ms=%.3f rc=%d errno=%d alarm=%d\n",
                    (long long)ts1.tv_sec, ts1.tv_nsec / 1000000, cmd,
                    op ? op->ddr3_addr : 0, op ? op->total_length : 0,
                    ms, r, ioctlErrno, (int)timeoutHit_);
            fflush(stderr);
            legacyLog = StallTiming::Span::between(logBegin, StallTiming::Stamp::now());
        }
        auto recordDiagnostic = [&](int applicationRc) {
            StallTiming::IoctlRecord record;
            record.syscall = StallTiming::Span::between(syscallBegin, syscallEnd);
            record.legacyLog = legacyLog;
            record.wrapperBegin = uint64_t(ts0.tv_sec) * 1000000000ULL + uint64_t(ts0.tv_nsec);
            record.wrapperEnd = uint64_t(ts1.tv_sec) * 1000000000ULL + uint64_t(ts1.tv_nsec);
            record.device = reinterpret_cast<uintptr_t>(this);
            record.command = cmd;
            record.address = requestedAddress;
            record.offset = requestedOffset;
            record.bytes = requestedBytes;
            record.rc = r; record.savedErrno = ioctlErrno;
            record.alarm = timeoutHit_; record.applicationRc = applicationRc;
            for (int camera = 0; camera < CAM_COUNT; ++camera) {
                for (int bank = 0; bank < 2; ++bank) {
                    const uint32_t base = CAM_BASE[camera][bank];
                    if (record.address >= base && record.address <= base + FRAME_BYTES) {
                        record.camera = camera + 1;
                        if (cmd == F2H_CMD && record.address == base + FRAME_BYTES && record.bytes == 16)
                            record.role = 1;
                        else if (cmd == F2H_CMD && record.address == base && record.bytes == FRAME_BYTES + 16)
                            record.role = 2;
                    }
                }
            }
            StallTiming::ioctls().record(record);
        };
        if (timeoutHit_) {
            err_ = "ioctl timeout";
            recordDiagnostic(-1);
            noteFailure();
            return -1;
        }
        if (r < 0) {
            recordDiagnostic(r);
            noteFailure();
            return r;
        }
        failures_ = 0;
        recordDiagnostic(r);
        return r;
    }
    /* 连续失败自愈：驱动的 pango_cdev_open 每次打开设备都会把 g_dma_flag 等状态清零，
       所以"退出进程 + 重新打开"本身就等于恢复，不需要 rmmod/insmod。连续失败到阈值就
       主动退出（硬退出，避免卡住的线程拖延），交给守护脚本 run_detview.sh 重启。 */
    void noteFailure() {
        const int n = ++failures_;
        if (n < kRecoverAfterFailures)
            return;
        fprintf(stderr, "[recover] %d consecutive pango ioctl failures -> exit(3) for supervisor restart\n", n);
        fflush(stderr);
        ::_exit(3);
    }
    void close() {
        if (fd_ >= 0)
            ::close(fd_);
        fd_ = -1;
    }
    const char *err_ = "ok";
    int fd_ = -1;
    uint8_t *tx_ = nullptr;
    uint8_t *rx_ = nullptr;
    QMutex dmaMutex_;   // 保护 tx_/rx_ 与 DMA ioctl（四路采集线程共用）
    static const int kRecoverAfterFailures = 6;   // 连续失败几次就退出，让守护脚本重启
    std::atomic<int> failures_{0};
};

volatile sig_atomic_t PangoDev::timeoutHit_ = 0;

/* ---------------- 四路采集（与运行版 camview 同构） ----------------
   每路一个线程：轮询本路 ping/pong 帧标签 -> DDR DMA 读整帧 -> 存入 LatestFrames。
   合成与显示由 CameraThread 按“代（gen）变化”推进，避免空转重绘。 */
struct LatestFrames {
    QMutex mutex;
    QByteArray c[CAM_COUNT];
    bool have[CAM_COUNT] = {};
    uint64_t errors[CAM_COUNT] = {};
    double fps[CAM_COUNT] = {};
    qint64 lastCapturedMs[CAM_COUNT] = {};
    qint64 rawCapturedMs[CAM_COUNT] = {};
    quint32 tags[CAM_COUNT] = {};
    int sourceGenerations[CAM_COUNT] = {};
    uint64_t gen = 0;                // 存下任意一帧就自增（显示侧据此推进）
    uint64_t camGen[CAM_COUNT] = {}; // 每路自己的帧计数（只转换变化的那一路）
};

/* 单行 RGB565 -> RGB888（推理输入与四路合成都用它） */
static void rgb565ToRgb888Line(const uint8_t *src, int pixels, uint8_t *dst) {
    const uint16_t *s = reinterpret_cast<const uint16_t *>(src);
    for (int i = 0; i < pixels; i++) {
        const uint16_t v = s[i];
        const uint8_t r5 = (v >> 11) & 0x1F;
        const uint8_t g6 = (v >> 5) & 0x3F;
        const uint8_t b5 = v & 0x1F;
        dst[3 * i + 0] = (r5 << 3) | (r5 >> 2);
        dst[3 * i + 1] = (g6 << 2) | (g6 >> 4);
        dst[3 * i + 2] = (b5 << 3) | (b5 >> 2);
    }
}

class CameraWorker : public QThread {
public:
    CameraWorker(PangoDev *dev, LatestFrames *frames, int camera)
        : dev_(dev), frames_(frames), camera_(camera) {}
    void stop() { running_ = false; }
    /* Deliver owned camera pixels to a bounded analytics mailbox, not a GUI event queue. */
    void setVisionSink(const std::atomic<int> *pane, const std::atomic<int> *generation,
                       std::atomic<quint64> *sequence, std::function<void(const VisionFrame&)> sink,
                       int stereoMask) {
        inferPane_ = pane;
        generation_ = generation;
        sequence_ = sequence;
        visionSink_ = std::move(sink);
        stereoMask_ = stereoMask;
    }
    /* 当前显示模式（0..5 = 单路，CAM_COUNT = 整幅）：单路时只采那一路，其余停采 */
    void setModePtr(const std::atomic<int> *mode) { mode_ = mode; }
    void setPausedPtr(const std::atomic<bool> *paused) { paused_ = paused; }

protected:
    void run() override {
        static const uint32_t base[CAM_COUNT][2] = {
            {CAM_BASE[0][0], CAM_BASE[0][1]}, {CAM_BASE[1][0], CAM_BASE[1][1]},
            {CAM_BASE[2][0], CAM_BASE[2][1]}, {CAM_BASE[3][0], CAM_BASE[3][1]},
            {CAM_BASE[4][0], CAM_BASE[4][1]}, {CAM_BASE[5][0], CAM_BASE[5][1]}};
        const int idx = camera_ - 1;
        uint32_t deliveredTag = 0;
        bool delivered = false;
        QByteArray frame(FRAME_BYTES, 0);
        StallTiming::CameraWindow diagnosticWindow(idx + 1);
        tdm::FrameRate captureRate;
        captureRate.reset(monotonicMs());
        qint64 auditStartMs = monotonicMs(), readNs = 0, dmaNsTotal = 0, copyNsTotal = 0;
        uint64_t auditFrames = 0, sequenceAdvance = 0, unstable = 0;
        bool measuring = true;
        bool measureTagAdvance = false;
        auto suspendMeasurement = [&]() {
            if (!measuring) return;
            measuring = false;
            measureTagAdvance = false;
            QMutexLocker lock(&frames_->mutex);
            frames_->fps[idx] = 0;
            frames_->lastCapturedMs[idx] = 0;
        };
        while (running_) {
            diagnosticWindow.poll();
            if (paused_ && paused_->load()) { suspendMeasurement(); msleep(20); continue; }
            const int sourceGeneration = generation_ ? generation_->load() : 0;
            /* 设备模式：整幅时六路全采；单选时只采那一路（其余不发 DMA、不轮询标签） */
            if (mode_) {
                const int mode = mode_->load();
                if (mode != CAM_COUNT && mode != idx && !(stereoMask_ & (1 << idx))) {
                    suspendMeasurement();
                    msleep(50);
                    continue;
                }
            }
            if (!measuring) {
                measuring = true;
                captureRate.reset(monotonicMs());
                auditStartMs = monotonicMs(); auditFrames = sequenceAdvance = unstable = 0;
                readNs = dmaNsTotal = copyNsTotal = 0;
            }
            StallTiming::CameraAttempt diagnostic(diagnosticWindow);
            const auto readBegin = StallTiming::Stamp::now();
            QElapsedTimer readTimer; readTimer.start();
            // A display snapshot may still own this recycled buffer. Allocate
            // fresh writable storage instead of copying old pixels on detach;
            // cameraRead overwrites every pixel before publishing it.
            const auto allocBegin = StallTiming::Stamp::now();
            if (!frame.isDetached()) frame = QByteArray(FRAME_BYTES, Qt::Uninitialized);
            char* writablePixels = frame.data();
            diagnostic.add(StallTiming::Alloc, allocBegin, StallTiming::Stamp::now());
            uint32_t selectedTag = 0;
            qint64 dmaNs = 0, copyNs = 0, capturedMs = 0;
            const int result = dev_->cameraRead(idx, base[idx][0], base[idx][1], delivered, deliveredTag,
                                                writablePixels, selectedTag, dmaNs, copyNs, capturedMs, diagnostic);
            diagnostic.add(StallTiming::Read, readBegin, StallTiming::Stamp::now());
            if (result == 0) { diagnostic.finish(result); msleep(6); continue; }
            if (result == 2) { ++unstable; diagnostic.finish(result); msleep(1); continue; }
            if (result < 0) {
                const auto publishWaitBegin = StallTiming::Stamp::now();
                { QMutexLocker lock(&frames_->mutex);
                  const auto publishHoldBegin = StallTiming::Stamp::now();
                  diagnostic.add(StallTiming::PublishWait, publishWaitBegin, publishHoldBegin);
                  ++frames_->errors[idx];
                  lock.unlock();
                  diagnostic.add(StallTiming::PublishHold, publishHoldBegin, StallTiming::Stamp::now()); }
                diagnostic.finish(result);
                msleep(25);
                continue;
            }
            if (delivered && measureTagAdvance) {
                sequenceAdvance += uint32_t(selectedTag - deliveredTag);
                diagnostic.tag(deliveredTag, selectedTag);
            }
            measureTagAdvance = true;
            deliveredTag = selectedTag;
            delivered = true;
            readNs += readTimer.nsecsElapsed();
            dmaNsTotal += dmaNs; copyNsTotal += copyNs; ++auditFrames;
            const qint64 completedMs = monotonicMs();
            captureRate.add(completedMs);
            if (visionSink_ && ((inferPane_ && inferPane_->load() == idx) || (stereoMask_ & (1 << idx))) &&
                generation_ && sourceGeneration == generation_->load()) {
                const auto imageAllocBegin = StallTiming::Stamp::now();
                QImage pixels(IMG_W, IMG_H, QImage::Format_RGB888);
                diagnostic.add(StallTiming::Alloc, imageAllocBegin, StallTiming::Stamp::now());
                const auto convertBegin = StallTiming::Stamp::now();
                const uint16_t *src = reinterpret_cast<const uint16_t *>(frame.constData());
                for (int y = 0; y < IMG_H; ++y)
                    rgb565ToRgb888Line(reinterpret_cast<const uint8_t *>(src + (size_t)y * IMG_W),
                                       IMG_W, pixels.scanLine(y));
                diagnostic.add(StallTiming::Convert, convertBegin, StallTiming::Stamp::now());
                VisionFrame packet;
                packet.image = std::move(pixels);
                packet.frameId = sequence_->fetch_add(1) + 1;
                packet.camera = idx;
                packet.sourceGeneration = sourceGeneration;
                packet.tag = selectedTag;
                packet.capturedMs = capturedMs;
                const auto sinkBegin = StallTiming::Stamp::now();
                visionSink_(packet);
                diagnostic.add(StallTiming::Sink, sinkBegin, StallTiming::Stamp::now());
            }
            const auto publishWaitBegin = StallTiming::Stamp::now();
            QMutexLocker lock(&frames_->mutex);
            const auto publishHoldBegin = StallTiming::Stamp::now();
            diagnostic.add(StallTiming::PublishWait, publishWaitBegin, publishHoldBegin);
            /* 零拷贝交接：与槽位互换缓冲。原来 `frames_->c[idx] = frame` 会因
               QByteArray 隐式共享在下一次写入时 detach（每帧每路白拷 0.6MB，
               4~6 路 × 25fps ≈ 60~90MB/s 的 DDR 流量）。交换后采集线程拿回旧缓冲继续用。 */
            qSwap(frame, frames_->c[idx]);
            if (frame.size() != FRAME_BYTES) {
                const auto resizeBegin = StallTiming::Stamp::now();
                frame.resize(FRAME_BYTES);
                diagnostic.add(StallTiming::Alloc, resizeBegin, StallTiming::Stamp::now());
            }
            frames_->have[idx] = true;
            frames_->lastCapturedMs[idx] = completedMs;
            frames_->rawCapturedMs[idx] = capturedMs;
            frames_->tags[idx] = selectedTag;
            frames_->sourceGenerations[idx] = sourceGeneration;
            ++frames_->gen;
            ++frames_->camGen[idx];
            frames_->fps[idx] = captureRate.rate(completedMs);
            lock.unlock();
            diagnostic.add(StallTiming::PublishHold, publishHoldBegin, StallTiming::Stamp::now());
            diagnostic.finish(result);
            const qint64 auditNow = monotonicMs();
            if (auditNow - auditStartMs >= 5000) {
                const double seconds = (auditNow - auditStartMs) / 1000.0;
                fprintf(stderr, "[capture] camera=%d delivered_fps=%.2f tag_advance_rate=%.2f read_ms=%.3f frame_dma_ms=%.3f copy_ms=%.3f unstable=%llu\n",
                        idx + 1, auditFrames / seconds, sequenceAdvance / seconds,
                        readNs / 1e6 / auditFrames, dmaNsTotal / 1e6 / auditFrames,
                        copyNsTotal / 1e6 / auditFrames, (unsigned long long)unstable);
                auditStartMs = auditNow; auditFrames = sequenceAdvance = unstable = 0;
                readNs = dmaNsTotal = copyNsTotal = 0;
            }
            msleep(6);
        }
    }

private:
    PangoDev *dev_;
    LatestFrames *frames_;
    int camera_;
    std::atomic_bool running_{true};
    const std::atomic<int> *inferPane_ = nullptr;
    const std::atomic<int> *generation_ = nullptr;
    const std::atomic<bool> *paused_ = nullptr;
    std::atomic<quint64> *sequence_ = nullptr;
    int stereoMask_ = 0;
    const std::atomic<int> *mode_ = nullptr;
    std::function<void(const VisionFrame&)> visionSink_;
};

