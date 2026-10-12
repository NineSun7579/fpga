// detview - OV5640 live detection UI for RK3568 + Pango FPGA + RKNN
// Cam path: OV5640 -> DDR3 ping-pong (0x00800000/0x00A00000, RGB565 640x480)
//           -> PCIe DMA read -> letterbox 640x640 -> RKNN model
#include <QApplication>
#include <QAction>
#include <QComboBox>
#include <QCheckBox>
#include <QHash>
#include <QMenu>
#include <QTimer>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QKeyEvent>
#include <QLabel>
#include <QMutex>
#include <QOpenGLFunctions>
#include <QOpenGLShaderProgram>
#include <QOpenGLWindow>
#include <QPainter>
#include <QProcess>
#include <QPushButton>
#include <QScreen>
#include <QSlider>
#include <QThread>
#include <QVBoxLayout>
#include <QWaitCondition>
#include <QWidget>

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <csignal>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <fcntl.h>
#include <functional>
#include <memory>
#include <stdexcept>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <time.h>
#include <vector>

#include "vision_types.h"
#include "vision_pipeline.h"
#include "template_tracker.h"
#include "camera_dma.h"
#include "capture_pacing.h"
#include "frame_metrics.h"
#include "display_perf.h"
#include "inference_preprocess.h"
#include "stereo_demo/stereo_depth.h"

#include "rknn_api.h"

#include <rga/im2d.h>
#include <rga/rga.h>

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

static qint64 monotonicNs() {
    timespec stamp{};
    clock_gettime(CLOCK_MONOTONIC, &stamp);
    return stamp.tv_sec * 1000000000LL + stamp.tv_nsec;
}
static qint64 monotonicMs() { return monotonicNs() / 1000000; }

/* ---------------- dma-heap 缓冲：RGA 只能操作 dma-buf ---------------- */
struct DmaHeapAllocData {
    uint64_t len;
    uint32_t fd;
    uint32_t fd_flags;
    uint64_t heap_flags;
};
#define DMA_HEAP_IOC_MAGIC 'H'
#define DMA_HEAP_IOCTL_ALLOC _IOWR(DMA_HEAP_IOC_MAGIC, 0x0, struct DmaHeapAllocData)

struct DmaBuffer {
    int fd = -1;
    void *p = nullptr;
    size_t size = 0;

    bool alloc(size_t bytes) {
        release();
        const int heap = ::open("/dev/dma_heap/system", O_RDWR | O_CLOEXEC);
        if (heap < 0)
            return false;
        DmaHeapAllocData data{};
        data.len = bytes;
        data.fd_flags = O_RDWR | O_CLOEXEC;
        const bool ok = ioctl(heap, DMA_HEAP_IOCTL_ALLOC, &data) == 0;
        ::close(heap);
        if (!ok)
            return false;
        fd = (int)data.fd;
        size = bytes;
        p = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        if (p == MAP_FAILED) {
            p = nullptr;
            release();
            return false;
        }
        return true;
    }
    /* 只在需要更大时重新分配，避免每帧分配 */
    bool ensure(size_t bytes) { return size >= bytes ? true : alloc(bytes); }
    void release() {
        if (p) {
            munmap(p, size);
            p = nullptr;
        }
        if (fd >= 0) {
            ::close(fd);
            fd = -1;
        }
        size = 0;
    }
};

struct DmaOp {
    uint32_t current_len, offset_addr, cmd, ddr3_addr, total_length;
    void *read_buf, *write_buf;
};

struct ModelInfo {
    QString path;
    QStringList classes;
    int nc = 1;
    bool xyxy = false;
    bool lane = false;
};

static bool selectRotation(const QVector<ModelInfo>& models, const QStringList& selectors,
                           QVector<ModelInfo>& chosen) {
    chosen.clear();
    if (selectors.size() < 2 || selectors.size() > 4) return false;
    for (const QString& selector : selectors) {
        if (selector.trimmed().isEmpty()) return false;
        ModelInfo match;
        int count = 0;
        for (const auto& candidate : models) {
            if (!candidate.lane && QFileInfo(candidate.path).fileName().startsWith("det-") &&
                candidate.path.contains(selector.trimmed(), Qt::CaseInsensitive)) {
                match = candidate;
                ++count;
            }
        }
        if (count != 1) return false;
        for (const auto& already : chosen) if (already.path == match.path) return false;
        chosen.append(match);
    }
    return true;
}

static QVector<ModelInfo> scanModels() {
    QVector<ModelInfo> list;
    const QStringList dirs = {"/root/npu/yolov8n/zebra640", "/root/npu/yolov8n/vehicle640",
                              "/root/npu", "/root/npu/yolo11n", "/root/models/yolo26_rk3568",
                              "/root/npu/tt100k", "/root/npu/tt100k_yolov8n",
                              "/root/npu/lane_linknet", "/root/npu/whiteboard_3cls"};
    for (const QString &d : dirs) {
        QDir dir(d);
        const QStringList files = dir.entryList(QStringList() << "*.rknn", QDir::Files, QDir::Name);
        for (const QString &f : files) {
            ModelInfo mi;
            mi.path = dir.absoluteFilePath(f);
            const QString lower = f.toLower();
            if (lower.startsWith("seg-linknet-lane640-")) {
                mi.lane = true;
                mi.nc = lower.contains("multiclass") ? 9 : 2;
                mi.classes = mi.nc == 9
                    ? (QStringList() << "background" << "lane0" << "lane1" << "lane2"
                                     << "lane3" << "lane4" << "lane5" << "lane6" << "lane7")
                    : (QStringList() << "background" << "lane");
            } else if (lower.contains("tt100k")) {
                mi.classes = QStringList() << "非机动车" << "机动车" << "靠右侧行驶" << "人行横道"
                                           << "禁止掉头" << "禁止机动车驶入" << "禁止鸣喇叭"
                                           << "禁止右转" << "禁止左转" << "禁止货车驶入"
                                           << "减速让行" << "限高4.5m" << "限速20" << "限速30"
                                           << "限速40" << "限速50" << "限速60" << "限速70"
                                           << "限速80" << "限速100" << "限速120" << "限质20t"
                                           << "禁止驶入" << "停车让行" << "十字路口" << "施工"
                                           << "注意儿童" << "注意行人" << "注意合流";
                mi.nc = 29;
                mi.xyxy = false;
            } else if (lower.contains("yolo11n") && lower.startsWith("det")) {
                mi.classes = QStringList() << "person"
                                           << "vehicle"
                                           << "traffic_light"
                                           << "traffic_sign";
                mi.nc = 4;
                mi.xyxy = false;
            } else if (lower.contains("yolo11n") && lower.startsWith("seg")) {
                mi.classes = QStringList() << "crosswalk"
                                           << "lane_solid"
                                           << "lane_dashed"
                                           << "stop_line"
                                           << "arrow"
                                           << "road_marking";
                mi.nc = 6;
                mi.xyxy = false;
            } else if (lower.contains("-3cls-wb")) {
                /* 白板剪枝压缩实验（V0 base → V4 combo）：沿用 zebra/vehicle/person 三类 */
                mi.classes = QStringList() << "zebra"
                                           << "vehicle"
                                           << "person";
                mi.nc = 3;
                mi.xyxy = false;
            } else if (lower.contains("yolov8n")) {
                if (lower.contains("zebra")) {
                    mi.classes = QStringList() << "zebra"
                                               << "vehicle"
                                               << "person";
                    mi.nc = 3;
                } else {
                    mi.classes = QStringList() << "vehicle";
                    mi.nc = 1;
                }
                mi.xyxy = false;  // [1,4,N] cx,cy,w,h + [1,nc,N] scores (已 sigmoid)
            } else if (lower.contains("zebra")) {
                mi.classes = QStringList() << "zebra"
                                           << "vehicle"
                                           << "person";
                mi.nc = 3;
            } else {
                mi.classes = QStringList() << "vehicle";
                mi.nc = 1;
            }
            list.append(mi);
        }
    }
    return list;
}

class PangoDev {
public:
    ~PangoDev() { close(); }

    bool openDev() {
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
                    qint64& capturedMs, quint64& transferBytes, qint64& frameStartedNs) {
        transferBytes = 0;
        frameStartedNs = 0;
        if (camera < 0 || camera >= CAM_COUNT) return -1;
        QMutexLocker lock(&dmaMutex_);
        uint32_t a = 0, b = 0;
        if (!cameraTagLocked(ping + FRAME_BYTES, a)) return -1;
        transferBytes += 16;
        if (!cameraTagLocked(pong + FRAME_BYTES, b)) return -1;
        transferBytes += 16;
        const int bank = tdm::newestCameraBank(a, b, delivered, last);
        if (bank < 0) return 0;
        selected = bank == 0 ? a : b;
        DmaOp op{};
        op.offset_addr = tdm::cameraSlotOffset(camera);
        op.ddr3_addr = bank == 0 ? ping : pong;
        op.total_length = FRAME_BYTES + 16;
        QElapsedTimer timer; timer.start();
        frameStartedNs = monotonicNs();
        if (ioctlTmo(F2H_CMD, &op, 2) != 0) return -1;
        transferBytes += op.total_length;
        dmaNs = timer.nsecsElapsed();
        capturedMs = monotonicMs();
        const uint8_t* pixels = rx_ + op.offset_addr;
        uint32_t actual = 0;
        memcpy(&actual, pixels + FRAME_BYTES, sizeof(actual));
        if (actual != selected) return 2;
        lock.unlock();
        timer.restart();
        tdm::copyCameraPixels(output, pixels, FRAME_BYTES);
        copyNs = timer.nsecsElapsed();
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
        timeoutHit_ = false;
        struct timespec ts0{}, ts1{};
        clock_gettime(CLOCK_MONOTONIC, &ts0);
        alarm(sec);
        int r = ::ioctl(fd_, cmd, op);
        const int ioctlErrno = errno;
        alarm(0);
        clock_gettime(CLOCK_MONOTONIC, &ts1);
        const double ms = (ts1.tv_sec - ts0.tv_sec) * 1000.0 +
                          (ts1.tv_nsec - ts0.tv_nsec) / 1e6;
        if (ms >= 30.0) {
            fprintf(stderr, "[diag] t=%lld.%03ld pango_ioctl cmd=%lx addr=0x%08x len=%u ms=%.3f rc=%d errno=%d alarm=%d\n",
                    (long long)ts1.tv_sec, ts1.tv_nsec / 1000000, cmd,
                    op ? op->ddr3_addr : 0, op ? op->total_length : 0,
                    ms, r, ioctlErrno, (int)timeoutHit_);
            fflush(stderr);
        }
        if (timeoutHit_) {
            err_ = "ioctl timeout";
            noteFailure();
            return -1;
        }
        if (r < 0) {
            noteFailure();
            return r;
        }
        failures_ = 0;
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
        tdm::FrameRate captureRate;
        captureRate.reset(monotonicMs());
        qint64 auditStartMs = monotonicMs(), readNs = 0, dmaNsTotal = 0, copyNsTotal = 0;
        uint64_t auditFrames = 0, sequenceAdvance = 0, unstable = 0;
        quint64 auditBytes = 0, auditFrameDmas = 0, auditPolls = 0, auditReadErrors = 0;
        const int captureMaximumFps = qBound(0, qEnvironmentVariableIntValue("DETVIEW_CAPTURE_MAX_FPS"), 120);
        tdm::CapturePacing pacing(captureMaximumFps);
        auto reportCapture = [&](bool force) {
            const qint64 now = monotonicMs();
            if ((!force && now - auditStartMs < 5000) || now <= auditStartMs) return;
            const double seconds = (now - auditStartMs) / 1000.0;
            fprintf(stderr, "[capture] camera=%d delivered_fps=%.2f tag_advance_rate=%.2f read_ms=%.3f frame_dma_ms=%.3f copy_ms=%.3f unstable=%llu\n",
                    idx + 1, auditFrames / seconds, sequenceAdvance / seconds,
                    auditFrames ? readNs / 1e6 / auditFrames : 0,
                    auditFrames ? dmaNsTotal / 1e6 / auditFrames : 0,
                    auditFrames ? copyNsTotal / 1e6 / auditFrames : 0, (unsigned long long)unstable);
            fprintf(stderr, "[capture-traffic] camera=%d started_ms=%lld ended_ms=%lld seconds=%.3f polls=%llu frame_dmas=%llu dma_bytes=%llu delivered_frames=%llu unstable=%llu read_errors=%llu maximum_fps=%d\n",
                    idx + 1, (long long)auditStartMs, (long long)now, seconds,
                    (unsigned long long)auditPolls, (unsigned long long)auditFrameDmas,
                    (unsigned long long)auditBytes, (unsigned long long)auditFrames,
                    (unsigned long long)unstable, (unsigned long long)auditReadErrors, captureMaximumFps);
            auditStartMs = now; auditFrames = sequenceAdvance = unstable = 0;
            readNs = dmaNsTotal = copyNsTotal = 0;
            auditBytes = auditFrameDmas = auditPolls = auditReadErrors = 0;
        };
        bool measuring = true;
        bool measureTagAdvance = false;
        auto suspendMeasurement = [&]() {
            if (!measuring) return;
            reportCapture(true);
            measuring = false;
            measureTagAdvance = false;
            pacing.reset();
            QMutexLocker lock(&frames_->mutex);
            frames_->fps[idx] = 0;
            frames_->lastCapturedMs[idx] = 0;
        };
        while (running_) {
            if (measuring) reportCapture(false);
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
                auditBytes = auditFrameDmas = auditPolls = auditReadErrors = 0;
            }
            const qint64 pacingWait = pacing.waitNs(monotonicNs());
            if (pacingWait > 0) {
                msleep(static_cast<unsigned long>(std::min<qint64>(10, (pacingWait + 999999) / 1000000)));
                continue;
            }
            QElapsedTimer readTimer; readTimer.start();
            // A display snapshot may still own this recycled buffer. Allocate
            // fresh writable storage instead of copying old pixels on detach;
            // cameraRead overwrites every pixel before publishing it.
            if (!frame.isDetached()) frame = QByteArray(FRAME_BYTES, Qt::Uninitialized);
            uint32_t selectedTag = 0;
            qint64 dmaNs = 0, copyNs = 0, capturedMs = 0;
            quint64 transferBytes = 0;
            qint64 frameStartedNs = 0;
            const int result = dev_->cameraRead(idx, base[idx][0], base[idx][1], delivered, deliveredTag,
                                                frame.data(), selectedTag, dmaNs, copyNs, capturedMs, transferBytes, frameStartedNs);
            if (frameStartedNs) pacing.delivered(frameStartedNs);
            auditBytes += transferBytes; ++auditPolls;
            if (result == 1 || result == 2) ++auditFrameDmas;
            if (result == 0) { msleep(6); continue; }
            if (result == 2) { ++unstable; msleep(1); continue; }
            if (result < 0) {
                ++auditReadErrors;
                { QMutexLocker lock(&frames_->mutex); ++frames_->errors[idx]; }
                msleep(25);
                continue;
            }
            if (delivered && measureTagAdvance) sequenceAdvance += uint32_t(selectedTag - deliveredTag);
            measureTagAdvance = true;
            deliveredTag = selectedTag;
            delivered = true;
            readNs += readTimer.nsecsElapsed();
            dmaNsTotal += dmaNs; copyNsTotal += copyNs; ++auditFrames;
            const qint64 completedMs = monotonicMs();
            captureRate.add(completedMs);
            if (visionSink_ && ((inferPane_ && inferPane_->load() == idx) || (stereoMask_ & (1 << idx))) &&
                generation_ && sourceGeneration == generation_->load()) {
                QImage pixels(IMG_W, IMG_H, QImage::Format_RGB888);
                const uint16_t *src = reinterpret_cast<const uint16_t *>(frame.constData());
                for (int y = 0; y < IMG_H; ++y)
                    rgb565ToRgb888Line(reinterpret_cast<const uint8_t *>(src + (size_t)y * IMG_W),
                                       IMG_W, pixels.scanLine(y));
                VisionFrame packet;
                packet.image = std::move(pixels);
                packet.frameId = sequence_->fetch_add(1) + 1;
                packet.camera = idx;
                packet.sourceGeneration = sourceGeneration;
                packet.tag = selectedTag;
                packet.capturedMs = capturedMs;
                visionSink_(packet);
            }
            QMutexLocker lock(&frames_->mutex);
            /* 零拷贝交接：与槽位互换缓冲。原来 `frames_->c[idx] = frame` 会因
               QByteArray 隐式共享在下一次写入时 detach（每帧每路白拷 0.6MB，
               4~6 路 × 25fps ≈ 60~90MB/s 的 DDR 流量）。交换后采集线程拿回旧缓冲继续用。 */
            qSwap(frame, frames_->c[idx]);
            if (frame.size() != FRAME_BYTES)
                frame.resize(FRAME_BYTES);
            frames_->have[idx] = true;
            frames_->lastCapturedMs[idx] = completedMs;
            ++frames_->gen;
            ++frames_->camGen[idx];
            frames_->fps[idx] = captureRate.rate(completedMs);
            lock.unlock();
            msleep(6);
        }
        if (measuring) reportCapture(true);
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

class CameraThread : public QThread {
    Q_OBJECT
public:
    struct DisplayFrame {
        QImage image;
        int generation = 0, paneMask = 0, pane = 0, changedMask = 0;
        double fps = 0;
        QVector<double> camFps;
        bool video = false;
        std::array<uint64_t, CAM_COUNT> cameraSequences{};
        std::array<qint64, CAM_COUNT> capturedMs{};
        quint64 videoSequence = 0;
        std::array<QByteArray, CAM_COUNT> cameraPixels{};
        qint64 publishedMs = 0;
        uint64_t replacedBeforeTake = 0;
    };
    DisplayFrame takeDisplay() {
        QMutexLocker lock(&m_displayMutex);
        DisplayFrame frame = m_latestDisplay;
        m_latestDisplay = {};
        m_displayPending = false;
        return frame;
    }
    static bool selfTestDisplay() {
        CameraThread source;
        int notifications = 0;
        QObject::connect(&source, &CameraThread::displayAvailable, &source,
                         [&] { ++notifications; }, Qt::DirectConnection);
        DisplayFrame frame;
        frame.generation = 1; frame.paneMask = 0x3F; frame.changedMask = 1;
        frame.cameraPixels[0] = QByteArray(FRAME_BYTES, char(0x11));
        source.publishDisplay(frame);
        if (source.takeDisplay().changedMask != 0x3F) return false;
        source.publishDisplay(frame);
        // A writer taking a new buffer must not overwrite the GUI's snapshot.
        frame.cameraPixels[0].fill(char(0x22));
        const auto previous = source.takeDisplay();
        if (previous.cameraPixels[0][0] != char(0x11)) return false;
        source.publishDisplay(frame);
        frame.changedMask = 2;
        source.publishDisplay(frame);
        if (notifications != 3) return false;
        const auto newest = source.takeDisplay();
        if (newest.changedMask != 3 || newest.cameraPixels[0][0] != char(0x22)) return false;
        frame.changedMask = 1; source.publishDisplay(frame);
        frame.generation = 2; frame.pane = 1; frame.changedMask = 4;
        source.publishDisplay(frame);
        const auto switched = source.takeDisplay();
        return notifications == 4 && switched.generation == 2 && switched.changedMask == 0x3F &&
               source.takeDisplay().cameraPixels[0].isEmpty();
    }
    void stop() { m_stop = true; }
    void setMode(int mode) {
        QMutexLocker lock(&m_configMutex);
        m_selectedCamera = mode == CAM_COUNT ? (m_options.stereoEnabled() ? m_options.primaryStereoLeft() : 0) : mode;
        m_mode = mode;
    }
    void setSourceGeneration(int generation) {
        QMutexLocker lock(&m_configMutex);
        m_sourceGeneration = generation;
    }
    void setVisionSink(VisionOptions options, std::function<void(const VisionFrame&)> sink) {
        m_options = options;
        m_visionSink = std::move(sink);
        setMode(m_mode.load());
    }
    void setPaused(bool paused) { m_paused = paused; }
    void setVideoSource(const QString &source) { m_videoSource = source; }
    /* 控件尺寸：相机线程据此决定 RGA 缩放目标（letterbox 后的内容尺寸） */
    void setDisplaySize(int w, int h) { m_dispW = w; m_dispH = h; }

signals:
    void displayAvailable();
    /* 四路：已按控件尺寸缩放好的内容帧（RGB888）；ox>=0 表示直接在 (ox,oy) 1:1 贴图，
       ox<0 表示未缩放、由控件自行缩放铺满。paneMask/pane 同前 */
    void frameReady(QImage content, int paneMask, int pane, double fps, QVector<double> camFps,
                    int changedMask);
    /* 视频源路径：单路 RGB888 帧 */
    void imageReady(QImage frame, double fps);
    void statusMsg(QString s);

protected:
    void run() override {
        if (!m_videoSource.isEmpty()) { runVideo(); return; }
        PangoDev dev;
        if (!dev.openDev()) { emit statusMsg(QString("FATAL: ") + dev.lastErr()); return; }
        // 六路采用运行版 camview 6 路版的 DDR 地址和帧标签，不改写 FPGA 相机寄存器。
        LatestFrames latest;
        CameraWorker workers[CAM_COUNT] = {
            CameraWorker(&dev, &latest, 1), CameraWorker(&dev, &latest, 2),
            CameraWorker(&dev, &latest, 3), CameraWorker(&dev, &latest, 4),
            CameraWorker(&dev, &latest, 5), CameraWorker(&dev, &latest, 6)};
        const int stereoMask = m_options.stereoCameraMask();
        for (CameraWorker &w : workers) {
            w.setVisionSink(&m_selectedCamera, &m_sourceGeneration, &m_frameSequence, m_visionSink, stereoMask);
            w.setModePtr(&m_mode);
            w.setPausedPtr(&m_paused);
        }
        for (CameraWorker &w : workers) w.start();
        emit statusMsg("Six-camera DMA ready; 3x2 view, inference uses the selected pane");
        // Same owned per-camera snapshot path as optimized camview: no CPU
        // composite, row copies, or GLES2 tile packing in the display pipeline.
        std::array<QByteArray, CAM_COUNT> cameraPixels;
        uint64_t lastCamGen[CAM_COUNT] = {};
        // Same 16ms submit pacing as current camview, including composition time.
        const int minIntervalMs = qEnvironmentVariableIsSet("DETVIEW_MIN_MS")
                                       ? std::max(0, qEnvironmentVariableIntValue("DETVIEW_MIN_MS")) : 16;
        uint64_t lastGen = 0;
        int lastMode = -1, lastDisplayGeneration = -1;
        /* 诊断：DET_DUMP_COMP=1 时把合成缓冲原样存一张 PNG，用来分辨
           “合成内容错”还是“显示映射错”（两者症状很像） */
        const bool dumpComp = qEnvironmentVariableIsSet("DET_DUMP_COMP");
        bool dumped = false;
        QElapsedTimer startup; startup.start();
        QElapsedTimer rate; rate.start();
        QElapsedTimer displayPace; displayPace.start();
        int frames = 0;
        double fps = 0;
        bool wasPaused = false;
        while (!m_stop) {
            if (m_paused) { wasPaused = true; msleep(25); continue; }
            if (wasPaused) {
                wasPaused = false; rate.restart(); frames = 0; fps = 0;
                displayPace.restart();
            }
            if (minIntervalMs > 0 && displayPace.elapsed() < minIntervalMs) { msleep(1); continue; }
            int mode, displayGeneration, pane;
            {
                QMutexLocker lock(&m_configMutex);
                mode = m_mode.load(); displayGeneration = m_sourceGeneration.load(); pane = m_selectedCamera.load();
            }
            const int paneMask = mode == CAM_COUNT ? 0x3F : (1 << pane);
            bool ready = false;
            uint64_t gen = 0;
            uint64_t camGen[CAM_COUNT] = {};
            uint64_t errors[CAM_COUNT] = {};
            bool have[CAM_COUNT] = {};
            double camFps[CAM_COUNT] = {};
            std::array<qint64, CAM_COUNT> captureTimes{};
            {
                QMutexLocker lock(&latest.mutex);
                for (int i = 0; i < CAM_COUNT; i++)
                    ready = ready || latest.have[i];
                gen = latest.gen;
                if (gen == lastGen && mode == lastMode && displayGeneration == lastDisplayGeneration) {
                    lock.unlock(); msleep(2); continue;
                }
                for (int i = 0; i < CAM_COUNT; i++) {
                    have[i] = latest.have[i];
                    errors[i] = latest.errors[i];
                    camFps[i] = latest.fps[i];
                    captureTimes[i] = latest.lastCapturedMs[i];
                    if (monotonicMs() - captureTimes[i] > 1000) camFps[i] = 0;
                    camGen[i] = latest.camGen[i];
                }
                for (int i = 0; i < CAM_COUNT; ++i)
                    if (have[i]) cameraPixels[i] = latest.c[i];
            }
            if (!ready) { msleep(2); continue; }

            bool freshVisible = false;
            for (int camera = 0; camera < CAM_COUNT; ++camera)
                if ((paneMask & (1 << camera)) && have[camera] && camGen[camera] != lastCamGen[camera])
                    freshVisible = true;
            if (!freshVisible && mode == lastMode && displayGeneration == lastDisplayGeneration) {
                lastGen = gen;
                msleep(2); continue;
            }
            lastGen = gen;
            displayPace.restart();
            lastMode = mode;
            lastDisplayGeneration = displayGeneration;

            int changedMask = 0;   // 本次真正更新的格子（供显示端只传这几块纹理）
            for (int c = 0; c < CAM_COUNT; ++c) {
                const bool firstFrame = (lastCamGen[c] == 0);
                if (!firstFrame && camGen[c] == lastCamGen[c])
                    continue;
                if (!have[c])
                    continue;
                lastCamGen[c] = camGen[c];
                changedMask |= 1 << c;
            }

            if (freshVisible) ++frames;
            if (rate.elapsed() >= 1000) {
                fps = frames * 1000.0 / rate.elapsed();
                frames = 0;
                rate.restart();
                fprintf(stderr,
                        "[panes] mode=%d submit_fps=%.1f have=%d%d%d%d%d%d capture_fps=%.1f/%.1f/%.1f/%.1f/%.1f/%.1f err=%llu/%llu/%llu/%llu/%llu/%llu\n",
                        mode, fps, have[0], have[1], have[2], have[3], have[4], have[5], camFps[0],
                        camFps[1], camFps[2], camFps[3], camFps[4], camFps[5],
                        (unsigned long long)errors[0], (unsigned long long)errors[1],
                        (unsigned long long)errors[2], (unsigned long long)errors[3],
                        (unsigned long long)errors[4], (unsigned long long)errors[5]);
            }
            if (dumpComp && !dumped && startup.elapsed() >= 8000) {
                dumped = true;
                QImage compImg(GRID_COLS * IMG_W, GRID_ROWS * IMG_H, QImage::Format_RGB16);
                compImg.fill(Qt::black);
                for (int c = 0; c < CAM_COUNT; ++c) {
                    if (cameraPixels[c].size() != FRAME_BYTES) continue;
                    for (int y = 0; y < IMG_H; ++y)
                        memcpy(compImg.scanLine((c / GRID_COLS) * IMG_H + y) + (c % GRID_COLS) * IMG_W * 2,
                               cameraPixels[c].constData() + y * IMG_W * 2, IMG_W * 2);
                }
                const bool ok = compImg.save("/tmp/det_comp.png", "PNG");
                fprintf(stderr, "[dump] composite %dx%d stride=%d save=%s\n", compImg.width(), compImg.height(),
                        compImg.bytesPerLine(), ok ? "ok" : "fail");
                fflush(stderr);
            }
            QVector<double> fpsVec;
            for (int i = 0; i < CAM_COUNT; ++i)
                fpsVec.append(camFps[i]);
            DisplayFrame display{{}, displayGeneration, paneMask, pane, changedMask, fps, fpsVec, false};
            display.cameraPixels = cameraPixels;
            std::copy(camGen, camGen + CAM_COUNT, display.cameraSequences.begin());
            display.capturedMs = captureTimes;
            {
                QMutexLocker lock(&m_configMutex);
                if (mode == m_mode.load() && pane == m_selectedCamera.load() &&
                    displayGeneration == m_sourceGeneration.load() && !m_paused)
                    publishDisplay(std::move(display));
            }
        }
        for (CameraWorker &w : workers)
            w.stop();
        for (CameraWorker &w : workers)
            w.wait();
    }

private:
    void runVideo() {
        QProcess decoder;
        QStringList args = {"-nostdin", "-loglevel", "error"};
        if (m_videoSource.startsWith("/dev/video"))
            args += {"-f", "v4l2"};
        else if (!m_videoSource.contains("://"))
            args.append("-re");
        args += {"-i", m_videoSource, "-an", "-vf",
                 "scale=640:480:force_original_aspect_ratio=decrease:flags=fast_bilinear,pad=640:480:(ow-iw)/2:(oh-ih)/2:color=0x727272",
                 "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"};
        decoder.start("ffmpeg", args, QIODevice::ReadOnly);
        if (!decoder.waitForStarted(5000)) {
            emit statusMsg("视频解码器启动失败");
            return;
        }
        const int bytes = IMG_W * IMG_H * 3;
        QByteArray frame;
        frame.reserve(bytes);
        tdm::FrameRate videoCaptureRate;
        videoCaptureRate.reset(monotonicMs());
        QElapsedTimer audit; audit.start();
        while (!m_stop) {
            while (frame.size() < bytes && decoder.state() != QProcess::NotRunning && !m_stop) {
                if (decoder.bytesAvailable() == 0 && !decoder.waitForReadyRead(200)) continue;
                frame += decoder.read(bytes - frame.size());
            }
            if (frame.size() != bytes) break;
            QImage rgb(reinterpret_cast<const uchar *>(frame.constData()),
                       IMG_W, IMG_H, IMG_W * 3, QImage::Format_RGB888);
            const qint64 now = monotonicMs();
            videoCaptureRate.add(now);
            const double fps = videoCaptureRate.rate(now);
            if (audit.elapsed() >= 1000) {
                audit.restart();
                fprintf(stderr, "[video] capture_fps=%.1f\n", fps);
            }
            // rgb 只是包装解码缓冲，跨线程投递前必须深拷贝
            const QImage owned = rgb.copy();
            DisplayFrame display{owned, m_sourceGeneration.load(), 1, 0, 1, fps, {}, true};
            display.videoSequence = ++m_videoSequence;
            publishDisplay(std::move(display));
            if (m_visionSink) {
                VisionFrame packet;
                packet.image = owned;
                packet.frameId = m_frameSequence.fetch_add(1) + 1;
                packet.sourceGeneration = m_sourceGeneration.load();
                packet.capturedMs = monotonicMs();
                m_visionSink(packet);
            }
            frame.clear();
            const bool paused = m_paused.load();
            while (m_paused && !m_stop) msleep(25);
            if (paused) { videoCaptureRate.reset(monotonicMs()); audit.restart(); }
        }
        decoder.kill();
        decoder.waitForFinished(2000);
        emit statusMsg("视频源结束");
    }
    void publishDisplay(DisplayFrame frame) {
        frame.publishedMs = monotonicMs();
        bool notify = false;
        {
            QMutexLocker lock(&m_displayMutex);
            if (frame.generation != m_lastDisplayGeneration) {
                frame.changedMask = frame.video ? 1 : 0x3F;
                m_lastDisplayGeneration = frame.generation;
            }
            if (m_displayPending && m_latestDisplay.generation == frame.generation)
                frame.changedMask |= m_latestDisplay.changedMask;
            if (m_displayPending) frame.replacedBeforeTake = m_latestDisplay.replacedBeforeTake + 1;
            m_latestDisplay = std::move(frame);
            notify = !m_displayPending;
            m_displayPending = true;
        }
        if (notify) emit displayAvailable();
    }
    QMutex m_displayMutex;
    QMutex m_configMutex;
    DisplayFrame m_latestDisplay;
    bool m_displayPending = false;
    int m_lastDisplayGeneration = -1;
    quint64 m_videoSequence = 0;
    std::atomic<bool> m_stop{false};
    std::atomic<int> m_mode{CAM_COUNT};
    std::atomic<int> m_selectedCamera{0};
    std::atomic<int> m_sourceGeneration{0};
    std::atomic<quint64> m_frameSequence{0};
    VisionOptions m_options;
    std::function<void(const VisionFrame&)> m_visionSink;
    QString m_videoSource;
    std::atomic<bool> m_paused{false};
    std::atomic<int> m_dispW{1920};
    std::atomic<int> m_dispH{1000};
    QImage m_dispImg[2];
    QImage m_modelImg[2];
    int m_bufIdx = 0;
    bool m_rga = true;
    int m_rgaFail = 0;
};

class InferenceThread : public QThread {
    Q_OBJECT
public:
    InferenceThread(QObject *parent = nullptr) : QThread(parent) {}

    struct Metrics {
        double started = 0, completed = 0, failed = 0;
        QHash<QString, double> modelRates;
        QHash<QString, qint64> completedMs;
    };
    void resetMetrics(int generation) {
        QMutexLocker lock(&m_metricsMutex);
        m_metricsGeneration = generation;
        const qint64 now = monotonicMs();
        m_startedRate.reset(now); m_completedRate.reset(now); m_failedRate.reset(now);
        m_modelRates.clear(); m_completedAt.clear();
        m_metricsStartMs = now;
    }
    Metrics metrics(int generation) {
        QMutexLocker lock(&m_metricsMutex);
        Metrics result;
        if (generation != m_metricsGeneration) return result;
        const qint64 now = monotonicMs();
        result.started = m_startedRate.rate(now);
        result.completed = m_completedRate.rate(now);
        result.failed = m_failedRate.rate(now);
        for (auto it = m_modelRates.begin(); it != m_modelRates.end(); ++it)
            result.modelRates[it.key()] = it.value().rate(now);
        result.completedMs = m_completedAt;
        return result;
    }

    static QImage decodeLaneMask(const rknn_output &out, const rknn_tensor_attr &attr, int nc) {
        if (!out.buf || attr.n_dims != 4 || attr.dims[0] != 1)
            return {};
        const bool nchw = attr.dims[1] == (uint32_t)nc &&
                          (attr.fmt == RKNN_TENSOR_NCHW || attr.dims[3] != (uint32_t)nc);
        const int channels = nchw ? attr.dims[1] : attr.dims[3];
        const int height = nchw ? attr.dims[2] : attr.dims[1];
        const int width = nchw ? attr.dims[3] : attr.dims[2];
        if (channels != nc || width != MODEL_W || height != MODEL_H)
            return {};
        const float *logits = static_cast<const float *>(out.buf);
        static const QRgb colors[] = {
            0, qRgba(0, 255, 255, 120), qRgba(255, 210, 0, 120),
            qRgba(255, 70, 70, 120), qRgba(90, 255, 90, 120),
            qRgba(190, 100, 255, 120), qRgba(255, 120, 200, 120),
            qRgba(80, 140, 255, 120), qRgba(255, 155, 55, 120)
        };
        QImage mask(width, height, QImage::Format_ARGB32);
        const size_t plane = (size_t)width * height;
        for (int y = 0; y < height; ++y) {
            QRgb *row = reinterpret_cast<QRgb *>(mask.scanLine(y));
            for (int x = 0; x < width; ++x) {
                const size_t pixel = (size_t)y * width + x;
                int best = 0;
                float score = logits[nchw ? pixel : pixel * channels];
                for (int c = 1; c < channels; ++c) {
                    const float value = logits[nchw ? (size_t)c * plane + pixel
                                                    : pixel * channels + c];
                    if (value > score) { score = value; best = c; }
                }
                row[x] = colors[best];
            }
        }
        return mask;
    }

    static bool selfTestLane() {
        float logits[2 * MODEL_W * MODEL_H] = {};
        const size_t pixel = (size_t)100 * MODEL_W + 200;
        logits[MODEL_W * MODEL_H + pixel] = 1.0f;
        rknn_output out{};
        out.buf = logits;
        rknn_tensor_attr attr{};
        attr.n_dims = 4;
        attr.fmt = RKNN_TENSOR_NCHW;
        attr.dims[0] = 1; attr.dims[1] = 2;
        attr.dims[2] = MODEL_H; attr.dims[3] = MODEL_W;
        const QImage mask = decodeLaneMask(out, attr, 2);
        if (mask.isNull() || qAlpha(mask.pixel(100, 200)) != 0 ||
            qAlpha(mask.pixel(200, 100)) == 0 ||
            !decodeLaneMask(out, attr, 9).isNull())
            return false;
        float interleaved[MODEL_W * MODEL_H * 2] = {};
        interleaved[2 * pixel + 1] = 1.0f;
        out.buf = interleaved;
        attr.fmt = RKNN_TENSOR_NHWC;
        attr.dims[1] = MODEL_H; attr.dims[2] = MODEL_W; attr.dims[3] = 2;
        const QImage nhwcMask = decodeLaneMask(out, attr, 2);
        return !nhwcMask.isNull() && qAlpha(nhwcMask.pixel(200, 100)) > 0;
    }

    static bool probeLaneModel(const QString &path, int nc) {
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly))
            return false;
        const QByteArray model = file.readAll();
        rknn_context ctx = 0;
        if (rknn_init(&ctx, const_cast<char *>(model.constData()), (uint32_t)model.size(), 0, nullptr))
            return false;
        rknn_input_output_num io{};
        rknn_tensor_attr output{};
        output.index = 0;
        const bool ok = rknn_query(ctx, RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io)) == 0 &&
                        io.n_input == 1 && io.n_output == 1 &&
                        rknn_query(ctx, RKNN_QUERY_OUTPUT_ATTR, &output, sizeof(output)) == 0 &&
                        output.n_dims == 4 && output.dims[0] == 1 &&
                        ((output.dims[1] == (uint32_t)nc && output.dims[2] == MODEL_H &&
                          output.dims[3] == MODEL_W) ||
                         (output.dims[1] == MODEL_H && output.dims[2] == MODEL_W &&
                          output.dims[3] == (uint32_t)nc));
        fprintf(stderr, "[lane-probe] %s: %s output=[%u,%u,%u,%u] fmt=%d\n",
                path.toLocal8Bit().constData(), ok ? "OK" : "FAIL",
                output.dims[0], output.dims[1], output.dims[2], output.dims[3], output.fmt);
        rknn_destroy(ctx);
        return ok;
    }

    /* 合成一份 DFL 输出验证解码链路（--dfl-selftest） */
    static bool selfTestDfl(int bins = 16, int nc = 1) {
        InferenceThread t;
        t.m_nc = nc;
        const int H = 80, W = 80;
        std::vector<float> box((size_t)4 * bins * H * W, -10.0f);
        std::vector<float> cls((size_t)nc * H * W, 0.05f);
        const int ty = 10, tx = 20;
        const size_t base = (size_t)ty * W + tx;
        const int dist[4] = {1, 2, 3, 4};
        for (int sIde = 0; sIde < 4; sIde++)
            box[(size_t)(sIde * bins + dist[sIde]) * H * W + base] = 10.0f;
        cls[base] = 0.9f;

        std::vector<rknn_output> outs(2);
        std::vector<rknn_tensor_attr> attrs(2);
        memset(&outs[0], 0, sizeof(rknn_output));
        outs[0].buf = box.data();
        memset(&attrs[0], 0, sizeof(rknn_tensor_attr));
        attrs[0].n_dims = 4;
        attrs[0].dims[0] = 1; attrs[0].dims[1] = 4 * bins; attrs[0].dims[2] = H; attrs[0].dims[3] = W;
        memset(&outs[1], 0, sizeof(rknn_output));
        outs[1].buf = cls.data();
        memset(&attrs[1], 0, sizeof(rknn_tensor_attr));
        attrs[1].n_dims = 4;
        attrs[1].dims[0] = 1; attrs[1].dims[1] = nc; attrs[1].dims[2] = H; attrs[1].dims[3] = W;

        const QVector<Detection> dets = t.decode(outs, attrs);
        const float stride = MODEL_W / (float)W;
        const float cx = (tx + 0.5f) * stride, cy = (ty + 0.5f) * stride;
        const float ex1 = cx - dist[0] * stride, ey1 = cy - dist[1] * stride;
        const float ex2 = cx + dist[2] * stride, ey2 = cy + dist[3] * stride;
        bool ok = dets.size() == 1;
        if (ok) {
            const Detection &d = dets[0];
            ok = std::fabs(d.x1 - ex1) < 1.5f && std::fabs(d.y1 - ey1) < 1.5f &&
                 std::fabs(d.x2 - ex2) < 1.5f && std::fabs(d.y2 - ey2) < 1.5f &&
                 std::fabs(d.score - 0.9f) < 0.01f && d.cls == 0;
            fprintf(stderr, "[dfl-selftest] got n=%d box=(%.1f,%.1f,%.1f,%.1f) score=%.2f cls=%d\n",
                    dets.size(), d.x1, d.y1, d.x2, d.y2, d.score, d.cls);
        } else {
            fprintf(stderr, "[dfl-selftest] got n=%d (expect 1)\n", dets.size());
        }
        fprintf(stderr, "[dfl-selftest] expect box=(%.1f,%.1f,%.1f,%.1f) score=%.2f\n", ex1, ey1, ex2,
                ey2, 0.9f);
        return ok;
    }

    void submit(const QImage &img, int sourceGeneration = 0, quint64 frameId = 0) {
        // RGB888 camera (640x480) or prepared model (640x640) pixels only.
        // Validation runs after dequeue so failures carry this request's identity.
        QMutexLocker lock(&m_mutex);
        m_pending = img;
        m_pendingGeneration = sourceGeneration;
        m_pendingFrameId = frameId;
        m_hasPending = true;
        m_cond.wakeOne();
    }
    void setModel(const ModelInfo &info) {
        QMutexLocker lock(&m_mutex);
        m_selection = {info};
        m_manualFormat = info.xyxy;
        m_modelChanged = true;
        m_cond.wakeOne();
    }
    void setModels(const QVector<ModelInfo> &models) {
        QMutexLocker lock(&m_mutex);
        m_selection = models;
        m_modelChanged = true;
        m_cond.wakeOne();
    }
    void setFormat(bool xyxy) {
        m_manualFormat = xyxy;
    }
    void setConf(float c) { m_conf.store(c); }
    void stop() {
        m_stop = true;
        m_cond.wakeOne();
        wait();
    }

signals:
    void detectionsReady(QString modelPath, int sourceGeneration, quint64 frameId, QVector<Detection> dets,
                         double inferFps, double inferMs);
    void laneMaskReady(QImage mask, int sourceGeneration, quint64 frameId, double inferFps, double inferMs);
    void inferenceFailed(int sourceGeneration, quint64 frameId);
    void modelLoaded(QString path, bool ok, QString info);

protected:
    void run() override {
        struct CachedModel {
            ModelInfo info;
            QByteArray bytes;
            rknn_context context = 0;
            uint32_t outputs = 0;
            // Fixed-shape attributes and descriptor storage belong to this context.
            std::vector<rknn_tensor_attr> attrs;
            std::vector<rknn_output> outs;
        };
        QVector<CachedModel> cache;
        InferencePreprocessor preprocessor;
        int next = 0;
        /* 诊断（DET_BENCH）：每秒统计“等帧时间”与“单次运行时间”，判断推理线程是否被饿着 */
        const bool diag = qEnvironmentVariableIsSet("DET_BENCH");
        QElapsedTimer diagTimer;
        if (diag)
            diagTimer.start();
        double diagWaitMs = 0, diagRunMs = 0;
        int diagRuns = 0;
        qint64 inferenceWindowStart = monotonicMs();
        quint64 successfulRuns = 0, failedRuns = 0;
        while (!m_stop) {
            const qint64 waitStart = diag ? QDateTime::currentMSecsSinceEpoch() : 0;
            QMutexLocker lock(&m_mutex);
            if (!m_hasPending && !m_modelChanged && !m_stop)
                m_cond.wait(&m_mutex, 200);
            if (m_stop)
                break;
            const bool reload = m_modelChanged;
            /* 只在型号切换时拷贝列表：原来每轮都深拷贝（含 29 个类名的 QStringList） */
            QVector<ModelInfo> selected;
            if (reload)
                selected = m_selection;
            QImage frame;
            const bool hadPending = m_hasPending;
            int sourceGeneration = m_pendingGeneration;
            const quint64 frameId = m_pendingFrameId;
            if (m_hasPending) {
                frame = m_pending;
                m_hasPending = false;
            }
            m_modelChanged = false;
            lock.unlock();
            if (diag && !frame.isNull())
                diagWaitMs += QDateTime::currentMSecsSinceEpoch() - waitStart;

            if (reload) {
                for (CachedModel &old : cache) rknn_destroy(old.context);
                cache.clear();
                next = 0;
                for (const ModelInfo &info : selected) {
                    CachedModel item;
                    item.info = info;
                    QFile file(info.path);
                    if (!file.open(QIODevice::ReadOnly)) {
                        emit modelLoaded(info.path, false, "open failed");
                        continue;
                    }
                    item.bytes = file.readAll();
                    const int ret = rknn_init(&item.context, item.bytes.data(),
                                              (uint32_t)item.bytes.size(), 0, nullptr);
                    if (ret != 0) {
                        emit modelLoaded(info.path, false, QString("rknn_init %1").arg(ret));
                        continue;
                    }
                    rknn_input_output_num ioNum{};
                    if (rknn_query(item.context, RKNN_QUERY_IN_OUT_NUM, &ioNum, sizeof(ioNum)) != 0 ||
                        ioNum.n_input != 1 || ioNum.n_output == 0 ||
                        (info.lane && ioNum.n_output != 1)) {
                        rknn_destroy(item.context);
                        emit modelLoaded(info.path, false, "unsupported input/output count");
                        continue;
                    }
                    item.outputs = ioNum.n_output;
                    item.attrs.resize(item.outputs);
                    bool attrsReady = true;
                    for (uint32_t i = 0; i < item.outputs; ++i) {
                        memset(&item.attrs[i], 0, sizeof(rknn_tensor_attr));
                        item.attrs[i].index = i;
                        const int queryRet = rknn_query(item.context, RKNN_QUERY_OUTPUT_ATTR,
                                                       &item.attrs[i], sizeof(rknn_tensor_attr));
                        if (queryRet != 0) {
                            rknn_destroy(item.context);
                            emit modelLoaded(info.path, false,
                                             QString("output attr %1 query %2").arg(i).arg(queryRet));
                            attrsReady = false;
                            break;
                        }
                    }
                    if (!attrsReady)
                        continue;
                    item.outs.resize(item.outputs);
                    resetOutputs(item.outs);
                    cache.append(std::move(item));
                    emit modelLoaded(info.path, true, QString("%1 outputs cached").arg(ioNum.n_output));
                }
            }
            if (hadPending && !cache.isEmpty()) {
                CachedModel &item = cache[next];
                next = (next + 1) % cache.size();
                m_ctx = item.context;
                m_nOutput = item.outputs;
                m_nc = item.info.nc;
                m_xyxy = cache.size() == 1 ? m_manualFormat.load() : item.info.xyxy;
                m_lane = item.info.lane;
                const qint64 runStart = diag ? QDateTime::currentMSecsSinceEpoch() : 0;
                recordMetric(sourceGeneration, item.info.path, 0);
                QElapsedTimer preprocessingTimer;
                if (diag) preprocessingTimer.start();
                const QImage* prepared = preprocessor.prepare(frame);
                const double preprocessingMs = diag ? preprocessingTimer.nsecsElapsed() / 1e6 : 0;
                const bool successful = prepared && runOnce(*prepared, item.info.path, sourceGeneration, frameId,
                                                           preprocessingMs, item.attrs, item.outs);
                if (successful) ++successfulRuns;
                else {
                    ++failedRuns;
                    recordMetric(sourceGeneration, item.info.path, 2);
                    emit inferenceFailed(sourceGeneration, frameId);
                }
                if (diag) {
                    diagRunMs += QDateTime::currentMSecsSinceEpoch() - runStart;
                    ++diagRuns;
                }
            } else if (hadPending) {
                ++failedRuns;
                emit inferenceFailed(sourceGeneration, frameId);
            }
            const qint64 inferenceNow = monotonicMs();
            if (inferenceNow - inferenceWindowStart >= 5000) {
                const double seconds = (inferenceNow - inferenceWindowStart) / 1000.0;
                fprintf(stderr, "[infer-perf] started_ms=%lld ended_ms=%lld seconds=%.3f completed=%llu failed=%llu completed_fps=%.3f\n",
                        (long long)inferenceWindowStart, (long long)inferenceNow, seconds,
                        (unsigned long long)successfulRuns, (unsigned long long)failedRuns,
                        successfulRuns / seconds);
                inferenceWindowStart = inferenceNow;
                successfulRuns = failedRuns = 0;
            }
            if (diag && diagTimer.isValid() && diagTimer.elapsed() >= 1000 && diagRuns > 0) {
                fprintf(stderr,
                        "[infer-diag] runs=%d 平均运行=%.1fms 平均等帧=%.1fms 单次=%d\n",
                        diagRuns,
                        diagRunMs / diagRuns,
                        diagWaitMs / diagRuns,
                        (int)((diagRunMs + diagWaitMs) / diagRuns));
                fflush(stderr);
                diagRuns = 0;
                diagWaitMs = 0;
                diagRunMs = 0;
                diagTimer.restart();
            }
        }
        for (CachedModel &item : cache) rknn_destroy(item.context);
        m_ctx = 0;
    }

private:
    double recordMetric(int generation, const QString& model, int event) {
        QMutexLocker lock(&m_metricsMutex);
        if (m_metricsGeneration < 0) {
            m_metricsGeneration = generation;
            m_metricsStartMs = monotonicMs();
            m_startedRate.reset(m_metricsStartMs); m_completedRate.reset(m_metricsStartMs);
            m_failedRate.reset(m_metricsStartMs);
        }
        if (generation != m_metricsGeneration) return 0;
        const qint64 now = monotonicMs();
        if (event == 0) m_startedRate.add(now);
        else if (event == 2) m_failedRate.add(now);
        else {
            m_completedRate.add(now);
            if (!m_modelRates.contains(model)) m_modelRates[model].reset(m_metricsStartMs);
            m_modelRates[model].add(now);
            m_completedAt[model] = now;
        }
        return m_completedRate.rate(now);
    }
    /* DET_BENCH 用：结束上一段计时 */
    static void markLap(QElapsedTimer &lap, double &slot) {
        slot = lap.nsecsElapsed() / 1e6;
        lap.restart();
    }
    static void resetOutputs(std::vector<rknn_output> &outs) {
        for (size_t i = 0; i < outs.size(); ++i) {
            memset(&outs[i], 0, sizeof(rknn_output));
            outs[i].index = static_cast<uint32_t>(i);
            outs[i].want_float = 1;
        }
    }

    bool runOnce(const QImage &src, const QString &modelPath, int sourceGeneration, quint64 frameId,
                 double preprocessingMs, const std::vector<rknn_tensor_attr> &attrs,
                 std::vector<rknn_output> &outs) {
        /* DET_BENCH 分段计时：定位应用内比纯 NPU 慢在哪一段
           prep=输入拷贝, set=rknn_inputs_set, run=NPU, get=输出反量化,
            query=0 (fixed-shape attributes cached at model load), decode=DFL+NMS,
            release=释放及描述符清空; load-time query cost is outside per-frame ms. */
        const bool bench = qEnvironmentVariableIsSet("DET_BENCH");
        const bool int8In = qEnvironmentVariableIsSet("DET_INT8_IN");
        QElapsedTimer lap;
        double tPrep = 0, tSet = 0, tRun = 0, tGet = 0, tQuery = 0, tDecode = 0, tRel = 0;
        if (bench)
            lap.start();
        /* Worker preprocessing has validated RGB888 model dimensions. The worker
           owns raw-frame letterbox storage; square submissions remain alive here.
           Tight UINT8 inputs can feed RKNN without another full-frame copy. */
        const QImage *feed = nullptr;
        if (!int8In && src.width() == MODEL_W && src.height() == MODEL_H &&
            src.format() == QImage::Format_RGB888 && src.bytesPerLine() == MODEL_W * 3) {
            feed = &src;
        } else {
            if (m_input.size() != (int)MODEL_SIZE)
                m_input.resize((int)MODEL_SIZE);
            if (src.bytesPerLine() == MODEL_W * 3)
                memcpy(m_input.data(), src.constBits(), MODEL_SIZE);
            else
                for (int y = 0; y < MODEL_H; y++)
                    memcpy(m_input.data() + y * MODEL_W * 3,
                           src.constScanLine(y), MODEL_W * 3);
        }

        /* 实测：输入按 INT8 直传反而慢得多（inputs_set 1.4ms → 16.9ms，整体 +58%），
           驱动对 UINT8 输入是快路径；默认走 UINT8，DET_INT8_IN=1 仅用于对照。 */
        if (int8In) {
            uint8_t *p = reinterpret_cast<uint8_t *>(m_input.data());
            for (int i = 0; i < (int)MODEL_SIZE; ++i)
                p[i] = (uint8_t)(p[i] - 128);
        }
        if (bench) markLap(lap, tPrep);
        rknn_input input;
        memset(&input, 0, sizeof(input));
        input.index = 0;
        input.buf = feed ? (void *)feed->constBits() : (void *)m_input.constData();
        input.size = (uint32_t)MODEL_SIZE;
        input.type = int8In ? RKNN_TENSOR_INT8 : RKNN_TENSOR_UINT8;
        input.fmt = RKNN_TENSOR_NHWC;
        QElapsedTimer timer;
        timer.start();
        if (rknn_inputs_set(m_ctx, 1, &input) != 0)
            return false;
        if (bench) markLap(lap, tSet);
        if (rknn_run(m_ctx, nullptr) != 0)
            return false;
        if (bench) markLap(lap, tRun);
        resetOutputs(outs);
        if (rknn_outputs_get(m_ctx, m_nOutput, outs.data(), nullptr) != 0) {
            // Preserve the existing failed-get release policy; retain no returned pointer.
            resetOutputs(outs);
            return false;
        }
        if (bench) markLap(lap, tGet);
        // tQuery stays zero: no per-frame query or artificial timing lap.
        QImage laneMask;
        QVector<Detection> dets;
        if (m_lane)
            laneMask = decodeLaneMask(outs[0], attrs[0], m_nc);
        else
            dets = decode(outs, attrs);
        if (bench) markLap(lap, tDecode);
        rknn_outputs_release(m_ctx, m_nOutput, outs.data());
        resetOutputs(outs);
        if (bench) markLap(lap, tRel);
        const double ms = timer.nsecsElapsed() / 1e6;
        const int completed = ++m_completed[modelPath];
        if (qEnvironmentVariableIsSet("DET_BENCH")) {
            timespec stamp{};
            clock_gettime(CLOCK_MONOTONIC, &stamp);
            fprintf(stderr, "[tdm_bench] t=%.6f model=%s ms=%.3f preprocessing_ms=%.3f\n",
                    stamp.tv_sec + stamp.tv_nsec / 1e9, qPrintable(modelPath), ms, preprocessingMs + tPrep);
        }
        if (completed == 1 || completed % 20 == 0)
            fprintf(stderr, "[tdm] model=%s completed=%d ms=%.2f source_generation=%d\n",
                    qPrintable(modelPath), completed, ms, sourceGeneration);
        if (bench) {
            m_accPrep += tPrep; m_accSet += tSet; m_accRun += tRun; m_accGet += tGet;
            m_accQuery += tQuery; m_accDecode += tDecode; m_accRel += tRel; m_accSplitN++;
            if (m_accSplitN >= 10) {
                const double n = m_accSplitN;
                fprintf(stderr,
                        "[infer-split] n=%d prep=%.2f set=%.2f run=%.2f get=%.2f query=%.2f decode=%.2f release=%.2f | sum=%.2f ms\n",
                        m_accSplitN, m_accPrep / n, m_accSet / n, m_accRun / n, m_accGet / n,
                        m_accQuery / n, m_accDecode / n, m_accRel / n,
                        (m_accPrep + m_accSet + m_accRun + m_accGet + m_accQuery + m_accDecode + m_accRel) / n);
                fflush(stderr);
                m_accPrep = m_accSet = m_accRun = m_accGet = m_accQuery = m_accDecode = m_accRel = 0;
                m_accSplitN = 0;
            }
        }
        if (m_lane && laneMask.isNull()) return false;
        const double completedFps = recordMetric(sourceGeneration, modelPath, 1);
        if (m_lane) {
            emit laneMaskReady(laneMask, sourceGeneration, frameId, completedFps, ms);
        } else {
            emit detectionsReady(modelPath, sourceGeneration, frameId, dets, completedFps, ms);
        }
        return true;
    }

    static float sigmoidf(float x) { return 1.0f / (1.0f + std::exp(-x)); }

    struct CandD {
        float score, x1, y1, x2, y2;
        int cls;
    };

    static void nmsAppend(QVector<Detection> &dets, std::vector<CandD> &cands) {
        std::sort(cands.begin(), cands.end(),
                  [](const CandD &a, const CandD &b) { return a.score > b.score; });
        std::vector<bool> removed(cands.size(), false);
        for (size_t i = 0; i < cands.size(); i++) {
            if (removed[i])
                continue;
            const CandD &a = cands[i];
            dets.append({a.cls, a.score, a.x1, a.y1, a.x2, a.y2});
            for (size_t j = i + 1; j < cands.size(); j++) {
                if (removed[j])
                    continue;
                const CandD &b = cands[j];
                const float xx1 = std::max(a.x1, b.x1);
                const float yy1 = std::max(a.y1, b.y1);
                const float xx2 = std::min(a.x2, b.x2);
                const float yy2 = std::min(a.y2, b.y2);
                const float w = std::max(0.0f, xx2 - xx1);
                const float h = std::max(0.0f, yy2 - yy1);
                const float inter = w * h;
                const float ai = (a.x2 - a.x1) * (a.y2 - a.y1);
                const float bj = (b.x2 - b.x1) * (b.y2 - b.y1);
                if (inter / (ai + bj - inter + 1e-6f) > IOU_THRESH)
                    removed[j] = true;
            }
        }
    }

    /* zoo 风格 6 输出（DFL 未在模型内解码）：3x[1,4*bins,H,W] + 3x[1,nc,H,W]
       命中该布局返回 true；否则返回 false 交回原有解码路径 */
    bool tryDecodeDfl(const std::vector<rknn_output> &outs,
                      const std::vector<rknn_tensor_attr> &attrs, float confThresh,
                      QVector<Detection> &dets) {
        struct Item {
            const float *data;
            int ch, h, w;
        };
        std::vector<Item> items;
        for (size_t i = 0; i < outs.size(); i++) {
            if (attrs[i].n_dims != 4)
                continue;
            items.push_back({(const float *)outs[i].buf, (int)attrs[i].dims[1],
                             (int)attrs[i].dims[2], (int)attrs[i].dims[3]});
        }

        struct Scale {
            const float *box;
            const float *cls;
            int h, w, nc, bins;
        };
        std::vector<Scale> scales;
        /* 按 (h,w) 配对：同一尺度下 cls 的通道数等于/最接近 m_nc，另一路即 box，
           bins 由 box 通道数推出（4*bins）。不写死 64/16，reg_max 变了也不用改代码。 */
        for (const Item &a : items) {
            const Item *peer = nullptr;
            for (const Item &b : items) {
                if (&b == &a || b.h != a.h || b.w != a.w)
                    continue;
                if (!peer || std::abs(b.ch - m_nc) < std::abs(peer->ch - m_nc))
                    peer = &b;
            }
            if (!peer)
                continue;
            /* 只从 box 那一侧建条目，避免同一尺度被登记两次 */
            if (std::abs(a.ch - m_nc) <= std::abs(peer->ch - m_nc))
                continue;
            if (a.ch % 4 != 0 || a.ch / 4 < 1 || a.ch / 4 > 32)
                continue;
            scales.push_back({a.data, peer->data, a.h, a.w, peer->ch, a.ch / 4});
        }
        if (scales.empty())
            return false;

        bool sigmoid = false;
        {
            const Scale &sc = scales[0];
            float mx = -1e9f, mn = 1e9f;
            const int n = std::min(sc.h * sc.w, 2000);
            for (int i = 0; i < n; i++) {
                mx = std::max(mx, sc.cls[i]);
                mn = std::min(mn, sc.cls[i]);
            }
            sigmoid = (mx > 1.5f || mn < -0.5f);
        }

        struct AC {
            float score;
            int cls, s, y, x;
        };
        std::vector<AC> cands;
        for (int si = 0; si < (int)scales.size(); si++) {
            const Scale &sc = scales[si];
            const int plane = sc.h * sc.w;
            const int nc = std::min(sc.nc, m_nc > 0 ? m_nc : sc.nc);
            for (int y = 0; y < sc.h; y++)
                for (int x = 0; x < sc.w; x++) {
                    const int off = y * sc.w + x;
                    float best = -1.0f;
                    int bestCls = -1;
                    for (int c = 0; c < nc; c++) {
                        float v = sc.cls[(size_t)c * plane + off];
                        if (sigmoid)
                            v = sigmoidf(v);
                        if (v > best) {
                            best = v;
                            bestCls = c;
                        }
                    }
                    if (best >= confThresh && bestCls >= 0)
                        cands.push_back({best, bestCls, si, y, x});
                }
        }
        if (cands.empty())
            return true;
        std::sort(cands.begin(), cands.end(),
                  [](const AC &a, const AC &b) { return a.score > b.score; });
        if (cands.size() > 300)
            cands.resize(300);

        std::vector<CandD> boxes;
        boxes.reserve(cands.size());
        for (const AC &c : cands) {
            const Scale &sc = scales[c.s];
            const int plane = sc.h * sc.w;
            const int stride = MODEL_W / sc.w;
            const size_t base = (size_t)c.y * sc.w + c.x;
            float d[4];
            for (int k = 0; k < 4; k++) {
                const float *p = sc.box + (size_t)(k * sc.bins) * plane + base;
                float mx = p[0];
                for (int b = 1; b < sc.bins; b++)
                    mx = std::max(mx, p[(size_t)b * plane]);
                float e[32];
                const int nb = std::min(sc.bins, 32);
                float sum = 0;
                for (int b = 0; b < nb; b++) {
                    e[b] = std::exp(p[(size_t)b * plane] - mx);
                    sum += e[b];
                }
                float res = 0;
                for (int b = 0; b < nb; b++)
                    res += b * e[b] / (sum + 1e-9f);
                d[k] = res;
            }
            const float cx = (c.x + 0.5f) * stride;
            const float cy = (c.y + 0.5f) * stride;
            boxes.push_back({c.score, cx - d[0] * stride, cy - d[1] * stride,
                             cx + d[2] * stride, cy + d[3] * stride, c.cls});
        }
        nmsAppend(dets, boxes);
        return true;
    }

    QVector<Detection> decode(const std::vector<rknn_output> &outs,
                              const std::vector<rknn_tensor_attr> &attrs) {
        QVector<Detection> dets;
        const float confThresh = m_conf.load();
        if (outs.empty())
            return dets;
        if (tryDecodeDfl(outs, attrs, confThresh, dets))
            return dets;
        const float *boxData = nullptr;
        int boxN = 0;
        const float *combined = nullptr;
        int combinedC = 0, combinedN = 0;
        const float *clsTensor = nullptr;
        int clsRows = 0, clsN = 0, clsRowOffset = 0;
        bool e2e = false;
        int e2eN = 0;

        // pass 1: locate the e2e [N,6] tensor, the 4-row box tensor, or a fused box+cls tensor
        for (size_t i = 0; i < outs.size(); i++) {
            if (attrs[i].n_dims != 3)
                continue;
            const float *data = (const float *)outs[i].buf;
            if (attrs[i].dims[2] == 6) {
                e2e = true;
                e2eN = attrs[i].dims[1];
                boxData = data;
            } else if (attrs[i].dims[1] == 4 && !boxData) {
                boxData = data;
                boxN = attrs[i].dims[2];
            } else if (attrs[i].dims[1] > 4) {
                combined = data;
                combinedC = attrs[i].dims[1];
                combinedN = attrs[i].dims[2];
            }
        }
        // pass 2: separate scores tensor sharing the anchor count (any class count)
        if (!e2e && boxData) {
            for (size_t i = 0; i < outs.size(); i++) {
                if (attrs[i].n_dims != 3)
                    continue;
                const float *data = (const float *)outs[i].buf;
                if (data == boxData || (int)attrs[i].dims[2] != boxN)
                    continue;
                clsTensor = data;
                clsRows = attrs[i].dims[1];
                clsN = attrs[i].dims[2];
                clsRowOffset = 0;
                break;
            }
        }
        if (!e2e && !clsTensor && combined && combinedC > 4) {
            boxData = combined;
            boxN = combinedN;
            clsTensor = combined;
            clsRows = combinedC - 4;
            clsN = combinedN;
            clsRowOffset = 4;
        }
        if (e2e && boxData) {
            for (int i = 0; i < e2eN; i++) {
                const float *r = boxData + (size_t)i * 6;
                if (r[4] < confThresh)
                    continue;
                Detection d;
                d.x1 = r[0];
                d.y1 = r[1];
                d.x2 = r[2];
                d.y2 = r[3];
                d.score = r[4];
                d.cls = (int)r[5];
                dets.append(d);
            }
            return dets;
        }
        if (!boxData || boxN <= 0 || !clsTensor || clsRows <= 0)
            return dets;

        const int nClasses = std::min(clsRows, m_nc > 0 ? m_nc : clsRows);

        bool sigmoid = false;
        {
            float mx = -1e9f, mn = 1e9f;
            for (int i = 0; i < clsN && i < 1000; i++) {
                const float v = clsTensor[(size_t)clsRowOffset * clsN + i];
                mx = std::max(mx, v);
                mn = std::min(mn, v);
            }
            sigmoid = (mx > 1.5f || mn < -0.5f);
        }

        std::vector<CandD> cands;
        for (int i = 0; i < boxN; i++) {
            float best = -1.0f;
            int bestCls = -1;
            for (int c = 0; c < nClasses; c++) {
                float s = clsTensor[(size_t)(clsRowOffset + c) * clsN + i];
                if (sigmoid)
                    s = sigmoidf(s);
                if (s > best) {
                    best = s;
                    bestCls = c;
                }
            }
            if (best < confThresh || bestCls < 0)
                continue;
            const float a0 = boxData[i];
            const float a1 = boxData[boxN + i];
            const float a2 = boxData[2 * boxN + i];
            const float a3 = boxData[3 * boxN + i];
            float x1, y1, x2, y2;
            if (m_xyxy) {
                x1 = a0;
                y1 = a1;
                x2 = a2;
                y2 = a3;
            } else {
                x1 = a0 - a2 / 2;
                y1 = a1 - a3 / 2;
                x2 = a0 + a2 / 2;
                y2 = a1 + a3 / 2;
            }
            cands.push_back({best, x1, y1, x2, y2, bestCls});
        }
        nmsAppend(dets, cands);
        return dets;
    }

    QMutex m_mutex;
    QWaitCondition m_cond;
    QImage m_pending;
    int m_pendingGeneration = 0;
    quint64 m_pendingFrameId = 0;
    bool m_hasPending = false;
    bool m_modelChanged = false;
    QVector<ModelInfo> m_selection;
    QHash<QString, int> m_completed;
    int m_nc = 1;
    bool m_xyxy = false;
    std::atomic<bool> m_manualFormat{false};
    bool m_lane = false;
    std::atomic<float> m_conf{0.25f};
    std::atomic<bool> m_stop{false};
    rknn_context m_ctx = 0;
    uint32_t m_nOutput = 0;
    QByteArray m_input;
    QMutex m_metricsMutex;
    int m_metricsGeneration = -1;
    qint64 m_metricsStartMs = 0;
    tdm::FrameRate m_startedRate, m_completedRate, m_failedRate;
    QHash<QString, tdm::FrameRate> m_modelRates;
    QHash<QString, qint64> m_completedAt;
    /* DET_BENCH 分段累计 */
    double m_accPrep = 0, m_accSet = 0, m_accRun = 0, m_accGet = 0;
    double m_accQuery = 0, m_accDecode = 0, m_accRel = 0;
    int m_accSplitN = 0;
};

/* ---------------- 显示（纯 CPU 绘制，不依赖 GL / 合成器） ----------------
   板端没有合成器在跑（_NET_WM_CM_S0 不存在）：QOpenGLWidget 与“顶层 GL 窗口 +
   createWindowContainer”都会出现陈旧区域与双份绘制（画面闪、留残影）。因此显示改成
   普通 QWidget：相机线程给出 RGB888 的 2x2 合成（缓冲复用、QImage 只包装不拷贝），
   本控件每帧只做一次缩放 drawImage，检测框与车道掩码在同一个 paintEvent 里叠加。
   单路显示时从合成里取那一格的源矩形，铺满内容区。 */
/* ---------------- 显示（顶层 QOpenGLWindow，camview 同款） ----------------
   板端没有合成器在跑（_NET_WM_CM_S0 不存在），QWidget 系的 GL 方案
   （QOpenGLWidget / createWindowContainer）都会出现陈旧区域与双份绘制。
   因此整个 UI 就是这一个顶层 GL 窗口：
   - 采集线程给出 RGB888 3x2 合成帧（缓冲复用，QImage 只包装不拷贝）；
   - glTexImage2D 上传 + 着色器 letterbox（GPU 缩放，CPU 不碰像素）；
   - 检测框用 QPainter 画矩形（便宜），文字先画进小缓存位图再 blit
     （直接在 GL 窗口上画文字会被 Mali ES2 的字形图集画花，camview 已踩过）；
   - 工具栏信息（模型/轮换/置信度/各路 fps/帮助）全部画在 HUD，控制用键盘。
   paneMask 指示画面里有哪几路（bit0..bit5）；单路时纹理里取该格子矩形。 */
class DetView : public QOpenGLWindow, protected QOpenGLFunctions {
    Q_OBJECT
public:
    DetView() {
        setTitle("detview");
        m_perfEnabled = !qEnvironmentVariableIsSet("DETVIEW_PERF") ||
                        qEnvironmentVariableIntValue("DETVIEW_PERF") != 0;
        m_perfStartedMs = monotonicMs();
        connect(this, &QOpenGLWindow::frameSwapped, this, [this] {
            if (m_perfEnabled) ++m_perf.swaps;
        });
        m_textureRing = qEnvironmentVariableIsSet("DETVIEW_TEXTURE_RING") ?
            qBound(1, qEnvironmentVariableIntValue("DETVIEW_TEXTURE_RING"), kTextureRing) : 1;
        /* camview [SURF]：先按屏幕尺寸建表面，避免交换链残留旧尺寸 */
        const QRect sg = QGuiApplication::primaryScreen()->geometry();
        resize(sg.size());
    }
    ~DetView() override {
        if (!context()) return;
        makeCurrent();
        glDeleteTextures(CAM_COUNT * kTextureRing, &m_cameraTextures[0][0]);
        glDeleteTextures(1, &m_overlayTexture);
        glDeleteBuffers(1, &m_vertexBuffer);
        if (m_tex) {
            glDeleteTextures(1, &m_tex);
            m_tex = 0;
        }
        doneCurrent();
    }
    static bool selfTestRefresh() {
        DetView view;
        const auto initial = view.m_detectionRevision;
        view.setLaneMask({}); view.setLaneMask({});
        view.setStereoPreview({}, {});
        if (view.m_detectionRevision != initial) return false;
        QImage mask(16, 16, QImage::Format_ARGB32); mask.fill(Qt::red);
        view.setLaneMask(mask);
        const auto withMask = view.m_detectionRevision;
        view.setLaneMask(mask);
        if (view.m_detectionRevision != withMask) return false;
        view.setLaneMask({}); view.setLaneMask({});
        if (view.m_detectionRevision != withMask + 1) return false;
        Detection d; d.cls = 1; d.score = .8f; d.x1 = 10; d.x2 = 40; d.y1 = 90; d.y2 = 130;
        d.validUntilMs = 2000;
        view.setDetections({d}, {"a", "b"});
        const auto first = view.m_detectionRevision;
        view.setDetections({d}, {"a", "b"});
        if (view.m_detectionRevision != first) return false;
        d.validUntilMs = 2100; // A new deadline must still invalidate the HUD.
        view.setDetections({d}, {"a", "b"});
        if (view.m_detectionRevision != first + 1) return false;
        view.setDetections({}, {"a", "b"});
        const auto cleared = view.m_detectionRevision;
        view.setDetections({}, {"a", "b"});
        if (view.m_detectionRevision != cleared) return false;
        fprintf(stderr, "DISPLAY_REFRESH_SELFTEST_PASS\n");
        return true;
    }

    struct PaintStats { int count; double averageMs; };
    PaintStats takePaintStats() {
        const PaintStats result{m_paintCount, m_paintCount ? m_paintMsSum / m_paintCount : 0.0};
        m_paintCount = 0;
        m_paintMsSum = 0;
        return result;
    }
    void resetRates() {
        const qint64 now = monotonicMs();
        m_takeRate.reset(now); m_uploadRate.reset(now); m_newPaintRate.reset(now); m_paintRate.reset(now);
        for (auto& rate : m_cameraUploadRates) rate.reset(now);
    }
    double newFrameRate() { return m_newPaintRate.rate(monotonicMs()); }
    void setMetricsPaused(bool paused) { m_metricsPaused = paused; m_overlayUpdatedMs = 0; }
    double takeRate() { return m_takeRate.rate(monotonicMs()); }
    double uploadRate() { return m_uploadRate.rate(monotonicMs()); }
    double paintRate() { return m_paintRate.rate(monotonicMs()); }
    void observeFrame(const CameraThread::DisplayFrame& frame) {
        m_sequences = frame.cameraSequences;
        m_capturedMs = frame.capturedMs;
        m_videoSequence = frame.videoSequence;
        m_videoReceivedMs = monotonicMs();
        m_takeRate.add(m_videoReceivedMs);
        if (m_perfEnabled) {
            ++m_perf.takes;
            m_perf.replacedSnapshots += frame.replacedBeforeTake;
            if (frame.publishedMs > 0 && m_videoReceivedMs >= frame.publishedMs)
                m_perf.time[tdm::GuiDelay].add(m_videoReceivedMs - frame.publishedMs);
        }
    }

    void submitCameras(const CameraThread::DisplayFrame& frame) {
        if (m_videoMode || m_paneMask != frame.paneMask || m_pane != frame.pane) m_overlayUpdatedMs = 0;
        m_cameraPixels = frame.cameraPixels;
        m_paneMask = frame.paneMask;
        m_pane = frame.pane;
        m_dispFps = frame.fps;
        m_camFps = frame.camFps;
        m_changedMask |= frame.changedMask;
        m_videoMode = false;
        m_dirty = true;
        m_haveFrame = true;
        update();
    }

    /* 相机线程：RGB888 合成帧（3x2 或单格），paneMask/pane 同 detview 约定 */
    void submitComposite(const QImage &composite, int paneMask, int pane, double fps,
                         const QVector<double> &camFps, int changedMask) {
        QMutexLocker lock(&m_uiMutex);
        m_comp = composite;
        m_paneMask = paneMask;
        m_pane = pane;
        m_dispFps = fps;
        m_camFps = camFps;
        m_changedMask |= changedMask;
        m_videoMode = false;
        m_dirty = true;
        m_haveFrame = true;
        lock.unlock();
        update();
    }
    /* 视频源路径：单路 RGB888 帧 */
    void submitImage(const QImage &img, double fps = 0) {
        QMutexLocker lock(&m_uiMutex);
        m_image = img.format() == QImage::Format_RGB888 ? img
                                                        : img.convertToFormat(QImage::Format_RGB888);
        m_videoMode = true;
        m_paneMask = 0x1;
        m_pane = 0;
        m_dispFps = fps;
        m_dirty = true;
        m_haveFrame = true;
        lock.unlock();
        update();
    }
    void setDetections(const QVector<Detection> &dets, const QStringList &classes) {
        QMutexLocker lock(&m_uiMutex);
        auto sameNumber = [](double a, double b) { return a == b || (std::isnan(a) && std::isnan(b)); };
        bool same = m_classes == classes && m_dets.size() == dets.size();
        for (int i = 0; same && i < dets.size(); ++i) {
            const auto& a = m_dets[i]; const auto& b = dets[i];
            same = a.cls == b.cls && a.score == b.score && a.x1 == b.x1 && a.x2 == b.x2 &&
                   a.y1 == b.y1 && a.y2 == b.y2 && a.trackId == b.trackId &&
                   a.matchScore == b.matchScore && a.predicted == b.predicted &&
                   a.validUntilMs == b.validUntilMs && sameNumber(a.depthMeters, b.depthMeters) &&
                   a.depthCapturedMs == b.depthCapturedMs && a.depthAgeMs == b.depthAgeMs;
        }
        if (same) return;
        m_dets = dets;
        m_classes = classes;
        ++m_detectionRevision;
        lock.unlock();
        update();
    }
    void setLaneMask(const QImage &mask) {
        QMutexLocker lock(&m_uiMutex);
        if ((mask.isNull() && m_laneMask.isNull()) ||
            (!mask.isNull() && !m_laneMask.isNull() && mask.cacheKey() == m_laneMask.cacheKey())) return;
        m_laneMask = mask;
        ++m_detectionRevision;
        lock.unlock();
        update();
    }
    void refreshExpiredContent() {
        if (m_settingsVisible) {
            if (!m_overlaySettings || m_overlaySize != size() || m_overlayRevision != m_settingsRevision) update();
            return;
        }
        const qint64 now = monotonicMs();
        const bool expired = m_overlayExpiresMs > 0 && now > m_overlayExpiresMs;
        const bool periodic = now - m_overlayUpdatedMs >= 300;
        if (expired || periodic) update();
    }
    void reportPerformance() {
        if (!m_perfEnabled) return;
        const qint64 now = monotonicMs();
        const double seconds = std::max(0.001, (now - m_perfStartedMs) / 1000.0);
        fprintf(stderr, "[display-perf] started_ms=%lld ended_ms=%lld seconds=%.3f take_fps=%.2f upload_fps=%.2f new_paint_fps=%.2f swap_fps=%.2f replaced_snapshots=%llu hud_rebuilds=%llu revision=%llu periodic=%llu expired=%llu layout=%llu upload_rects=%llu upload_bytes=%llu draw_rects=%llu text_hits=%llu text_misses=%llu text_clears=%llu\n",
                (long long)m_perfStartedMs, (long long)now, seconds, m_perf.takes / seconds, m_perf.uploads / seconds, m_perf.freshPaints / seconds,
                m_perf.swaps / seconds, (unsigned long long)m_perf.replacedSnapshots, (unsigned long long)m_perf.hudRebuilds,
                (unsigned long long)m_perf.hudRevision, (unsigned long long)m_perf.hudPeriodic,
                (unsigned long long)m_perf.hudExpired, (unsigned long long)m_perf.hudLayout,
                (unsigned long long)m_perf.hudUploadRects, (unsigned long long)m_perf.hudUploadBytes,
                (unsigned long long)m_perf.hudDrawRects, (unsigned long long)m_perf.textHits,
                (unsigned long long)m_perf.textMisses, (unsigned long long)m_perf.textClears);
        fprintf(stderr, "[display-events] takes=%llu uploads=%llu new_paints=%llu swaps=%llu\n",
                (unsigned long long)m_perf.takes, (unsigned long long)m_perf.uploads,
                (unsigned long long)m_perf.freshPaints, (unsigned long long)m_perf.swaps);
        static const char* names[] = {"camera_upload", "hud_regions", "hud_raster", "hud_pack", "hud_upload",
            "camera_draw", "hud_draw", "paint_total", "settings_paint", "gui_delay", "capture_to_upload"};
        for (int i = 0; i < tdm::DisplayStageCount; ++i) {
            const auto& v = m_perf.time[i];
            fprintf(stderr, "[display-stage] name=%s count=%llu sum_ms=%.3f mean_ms=%.3f p50_le_ms=%.1f p95_le_ms=%.1f p99_le_ms=%.1f max_ms=%.3f overflow=%llu\n",
                    names[i], (unsigned long long)v.count, v.sumMs, v.mean(), v.percentile(.50), v.percentile(.95),
                    v.percentile(.99), v.maxMs, (unsigned long long)v.overflow);
        }
        for (int c = 0; c < CAM_COUNT; ++c)
            fprintf(stderr, "[display-upload] camera=%d count=%llu bytes=%llu\n", c + 1,
                    (unsigned long long)m_perf.cameraUploads[c], (unsigned long long)m_perf.cameraUploadBytes[c]);
        m_perf = {}; m_perfStartedMs = now;
    }
    void setStatusLine(const QString &s) {
        QMutexLocker lock(&m_uiMutex);
        if (m_statusLine == s)
            return;
        m_statusLine = s;
        ++m_settingsRevision;
        lock.unlock();
        update();
    }
    void setModelLine(const QString &s) {
        QMutexLocker lock(&m_uiMutex);
        if (m_modelLine == s)
            return;
        m_modelLine = s;
        lock.unlock();
        update();
    }
    void setConfLine(const QString &s) {
        QMutexLocker lock(&m_uiMutex);
        if (m_confLine == s)
            return;
        m_confLine = s;
        lock.unlock();
        update();
    }
    void setHelpVisible(bool on) {
        m_help = on;
        update();
    }
    bool settingsVisible() const { return m_settingsVisible; }
    void setSettingsVisible(bool visible) {
        m_settingsVisible = visible;
        // Keep pending pixels/masks until monitoring resumes. Old content is
        // uploaded once; opening settings never pauses capture or inference.
        resetRates();
        update();
    }
    void moveSetting(int direction) {
        m_settingRow = (m_settingRow + direction + 6) % 6;
        update();
    }
    int settingRow() const { return m_settingRow; }
    void setCameraLayout(int mode, int selectedCamera) {
        if (m_videoMode) return;
        m_paneMask = mode == CAM_COUNT ? 0x3F : (1 << mode);
        m_pane = selectedCamera;
        m_overlayUpdatedMs = 0;
        update();
    }
    void setSettings(const QStringList& values, const QStringList& models, int currentModel,
                     const QString& pipeline, const QString& throughput, const QString& monitor) {
        if (m_settingValues != values || m_settingModels != models || m_settingModelIndex != currentModel)
            m_overlayUpdatedMs = 0;
        if (m_settingValues != values || m_settingModels != models || m_settingModelIndex != currentModel ||
            m_pipelineSummary != pipeline || m_throughputSummary != throughput)
            ++m_settingsRevision;
        m_settingValues = values;
        m_settingModels = models;
        m_settingModelIndex = currentModel;
        m_pipelineSummary = pipeline;
        m_throughputSummary = throughput;
        m_monitorSummary = monitor;
    }
    void setVisionLine(const QString &text) {
        if (m_visionLine != text) ++m_settingsRevision;
        m_visionLine = text; update();
    }
    void setStereoPreview(const QImage &image, const QString &status) {
        if (m_stereoStatus == status &&
            ((image.isNull() && m_stereoPreview.isNull()) ||
             (!image.isNull() && !m_stereoPreview.isNull() && image.cacheKey() == m_stereoPreview.cacheKey()))) return;
        m_stereoPreview = image;
        ++m_detectionRevision;
        if (m_stereoStatus != status) ++m_settingsRevision;
        m_stereoStatus = status;
        update();
    }
    /* 键盘统一在 GL 窗口处理：控制器把按键回调装进来 */
    void setKeyHook(std::function<void(QKeyEvent *)> hook) { m_keyHook = std::move(hook); }
    /* 截屏：直接抓 GL 帧缓冲 */
    QImage grabFrame() { return grabFramebuffer(); }

protected:
    void initializeGL() override {
        initializeOpenGLFunctions();
        static const char *vsrc =
            "attribute highp vec2 aPos;\n"
            "attribute highp vec2 aTex;\n"
            "varying mediump vec2 vTex;\n"
            "void main() { vTex = aTex; gl_Position = vec4(aPos, 0.0, 1.0); }\n";
        static const char *fsrc =
            "precision mediump float;\n"
            "varying mediump vec2 vTex;\n"
            "uniform sampler2D uTex;\n"
            "void main() { gl_FragColor = texture2D(uTex, vTex); }\n";
        m_prog.addShaderFromSourceCode(QOpenGLShader::Vertex, vsrc);
        m_prog.addShaderFromSourceCode(QOpenGLShader::Fragment, fsrc);
        m_prog.bindAttributeLocation("aPos", 0);
        m_prog.bindAttributeLocation("aTex", 1);
        if (!m_prog.link())
            fprintf(stderr, "[gl] shader link failed: %s\n", qPrintable(m_prog.log()));
        glGenTextures(1, &m_tex);
        glBindTexture(GL_TEXTURE_2D, m_tex);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
        glGenTextures(CAM_COUNT * kTextureRing, &m_cameraTextures[0][0]);
        for (int camera = 0; camera < CAM_COUNT; ++camera) {
            for (int slot = 0; slot < kTextureRing; ++slot) {
                glBindTexture(GL_TEXTURE_2D, m_cameraTextures[camera][slot]);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
            }
        }
        glGenBuffers(1, &m_vertexBuffer);
        glBindBuffer(GL_ARRAY_BUFFER, m_vertexBuffer);
        glBufferData(GL_ARRAY_BUFFER, sizeof(m_vertices), nullptr, GL_STATIC_DRAW);
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        glGenTextures(1, &m_overlayTexture);
        glBindTexture(GL_TEXTURE_2D, m_overlayTexture);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        const char *ren = (const char *)glGetString(GL_RENDERER);
        fprintf(stderr, "detview_gl_renderer=%s\n", ren ? ren : "?");
        fflush(stderr);
    }

    void paintGL() override {
        QElapsedTimer pt;
        pt.start();
        const float dpr = (float)devicePixelRatioF();
        glViewport(0, 0, (int)(width() * dpr), (int)(height() * dpr));
        glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
        glDisable(GL_BLEND);
        glDisable(GL_SCISSOR_TEST);
        if (m_settingsVisible) {
            if (!m_overlaySettings || m_overlaySize != size() || m_overlayRevision != m_settingsRevision ||
                m_overlayRow != m_settingRow) {
                if (!m_overlaySettings || m_overlaySize != size() || m_overlayRow != m_settingRow ||
                    monotonicMs() - m_overlayUpdatedMs >= 300) {
                QImage image(size(), QImage::Format_RGBA8888_Premultiplied);
                QPainter painter(&image);
                drawSettingsCanvas(painter);
                painter.end();
                uploadOverlay(image);
                m_overlayRevision = m_settingsRevision;
                m_overlayRow = m_settingRow;
                m_overlayUpdatedMs = monotonicMs();
                }
            }
            m_overlaySettings = true;
            glClear(GL_COLOR_BUFFER_BIT);
            drawOverlay({QRect(QPoint(0, 0), size())});
            recordPaint(pt, false);
            return;
        }

        /* 快照显示状态（采集/推理线程写，这里读） */
        const bool videoMode = m_videoMode;
        const int paneMask = m_paneMask, pane = m_pane;
        QVector<double> camFps = m_camFps;
        QVector<Detection> dets = m_dets;
        QStringList classes = m_classes;
        QImage video = m_videoMode ? m_image : QImage();
        QImage laneMask = m_laneMask;
        const qint64 metricNow = monotonicMs();
        for (int camera = 0; camera < camFps.size(); ++camera)
            if (m_metricsPaused || metricNow - m_capturedMs[camera] >= 1000) camFps[camera] = 0;
        bool freshVisibleFrame = false;

        /* 画面内容（逻辑坐标）：整幅 2:1，单选某路时 4:3 */
        QRectF content;
        std::function<void()> drawContent;
        int cw = 0, ch = 0;
        if (videoMode) {
            cw = video.width();
            ch = video.height();
        } else if (m_haveFrame) {
            cw = (paneMask == 0x3F) ? GRID_COLS * IMG_W : IMG_W;
            ch = (paneMask == 0x3F) ? GRID_ROWS * IMG_H : IMG_H;
        }
        if (cw > 0 && ch > 0) {
            const float ia = (float)cw / (float)ch;
            const int top = std::min(56, height() / 8);
            const int bottom = std::min(40, height() / 10);
            const int viewHeight = qMax(1, height() - top - bottom);
            const float wa = (float)width() / viewHeight;
            float w = width(), h = viewHeight;
            if (ia > wa) h = width() / ia; else w = viewHeight * ia;
            content = QRectF((width() - w) / 2.0, top + (viewHeight - h) / 2.0, w, h);
            glViewport(0, int(bottom * dpr), int(width() * dpr), int(viewHeight * dpr));

            /* 相机纹理采用与新版 camview 相同的独立三槽轮换：每路更新自己的
               RGB565纹理，避免单张合成纹理仍在显示时被glTexSubImage2D阻塞Mali。
               合成QImage只作为兼容的CPU邮箱，上传路径不再把六路拼成一张GPU纹理。 */
            if (m_dirty || !m_texAlloc) {
                QElapsedTimer uploadTimer; if (m_perfEnabled) uploadTimer.start();
                int uploadedMask = 0;
                if (videoMode) {
                    glBindTexture(GL_TEXTURE_2D, m_tex);
                    /* 视频源是 RGB888（解码器给的就是 8bit/像素） */
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, video.width(), video.height(), 0, GL_RGB,
                                 GL_UNSIGNED_BYTE, video.constBits());
                    m_texW = video.width();
                    m_texH = video.height();
                    freshVisibleFrame = m_videoSequence != 0 && m_videoSequence != m_uploadedVideoSequence;
                    m_uploadedVideoSequence = m_videoSequence;
                } else {
                    const int mask = m_changedMask ? m_changedMask : 0x3F;
                    for (int c = 0; c < CAM_COUNT; ++c) {
                        if (!(mask & (1 << c)))
                            continue;
                        if (m_cameraPixels[c].size() != FRAME_BYTES) continue;
                        const int slot = (m_cameraTextureSlot[c] + 1) % m_textureRing;
                        glBindTexture(GL_TEXTURE_2D, m_cameraTextures[c][slot]);
                        if (!m_cameraTextureAllocated[c][slot]) {
                            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, IMG_W, IMG_H, 0, GL_RGB,
                                         GL_UNSIGNED_SHORT_5_6_5, m_cameraPixels[c].constData());
                            m_cameraTextureAllocated[c][slot] = true;
                        } else {
                            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, IMG_W, IMG_H, GL_RGB,
                                            GL_UNSIGNED_SHORT_5_6_5, m_cameraPixels[c].constData());
                        }
                        m_cameraTextureSlot[c] = slot;
                        if (m_perfEnabled) {
                            ++m_perf.cameraUploads[c]; m_perf.cameraUploadBytes[c] += FRAME_BYTES;
                            const qint64 uploadedAt = monotonicMs();
                            if (m_capturedMs[c] > 0 && uploadedAt >= m_capturedMs[c])
                                m_perf.time[tdm::CaptureToUpload].add(uploadedAt - m_capturedMs[c]);
                        }
                        uploadedMask |= 1 << c;
                    }
                }
                if (!videoMode) {
                    for (int camera = 0; camera < CAM_COUNT; ++camera) {
                        if (!(uploadedMask & (1 << camera))) continue;
                        const bool fresh = m_sequences[camera] != 0 &&
                                           m_sequences[camera] != m_uploadedSequences[camera];
                        m_uploadedSequences[camera] = m_sequences[camera];
                        if (fresh && !m_metricsPaused && (paneMask & (1 << camera))) {
                            freshVisibleFrame = true;
                            m_cameraUploadRates[camera].add(metricNow);
                        }
                    }
                }
                if (freshVisibleFrame && !m_metricsPaused) m_uploadRate.add(metricNow);
                if (m_perfEnabled) {
                    m_perf.time[tdm::CameraUpload].add(uploadTimer.nsecsElapsed() / 1e6);
                    if (freshVisibleFrame && !m_metricsPaused) ++m_perf.uploads;
                }
                m_texAlloc = true;
                m_dirty = false;
                m_changedMask = 0;
            }
            float ndcx = 1.0f, ndcy = 1.0f;
            if (ia > wa) ndcy = wa / ia; else ndcx = ia / wa;
            drawContent = [this, ndcx, ndcy, videoMode, paneMask, pane, content] {
            m_prog.bind();
            m_prog.enableAttributeArray(0);
            m_prog.enableAttributeArray(1);
            m_prog.setUniformValue("uTex", 0);
            glActiveTexture(GL_TEXTURE0);
            auto drawCamera = [&](int camera, const QRectF &tile) {
                const float tx0 = float((tile.left() - content.left()) / content.width());
                const float tx1 = float((tile.right() - content.left()) / content.width());
                const float ty0 = float((tile.top() - content.top()) / content.height());
                const float ty1 = float((tile.bottom() - content.top()) / content.height());
                /* NDC y=+ maps to the top of the content, matching the old
                   composite texture's v=0 orientation. */
                const GLfloat verts[] = {
                    -ndcx + 2.0f * ndcx * tx0,  ndcy - 2.0f * ndcy * ty0, 0, 0,
                    -ndcx + 2.0f * ndcx * tx1,  ndcy - 2.0f * ndcy * ty0, 1, 0,
                    -ndcx + 2.0f * ndcx * tx0,  ndcy - 2.0f * ndcy * ty1, 0, 1,
                    -ndcx + 2.0f * ndcx * tx1,  ndcy - 2.0f * ndcy * ty1, 1, 1,
                };
                setVertices(verts, camera);
                glBindTexture(GL_TEXTURE_2D, m_cameraTextures[camera][m_cameraTextureSlot[camera]]);
                glDrawArrays(GL_TRIANGLE_STRIP, camera * 4, 4);
            };
            if (videoMode) {
                const GLfloat verts[] = {
                    -ndcx, ndcy, 0, 0, ndcx, ndcy, 1, 0,
                    -ndcx, -ndcy, 0, 1, ndcx, -ndcy, 1, 1};
                setVertices(verts, CAM_COUNT);
                glBindTexture(GL_TEXTURE_2D, m_tex);
                glDrawArrays(GL_TRIANGLE_STRIP, CAM_COUNT * 4, 4);
            } else {
                const bool quad = paneMask == 0x3F;
                for (int c = 0; c < CAM_COUNT; ++c) {
                    if (!quad && c != pane) continue;
                    const QRectF tile = quad ? QRectF(content.left() + (c % GRID_COLS) * content.width() / GRID_COLS,
                                                      content.top() + (c / GRID_COLS) * content.height() / GRID_ROWS,
                                                      content.width() / GRID_COLS, content.height() / GRID_ROWS)
                                             : content;
                    drawCamera(c, tile);
                }
            }
            m_prog.disableAttributeArray(0);
            m_prog.disableAttributeArray(1);
            m_prog.release();
            };
        }

        /* ---- HUD ---- */
        QElapsedTimer regionTimer; if (m_perfEnabled) regionTimer.start();
        QRectF paneRect = content;
        if (!videoMode && paneMask == 0x3F) {
            const double pw = content.width() / GRID_COLS, ph = content.height() / GRID_ROWS;
            paneRect = QRectF(content.left() + (pane % GRID_COLS) * pw,
                              content.top() + (pane / GRID_COLS) * ph, pw, ph);
        }
        QList<QRect> hudRegions;
        QFont labelFont; labelFont.setPointSize(11);
        const int labelImageHeight = QFontMetrics(labelFont).height() + 8;
        const int cameraLabelHeight = std::max(30, labelImageHeight + 3);
        auto borderRegions = [&](const QRectF& box, int thickness) {
            const QRect r = box.toAlignedRect().adjusted(-thickness, -thickness, thickness, thickness);
            hudRegions << QRect(r.x(), r.y(), r.width(), thickness * 2)
                       << QRect(r.x(), r.bottom() - thickness * 2 + 1, r.width(), thickness * 2)
                       << QRect(r.x(), r.y(), thickness * 2, r.height())
                       << QRect(r.right() - thickness * 2 + 1, r.y(), thickness * 2, r.height());
        };
        const int top = std::min(56, height() / 8), bottom = std::min(40, height() / 10);
        hudRegions << QRect(0, 0, width(), top) << QRect(0, height() - bottom, width(), bottom);
        if (!content.isEmpty()) {
            const bool quad = !videoMode && paneMask == 0x3F;
            if (quad) borderRegions(paneRect.adjusted(1, 1, -1, -1), 2);
            for (int c = 0; c < (quad ? CAM_COUNT : 1); ++c) {
                const double pw = content.width() / (quad ? GRID_COLS : 1);
                const double ph = content.height() / (quad ? GRID_ROWS : 1);
                hudRegions << QRect(int(content.left() + (quad ? c % GRID_COLS * pw : 0) + 6),
                                    int(content.top() + (quad ? c / GRID_COLS * ph : 0) + 6),
                                    int(std::min(280.0, pw - 12)), cameraLabelHeight);
            }
            if (!laneMask.isNull()) hudRegions << paneRect.toAlignedRect();
            else {
                const double sx = paneRect.width() / MODEL_W, sy = paneRect.height() / IMG_H;
                const double bx = paneRect.left(), by = paneRect.top() - 80 * sy;
                for (const auto& d : dets) {
                    if (d.validUntilMs > 0 && metricNow > d.validUntilMs) continue;
                    const QRectF box(bx + d.x1 * sx, by + d.y1 * sy,
                                     std::max(1.0, (d.x2 - d.x1) * sx), std::max(1.0, (d.y2 - d.y1) * sy));
                    const int firstRegion = hudRegions.size();
                    borderRegions(box, 3);
                    hudRegions << QRect(int(box.left()), int(std::max(box.top(), paneRect.top() + 42)),
                                        qMax(0, int(paneRect.right() - box.left()) + 1), labelImageHeight + 2);
                    for (int r = firstRegion; r < hudRegions.size(); ++r)
                        hudRegions[r] &= paneRect.toAlignedRect();
                }
            }
        }
        // Preview can overlap the selected pane or footer. Merge these to avoid
        // blending the same semi-transparent HUD pixels twice.
        if (!m_stereoPreview.isNull()) {
            const int pw = std::min(240, width() / 4);
            QRect preview(width() - pw - 8, height() - pw * m_stereoPreview.height() / m_stereoPreview.width() - 8,
                          pw, pw * m_stereoPreview.height() / m_stereoPreview.width());
            for (int i = hudRegions.size() - 1; i >= 0; --i) {
                if (preview.intersects(hudRegions[i])) preview = preview.united(hudRegions.takeAt(i));
            }
            hudRegions << preview;
        }
        // Keep the CPU raster HUD, but avoid QPainter's GL engine. Its state
        // transitions force a costly synchronization on this Mali stack.
        const qint64 hudNow = monotonicMs();
        const bool repaintHud = m_overlaySettings || m_overlaySize != size() ||
            m_overlayDetections != m_detectionRevision || hudNow - m_overlayUpdatedMs >= 300 ||
            (m_overlayExpiresMs > 0 && hudNow > m_overlayExpiresMs);
        if (m_perfEnabled) m_perf.time[tdm::HudRegions].add(regionTimer.nsecsElapsed() / 1e6);
        if (repaintHud) {
        QElapsedTimer rasterTimer; if (m_perfEnabled) {
            rasterTimer.start(); ++m_perf.hudRebuilds;
            if (m_overlaySettings || m_overlaySize != size()) ++m_perf.hudLayout;
            if (m_overlayDetections != m_detectionRevision) ++m_perf.hudRevision;
            if (hudNow - m_overlayUpdatedMs >= 300) ++m_perf.hudPeriodic;
            if (m_overlayExpiresMs > 0 && hudNow > m_overlayExpiresMs) ++m_perf.hudExpired;
        }
        m_overlayExpiresMs = 0;
        // Clear the previous frame's glyph/box pixels too, then draw only the
        // new region set. This removes old boxes when tracks move or expire.
        QList<QRect> uploadRegions = hudRegions;
        uploadRegions.append(m_previousHudRegions);
        if (m_rasterOverlay.size() != size()) {
            m_rasterOverlay = QImage(size(), QImage::Format_RGBA8888_Premultiplied);
            m_rasterOverlay.fill(Qt::transparent);
        }
        QPainter painter(&m_rasterOverlay);
        QRegion dirtyRegion;
        for (const auto& r : uploadRegions) dirtyRegion += r;
        painter.setClipRegion(dirtyRegion);
        painter.setCompositionMode(QPainter::CompositionMode_Source);
        for (const QRect& r : dirtyRegion) painter.fillRect(r, Qt::transparent);
        painter.setCompositionMode(QPainter::CompositionMode_SourceOver);
        paintMonitorChrome(painter);
        /* 每路采集帧率标签（六路 3×2 逐格，单路只一个）：只贴几张小位图（走 textImage
           缓存）。早先版本每帧上传一张整窗 ARGB HUD 位图（1898x955x4≈7.3MB），实测
           paintGL 里每帧多花 10ms 以上。 */
        {
            const bool quad = (!videoMode && paneMask == 0x3F);
            const int nLab = quad ? CAM_COUNT : 1;
            const double pw = content.width() / (quad ? GRID_COLS : 1);
            const double ph = content.height() / (quad ? GRID_ROWS : 1);
            const double ox = content.left(), oy = content.top();
            for (int i = 0; i < nLab; ++i) {
                const QRectF box(ox + (quad ? (i % GRID_COLS) * pw + 6 : 6),
                                  oy + (quad ? (i / GRID_COLS) * ph + 6 : 6), std::min(280.0, pw - 12), cameraLabelHeight);
                if (box.right() > content.right() || box.bottom() > content.bottom())
                    continue;
                const int cameraIndex = quad ? i : pane;
                const bool selected = !videoMode && cameraIndex == pane;
                painter.fillRect(box, selected ? QColor(12, 78, 86, 225) : QColor(12, 22, 34, 210));
                painter.drawImage(box.left() + 8, box.top() + 3,
                                  textImage(videoMode ? QString("视频 · 采集 %1 fps").arg(
                                                m_metricsPaused || metricNow - m_videoReceivedMs >= 1000 ? 0 : m_dispFps, 0, 'f', 1) :
                                            QString("C%1  采集 %2 · 画面 %3").arg(cameraIndex + 1)
                                                .arg(camFps.value(cameraIndex), 0, 'f', 1)
                                                .arg(m_cameraUploadRates[cameraIndex].rate(metricNow), 0, 'f', 1),
                                            QColor(225, 239, 245), 11));
            }
            if (!videoMode && paneMask == 0x3F) {
                painter.setPen(QPen(QColor(62, 213, 199), 2));
                painter.drawRect(paneRect.adjusted(1, 1, -1, -1));
            }
        }
        /* 检测框/车道掩码：矩形用 QPainter 画（便宜），标签文字走缓存位图 */
        {
            painter.save();
            painter.setClipRect(paneRect, Qt::IntersectClip);
            const double sx = paneRect.width() / (double)MODEL_W;
            const double sy = paneRect.height() / (double)IMG_H;
            const double baseX = paneRect.left();
            const double baseY = paneRect.top() - 80.0 * sy;
            if (!laneMask.isNull())
                painter.drawImage(QRectF(baseX, baseY, MODEL_W * sx, MODEL_H * sy), laneMask);
            for (const Detection &d : dets) {
                if (d.validUntilMs > 0 && monotonicMs() > d.validUntilMs) continue;
                auto expireAt = [&](qint64 deadline) {
                    if (deadline > hudNow && (m_overlayExpiresMs == 0 || deadline < m_overlayExpiresMs))
                        m_overlayExpiresMs = deadline;
                };
                expireAt(d.validUntilMs);
                const double x1 = baseX + d.x1 * sx;
                const double x2 = baseX + d.x2 * sx;
                const double y1 = baseY + d.y1 * sy;
                const double y2 = baseY + d.y2 * sy;
                const QRectF r(x1, y1, std::max(1.0, x2 - x1), std::max(1.0, y2 - y1));
                const QColor color = d.cls == 0 ? QColor(0, 255, 0)
                                    : (d.cls == 1 ? QColor(255, 60, 60) : QColor(255, 220, 0));
                painter.setPen(QPen(color, 3));
                painter.drawRect(r);
                QString label =
                    QString("%1 %2")
                        .arg(d.cls >= 0 && d.cls < classes.size() ? classes[d.cls]
                                                                  : QString::number(d.cls))
                         .arg(d.score, 0, 'f', 2);
                if (d.trackId)
                    label += QString(" #%1 %2").arg(d.trackId).arg(d.predicted ? "预测" : "追踪");
                const qint64 depthAge = monotonicMs() - d.depthCapturedMs;
                if (std::isfinite(d.depthMeters) && d.depthCapturedMs > 0 && depthAge >= 0 && depthAge <= 300)
                    label += QString(" Z=%1m (%2ms)").arg(d.depthMeters, 0, 'f', 2).arg(depthAge);
                if (std::isfinite(d.depthMeters) && d.depthCapturedMs > 0) expireAt(d.depthCapturedMs + 300);
                QImage tag = textImage(label, color, 11);
                painter.drawImage(r.left(), std::max(r.top(), paneRect.top() + 42), tag);
            }
            painter.restore();
            if (!m_stereoPreview.isNull()) {
                const int previewWidth = std::min(240, width() / 4);
                const int previewHeight = previewWidth * m_stereoPreview.height() / m_stereoPreview.width();
                painter.drawImage(QRect(width() - previewWidth - 8, height() - previewHeight - 8,
                                        previewWidth, previewHeight), m_stereoPreview);
            }
            painter.end();
        }
        if (m_perfEnabled) m_perf.time[tdm::HudRaster].add(rasterTimer.nsecsElapsed() / 1e6);
        uploadOverlay(m_rasterOverlay, uploadRegions);
        m_previousHudRegions = hudRegions;
        m_overlayUpdatedMs = hudNow;
        m_overlayDetections = m_detectionRevision;
        }
        m_overlaySettings = false;
        // All camera and HUD uploads precede framebuffer drawing. Updating the
        // HUD after a camera draw otherwise flushes Mali's tile render pass.
        const int viewHeight = qMax(1, height() - top - bottom);
        QElapsedTimer drawTimer; if (m_perfEnabled) drawTimer.start();
        glViewport(0, int(bottom * dpr), int(width() * dpr), int(viewHeight * dpr));
        glClear(GL_COLOR_BUFFER_BIT);
        if (drawContent) drawContent();
        if (m_perfEnabled) m_perf.time[tdm::CameraDraw].add(drawTimer.nsecsElapsed() / 1e6);
        drawOverlay(hudRegions);
        recordPaint(pt, freshVisibleFrame);
    }

    void keyPressEvent(QKeyEvent *e) override {
        if (m_keyHook)
            m_keyHook(e);
        else
            QOpenGLWindow::keyPressEvent(e);
    }

private:
    void setVertices(const GLfloat* vertices, int slot) {
        glBindBuffer(GL_ARRAY_BUFFER, m_vertexBuffer);
        if (!m_vertexValid[slot] || std::memcmp(m_vertices[slot], vertices, sizeof(m_vertices[slot])) != 0) {
            std::memcpy(m_vertices[slot], vertices, sizeof(m_vertices[slot]));
            glBufferSubData(GL_ARRAY_BUFFER, slot * sizeof(m_vertices[slot]), sizeof(m_vertices[slot]), vertices);
            m_vertexValid[slot] = true;
        }
        m_prog.setAttributeBuffer(0, GL_FLOAT, 0, 2, 4 * sizeof(GLfloat));
        m_prog.setAttributeBuffer(1, GL_FLOAT, 2 * sizeof(GLfloat), 2, 4 * sizeof(GLfloat));
    }
    void uploadOverlay(const QImage& image, const QList<QRect>& regions = {}) {
        QElapsedTimer timer; if (m_perfEnabled) timer.start();
        double packMs = 0;
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, m_overlayTexture);
        if (m_overlaySize != image.size()) {
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image.width(), image.height(), 0,
                         GL_RGBA, GL_UNSIGNED_BYTE, image.constBits());
            m_overlaySize = image.size();
            if (m_perfEnabled) { ++m_perf.hudUploadRects; m_perf.hudUploadBytes += uint64_t(image.width()) * image.height() * 4; }
        } else if (regions.isEmpty()) {
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, image.width(), image.height(),
                            GL_RGBA, GL_UNSIGNED_BYTE, image.constBits());
            if (m_perfEnabled) { ++m_perf.hudUploadRects; m_perf.hudUploadBytes += uint64_t(image.width()) * image.height() * 4; }
        } else {
            // GLES2 row-length packing is now limited to small HUD regions,
            // never the six camera frames or a full-window HUD every frame.
            QRegion unionRegion;
            for (const auto& region : regions) unionRegion += region;
            unionRegion &= image.rect();
            for (const QRect& r : unionRegion) {
                if (r.isEmpty()) continue;
                QElapsedTimer pack; if (m_perfEnabled) pack.start();
                const QImage tile = image.copy(r);
                if (m_perfEnabled) {
                    packMs += pack.nsecsElapsed() / 1e6;
                    ++m_perf.hudUploadRects; m_perf.hudUploadBytes += uint64_t(r.width()) * r.height() * 4;
                }
                glTexSubImage2D(GL_TEXTURE_2D, 0, r.x(), r.y(), r.width(), r.height(),
                                GL_RGBA, GL_UNSIGNED_BYTE, tile.constBits());
            }
        }
        if (m_perfEnabled) {
            m_perf.time[tdm::HudPack].add(packMs);
            m_perf.time[tdm::HudUpload].add(std::max(0.0, timer.nsecsElapsed() / 1e6 - packMs));
        }
    }
    void drawOverlay(const QList<QRect>& regions) {
        QElapsedTimer timer; if (m_perfEnabled) timer.start();
        glViewport(0, 0, int(width() * devicePixelRatioF()), int(height() * devicePixelRatioF()));
        glEnable(GL_BLEND);
        glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
        m_prog.bind();
        m_prog.enableAttributeArray(0); m_prog.enableAttributeArray(1);
        const GLfloat vertices[] = {-1, 1, 0, 0, 1, 1, 1, 0, -1, -1, 0, 1, 1, -1, 1, 1};
        setVertices(vertices, CAM_COUNT + 1);
        m_prog.setUniformValue("uTex", 0);
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, m_overlayTexture);
        glEnable(GL_SCISSOR_TEST);
        const double ratio = devicePixelRatioF();
        QRegion unionRegion;
        for (const auto& region : regions) unionRegion += region;
        unionRegion &= QRect(QPoint(0, 0), size());
        for (const QRect& r : unionRegion) {
            if (r.isEmpty()) continue;
            if (m_perfEnabled) ++m_perf.hudDrawRects;
            glScissor(int(r.x() * ratio), int((height() - r.y() - r.height()) * ratio),
                      int(r.width() * ratio), int(r.height() * ratio));
            glDrawArrays(GL_TRIANGLE_STRIP, (CAM_COUNT + 1) * 4, 4);
        }
        glDisable(GL_SCISSOR_TEST); glDisable(GL_BLEND);
        m_prog.disableAttributeArray(0); m_prog.disableAttributeArray(1);
        m_prog.release();
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        if (m_perfEnabled) m_perf.time[tdm::HudDraw].add(timer.nsecsElapsed() / 1e6);
    }
    void recordPaint(const QElapsedTimer& timer, bool fresh) {
        m_paintMsSum += timer.nsecsElapsed() / 1e6;
        ++m_paintCount;
        const qint64 now = monotonicMs();
        m_paintRate.add(now);
        if (fresh && !m_metricsPaused) m_newPaintRate.add(now);
        if (m_perfEnabled) {
            m_perf.time[m_settingsVisible ? tdm::SettingsPaint : tdm::PaintTotal].add(timer.nsecsElapsed() / 1e6);
            if (fresh && !m_metricsPaused) ++m_perf.freshPaints;
        }
    }

    void paintMonitorChrome(QPainter& painter) {
        const int top = std::min(56, height() / 8);
        const int bottom = std::min(40, height() / 10);
        const QColor ink(223, 234, 244), muted(144, 166, 187), accent(62, 213, 199);
        painter.fillRect(QRect(0, 0, width(), top), QColor(15, 25, 38));
        painter.fillRect(QRect(0, height() - bottom, width(), bottom), QColor(15, 25, 38));
        const QString title = m_videoMode ? "视频监看" : "摄像头监看";
        painter.drawImage(16, std::max(0, (top - 30) / 2), textImage(title, accent, 13));
        const QString summary = QString("%1 · %2 · 新画面 %3 fps")
            .arg(m_metricsPaused ? "已暂停" : "运行中")
            .arg(m_monitorSummary).arg(newFrameRate(), 0, 'f', 0);
        QFont summaryFont; summaryFont.setPointSize(11);
        const QFontMetrics metrics(summaryFont);
        const QString concise = metrics.elidedText(summary, Qt::ElideRight, qMax(0, width() - 470));
        painter.drawImage(180, std::max(0, (top - 30) / 2), textImage(concise, ink, 11));
        painter.drawImage(qMax(180, width() - 250), std::max(0, (top - 30) / 2),
                          textImage("Tab  设置  /  监看", accent, 11));
        QString keys = m_help ?
            "Tab 设置   V 切换单路/六路   P 暂停   S 截屏   F 全屏   Q 退出  ·  模型与参数请到设置页" :
            "V 切换相机     G 六路总览     P 暂停     S 截屏     H 帮助     Tab 设置";
        if (m_statusLine.contains("FATAL") || m_statusLine.contains("FAIL"))
            keys = "设备异常 · " + m_statusLine + " · Tab 查看设置";
        keys = metrics.elidedText(keys, Qt::ElideRight, qMax(1, width() - 32));
        painter.drawImage(16, height() - bottom + std::max(0, (bottom - 28) / 2),
                          textImage(keys, muted, 11));
    }

    void paintSettings(QPainter& painter) {
        // Mali's ES2 glyph path corrupts direct drawText. Rasterize the page on
        // the CPU, then use the same image upload path as the monitor labels.
        const QString key = QString("%1/%2/%3/%4/%5/").arg(width()).arg(height())
            .arg(m_settingRow).arg(m_settingModelIndex).arg(m_settingsRevision);
        if (m_settingsImage.isNull() || key != m_settingsImageKey) {
            m_settingsImage = QImage(size(), QImage::Format_ARGB32_Premultiplied);
            QPainter raster(&m_settingsImage);
            drawSettingsCanvas(raster);
            raster.end();
            m_settingsImageKey = key;
        }
        painter.drawImage(0, 0, m_settingsImage);
    }

    void drawSettingsCanvas(QPainter& painter) {
        // One logical layout scales uniformly, including fonts, on small displays.
        painter.fillRect(QRect(0, 0, width(), height()), QColor(10, 18, 29));
        const double scale = std::min(width() / 1280.0, height() / 720.0);
        painter.translate((width() - 1280 * scale) / 2, (height() - 720 * scale) / 2);
        painter.scale(scale, scale);
        painter.setRenderHint(QPainter::Antialiasing);
        const QColor ink(229, 237, 245), muted(139, 162, 184), accent(62, 213, 199);
        auto font = [&](int pixels, bool bold = false) {
            QFont f; f.setPixelSize(pixels); f.setBold(bold); painter.setFont(f);
        };
        auto text = [&](const QRect& rect, const QString& value, const QColor& color,
                        int pixels, bool bold = false, bool wrap = false) {
            font(pixels, bold); painter.setPen(color);
            painter.drawText(rect, Qt::AlignLeft | Qt::AlignVCenter |
                             (wrap ? Qt::TextWordWrap : Qt::TextSingleLine),
                             wrap ? value : QFontMetrics(painter.font()).elidedText(value, Qt::ElideRight, rect.width()));
        };
        auto card = [&](const QRect& rect, const QString& title) {
            painter.setPen(QColor(35, 52, 70)); painter.setBrush(QColor(17, 29, 44));
            painter.drawRoundedRect(rect, 12, 12);
            text(QRect(rect.x() + 20, rect.y() + 12, rect.width() - 40, 30), title, accent, 17, true);
        };
        text(QRect(32, 20, 760, 38), "设置", ink, 28, true);
        text(QRect(32, 62, 890, 30), "↑ ↓ 选择设置项     ← → 调整     Enter 切换     修改即时生效", muted, 16);
        text(QRect(990, 28, 250, 34), "Tab 返回摄像头", accent, 18, true);
        card(QRect(32, 110, 594, 422), "识别与显示");
        const QStringList labels = {"模型", "画面", "置信度阈值", "模型轮换", "框坐标格式", "运行状态"};
        const QStringList hints = {"← → 切换模型", "← → C1–C6 / 六路", "← → 每次 5%", "Enter 开关", "Enter 切换", "Enter 暂停 / 继续"};
        for (int row = 0; row < labels.size(); ++row) {
            const QRect rect(48, 162 + row * 58, 562, 52);
            if (row == m_settingRow) {
                painter.setPen(QColor(62, 213, 199)); painter.setBrush(QColor(22, 62, 70));
                painter.drawRoundedRect(rect, 8, 8);
            }
            text(QRect(62, rect.y() + 7, 154, 30), labels[row], row == m_settingRow ? accent : muted, 17);
            text(QRect(226, rect.y() + 2, 364, 26), m_settingValues.value(row), ink, 18, true);
            const QString hint = row == 4 && m_settingValues.value(row) == "按各模型配置" ?
                "轮换时使用各模型的坐标格式" : hints[row];
            text(QRect(226, rect.y() + 28, 364, 20), hint, muted, 12);
        }
        card(QRect(650, 110, 598, 136), "识别策略");
        text(QRect(670, 157, 558, 72), m_pipelineSummary, ink, 17, false, true);
        card(QRect(650, 264, 598, 120), "实时性能");
        text(QRect(670, 308, 558, 62), m_throughputSummary, ink, 17, false, true);
        card(QRect(650, 402, 598, 226), "模型列表");
        const int first = std::max(0, std::min(m_settingModelIndex - 2, m_settingModels.size() - 5));
        for (int index = first; index < std::min(first + 5, m_settingModels.size()); ++index) {
            const bool selected = index == m_settingModelIndex;
            text(QRect(670, 446 + (index - first) * 32, 558, 30),
                 QString("%1 %2  %3").arg(selected ? "›" : " ").arg(index + 1, 2).arg(m_settingModels[index]),
                 selected ? accent : muted, 16, selected);
        }
        card(QRect(32, 550, 594, 78), "设备状态");
        text(QRect(52, 590, 554, 26), m_statusLine, muted, 14);
        // Diagnostics occupy their own bounded region; never cover camera tiles.
        text(QRect(36, 642, 1208, 30), m_stereoStatus.isEmpty() ? m_visionLine : m_stereoStatus,
             muted, 13);
        text(QRect(36, 679, 1208, 25),
             "快捷键  1–9 模型 · R 轮换 · +/− 阈值 · V 相机 · C 坐标 · P 暂停 · S 截屏 · F 全屏 · Q 退出",
             muted, 14);
    }

    /* 文本 → 小缓存位图（按键值缓存，上限 64 条，超出清空重画） */
    QImage textImage(const QString &s, const QColor &color, int pointSize) {
        const QString key = QString("%1|%2|%3").arg(s).arg(color.rgba()).arg(pointSize);
        auto it = m_textCache.find(key);
        if (it != m_textCache.end()) {
            if (m_perfEnabled) ++m_perf.textHits;
            return it.value();
        }
        if (m_perfEnabled) ++m_perf.textMisses;
        QFont f;
        f.setPointSize(pointSize);
        QFontMetrics fm(f);
        QImage img(fm.horizontalAdvance(s) + 16, fm.height() + 8,
                   QImage::Format_ARGB32_Premultiplied);
        img.fill(QColor(0, 0, 0, 170));
        QPainter p(&img);
        p.setFont(f);
        p.setPen(color);
        p.drawText(img.rect().adjusted(8, 0, -8, 0), Qt::AlignLeft | Qt::AlignVCenter, s);
        p.end();
        if (m_textCache.size() > 64) {
            if (m_perfEnabled) ++m_perf.textClears;
            m_textCache.clear();
        }
        m_textCache.insert(key, img);
        return img;
    }

    QOpenGLShaderProgram m_prog;
    static constexpr int kTextureRing = 3;
    int m_textureRing = 1;
    GLuint m_tex = 0; // video texture
    GLuint m_overlayTexture = 0, m_vertexBuffer = 0;
    GLfloat m_vertices[CAM_COUNT + 2][16] = {};
    bool m_vertexValid[CAM_COUNT + 2] = {};
    QSize m_overlaySize;
    QImage m_rasterOverlay;
    QList<QRect> m_previousHudRegions;
    bool m_overlaySettings = false;
    quint64 m_overlayRevision = 0, m_detectionRevision = 0, m_overlayDetections = 0;
    qint64 m_overlayUpdatedMs = 0;
    qint64 m_overlayExpiresMs = 0;
    int m_overlayRow = -1;
    GLuint m_cameraTextures[CAM_COUNT][kTextureRing] = {};
    std::array<int, CAM_COUNT> m_cameraTextureSlot{};
    bool m_cameraTextureAllocated[CAM_COUNT][kTextureRing] = {};
    bool m_texAlloc = false;
    bool m_dirty = false;
    bool m_videoMode = false;
    bool m_help = false;
    bool m_settingsVisible = false;
    int m_settingRow = 0, m_settingModelIndex = 0;
    QStringList m_settingValues, m_settingModels;
    QString m_pipelineSummary, m_throughputSummary, m_monitorSummary;
    quint64 m_settingsRevision = 0;
    QImage m_settingsImage;
    QString m_settingsImageKey;
    QMutex m_uiMutex;              // 显示状态锁（采集/推理线程写，GL 线程读）
    bool m_haveFrame = false;
    QImage m_comp;                 // RGB565 3x2 合成（包装相机线程缓冲）
    std::array<QByteArray, CAM_COUNT> m_cameraPixels;
    int m_changedMask = 0x3F;      // 本次更新的格子（供按格 glTexSubImage2D）
    int m_texW = 0, m_texH = 0;    // 当前纹理尺寸（判断是否需要重新分配）
    QImage m_image;                // 视频源路径
    QImage m_laneMask;
    QImage m_stereoPreview;
    QByteArray m_uploadTile;
    QString m_stereoStatus, m_visionLine;

    QHash<QString, QImage> m_textCache;
    QVector<Detection> m_dets;
    QStringList m_classes;
    int m_paneMask = 0x3F, m_pane = 0;
    double m_dispFps = 0;
    QVector<double> m_camFps = QVector<double>(CAM_COUNT, 0.0);
    std::array<uint64_t, CAM_COUNT> m_sequences{}, m_uploadedSequences{};
    std::array<qint64, CAM_COUNT> m_capturedMs{};
    std::array<tdm::FrameRate, CAM_COUNT> m_cameraUploadRates;
    quint64 m_videoSequence = 0, m_uploadedVideoSequence = 0;
    qint64 m_videoReceivedMs = 0;
    bool m_metricsPaused = false;
    tdm::FrameRate m_takeRate, m_uploadRate, m_newPaintRate, m_paintRate;
    QString m_statusLine, m_modelLine, m_confLine;
    std::function<void(QKeyEvent *)> m_keyHook;
    int m_paintCount = 0;
    double m_paintMsSum = 0;
    tdm::DisplayPerfWindow m_perf;
    bool m_perfEnabled = true;
    qint64 m_perfStartedMs = 0;
};

/* 轮换模型在界面上的短名：去掉 det-/yolov8n- 前缀与 -rk3568 之后的量化后缀 */
static QString shortModelName(const QString &path) {
    QString n = QFileInfo(path).completeBaseName();
    const int cut = n.indexOf("-rk3568");
    if (cut > 0)
        n = n.left(cut);
    n.remove("det-");
    n.remove("yolov8n-");
    return n;
}

/* ---------------- 控制器（没有独立窗口，UI 全在 DetView 这一个 GL 窗口里） ----------------
   板端没有合成器，QWidget 系的 GL 方案（QOpenGLWidget / createWindowContainer）会闪、
   留残影；所以整个程序只有 DetView 一个顶层 GL 窗口：画面、检测框、HUD 三行文字都在
   它里面，操作全走键盘。本类只持有采集/推理线程与状态，把结果投给 DetView。 */
class DetViewController : public QObject {
    Q_OBJECT
public:
    DetViewController(const QVector<ModelInfo> &models, const QString &videoSource,
                      const VisionOptions &visionOptions)
        : m_models(models), m_visionOptions(visionOptions) {
        m_gl = new DetView();
        m_gl->setGeometry(QGuiApplication::primaryScreen()->geometry());
        m_gl->setKeyHook([this](QKeyEvent *e) { handleKey(e); });
        m_gl->show();

        m_camera = new CameraThread();
        m_videoMode = !videoSource.isEmpty();
        if (m_videoMode)
            m_camera->setVideoSource(videoSource);
        m_infer = new InferenceThread();
        m_vision = new VisionPipeline(visionOptions);
        m_camera->setVisionSink(visionOptions, [this](const VisionFrame& frame) { m_vision->submitFrame(frame); });
        connect(m_camera, &CameraThread::displayAvailable, this, [this]() {
            const auto frame = m_camera->takeDisplay();
            if (frame.generation != m_sourceGeneration || (frame.video && frame.image.isNull())) return;
            m_gl->observeFrame(frame);
            if (frame.video) onImage(frame.image, frame.fps);
            else {
                m_camFps = frame.fps;
                m_lastFrameMs = QDateTime::currentMSecsSinceEpoch();
                m_gl->submitCameras(frame);
                if (m_labelTimer.elapsed() >= 300) {
                    m_labelTimer.restart();
                    updateHudLines();
                }
            }
        });
        connect(m_camera, &CameraThread::statusMsg, this, [this](QString s) {
            m_gl->setStatusLine(s);
        });
        connect(m_infer, &InferenceThread::detectionsReady, m_vision,
                [vision = m_vision](QString model, int generation, quint64 id,
                                   QVector<Detection> dets, double, double ms) {
            vision->submitDetections(std::move(model), generation, id, std::move(dets), ms);
        }, Qt::DirectConnection);
        connect(m_infer, &InferenceThread::laneMaskReady, m_vision,
                [vision = m_vision](QImage, int generation, quint64 id, double, double) {
            vision->inferenceFailed(generation, id);
        }, Qt::DirectConnection);
        connect(m_infer, &InferenceThread::detectionsReady, this, &DetViewController::onDets, Qt::QueuedConnection);
        connect(m_infer, &InferenceThread::laneMaskReady, this, &DetViewController::onLaneMask, Qt::QueuedConnection);
        connect(m_infer, &InferenceThread::modelLoaded, this, &DetViewController::onModelLoaded);
        connect(m_vision, &VisionPipeline::inferenceRequested, this, [this](VisionFrame frame) {
            if (frame.sourceGeneration != m_sourceGeneration || m_paused) {
                m_vision->inferenceFailed(frame.sourceGeneration, frame.frameId);
                return;
            }
            m_infer->submit(frame.image, frame.sourceGeneration, frame.frameId);
            m_requestRate.add(monotonicMs());
        });
        connect(m_infer, &InferenceThread::inferenceFailed, m_vision,
                &VisionPipeline::inferenceFailed, Qt::DirectConnection);
        connect(m_vision, &VisionPipeline::tracksReady, this,
                [this](QString model, int generation, quint64, QVector<Detection> dets, double ms) {
            if (generation != m_sourceGeneration) return;
            if (m_rotationEnabled) {
                m_lastTrackMs = monotonicMs();
                m_results[model] = dets;
                m_resultTime[model] = monotonicMs();
                updateRotationOverlay();
            } else if (m_currentIndex >= 0 && m_models[m_currentIndex].path == model) {
                m_lastTrackMs = monotonicMs();
                m_gl->setDetections(dets, m_classes);
            }
            m_trackingMs = ms;
        });
        connect(m_vision, &VisionPipeline::stereoReady, this,
                [this](int generation, quint64, QImage disparity, QString status) {
            if (generation != m_sourceGeneration) return;
            m_lastStereoMs = monotonicMs();
            m_gl->setStereoPreview(disparity, status);
        });
        connect(m_vision, &VisionPipeline::diagnostics, this, [this](QString text) {
            m_gl->setVisionLine(text);
        });
        /* 未指定 --rotate-model 时，R 键在“全部非 lane 检测模型(最多 4 款)”上轮换 */
        for (const ModelInfo &model : m_models) {
            if (m_rotationSelection.size() >= 4)
                break;
            if (!model.lane && QFileInfo(model.path).fileName().startsWith("det-"))
                m_rotationSelection.append(model);
        }
        m_statsTimer.start();
        m_labelTimer.start();
        m_infer->start();
        m_vision->start();
        m_camera->start();
        /* 轮换结果 2 秒过期；过期只影响叠加显示，不影响推理 */
        auto *expiry = new QTimer(this);
        connect(expiry, &QTimer::timeout, this, [this]() {
            if (m_rotationEnabled)
                updateRotationOverlay();
            if (m_visionOptions.stereoEnabled() && monotonicMs() - m_lastStereoMs > 1000)
                m_gl->setStereoPreview({}, "双目：等待新帧，旧距离已失效");
            if (monotonicMs() - m_lastLaneMs > 2000) m_gl->setLaneMask({});
            updateHudLines();
            if (m_statsTimer.elapsed() >= 5000) {
                const double seconds = m_statsTimer.elapsed() / 1000.0;
                m_statsTimer.restart();
                const auto paints = m_gl->takePaintStats();
                const auto npu = m_infer->metrics(m_sourceGeneration);
                fprintf(stderr, "[stats] take_fps=%.2f upload_new_fps=%.2f paint_new_fps=%.2f paint_fps=%.2f paint_avg_ms=%.2f npu_request_fps=%.2f npu_started_fps=%.2f npu_completed_fps=%.2f npu_failed_fps=%.2f infer_service_ms=%.2f\n",
                        m_gl->takeRate(), m_gl->uploadRate(), m_gl->newFrameRate(), paints.count / seconds,
                        paints.averageMs, m_requestRate.rate(monotonicMs()), npu.started, npu.completed,
                        npu.failed, m_lastMs);
                m_gl->reportPerformance();
            }
            m_gl->refreshExpiredContent(); // Refresh labels/TTL only when due.
        });
        expiry->start(100);
        /* 看门狗：相机停摆（FPGA 不再出帧）或 ioctl 被驱动的信号量卡住时，
           ioctlTmo 的失败计数不会推进，应用会一直挂着不退。这里用"多久没有新帧"
           兜底：60 秒没有任何新帧就退出，交给 run_detview.sh 重启；暂停时不计时。 */
        m_lastFrameMs = QDateTime::currentMSecsSinceEpoch();
        /* 超时默认 60s，可用 DETVIEW_NOFRAME_MS 覆盖（自测看门狗时用） */
        m_noFrameTimeoutMs = qEnvironmentVariableIsSet("DETVIEW_NOFRAME_MS")
                                 ? qEnvironmentVariableIntValue("DETVIEW_NOFRAME_MS") : 60000;
        if (m_noFrameTimeoutMs <= 0)
            m_noFrameTimeoutMs = 60000;
        auto *watchdog = new QTimer(this);
        connect(watchdog, &QTimer::timeout, this, [this]() {
            if (m_paused || m_lastFrameMs == 0)
                return;
            const qint64 silent = QDateTime::currentMSecsSinceEpoch() - m_lastFrameMs;
            if (silent < m_noFrameTimeoutMs)
                return;
            fprintf(stderr, "[recover] no new frame for %lld ms -> exit(3) for supervisor restart\n",
                    (long long)silent);
            fflush(stderr);
            ::_exit(3);
        });
        watchdog->start(5000);
        if (!m_models.isEmpty())
            onModelChanged(0);
    }
    ~DetViewController() override {
        m_camera->stop();
        m_camera->wait();
        m_infer->stop();
        m_vision->stop();
        delete m_camera;
        delete m_infer;
        delete m_vision;
        delete m_gl;
    }

    void setModelIndex(int index) {
        if (index >= 0 && index < m_models.size())
            onModelChanged(index);
    }
    void setFullscreen(bool on) {
        m_full = on;
        on ? m_gl->showFullScreen() : m_gl->showNormal();
    }
    /* 0..5 = C1..C6 单路，CAM_COUNT = 6 路 3x2 */
    void setCameraMode(int mode) {
        if (mode >= 0 && mode <= CAM_COUNT)
            onCamChanged(mode);
    }
    bool setRotation(const QStringList &selectors) {
        QVector<ModelInfo> chosen;
        if (!selectRotation(m_models, selectors, chosen)) return false;
        m_rotationSelection = chosen;
        startRotation(chosen);
        return m_rotationEnabled;
    }
    /* --shot N：N 秒后自动截一张 GL 帧缓冲（远程/无人值守验证用），之后继续跑 */
    void takeShot() { onScreenshot(); }

private:
    void handleKey(QKeyEvent *e) {
        int k = e->key();
        if (k == Qt::Key_Escape && e->isAutoRepeat()) return;
        if (k == Qt::Key_Tab || k == Qt::Key_Backtab) {
            if (!e->isAutoRepeat()) {
                m_gl->setSettingsVisible(!m_gl->settingsVisible());
                fprintf(stderr, "[ui] page=%s\n", m_gl->settingsVisible() ? "settings" : "monitor");
                updateHudLines();
            }
            return;
        }
        if (m_gl->settingsVisible()) {
            if (k == Qt::Key_Escape) { m_gl->setSettingsVisible(false); return; }
            if (k == Qt::Key_Up || k == Qt::Key_Down) {
                m_gl->moveSetting(k == Qt::Key_Up ? -1 : 1);
                return;
            }
            if (k == Qt::Key_Left || k == Qt::Key_Right || k == Qt::Key_Return || k == Qt::Key_Enter) {
                const int direction = k == Qt::Key_Left ? -1 : 1;
                switch (m_gl->settingRow()) {
                case 0:
                    if (!m_models.isEmpty())
                        onModelChanged((m_currentIndex + direction + m_models.size()) % m_models.size());
                    return;
                case 1:
                    if (!m_videoMode) onCamChanged((m_camMode + direction + CAM_COUNT + 1) % (CAM_COUNT + 1));
                    return;
                case 2: onConfChanged(m_confPct + direction * 5); return;
                case 3: k = Qt::Key_R; break;
                case 4: k = Qt::Key_C; break;
                case 5: k = Qt::Key_P; break;
                }
            }
        }
        if (k >= Qt::Key_1 && k <= Qt::Key_9) {
            const int idx = k - Qt::Key_1;
            if (idx < m_models.size())
                onModelChanged(idx);
            return;
        }
        switch (k) {
        case Qt::Key_Q:
        case Qt::Key_Escape:
            qApp->quit();
            break;
        case Qt::Key_F:
            setFullscreen(!m_full);
            break;
        case Qt::Key_S:
            onScreenshot();
            break;
        case Qt::Key_C:
            if (m_rotationEnabled) {
                m_gl->setStatusLine("轮换时使用各模型的坐标格式");
                break;
            }
            m_xyxy = !m_xyxy;
            m_infer->setFormat(m_xyxy);
            resetVision();
            updateHudLines();
            break;
        case Qt::Key_V:
            if (!m_videoMode) onCamChanged((m_camMode + 1) % (CAM_COUNT + 1));
            break;
        case Qt::Key_G:
            if (!m_videoMode) onCamChanged(CAM_COUNT);
            m_gl->setSettingsVisible(false);
            break;
        case Qt::Key_P:
        case Qt::Key_Space:
            m_paused = !m_paused;
            m_gl->setMetricsPaused(m_paused);
            m_camera->setPaused(m_paused);
            if (!m_paused) m_lastFrameMs = QDateTime::currentMSecsSinceEpoch();
            resetVision();
            m_gl->setDetections({}, m_classes);
            m_gl->setStatusLine(m_paused ? "已暂停 (P/空格 继续)" : "运行中");
            updateHudLines();
            break;
        case Qt::Key_Minus:
        case Qt::Key_Underscore:
            onConfChanged(std::max(5, m_confPct - 5));
            break;
        case Qt::Key_Equal:
        case Qt::Key_Plus:
            onConfChanged(std::min(95, m_confPct + 5));
            break;
        case Qt::Key_H:
            m_helpVisible = !m_helpVisible;
            m_gl->setHelpVisible(m_helpVisible);
            break;
        case Qt::Key_R:
            if (m_rotationEnabled)
                onModelChanged(m_currentIndex < 0 ? 0 : m_currentIndex);
            else
                startRotation(m_rotationSelection);
            break;
        default:
            break;
        }
    }

    void onFrame(QImage content, int paneMask, int pane, double fps, QVector<double> camFps,
                 int changedMask) {
        m_camFps = fps;
        m_lastFrameMs = QDateTime::currentMSecsSinceEpoch();
        m_gl->submitComposite(content, paneMask, pane, fps, camFps, changedMask);
        if (m_labelTimer.elapsed() >= 300) {
            m_labelTimer.restart();
            updateHudLines();
        }
    }
    void onImage(QImage frame, double fps) {
        m_camFps = fps;
        m_lastFrameMs = QDateTime::currentMSecsSinceEpoch();
        m_gl->submitImage(frame, fps);
        if (m_labelTimer.elapsed() >= 300) {
            m_labelTimer.restart();
            updateHudLines();
        }
    }
    void resetVision() {
        ++m_sourceGeneration;
        m_infer->resetMetrics(m_sourceGeneration);
        m_requestRate.reset(monotonicMs());
        m_gl->resetRates();
        m_resultMs.clear(); m_resultFps.clear();
        m_rotInferFps = m_lastMs = 0;
        m_lastDets = 0;
        QStringList paths;
        bool lane = false;
        if (m_rotationEnabled) {
            for (const auto& model : m_rotation) paths.append(model.path);
        } else if (m_currentIndex >= 0) {
            paths.append(m_models[m_currentIndex].path);
            lane = m_models[m_currentIndex].lane;
        }
        const int selected = m_videoMode ? 0 : (m_camMode == CAM_COUNT ?
            (m_visionOptions.stereoEnabled() ? m_visionOptions.primaryStereoLeft() : 0) : m_camMode);
        m_vision->configure(m_sourceGeneration, selected, lane, paths);
        m_camera->setSourceGeneration(m_sourceGeneration);
        m_results.clear();
        m_resultTime.clear();
        m_gl->setDetections({}, m_classes);
        m_gl->setLaneMask({});
        m_lastStereoMs = m_lastTrackMs = 0;
        m_gl->setStereoPreview({}, m_visionOptions.stereoEnabled() ? "双目：等待配对帧" : QString());
    }

    void onCamChanged(int index) {
        if (index < 0 || index > CAM_COUNT)
            return;
        m_camMode = index;
        m_results.clear();
        m_resultTime.clear();
        m_resultMs.clear();
        m_resultFps.clear();
        m_rotInferFps = 0;
        m_gl->setDetections({}, m_classes);
        m_gl->setLaneMask({});
        m_camera->setMode(index);
        m_gl->setCameraLayout(index, index == CAM_COUNT ?
            (m_visionOptions.stereoEnabled() ? m_visionOptions.primaryStereoLeft() : 0) : index);
        resetVision();
        updateHudLines();
    }

    void onDets(QString modelPath, int sourceGeneration, quint64 frameId,
                QVector<Detection> dets, double fps, double ms) {
        if (sourceGeneration != m_sourceGeneration)
            return;
        Q_UNUSED(frameId);
        if (m_rotationEnabled) {
            bool chosen = false;
            for (const ModelInfo &model : m_rotation)
                if (model.path == modelPath)
                    chosen = true;
            if (!chosen)
                return;
            m_resultMs[modelPath] = ms;
            m_lastMs = ms;
            updateRotationOverlay();
        } else {
            if (m_currentIndex < 0 || m_models[m_currentIndex].path != modelPath)
                return;
            m_lastMs = ms;
            m_lastDets = dets.size();
            if (m_labelTimer.elapsed() >= 300) {
                m_labelTimer.restart();
                updateHudLines();
            }
        }
        Q_UNUSED(fps); // Throughput is sampled from the inference thread, independent of GUI queuing.
    }

    void onLaneMask(QImage mask, int generation, quint64 frameId, double fps, double ms) {
        if (generation != m_sourceGeneration) return;
        Q_UNUSED(frameId);
        m_lastLaneMs = monotonicMs();
        m_lastMs = ms;
        m_gl->setLaneMask(mask);
        Q_UNUSED(fps);
        updateHudLines();
    }

    void onModelLoaded(QString path, bool ok, QString info) {
        fprintf(stderr, "[model] %s %s %s\n", path.toLocal8Bit().constData(),
                ok ? "OK" : "FAIL", info.toLocal8Bit().constData());
        m_gl->setStatusLine(QString("%1 -> %2  %3")
                                .arg(QFileInfo(path).fileName())
                                .arg(ok ? "OK" : "FAIL")
                                .arg(info));
    }

    void onModelChanged(int index) {
        if (index < 0 || index >= m_models.size())
            return;
        m_rotationEnabled = false;
        m_currentIndex = index;
        m_results.clear();
        m_classes = m_models[index].classes;
        m_xyxy = m_models[index].xyxy;
        m_gl->setDetections({}, m_classes);
        m_gl->setLaneMask({});
        m_infer->setModel(m_models[index]);
        m_infer->setFormat(m_models[index].xyxy);
        resetVision();
        updateHudLines();
    }

    void startRotation(const QVector<ModelInfo> &selection) {
        if (selection.size() < 2 || selection.size() > 4) {
            m_gl->setStatusLine("轮换需要 2-4 款 YOLO 检测模型（启动时 --rotate-model a,b）");
            return;
        }
        m_rotInferFps = 0;
        m_rotation = selection;
        m_rotationEnabled = true;
        m_results.clear();
        m_resultTime.clear();
        m_resultMs.clear();
        m_resultFps.clear();
        m_gl->setDetections({}, {});
        m_gl->setLaneMask({});
        m_infer->setModels(selection);
        resetVision();
        m_gl->setStatusLine("加载轮换模型中...");
        updateHudLines();
    }

    void updateRotationOverlay() {
        QVector<Detection> all;
        QStringList labels, summaries;
        const qint64 now = monotonicMs();
        const auto npu = m_infer->metrics(m_sourceGeneration);
        m_rotInferFps = npu.completed;
        m_resultFps = npu.modelRates;
        summaries.append(QString("NPU完成 %1 fps").arg(m_rotInferFps, 0, 'f', 1));
        for (const ModelInfo &model : m_rotation) {
            const QString name = shortModelName(model.path);
            if (!m_resultTime.contains(model.path) || now - m_resultTime[model.path] >
                (m_visionOptions.tracking ? m_visionOptions.trackingMaxDetectionAgeMs : 2000))
                continue;
            const int offset = labels.size();
            for (const QString &cls : model.classes)
                labels.append(QString("%1:%2").arg(name, cls));
            for (Detection det : m_results.value(model.path)) {
                det.cls += offset;
                all.append(det);
            }
            summaries.append(QString("%1 %2ms %3个 %4fps NPU%5ms前")
                .arg(name).arg(m_resultMs.value(model.path), 0, 'f', 0)
                .arg(m_results.value(model.path).size()).arg(m_resultFps.value(model.path), 0, 'f', 1)
                .arg(npu.completedMs.contains(model.path) ? now - npu.completedMs.value(model.path) : -1));
        }
        m_visibleDets = all.size();
        m_gl->setDetections(all, labels);
        m_gl->setStatusLine(summaries.join(" | "));
        updateHudLines();
    }

    void onConfChanged(int pct) {
        m_confPct = std::min(95, std::max(5, pct));
        m_infer->setConf(m_confPct / 100.0f);
        resetVision();
        updateHudLines();
    }

    void onScreenshot() {
        const QPixmap pm = QPixmap::fromImage(m_gl->grabFrame());
        if (pm.isNull()) {
            m_gl->setStatusLine("截屏失败: 无画面");
            return;
        }
        const QString dir = "/userdata/detview_shots";
        QDir().mkpath(dir);
        const QString model = (m_currentIndex >= 0 && m_currentIndex < m_models.size())
                                  ? QFileInfo(m_models[m_currentIndex].path).completeBaseName()
                                  : QString("model");
        const QString ts = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
        QString path = QString("%1/shot_%2_%3.png").arg(dir).arg(model).arg(ts);
        if (!pm.save(path, "PNG")) {
            path = QString("%1/shot_%2_%3.jpg").arg(dir).arg(model).arg(ts);
            if (!pm.save(path, "JPG")) {
                m_gl->setStatusLine("截屏保存失败");
                return;
            }
        }
        m_gl->setStatusLine(QString("已保存: %1  (%2x%3)").arg(path).arg(pm.width()).arg(pm.height()));
    }

    QString camModeText() const {
        return m_camMode >= CAM_COUNT ? QString("6 路 3x2") : QString("C%1").arg(m_camMode + 1);
    }

    /* HUD 的模型行与相机/置信度行（状态行由采集/推理事件单独写） */
    void updateHudLines() {
        const auto npu = m_infer->metrics(m_sourceGeneration);
        m_resultFps = npu.modelRates;
        m_rotInferFps = npu.completed;
        QString modelLine;
        if (m_rotationEnabled) {
            QStringList per;
            for (const ModelInfo &model : m_rotation)
                per << QString("%1 %2fps").arg(shortModelName(model.path))
                           .arg(m_resultFps.value(model.path), 0, 'f', 1);
            modelLine = QString("轮换 %1 款: %2").arg(m_rotation.size()).arg(per.join("  "));
        } else if (m_currentIndex >= 0 && m_currentIndex < m_models.size()) {
            const ModelInfo &info = m_models[m_currentIndex];
            modelLine = QString("模型: %1").arg(QFileInfo(info.path).fileName());
            if (m_lastMs > 0)
                modelLine += QString("   处理 %1 ms  %2").arg(m_lastMs, 0, 'f', 1)
                    .arg(info.lane ? QString("lane mask") : QString("检测 %1").arg(m_lastDets));
        }
        m_gl->setModelLine(modelLine);
        m_gl->setConfLine(QString("%1 | conf %2 | %3 | 新画面 %4 fps | NPU 请求 %5 / 完成 %6 fps")
                              .arg(camModeText())
                              .arg(m_confPct / 100.0, 0, 'f', 2)
                              .arg(m_xyxy ? "xyxy" : "cxcywh")
                              .arg(m_gl->newFrameRate(), 0, 'f', 1)
                              .arg(m_requestRate.rate(monotonicMs()), 0, 'f', 1)
                              .arg(npu.completed, 0, 'f', 1));
        QStringList modelNames;
        for (const auto& model : m_models) modelNames.append(shortModelName(model.path));
        const QString activeModel = m_currentIndex >= 0 ? shortModelName(m_models[m_currentIndex].path) : "无模型";
        QStringList rotationNames;
        for (const auto& model : m_rotation) rotationNames.append(shortModelName(model.path));
        const QString rotation = m_rotationEnabled ? rotationNames.join(" + ") : "关闭";
        const QString monitor = QString("%1 · %2").arg(m_videoMode ? "视频" : camModeText())
            .arg(m_rotationEnabled ? "模型轮换" : activeModel);
        QStringList stereoDescriptions;
        for (const auto& pair : m_visionOptions.stereoPairs())
            stereoDescriptions << QString("C%1/C%2 %3·%4").arg(pair.left + 1).arg(pair.right + 1)
                .arg(pair.calibrationPath.isEmpty() ? "未标定" : "已标定")
                .arg(pair.synchronizationConfirmed && pair.hasTagOffset ? "同步已确认" : "同步未确认");
        const QString pipeline = QString("%1\n%2\n%3")
            .arg(m_visionOptions.tracking ? QString("模板追踪 · 检测间隔 %1 ms").arg(m_visionOptions.detectionIntervalMs) :
                                           QString("逐帧 NPU 检测"))
            .arg(m_visionOptions.tracking ? QString("最多 %1 目标 · 有效期 %2 ms")
                    .arg(m_visionOptions.maxTracks).arg(m_visionOptions.trackingMaxDetectionAgeMs) :
                    QString("模板追踪已关闭"))
            .arg(stereoDescriptions.isEmpty() ? QString("双目测距未启用") : stereoDescriptions.join("；"));
        const QString throughput = QString("NPU 请求 %1 / 完成 %2 次/秒\n处理 %3 ms · 追踪 %4 ms")
            .arg(m_requestRate.rate(monotonicMs()), 0, 'f', 0).arg(npu.completed, 0, 'f', 0)
            .arg(m_lastMs, 0, 'f', 1).arg(m_trackingMs, 0, 'f', 1);
        m_gl->setSettings({activeModel, m_videoMode ? "视频源" : camModeText(),
                           QString("%1 %").arg(m_confPct), rotation,
                           m_rotationEnabled ? "按各模型配置" : (m_xyxy ? "xyxy" : "cxcywh"),
                           m_paused ? "已暂停" : "运行中"},
                          modelNames, m_currentIndex, pipeline, throughput, monitor);
    }

    QVector<ModelInfo> m_models;
    QStringList m_classes;
    QVector<ModelInfo> m_rotation, m_rotationSelection;
    bool m_rotationEnabled = false;
    int m_currentIndex = -1;
    QHash<QString, QVector<Detection>> m_results;
    QHash<QString, qint64> m_resultTime;
    QHash<QString, double> m_resultMs;
    QHash<QString, double> m_resultFps;
    int m_visibleDets = 0;
    double m_rotInferFps = 0;
    tdm::FrameRate m_requestRate;
    int m_sourceGeneration = 0;
    bool m_xyxy = false;
    int m_confPct = 25;      /* 与 InferenceThread 默认 conf 一致 */
    int m_camMode = CAM_COUNT;
    bool m_full = false, m_paused = false, m_helpVisible = false, m_videoMode = false;
    double m_camFps = 0, m_lastMs = 0;
    int m_lastDets = 0;
    qint64 m_noFrameTimeoutMs = 60000;   // 无新帧超时（DETVIEW_NOFRAME_MS 可覆盖）
    qint64 m_lastFrameMs = 0;
    QElapsedTimer m_statsTimer, m_labelTimer;
    DetView *m_gl = nullptr;
    CameraThread *m_camera = nullptr;
    InferenceThread *m_infer = nullptr;
    VisionPipeline *m_vision = nullptr;
    VisionOptions m_visionOptions;
    double m_trackingMs = 0;
    qint64 m_lastStereoMs = 0, m_lastTrackMs = 0, m_lastLaneMs = 0;
};

int main(int argc, char **argv) {
    /* camview 同款：强制 Mali EGL/ES2，避免 GLX 回落到 llvmpipe 软件渲染 */
    qputenv("QT_XCB_GL_INTEGRATION", "xcb_egl");
    qputenv("QT_OPENGL", "es2");
    QSurfaceFormat fmt;
    fmt.setRenderableType(QSurfaceFormat::OpenGLES);
    fmt.setVersion(2, 0);
    fmt.setDepthBufferSize(0);
    fmt.setStencilBufferSize(0);
    // Match the deployed optimized camview, not only its source defaults.
    // Set DETVIEW_SWAP_INTERVAL=1 to restore vsync on displays that need it.
    fmt.setSwapInterval(qEnvironmentVariableIsSet("DETVIEW_SWAP_INTERVAL") ?
        qEnvironmentVariableIntValue("DETVIEW_SWAP_INTERVAL") : 0);
    QSurfaceFormat::setDefaultFormat(fmt);
    /* 板端 XFCE 的“窗口缩放”会让 Qt 逻辑尺寸与 X 实际窗口不一致（例如 1.25x 时
       Qt 认为 1920x1080 的窗口只有 1536x864），全屏时画面只能铺满左上角。
       这是全屏 kiosk 程序，按物理像素 1:1 对齐。 */
    if (!qEnvironmentVariableIsSet("QT_SCALE_FACTOR"))
        qputenv("QT_SCALE_FACTOR", "1");
    qputenv("QT_AUTO_SCREEN_SCALE_FACTOR", "0");

    QApplication app(argc, argv);
    qRegisterMetaType<QVector<Detection>>("QVector<Detection>");
    /* frameReady 跨线程带每路采集帧率：不注册这个类型，Qt 会丢掉整个排队信号
       （表现就是“显示 0.0 fps、无每路标签、画面不动”，推理却照常跑） */
    qRegisterMetaType<QVector<double>>("QVector<double>");
    qRegisterMetaType<VisionFrame>("VisionFrame");
    cv::setNumThreads(2);
    if (app.arguments().contains("--tracker-benchmark"))
        return tdm::runTrackerBenchmark();
    if (app.arguments().contains("--vision-selftest")) {
        const bool ok = CameraThread::selfTestDisplay() && DetView::selfTestRefresh() && tdm::runTrackerSelfTest() == 0 &&
                        tdm::runCameraDmaSelfTest() == 0 && runFrameMetricsSelfTest() == 0 &&
                        VisionPipeline::selfTest();
        fprintf(stderr, ok ? "VISION_SELFTEST_PASS\n" : "VISION_SELFTEST_FAIL\n");
        return ok ? 0 : 2;
    }
    if (app.arguments().contains("--dfl-selftest")) {
        const bool ok = InferenceThread::selfTestDfl() && InferenceThread::selfTestDfl(8, 29);
        fprintf(stderr, ok ? "DFL_SELFTEST_PASS\n" : "DFL_SELFTEST_FAIL\n");
        return ok ? 0 : 2;
    }
    if (app.arguments().contains("--camera-dma-selftest")) return tdm::runCameraDmaSelfTest();
    if (app.arguments().contains("--frame-metrics-selftest")) return runFrameMetricsSelfTest();
    if (app.arguments().contains("--lane-selftest")) {
        const bool ok = InferenceThread::selfTestLane();
        fprintf(stderr, ok ? "LANE_SELFTEST_PASS\n" : "LANE_SELFTEST_FAIL\n");
        return ok ? 0 : 2;
    }
    const int probeIndex = app.arguments().indexOf("--lane-probe");
    if (probeIndex >= 0 && probeIndex + 2 < app.arguments().size()) {
        const bool ok = InferenceThread::probeLaneModel(app.arguments()[probeIndex + 1],
                                                         app.arguments()[probeIndex + 2].toInt());
        return ok ? 0 : 2;
    }
    const QVector<ModelInfo> models = scanModels();
    const QStringList args = app.arguments();
    for (const QString &option : {QString("--video"), QString("--duration"), QString("--shot"),
                                  QString("--camera"), QString("--model"), QString("--model-index"),
                                  QString("--rotate-model")}) {
        const int index = args.indexOf(option);
        if (index >= 0 && (index + 1 >= args.size() || args[index + 1].startsWith("--") ||
                          args[index + 1].trimmed().isEmpty())) {
            fprintf(stderr, "%s requires a value\n", qPrintable(option));
            return 2;
        }
    }
    for (const QString &option : {QString("--duration"), QString("--shot"), QString("--camera"),
                                  QString("--model-index")}) {
        const int index = args.indexOf(option);
        if (index < 0) continue;
        bool valid = false;
        const int value = args[index + 1].toInt(&valid);
        const int minimum = option == "--model-index" ? 0 : 1;
        const int maximum = option == "--camera" ? CAM_COUNT :
                            option == "--model-index" ? models.size() - 1 : 3600;
        if (!valid || value < minimum || value > maximum) {
            fprintf(stderr, "%s has an invalid value\n", qPrintable(option));
            return 2;
        }
    }
    // Private parity harness: dispatch before camera/controller construction.
    const int parityTest = args.indexOf("--parity-selftest");
    if (parityTest >= 0) {
        const int modelArg = args.indexOf("--model");
        if (parityTest + 1 >= args.size() || modelArg < 0 || modelArg + 1 >= args.size()) return 2;
        QImage image = QImage(args[parityTest + 1]).convertToFormat(QImage::Format_RGB888);
        if (image.isNull() || image.width() != IMG_W || image.height() != IMG_H) return 2;
        QVector<ModelInfo> chosen;
        for (const ModelInfo &model : models)
            if (!model.lane && model.path == args[modelArg + 1]) chosen.append(model);
        if (chosen.size() != 1) {
            fprintf(stderr, "[parity] {\"event\":\"error\",\"reason\":\"exact model selector must match one detection model\"}\n");
            return 2;
        }
        InferenceThread worker;
        const int requested = 3;
        int completed = 0, errors = 0, rc = 2;
        QObject::connect(&worker, &InferenceThread::modelLoaded, &app,
            [&](QString, bool ok, QString info) {
                const QByteArray encoded = QJsonDocument(QJsonObject{{"event", "load"},
                    {"ok", ok}, {"info", info}}).toJson(QJsonDocument::Compact);
                fprintf(stderr, "[parity] %s\n", encoded.constData());
                if (!ok) { ++errors; app.quit(); }
            });
        QObject::connect(&worker, &InferenceThread::inferenceFailed, &app,
            [&](int, quint64) {
                ++errors;
                fprintf(stderr, "[parity] {\"event\":\"error\",\"reason\":\"inferenceFailed\"}\n");
                app.quit();
            });
        QObject::connect(&worker, &InferenceThread::detectionsReady, &app,
            [&](QString path, int, quint64 frameId, QVector<Detection> dets, double, double) {
                if (path != chosen[0].path || frameId != quint64(completed + 1)) ++errors;
                ++completed;
                fprintf(stderr, "[parity] {\"event\":\"frame\",\"completion\":%d,\"frame_id\":%llu,\"count\":%d,\"detections\":[",
                        completed, (unsigned long long)frameId, dets.size());
                for (int i = 0; i < dets.size(); ++i) {
                    const Detection &d = dets[i];
                    // 9 significant digits round-trip all float32 tuple values.
                    fprintf(stderr, "%s{\"class\":%d,\"score\":%.9g,\"x1\":%.9g,\"y1\":%.9g,\"x2\":%.9g,\"y2\":%.9g}",
                            i ? "," : "", d.cls, double(d.score), double(d.x1), double(d.y1), double(d.x2), double(d.y2));
                }
                fprintf(stderr, "]}\n");
                fflush(stderr);
                if (completed >= requested || errors) {
                    rc = completed == requested && errors == 0 ? 0 : 2;
                    app.quit();
                } else worker.submit(image, 0, completed + 1);
            });
        QTimer::singleShot(30000, &app, [&] {
            ++errors;
            fprintf(stderr, "[parity] {\"event\":\"error\",\"reason\":\"timeout\"}\n");
            app.quit();
        });
        worker.start();
        worker.setModels(chosen);
        worker.submit(image, 0, 1);
        app.exec();
        worker.stop();
        fprintf(stderr, "[parity] {\"event\":\"summary\",\"requested\":%d,\"completed\":%d,\"errors\":%d,\"rc\":%d}\n",
                requested, completed, errors, rc);
        return rc;
    }

    const int rotateTest = args.indexOf("--rotate-selftest");
    if (rotateTest >= 0 && rotateTest + 2 < args.size()) {
        const QImage image = QImage(args[rotateTest + 1]).convertToFormat(QImage::Format_RGB888);
        const QStringList selectors = args[rotateTest + 2].split(',', Qt::SkipEmptyParts);
        if (image.isNull() || selectors.size() < 2 || selectors.size() > 4) return 2;
        QVector<ModelInfo> chosen;
        for (const QString &selector : selectors) {
            ModelInfo match;
            int count = 0;
            for (const ModelInfo &candidate : models)
                if (!candidate.lane && QFileInfo(candidate.path).fileName().startsWith("det-") &&
                    candidate.path.contains(selector.trimmed(), Qt::CaseInsensitive)) {
                    match = candidate; ++count;
                }
            if (count != 1) { fprintf(stderr, "selector %s matched %d models\n",
                        qPrintable(selector), count); return 2; }
            chosen.append(match);
        }
        InferenceThread worker;
        QHash<QString, int> counts;
        int total = 0;
        int rc = 2;
        bool orderOk = true;
        QObject::connect(&worker, &InferenceThread::modelLoaded, &app,
            [&](QString path, bool ok, QString info) {
                fprintf(stderr, "[rotate-load] %s %s %s\n", qPrintable(path),
                        ok ? "OK" : "FAIL", qPrintable(info));
                if (!ok) app.quit();
            });
        QObject::connect(&worker, &InferenceThread::detectionsReady, &app,
            [&](QString path, int, quint64, QVector<Detection>, double, double ms) {
                if (path != chosen[total % chosen.size()].path) orderOk = false;
                ++counts[path];
                if (++total >= 80) {
                    rc = counts.size() == chosen.size() && orderOk ? 0 : 2;
                    app.quit();
                } else worker.submit(image);
                if (total <= 8) fprintf(stderr, "[rotate-frame] %d %s %.2fms\n",
                                         total, qPrintable(path), ms);
            });
        QTimer::singleShot(30000, &app, &QCoreApplication::quit);
        worker.start();
        worker.setModels(chosen);
        worker.submit(image);
        app.exec();
        worker.stop();
        for (const ModelInfo &model : chosen)
            fprintf(stderr, "[rotate-count] %s %d\n", qPrintable(model.path), counts.value(model.path));
        return rc;
    }
    const int videoArg = args.indexOf("--video");
    QString videoSource = videoArg >= 0 && videoArg + 1 < args.size()
        ? args[videoArg + 1] : QString();
    if (!videoSource.isEmpty() && !videoSource.contains("://") &&
        !videoSource.startsWith("/dev/video"))
        videoSource = QFileInfo(videoSource).absoluteFilePath();
    VisionOptions visionOptions;
    try {
        auto integerOption = [&](const QString &name, int fallback) {
            const int index = args.indexOf(name);
            if (index < 0) return fallback;
            if (index + 1 >= args.size()) throw std::invalid_argument(qPrintable(name + " needs a value"));
            bool ok = false;
            const int value = args[index + 1].toInt(&ok);
            if (!ok) throw std::invalid_argument(qPrintable(name + " requires an integer"));
            return value;
        };
        visionOptions.tracking = !args.contains("--no-tracking");
        visionOptions.detectionIntervalMs = integerOption("--detect-interval-ms", 250);
        visionOptions.minimumDetectionIntervalMs = integerOption("--detect-min-ms", 100);
        visionOptions.maxTracks = integerOption("--max-tracks", 12);
        visionOptions.trackingMaxDetectionAgeMs = integerOption("--track-max-age-ms", 2000);
        visionOptions.stereoIntervalMs = integerOption("--stereo-interval-ms", 200);
        visionOptions.stereoDisparities = integerOption("--stereo-disparities", 32);
        if (visionOptions.detectionIntervalMs < 50 || visionOptions.detectionIntervalMs > 2000 ||
            visionOptions.minimumDetectionIntervalMs < 50 ||
            visionOptions.minimumDetectionIntervalMs > visionOptions.detectionIntervalMs ||
            visionOptions.maxTracks < 1 || visionOptions.maxTracks > 12 ||
            visionOptions.trackingMaxDetectionAgeMs < 500 || visionOptions.trackingMaxDetectionAgeMs > 10000 ||
            visionOptions.stereoIntervalMs < 100 || visionOptions.stereoIntervalMs > 5000 ||
            visionOptions.stereoDisparities < 16 || visionOptions.stereoDisparities % 16 ||
            visionOptions.stereoDisparities > 128)
            throw std::invalid_argument("Invalid tracking/stereo timing, track count or disparity range");
        const int stereoArg = args.indexOf("--stereo");
        if (stereoArg >= 0) {
            if (stereoArg + 1 >= args.size()) throw std::invalid_argument("--stereo needs LEFT,RIGHT camera IDs");
            const auto cameras = args[stereoArg + 1].split(',');
            bool leftOk = false, rightOk = false;
            if (cameras.size() != 2) throw std::invalid_argument("--stereo needs LEFT,RIGHT");
            visionOptions.stereoLeft = cameras[0].toInt(&leftOk) - 1;
            visionOptions.stereoRight = cameras[1].toInt(&rightOk) - 1;
            if (!leftOk || !rightOk || visionOptions.stereoLeft < 0 || visionOptions.stereoLeft >= CAM_COUNT ||
                visionOptions.stereoRight < 0 || visionOptions.stereoRight >= CAM_COUNT ||
                visionOptions.stereoLeft == visionOptions.stereoRight || !videoSource.isEmpty())
                throw std::invalid_argument("Stereo requires two distinct FPGA cameras 1..6; video source is mono");
        }
        const int calibrationArg = args.indexOf("--stereo-calibration");
        if (calibrationArg >= 0) {
            if (calibrationArg + 1 >= args.size()) throw std::invalid_argument("Missing stereo calibration path");
            visionOptions.calibrationPath = args[calibrationArg + 1];
        }
        const int scaleArg = args.indexOf("--stereo-scale");
        if (scaleArg >= 0) {
            bool ok = false;
            if (scaleArg + 1 >= args.size()) throw std::invalid_argument("Missing stereo scale");
            visionOptions.stereoScale = args[scaleArg + 1].toDouble(&ok);
            if (!ok || !std::isfinite(visionOptions.stereoScale) || visionOptions.stereoScale < 0.125 ||
                visionOptions.stereoScale > 1)
                throw std::invalid_argument("Stereo scale must be 0.125..1");
        }
        visionOptions.synchronizationConfirmed = args.contains("--stereo-synchronized");
        visionOptions.hasTagOffset = args.contains("--stereo-tag-offset");
        visionOptions.tagOffset = integerOption("--stereo-tag-offset", 0);
        const int groupsArg = args.indexOf("--stereo-config");
        if (groupsArg >= 0) {
            if (stereoArg >= 0 || calibrationArg >= 0 || visionOptions.synchronizationConfirmed || visionOptions.hasTagOffset)
                throw std::invalid_argument("--stereo-config cannot combine with single-pair camera/calibration/sync options");
            if (groupsArg + 1 >= args.size() || !videoSource.isEmpty())
                throw std::invalid_argument("--stereo-config requires a JSON path and FPGA cameras");
            const QFileInfo configInfo(args[groupsArg + 1]);
            QFile file(configInfo.absoluteFilePath());
            if (!file.open(QIODevice::ReadOnly)) throw std::invalid_argument("Cannot open stereo config");
            QJsonParseError error;
            const auto doc = QJsonDocument::fromJson(file.readAll(), &error);
            if (error.error != QJsonParseError::NoError || !doc.isObject() || !doc.object().value("pairs").isArray())
                throw std::invalid_argument("Stereo config requires a JSON object with pairs array");
            const auto groups = doc.object().value("pairs").toArray();
            if (groups.isEmpty() || groups.size() > 2) throw std::invalid_argument("Stereo config supports 1..2 pairs");
            int usedCameras = 0;
            for (const auto& value : groups) {
                if (!value.isObject()) throw std::invalid_argument("Each stereo pair must be an object");
                const auto object = value.toObject();
                auto camera = [&](const char* name) {
                    const auto v = object.value(name);
                    if (!v.isDouble() || v.toDouble() != v.toInt() || v.toInt() < 1 || v.toInt() > CAM_COUNT)
                        throw std::invalid_argument("Stereo camera IDs must be integers 1..6");
                    return v.toInt() - 1;
                };
                StereoPairOptions pair; pair.left = camera("left"); pair.right = camera("right");
                const int mask = (1 << pair.left) | (1 << pair.right);
                if (pair.left == pair.right || (usedCameras & mask))
                    throw std::invalid_argument("Stereo pairs must use distinct, non-overlapping cameras");
                usedCameras |= mask;
                if (object.contains("calibration") && !object.value("calibration").isString())
                    throw std::invalid_argument("Stereo calibration must be a path string");
                pair.calibrationPath = object.value("calibration").toString();
                if (!pair.calibrationPath.isEmpty())
                    pair.calibrationPath = configInfo.absoluteDir().absoluteFilePath(pair.calibrationPath);
                if (object.contains("synchronized") && !object.value("synchronized").isBool())
                    throw std::invalid_argument("Stereo synchronized must be boolean");
                pair.synchronizationConfirmed = object.value("synchronized").toBool(false);
                pair.hasTagOffset = object.contains("tag_offset");
                if (pair.hasTagOffset) {
                    const auto offset = object.value("tag_offset");
                    if (!offset.isDouble() || offset.toDouble() != offset.toInt())
                        throw std::invalid_argument("Stereo tag_offset must be a signed integer");
                    pair.tagOffset = offset.toInt();
                }
                if (object.contains("interval_ms")) {
                    const auto interval = object.value("interval_ms");
                    if (!interval.isDouble() || interval.toDouble() != interval.toInt() ||
                        interval.toInt() < 100 || interval.toInt() > 5000)
                        throw std::invalid_argument("Stereo interval_ms must be an integer 100..5000");
                    pair.intervalMs = interval.toInt();
                }
                visionOptions.stereoGroups.push_back(pair);
            }
        }
        if (!visionOptions.stereoEnabled() && (calibrationArg >= 0 || scaleArg >= 0 ||
            visionOptions.synchronizationConfirmed || visionOptions.hasTagOffset))
            throw std::invalid_argument("Stereo calibration/sync options require --stereo LEFT,RIGHT");
        if (visionOptions.stereoEnabled() &&
            cvRound(IMG_W * visionOptions.stereoScale) <= visionOptions.stereoDisparities + 5)
            throw std::invalid_argument("Stereo image is too small for the disparity search range");
        if (!visionOptions.stereoConfigurationError().isEmpty())
            throw std::invalid_argument(visionOptions.stereoConfigurationError().toStdString());
        for (const auto& pair : visionOptions.stereoPairs()) {
            if (pair.calibrationPath.isEmpty()) continue;
            const auto calibration = stereo::Calibration::load(pair.calibrationPath.toStdString());
            if (calibration.imageSize != cv::Size(IMG_W, IMG_H))
                throw std::invalid_argument("Stereo calibration must match 640x480 FPGA frames");
        }
    } catch (const std::exception &error) {
        fprintf(stderr, "detview options: %s\n", error.what());
        return 2;
    }
    const int rotateArg = args.indexOf("--rotate-model");
    const QStringList rotationSelectors = rotateArg >= 0 ? args[rotateArg + 1].split(',') : QStringList();
    QVector<ModelInfo> rotationModels;
    if (rotateArg >= 0 && !selectRotation(models, rotationSelectors, rotationModels)) {
        fprintf(stderr, "--rotate-model needs 2-4 unique YOLO model substrings\n");
        return 2;
    }
    DetViewController w(models, videoSource, visionOptions);
    const int ai = args.indexOf("--model-index");
    if (ai >= 0 && ai + 1 < args.size()) {
        const int idx = args[ai + 1].toInt();
        if (idx >= 0 && idx < models.size())
            w.setModelIndex(idx);
    } else {
        const int si = args.indexOf("--model");
        if (si >= 0 && si + 1 < args.size()) {
            for (int i = 0; i < models.size(); i++) {
                if (models[i].path.contains(args[si + 1], Qt::CaseInsensitive)) {
                    w.setModelIndex(i);
                    break;
                }
            }
        }
    }
    if (rotateArg >= 0 && !w.setRotation(rotationSelectors)) {
        fprintf(stderr, "--rotate-model needs 2-4 unique YOLO model substrings\n");
        return 2;
    }
    const int shotArg = args.indexOf("--shot");
    if (shotArg >= 0 && shotArg + 1 < args.size()) {
        const int seconds = args[shotArg + 1].toInt();
        if (seconds < 1 || seconds > 3600)
            return 2;
        QTimer::singleShot(seconds * 1000, &w, [&w]() { w.takeShot(); });
    }
    const int durationArg = args.indexOf("--duration");
    if (durationArg >= 0 && durationArg + 1 < args.size()) {
        const int seconds = args[durationArg + 1].toInt();
        if (seconds < 1 || seconds > 3600) return 2;
        QTimer::singleShot(seconds * 1000, &app, &QCoreApplication::quit);
    }
    if (args.contains("--fullscreen"))
        w.setFullscreen(true);
    const int camArg = args.indexOf("--camera");
    if (camArg >= 0 && camArg + 1 < args.size()) {
        const int cam = args[camArg + 1].toInt();
        if (cam < 1 || cam > CAM_COUNT)
            return 2;
        w.setCameraMode(cam - 1);   // C1..C6 单路
    }
    return app.exec();
}

#include "main.moc"
