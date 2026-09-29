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
#include <QKeyEvent>
#include <QLabel>
#include <QMutex>
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
#include <atomic>
#include <cmath>
#include <csignal>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <fcntl.h>
#include <functional>
#include <memory>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <time.h>
#include <vector>

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

struct Detection {
    int cls;
    float score;
    float x1, y1, x2, y2;  // model 640x640 coordinates
};
Q_DECLARE_METATYPE(Detection)
Q_DECLARE_METATYPE(QVector<Detection>)

struct ModelInfo {
    QString path;
    QStringList classes;
    int nc = 1;
    bool xyxy = false;
    bool lane = false;
};

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
        op.offset_addr = 0;
        op.ddr3_addr = addr;
        op.total_length = 16;
        if (ioctlTmo(F2H_CMD, &op, 3) != 0)
            return false;
        memcpy(&val, rx_, 4);
        return true;
    }

    /* 四路采集线程共用一条 DMA 通道与同一对 tx/rx 缓冲，必须串行化。
       单次等待上限取 2s（与 camview 一致）：丢 MSI 时不能让整块卡住几十秒，
       上层线程会保留上一帧并在下一次帧标签变化时重试。 */
    bool ddrRead(uint32_t addr, uint32_t len, void *out) {
        QMutexLocker dmaLock(&dmaMutex_);
        DmaOp op{};
        op.offset_addr = 0;
        op.ddr3_addr = addr;
        op.total_length = len;
        if (ioctlTmo(F2H_CMD, &op, 2) != 0)
            return false;
        memcpy(out, rx_, len);
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

    const char *lastErr() const { return err_; }

private:
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
            return -1;
        }
        return r;
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
    /* 选中用于推理的那一路（-1 = 不提交）；提交在本线程内完成，避免额外拷贝与锁竞争 */
    void setInferPane(const std::atomic<int> *pane, std::function<void(QImage)> emitFn) {
        inferPane_ = pane;
        emitInfer_ = std::move(emitFn);
    }
    /* 当前显示模式（0..5 = 单路，CAM_COUNT = 整幅）：单路时只采那一路，其余停采 */
    void setModePtr(const std::atomic<int> *mode) { mode_ = mode; }

protected:
    void run() override {
        static const uint32_t base[CAM_COUNT][2] = {
            {CAM_BASE[0][0], CAM_BASE[0][1]}, {CAM_BASE[1][0], CAM_BASE[1][1]},
            {CAM_BASE[2][0], CAM_BASE[2][1]}, {CAM_BASE[3][0], CAM_BASE[3][1]},
            {CAM_BASE[4][0], CAM_BASE[4][1]}, {CAM_BASE[5][0], CAM_BASE[5][1]}};
        const int idx = camera_ - 1;
        const uint32_t ta = base[idx][0] + FRAME_BYTES;
        const uint32_t tb = base[idx][1] + FRAME_BYTES;
        uint32_t a = 0, b = 0, la = 0, lb = 0;
        bool primed = false;
        QByteArray frame(FRAME_BYTES, 0);
        QElapsedTimer fpsTimer;
        int fpsFrames = 0;
        while (running_) {
            /* 设备模式：整幅时六路全采；单选时只采那一路（其余不发 DMA、不轮询标签） */
            if (mode_) {
                const int mode = mode_->load();
                if (mode != CAM_COUNT && mode != idx) {
                    msleep(50);
                    continue;
                }
            }
            if (!dev_->readTag(ta, a) || !dev_->readTag(tb, b)) { msleep(20); continue; }
            if (!primed) { la = a; lb = b; primed = true; msleep(20); continue; }
            const int which = (a != la) ? 0 : ((b != lb) ? 1 : -1);
            if (which < 0) { msleep(20); continue; }
            la = a; lb = b;
            if (!dev_->ddrRead(base[idx][which], FRAME_BYTES, frame.data())) {
                { QMutexLocker lock(&frames_->mutex); ++frames_->errors[idx]; }
                msleep(25);
                continue;
            }
            /* 若本路正是推理用路：就地转成 640x640 并提交（不额外拷贝、不占锁） */
            if (inferPane_ && inferPane_->load() == idx && emitInfer_) {
                QImage infer(MODEL_W, MODEL_H, QImage::Format_RGB888);
                memset(infer.bits(), 114, (size_t)MODEL_W * MODEL_H * 3);
                const uint16_t *src = reinterpret_cast<const uint16_t *>(frame.constData());
                for (int y = 0; y < IMG_H; ++y)
                    rgb565ToRgb888Line(reinterpret_cast<const uint8_t *>(src + (size_t)y * IMG_W),
                                       IMG_W, infer.bits() + (size_t)(y + 80) * MODEL_W * 3);
                emitInfer_(infer);
            }
            QMutexLocker lock(&frames_->mutex);
            frames_->c[idx] = frame;
            frames_->have[idx] = true;
            ++frames_->gen;
            ++frames_->camGen[idx];
            if (!fpsTimer.isValid()) fpsTimer.start();
            ++fpsFrames;
            if (fpsTimer.elapsed() >= 500) {
                frames_->fps[idx] = fpsFrames * 1000.0 / fpsTimer.elapsed();
                fpsFrames = 0;
                fpsTimer.restart();
            }
            lock.unlock();
            /* 传感器约 22–30fps（33–45ms/帧）。标签轮询是 16 字节的小 PCIe 事务，
               六个线程共用一条 DMA，轮询越密越容易互相排队，20ms 一档足够不漏帧。 */
            msleep(20);
        }
    }

private:
    PangoDev *dev_;
    LatestFrames *frames_;
    int camera_;
    std::atomic_bool running_{true};
    const std::atomic<int> *inferPane_ = nullptr;
    const std::atomic<int> *mode_ = nullptr;
    std::function<void(QImage)> emitInfer_;
};

class CameraThread : public QThread {
    Q_OBJECT
public:
    void stop() { m_stop = true; }
    void setMode(int mode) { m_mode = mode; }
    void setPaused(bool paused) { m_paused = paused; }
    void setVideoSource(const QString &source) { m_videoSource = source; }
    /* 控件尺寸：相机线程据此决定 RGA 缩放目标（letterbox 后的内容尺寸） */
    void setDisplaySize(int w, int h) { m_dispW = w; m_dispH = h; }

signals:
    /* 四路：已按控件尺寸缩放好的内容帧（RGB888）；ox>=0 表示直接在 (ox,oy) 1:1 贴图，
       ox<0 表示未缩放、由控件自行缩放铺满。paneMask/pane 同前 */
    void frameReady(QImage content, int ox, int oy, int paneMask, int pane, double fps);
    /* 视频源路径：单路 RGB888 帧 */
    void imageReady(QImage frame, double fps);
    /* 推理输入（640x640 letterbox RGB888） */
    void inferReady(QImage infer);
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
        for (CameraWorker &w : workers)
            w.start();
        /* 推理提交交给“选中那一路”的采集线程：它手里就有刚读到的帧，
           省掉一次 0.6MB 拷贝与锁竞争（原独立提交线程实测每轮要等帧 4–12ms）。 */
        std::atomic<int> inferPane{m_mode.load() == CAM_COUNT ? 0 : m_mode.load()};
        for (CameraWorker &w : workers) {
            w.setInferPane(&inferPane, [this](QImage img) { emit inferReady(img); });
            w.setModePtr(&m_mode);
        }
        emit statusMsg("Six-camera DMA ready; 3x2 view, inference uses the selected pane");
        /* 合成缓冲：RGB888 1920x960（3x2）。优先放 dma-heap：RGA 只能读 dma-buf，
           缩放交给硬件（同尺寸 Qt 缩放要 31ms，RGA 实测 5ms 且不占 CPU）。 */
        const int compW = GRID_COLS * IMG_W, compH = GRID_ROWS * IMG_H;
        const int compStride = compW * 3;
        const size_t compBytes = (size_t)compStride * compH;
        DmaBuffer compDma[2], cropDma, outDma[2];
        const bool rgaOk = compDma[0].alloc(compBytes) && compDma[1].alloc(compBytes) &&
                           cropDma.alloc((size_t)IMG_W * IMG_H * 3);
        QByteArray compFallback[2];
        uint8_t *compPtr[2] = {nullptr, nullptr};
        if (rgaOk) {
            compPtr[0] = reinterpret_cast<uint8_t *>(compDma[0].p);
            compPtr[1] = reinterpret_cast<uint8_t *>(compDma[1].p);
        } else {
            emit statusMsg("WARN: dma-heap unavailable, 显示退回 CPU 缩放");
            for (int i = 0; i < 2; i++) {
                compFallback[i].resize(compBytes);
                compPtr[i] = reinterpret_cast<uint8_t *>(compFallback[i].data());
            }
        }
        int compSlot = 0;
        int outW = 0, outH = 0, outStride = 0, outSlot = 0;
        QByteArray cam565[CAM_COUNT];
        for (QByteArray &s : cam565)
            s.resize(FRAME_BYTES);
        uint64_t lastCamGen[CAM_COUNT] = {};
        // 显示节流：与 camview 相同的 33ms 上限（0 = 不限速），可用环境变量覆盖
        const int minIntervalMs = qEnvironmentVariableIsSet("DETVIEW_MIN_MS")
                                      ? qEnvironmentVariableIntValue("DETVIEW_MIN_MS") : 33;
        uint64_t lastGen = 0;
        QElapsedTimer rate; rate.start();
        int frames = 0;
        double fps = 0;
        while (!m_stop) {
            if (m_paused) { msleep(25); continue; }
            bool ready = false;
            uint64_t gen = 0;
            uint64_t camGen[CAM_COUNT] = {};
            uint64_t errors[CAM_COUNT] = {};
            bool have[CAM_COUNT] = {};
            double camFps[CAM_COUNT] = {};
            {
                QMutexLocker lock(&latest.mutex);
                for (int i = 0; i < CAM_COUNT; i++)
                    ready = ready || latest.have[i];
                gen = latest.gen;
                for (int i = 0; i < CAM_COUNT; i++) {
                    have[i] = latest.have[i];
                    errors[i] = latest.errors[i];
                    camFps[i] = latest.fps[i];
                    camGen[i] = latest.camGen[i];
                }
                /* 帧数据在锁内拷到复用缓冲：既避免与采集线程竞争，也不产生每帧分配 */
                for (int i = 0; i < CAM_COUNT; i++) {
                    if (!have[i])
                        continue;
                    if (lastCamGen[i] != 0 && camGen[i] == lastCamGen[i])
                        continue;
                    if (latest.c[i].size() == FRAME_BYTES)
                        memcpy(cam565[i].data(), latest.c[i].constData(), FRAME_BYTES);
                }
            }
            if (!ready) { msleep(2); continue; }

            const int mode = m_mode.load();
            const int pane = mode == CAM_COUNT ? 0 : mode;      // 整幅时用 C1 推理
            const int paneMask = mode == CAM_COUNT ? 0x3F : (1 << pane);
            inferPane.store(pane);   // 提交线程据此切换要提交的那一路

            if (gen == lastGen) { msleep(2); continue; }   // 没有新帧就不重合成
            lastGen = gen;

            compSlot ^= 1;
            uint8_t *comp = compPtr[compSlot];
            /* 只把有新帧的那几路转成 RGB888 写进合成缓冲的对应格子（零分配、按 stride 写） */
            for (int c = 0; c < CAM_COUNT; ++c) {
                const bool firstFrame = (lastCamGen[c] == 0);
                if (!firstFrame && camGen[c] == lastCamGen[c])
                    continue;
                if (!have[c])
                    continue;
                lastCamGen[c] = camGen[c];
                uint8_t *dst = comp + (size_t)(c / GRID_COLS) * IMG_H * compStride +
                               (size_t)(c % GRID_COLS) * IMG_W * 3;
                const uint16_t *src = reinterpret_cast<const uint16_t *>(cam565[c].constData());
                for (int y = 0; y < IMG_H; ++y)
                    rgb565ToRgb888Line(reinterpret_cast<const uint8_t *>(src + (size_t)y * IMG_W),
                                       IMG_W, dst + (size_t)y * compStride);
            }

            ++frames;
            if (rate.elapsed() >= 1000) {
                fps = frames * 1000.0 / rate.elapsed();
                frames = 0;
                rate.restart();
                fprintf(stderr,
                        "[panes] mode=%d fps=%.1f have=%d%d%d%d%d%d cam=%.1f/%.1f/%.1f/%.1f/%.1f/%.1f err=%llu/%llu/%llu/%llu/%llu/%llu rga=%d\n",
                        mode, fps, have[0], have[1], have[2], have[3], have[4], have[5], camFps[0],
                        camFps[1], camFps[2], camFps[3], camFps[4], camFps[5],
                        (unsigned long long)errors[0], (unsigned long long)errors[1],
                        (unsigned long long)errors[2], (unsigned long long)errors[3],
                        (unsigned long long)errors[4], (unsigned long long)errors[5], rgaOk ? 1 : 0);
            }
            /* 缩放：RGA 把合成（或单选的那一格）缩到控件里的内容尺寸，控件只做 1:1 贴图 */
            bool scaled = false;
            if (rgaOk) {
                const int dispW = qMax(1, m_dispW.load()), dispH = qMax(1, m_dispH.load());
                const int srcW = (paneMask == 0x3F) ? compW : IMG_W;
                const int srcH = (paneMask == 0x3F) ? compH : IMG_H;
                int tw = dispW, th = (int)((int64_t)dispW * srcH / srcW);
                if (th > dispH) {
                    th = dispH;
                    tw = (int)((int64_t)dispH * srcW / srcH);
                }
                const int alignedW = (tw + 3) & ~3;
                if (tw > 0 && th > 0 && outDma[0].ensure((size_t)alignedW * th * 3) &&
                    outDma[1].ensure((size_t)alignedW * th * 3)) {
                    outW = tw;
                    outH = th;
                    outStride = alignedW * 3;
                    rga_buffer_t dstRga =
                        wrapbuffer_fd(outDma[outSlot].fd, alignedW, th, RK_FORMAT_RGB_888);
                    IM_STATUS st = IM_STATUS_FAILED;
                    if (paneMask == 0x3F) {
                        rga_buffer_t srcRga =
                            wrapbuffer_fd(compDma[compSlot].fd, compW, compH, RK_FORMAT_RGB_888);
                        st = imresize(srcRga, dstRga);
                    } else {
                        im_rect srect{(pane % GRID_COLS) * IMG_W, (pane / GRID_COLS) * IMG_H, IMG_W,
                                      IMG_H};
                        rga_buffer_t whole =
                            wrapbuffer_fd(compDma[compSlot].fd, compW, compH, RK_FORMAT_RGB_888);
                        rga_buffer_t cropRga =
                            wrapbuffer_fd(cropDma.fd, IMG_W, IMG_H, RK_FORMAT_RGB_888);
                        st = imcrop(whole, cropRga, srect);
                        if (st == IM_STATUS_SUCCESS)
                            st = imresize(cropRga, dstRga);
                    }
                    if (st == IM_STATUS_SUCCESS) {
                        const QImage outImg(reinterpret_cast<const uchar *>(outDma[outSlot].p), outW,
                                            outH, outStride, QImage::Format_RGB888);
                        emit frameReady(outImg, (dispW - outW) / 2, (dispH - outH) / 2, paneMask,
                                        pane, fps);
                        outSlot ^= 1;
                        scaled = true;
                    }
                }
            }
            if (!scaled) {
                /* 兜底：交给控件用 Qt 缩放铺满（RGA 不可用或失败时） */
                const QImage compImg(reinterpret_cast<const uchar *>(comp), compW, compH,
                                     compStride, QImage::Format_RGB888);
                emit frameReady(compImg, -1, -1, paneMask, pane, fps);
            }
            if (minIntervalMs > 0) msleep(minIntervalMs);
        }
        for (CameraWorker &w : workers)
            w.stop();
        for (CameraWorker &w : workers)
            w.wait(3000);
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
        QElapsedTimer rate;
        rate.start();
        int frames = 0;
        double fps = 0;
        while (!m_stop) {
            while (frame.size() < bytes && decoder.state() != QProcess::NotRunning && !m_stop) {
                if (decoder.bytesAvailable() == 0 && !decoder.waitForReadyRead(200)) continue;
                frame += decoder.read(bytes - frame.size());
            }
            if (frame.size() != bytes) break;
            QImage rgb(reinterpret_cast<const uchar *>(frame.constData()),
                       IMG_W, IMG_H, IMG_W * 3, QImage::Format_RGB888);
            QImage infer(MODEL_W, MODEL_H, QImage::Format_RGB888);
            infer.fill(QColor(114, 114, 114));
            QPainter inputPainter(&infer);
            inputPainter.drawImage(0, 80, rgb);
            inputPainter.end();
            if (++frames >= 30) {
                fps = frames * 1000.0 / rate.elapsed();
                frames = 0; rate.restart();
                fprintf(stderr, "[video] fps=%.1f\n", fps);
            }
            // rgb 只是包装解码缓冲，跨线程投递前必须深拷贝
            emit imageReady(rgb.copy(), fps);
            emit inferReady(infer);
            frame.clear();
            while (m_paused && !m_stop) msleep(25);
        }
        decoder.kill();
        decoder.waitForFinished(2000);
        emit statusMsg("视频源结束");
    }
    std::atomic<bool> m_stop{false};
    std::atomic<int> m_mode{CAM_COUNT};
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

    void submit(const QImage &img, int sourceGeneration = 0) {
        QMutexLocker lock(&m_mutex);
        m_pending = img;
        m_pendingGeneration = sourceGeneration;
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
    void detectionsReady(QString modelPath, int sourceGeneration, QVector<Detection> dets,
                         double inferFps, double inferMs);
    void laneMaskReady(QImage mask, double inferFps, double inferMs);
    void modelLoaded(QString path, bool ok, QString info);

protected:
    void run() override {
        struct CachedModel {
            ModelInfo info;
            QByteArray bytes;
            rknn_context context = 0;
            uint32_t outputs = 0;
        };
        QVector<CachedModel> cache;
        int next = 0;
        /* 诊断（DET_BENCH）：每秒统计“等帧时间”与“单次运行时间”，判断推理线程是否被饿着 */
        const bool diag = qEnvironmentVariableIsSet("DET_BENCH");
        QElapsedTimer diagTimer;
        if (diag)
            diagTimer.start();
        double diagWaitMs = 0, diagRunMs = 0;
        int diagRuns = 0;
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
            int sourceGeneration = m_pendingGeneration;
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
                        ioNum.n_input != 1 || (info.lane && ioNum.n_output != 1)) {
                        rknn_destroy(item.context);
                        emit modelLoaded(info.path, false, "unsupported input/output count");
                        continue;
                    }
                    item.outputs = ioNum.n_output;
                    cache.append(std::move(item));
                    emit modelLoaded(info.path, true, QString("%1 outputs cached").arg(ioNum.n_output));
                }
            }
            if (!frame.isNull() && !cache.isEmpty()) {
                CachedModel &item = cache[next];
                next = (next + 1) % cache.size();
                m_ctx = item.context;
                m_nOutput = item.outputs;
                m_nc = item.info.nc;
                m_xyxy = cache.size() == 1 ? m_manualFormat.load() : item.info.xyxy;
                m_lane = item.info.lane;
                const qint64 runStart = diag ? QDateTime::currentMSecsSinceEpoch() : 0;
                runOnce(frame, item.info.path, sourceGeneration);
                if (diag) {
                    diagRunMs += QDateTime::currentMSecsSinceEpoch() - runStart;
                    ++diagRuns;
                }
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
    void runOnce(const QImage &src, const QString &modelPath, int sourceGeneration) {
        if (m_input.size() != (int)MODEL_SIZE)
            m_input.resize((int)MODEL_SIZE);
        if (src.width() == MODEL_W && src.height() == MODEL_H) {
            // 相机线程已用 RGA 完成 letterbox（640x640 RGB888），直接拷贝
            const QImage rgb = src.format() == QImage::Format_RGB888
                                   ? src
                                   : src.convertToFormat(QImage::Format_RGB888);
            if (rgb.bytesPerLine() == MODEL_W * 3)
                memcpy(m_input.data(), rgb.constBits(), MODEL_SIZE);
            else
                for (int y = 0; y < MODEL_H; y++)
                    memcpy(m_input.data() + y * MODEL_W * 3,
                           rgb.constBits() + (size_t)y * rgb.bytesPerLine(), MODEL_W * 3);
        } else {
            const QImage rgb = src.convertToFormat(QImage::Format_RGB888);
            // letterbox 640x480 -> 640x640 (vertical pad, gray 114)
            memset(m_input.data(), 114, 80 * MODEL_W * 3);
            const int copyBytes = IMG_W * 3;
            const uint8_t *sp = rgb.constBits();
            uint8_t *dp = (uint8_t *)m_input.data() + 80 * copyBytes;
            for (int y = 0; y < IMG_H; y++)
                memcpy(dp + y * copyBytes, sp + y * IMG_W * 3, copyBytes);
            memset((uint8_t *)m_input.data() + (80 + IMG_H) * copyBytes, 114,
                   (MODEL_H - 80 - IMG_H) * copyBytes);
        }

        rknn_input input;
        memset(&input, 0, sizeof(input));
        input.index = 0;
        input.buf = (void *)m_input.constData();
        input.size = (uint32_t)MODEL_SIZE;
        input.type = RKNN_TENSOR_UINT8;
        input.fmt = RKNN_TENSOR_NHWC;
        QElapsedTimer timer;
        timer.start();
        if (rknn_inputs_set(m_ctx, 1, &input) != 0)
            return;
        if (rknn_run(m_ctx, nullptr) != 0)
            return;
        std::vector<rknn_output> outs(m_nOutput);
        for (uint32_t i = 0; i < m_nOutput; i++) {
            memset(&outs[i], 0, sizeof(rknn_output));
            outs[i].index = i;
            outs[i].want_float = 1;
        }
        if (rknn_outputs_get(m_ctx, m_nOutput, outs.data(), nullptr) != 0)
            return;
        std::vector<rknn_tensor_attr> attrs(m_nOutput);
        for (uint32_t i = 0; i < m_nOutput; i++) {
            memset(&attrs[i], 0, sizeof(rknn_tensor_attr));
            attrs[i].index = i;
            rknn_query(m_ctx, RKNN_QUERY_OUTPUT_ATTR, &attrs[i], sizeof(rknn_tensor_attr));
        }
        QImage laneMask;
        QVector<Detection> dets;
        if (m_lane)
            laneMask = decodeLaneMask(outs[0], attrs[0], m_nc);
        else
            dets = decode(outs, attrs);
        rknn_outputs_release(m_ctx, m_nOutput, outs.data());
        const double ms = timer.elapsed();
        const int completed = ++m_completed[modelPath];
        if (qEnvironmentVariableIsSet("DET_BENCH")) {
            timespec stamp{};
            clock_gettime(CLOCK_MONOTONIC, &stamp);
            fprintf(stderr, "[tdm_bench] t=%.6f model=%s ms=%.3f\n",
                    stamp.tv_sec + stamp.tv_nsec / 1e9, qPrintable(modelPath), ms);
        }
        if (completed == 1 || completed % 20 == 0)
            fprintf(stderr, "[tdm] model=%s completed=%d ms=%.2f source_generation=%d\n",
                    qPrintable(modelPath), completed, ms, sourceGeneration);
        m_accMs += ms;
        m_accCount++;
        if (m_accCount >= 10) {
            m_inferMs = m_accMs / m_accCount;
            m_inferFps = m_inferMs > 0 ? 1000.0 / m_inferMs : 0.0;
            m_accMs = 0;
            m_accCount = 0;
        }
        if (m_lane) {
            if (!laneMask.isNull())
                emit laneMaskReady(laneMask, m_inferFps, m_inferMs);
        } else {
            emit detectionsReady(modelPath, sourceGeneration, dets, ms > 0 ? 1000.0 / ms : 0.0, ms);
        }
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
    double m_inferFps = 0, m_inferMs = 0, m_accMs = 0;
    int m_accCount = 0;
};

/* ---------------- 显示（纯 CPU 绘制，不依赖 GL / 合成器） ----------------
   板端没有合成器在跑（_NET_WM_CM_S0 不存在）：QOpenGLWidget 与“顶层 GL 窗口 +
   createWindowContainer”都会出现陈旧区域与双份绘制（画面闪、留残影）。因此显示改成
   普通 QWidget：相机线程给出 RGB888 的 2x2 合成（缓冲复用、QImage 只包装不拷贝），
   本控件每帧只做一次缩放 drawImage，检测框与车道掩码在同一个 paintEvent 里叠加。
   单路显示时从合成里取那一格的源矩形，铺满内容区。 */
class VideoWidget : public QWidget {
    Q_OBJECT
public:
    explicit VideoWidget(QWidget *parent = nullptr) : QWidget(parent) {
        setMinimumSize(640, 480);
        setAutoFillBackground(true);
        setAttribute(Qt::WA_OpaquePaintEvent, true);
        QPalette pal = palette();
        pal.setColor(QPalette::Window, Qt::black);
        setPalette(pal);
    }

    int takePaintCount() { return m_paintCount; }
    double takePaintAvgMs() {
        double v = m_paintCount ? m_paintMsSum / m_paintCount : 0.0;
        m_paintCount = 0;
        m_paintMsSum = 0;
        return v;
    }

    /* 六路：content 可能是 RGA 已缩放好的内容（ox>=0 → 在 (ox,oy) 1:1 贴图），
       也可能是未缩放的 3x2 合成（ox<0 → 由本控件缩放铺满） */
    void submitScaled(const QImage &content, int ox, int oy, int paneMask, int pane) {
        m_comp = content;
        m_ox = ox;
        m_oy = oy;
        m_paneMask = paneMask;
        m_pane = pane;
        m_videoMode = false;
        update();
    }
    /* 视频源路径：单路 RGB888 帧 */
    void submitImage(const QImage &img) {
        m_image = img.format() == QImage::Format_RGB888 ? img
                                                        : img.convertToFormat(QImage::Format_RGB888);
        m_videoMode = true;
        m_paneMask = 0x1;
        m_pane = 0;
        update();
    }
    void setDetections(const QVector<Detection> &dets, const QStringList &classes) {
        m_dets = dets;
        m_classes = classes;
        update();
    }
    void setLaneMask(const QImage &mask) {
        m_laneMask = mask;
        update();
    }

protected:
    void paintEvent(QPaintEvent *) override {
        QElapsedTimer pt;
        pt.start();
        QPainter p(this);
        if (qEnvironmentVariableIsSet("DETVIEW_GEO")) {
            static QElapsedTimer geo;
            if (!geo.isValid() || geo.elapsed() >= 1000) {
                geo.start();
                const QScreen *scr = QGuiApplication::primaryScreen();
                const QSize screen = scr ? scr->geometry().size() : QSize();
                fprintf(stderr, "[geo] win=%dx%d dpr=%.2f screen=%dx%d\n", width(), height(),
                        (double)devicePixelRatioF(), screen.width(), screen.height());
                fflush(stderr);
            }
        }
        const QImage &src = m_videoMode ? m_image : m_comp;
        if (src.isNull()) {
            p.fillRect(rect(), Qt::black);
            m_paintMsSum += pt.nsecsElapsed() / 1e6;
            m_paintCount++;
            return;
        }
        QRect content;
        if (!m_videoMode && m_ox >= 0) {
            /* RGA 已缩放到内容尺寸，直接 1:1 贴图（缩放不占 CPU） */
            content = QRect(m_ox, m_oy, src.width(), src.height());
            p.fillRect(rect(), Qt::black);
            p.drawImage(m_ox, m_oy, src);
        } else {
            /* 兜底（dma-heap/RGA 不可用）或视频源：等比缩放铺满控件 */
            const double dispAspect = (!m_videoMode && m_paneMask != 0x3F)
                                          ? (double)IMG_W / IMG_H
                                          : (double)src.width() / src.height();
            int tw = width();
            int th = (int)(width() / dispAspect);
            if (th > height()) {
                th = height();
                tw = (int)(height() * dispAspect);
            }
            content = QRect((width() - tw) / 2, (height() - th) / 2, tw, th);
            p.fillRect(rect(), Qt::black);
            if (!m_videoMode && m_paneMask != 0x3F) {
                const QRect source((m_pane % GRID_COLS) * IMG_W, (m_pane / GRID_COLS) * IMG_H, IMG_W,
                                   IMG_H);
                p.drawImage(content, src, source);
            } else {
                p.drawImage(content, src);
            }
        }
        QRect pane = content;
        if (!m_videoMode && m_paneMask == 0x3F) {
            const int pw = content.width() / GRID_COLS, ph = content.height() / GRID_ROWS;
            pane = QRect(content.left() + (m_pane % GRID_COLS) * pw,
                         content.top() + (m_pane / GRID_COLS) * ph, pw, ph);
        }
        /* 覆盖层：车道掩码 + 检测框；模型输入是 640x640，画面贴在 y=80..560 */
        const double sx = pane.width() / (double)MODEL_W;
        const double sy = pane.height() / (double)IMG_H;
        const double baseX = pane.left();
        const double baseY = pane.top() - 80.0 * sy;
        if (!m_laneMask.isNull())
            p.drawImage(QRectF(baseX, baseY, MODEL_W * sx, MODEL_H * sy), m_laneMask);
        p.setClipRect(pane);
        for (const Detection &d : m_dets) {
            const double x1 = baseX + d.x1 * sx;
            const double x2 = baseX + d.x2 * sx;
            const double y1 = baseY + d.y1 * sy;
            const double y2 = baseY + d.y2 * sy;
            const QRectF r(x1, y1, std::max(1.0, x2 - x1), std::max(1.0, y2 - y1));
            const QColor color = d.cls == 0 ? QColor(0, 255, 0)
                                : (d.cls == 1 ? QColor(255, 60, 60) : QColor(255, 220, 0));
            p.setPen(QPen(color, 3));
            p.drawRect(r);
            const QString label =
                QString("%1 %2")
                    .arg(d.cls >= 0 && d.cls < m_classes.size() ? m_classes[d.cls]
                                                                : QString::number(d.cls))
                    .arg(d.score, 0, 'f', 2);
            p.setPen(Qt::black);
            p.drawText(QPointF(r.left() + 4, r.top() + 12), label);
            p.setPen(color);
            p.drawText(QPointF(r.left() + 3, r.top() + 11), label);
        }
        p.setClipping(false);
        m_paintMsSum += pt.nsecsElapsed() / 1e6;
        m_paintCount++;
    }

private:
    QImage m_comp;      // 2x2 合成（RGB888 1280x960，仅包装相机线程的复用缓冲）
    QImage m_image;     // 视频源路径
    QImage m_laneMask;
    QVector<Detection> m_dets;
    QStringList m_classes;
    bool m_videoMode = false;
    int m_paneMask = 0x3F, m_pane = 0;
    int m_ox = -1, m_oy = -1;
    int m_paintCount = 0;
    double m_paintMsSum = 0;
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

class MainWindow : public QWidget {
    Q_OBJECT
public:
    MainWindow(const QVector<ModelInfo> &models, const QString &videoSource = {}) : m_models(models) {
        auto *root = new QVBoxLayout(this);
        auto *bar = new QHBoxLayout();
        m_combo = new QComboBox(this);
        for (int i = 0; i < models.size(); i++)
            m_combo->addItem(QFileInfo(models[i].path).fileName(), i);
        m_pickBtn = new QPushButton("选择轮换模型", this);
        m_pickMenu = new QMenu(m_pickBtn);
        for (int i = 0; i < models.size(); ++i) {
            if (models[i].lane || !QFileInfo(models[i].path).fileName().startsWith("det-"))
                continue;
            QAction *action = m_pickMenu->addAction(QFileInfo(models[i].path).fileName());
            action->setCheckable(true);
            action->setData(i);
        }
        m_pickBtn->setMenu(m_pickMenu);
        m_rotateBtn = new QPushButton("轮换", this);
        m_rotateBtn->setCheckable(true);
        m_camLabel = new QLabel("cam: -- fps", this);
        m_camLabel->setMinimumWidth(110);
        m_inferLabel = new QLabel("infer: -- ms / -- fps   dets: --", this);
        m_inferLabel->setMinimumWidth(250);
        m_fmtCombo = new QComboBox(this);
        m_fmtCombo->addItem("cxcywh");
        m_fmtCombo->addItem("xyxy");
        m_camCombo = new QComboBox(this);
        m_camCombo->addItem("C1");
        m_camCombo->addItem("C2");
        m_camCombo->addItem("C3");
        m_camCombo->addItem("C4");
        m_camCombo->addItem("C5");
        m_camCombo->addItem("C6");
        m_camCombo->addItem("6 路 3x2 (infer C1)");
        m_camCombo->setCurrentIndex(CAM_COUNT);
        m_confSlider = new QSlider(Qt::Horizontal, this);
        m_confSlider->setRange(5, 95);
        m_confSlider->setValue(25);
        m_confSlider->setFixedWidth(150);
        m_confSlider->setToolTip("置信度阈值");
        m_confLabel = new QLabel("Conf 0.25", this);
        m_shotBtn = new QPushButton("截屏", this);
        bar->addWidget(new QLabel("Model:", this));
        bar->addWidget(m_combo, 1);
        bar->addWidget(m_pickBtn);
        bar->addWidget(m_rotateBtn);
        bar->addWidget(new QLabel("Box:", this));
        bar->addWidget(m_fmtCombo);
        bar->addWidget(new QLabel("Cam:", this));
        bar->addWidget(m_camCombo);
        bar->addWidget(m_confLabel);
        bar->addWidget(m_confSlider);
        bar->addWidget(m_camLabel);
        bar->addWidget(m_inferLabel);
        bar->addWidget(m_shotBtn);
        root->addLayout(bar);
        m_video = new VideoWidget(this);
        root->addWidget(m_video, 1);
        m_status = new QLabel("starting...", this);
        m_status->setWordWrap(true);
        root->addWidget(m_status);
        m_helpLabel = new QLabel(
            "快捷键:  1-9 切换模型 | C 切换框格式(cxcywh/xyxy) | V 切换相机(C1..C6 / 6 路 3x2) | "
            "+/- 置信度 | S 截屏 | P/空格 暂停 | F 全屏 | H 帮助 | Q/Esc 退出",
            this);
        m_helpLabel->setStyleSheet("background:#111; color:#0f0; font:13px monospace; padding:4px;");
        m_helpLabel->setWordWrap(true);
        m_helpLabel->setVisible(false);
        root->addWidget(m_helpLabel);
        setFocusPolicy(Qt::StrongFocus);

        m_camera = new CameraThread();
        if (!videoSource.isEmpty()) {
            m_camera->setVideoSource(videoSource);
            m_camCombo->setCurrentIndex(0);
            m_camCombo->setEnabled(false);
        }
        m_infer = new InferenceThread();
        connect(m_camera, &CameraThread::frameReady, this, &MainWindow::onFrame);
        connect(m_camera, &CameraThread::imageReady, this, &MainWindow::onImage);
        connect(m_camera, &CameraThread::inferReady, this, &MainWindow::onInfer);
        connect(m_camera, &CameraThread::statusMsg, this, [this](QString s) {
            m_status->setText(s);
        });
        connect(m_infer, &InferenceThread::detectionsReady, this, &MainWindow::onDets);
        connect(m_infer, &InferenceThread::laneMaskReady, this, &MainWindow::onLaneMask);
        connect(m_infer, &InferenceThread::modelLoaded, this, &MainWindow::onModelLoaded);
        connect(m_combo, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
                &MainWindow::onModelChanged);
        connect(m_rotateBtn, &QPushButton::clicked, this, &MainWindow::onRotateClicked);
        connect(m_camCombo, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
                &MainWindow::onCamChanged);
        connect(m_fmtCombo, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
                &MainWindow::onFormatChanged);
        connect(m_confSlider, &QSlider::valueChanged, this, &MainWindow::onConfChanged);
        connect(m_shotBtn, &QPushButton::clicked, this, &MainWindow::onScreenshot);
        m_statsTimer.start();
        m_camLabelTimer.start();
        m_inferLabelTimer.start();
        m_infer->start();
        m_camera->start();
        auto *expiryTimer = new QTimer(this);
        connect(expiryTimer, &QTimer::timeout, this, [this]() {
            if (m_rotationEnabled) updateRotationOverlay();
        });
        expiryTimer->start(250);
        if (!models.isEmpty())
            onModelChanged(0);
        setWindowTitle("detview - OV5640 + RKNN");
        resize(1280, 800);
    }
    ~MainWindow() override {
        m_camera->stop();
        m_camera->wait();
        m_infer->stop();
    }

    void setModelIndex(int index) {
        if (index >= 0 && index < m_models.size())
            m_combo->setCurrentIndex(index);
    }
    void setFullscreen(bool on) {
        m_full = on;
        on ? showFullScreen() : showNormal();
    }
    /* 0..5 = C1..C6 单路，CAM_COUNT = 6 路 3x2 */
    void setCameraMode(int mode) {
        if (mode >= 0 && mode <= CAM_COUNT)
            m_camCombo->setCurrentIndex(mode);
    }
    bool setRotation(const QStringList &selectors) {
        if (selectors.size() < 2 || selectors.size() > 4)
            return false;
        QVector<int> indices;
        for (const QString &selector : selectors) {
            if (selector.trimmed().isEmpty()) return false;
            int matched = -1;
            for (QAction *action : m_pickMenu->actions()) {
                const int index = action->data().toInt();
                if (!m_models[index].path.contains(selector.trimmed(), Qt::CaseInsensitive))
                    continue;
                if (matched >= 0) return false;
                matched = index;
            }
            if (matched < 0 || indices.contains(matched)) return false;
            indices.append(matched);
        }
        for (QAction *action : m_pickMenu->actions()) {
            action->setChecked(indices.contains(action->data().toInt()));
        }
        onRotateClicked(true);
        return m_rotationEnabled;
    }

protected:
    void keyPressEvent(QKeyEvent *e) override {
        const int k = e->key();
        if (k >= Qt::Key_1 && k <= Qt::Key_9) {
            const int idx = k - Qt::Key_1;
            if (idx < m_models.size())
                m_combo->setCurrentIndex(idx);
            return;
        }
        switch (k) {
        case Qt::Key_Q:
        case Qt::Key_Escape:
            close();
            break;
        case Qt::Key_F:
            m_full = !m_full;
            m_full ? showFullScreen() : showNormal();
            break;
        case Qt::Key_S:
            onScreenshot();
            break;
        case Qt::Key_C:
            m_fmtCombo->setCurrentIndex((m_fmtCombo->currentIndex() + 1) % 2);
            break;
        case Qt::Key_V:
            m_camCombo->setCurrentIndex((m_camCombo->currentIndex() + 1) % (CAM_COUNT + 1));
            break;
        case Qt::Key_P:
        case Qt::Key_Space:
            m_paused = !m_paused;
            m_camera->setPaused(m_paused);
            m_status->setText(m_paused ? "已暂停 (P/空格 继续)" : "运行中");
            break;
        case Qt::Key_Minus:
        case Qt::Key_Underscore:
            m_confSlider->setValue(std::max(5, m_confSlider->value() - 5));
            break;
        case Qt::Key_Equal:
        case Qt::Key_Plus:
            m_confSlider->setValue(std::min(95, m_confSlider->value() + 5));
            break;
        case Qt::Key_H:
            m_helpLabel->setVisible(!m_helpLabel->isVisible());
            break;
        default:
            QWidget::keyPressEvent(e);
        }
    }

private slots:
    void onFrame(QImage content, int ox, int oy, int paneMask, int pane, double fps) {
        m_camFps = fps;
        m_camera->setDisplaySize(m_video->width(), m_video->height());
        m_video->submitScaled(content, ox, oy, paneMask, pane);
        if (m_camLabelTimer.elapsed() >= 400) {
            m_camLabelTimer.restart();
            m_camLabel->setText(QString("cam: %1 fps").arg(fps, 0, 'f', 1));
        }
    }
    void onImage(QImage frame, double fps) {
        m_camFps = fps;
        m_video->submitImage(frame);
        if (m_camLabelTimer.elapsed() >= 400) {
            m_camLabelTimer.restart();
            m_camLabel->setText(QString("cam: %1 fps").arg(fps, 0, 'f', 1));
        }
    }
    void onInfer(QImage infer) { m_infer->submit(infer, m_sourceGeneration); }
    void onCamChanged(int index) {
        ++m_sourceGeneration;
        m_results.clear();
        m_resultTime.clear();
        m_fpsWindowStart = 0;
        m_fpsWindowTotal = 0;
        m_fpsWindowModel.clear();
        m_rotInferFps = 0;
        m_video->setDetections({}, m_classes);
        m_video->setLaneMask({});
        m_camera->setMode(index);
    }
    void onDets(QString modelPath, int sourceGeneration, QVector<Detection> dets, double fps, double ms) {
        if (sourceGeneration != m_sourceGeneration) return;
        if (m_rotationEnabled) {
            bool chosen = false;
            for (const ModelInfo &model : m_rotation)
                if (model.path == modelPath) chosen = true;
            if (!chosen) return;
            const qint64 now = QDateTime::currentMSecsSinceEpoch();
            /* 帧率按 1 秒窗口计数：GUI 线程绘制时会把排队的完成信号挤在一起处理，
               按相邻时间戳求倒数会算出几百 fps 的假值（实测差 1ms 就是 1000fps）。 */
            if (m_fpsWindowStart == 0)
                m_fpsWindowStart = now;
            ++m_fpsWindowTotal;
            ++m_fpsWindowModel[modelPath];
            if (now - m_fpsWindowStart >= 1000) {
                const double span = (now - m_fpsWindowStart) / 1000.0;
                m_rotInferFps = m_fpsWindowTotal / span;
                for (auto it = m_fpsWindowModel.constBegin(); it != m_fpsWindowModel.constEnd(); ++it)
                    m_resultFps[it.key()] = it.value() / span;
                m_fpsWindowTotal = 0;
                m_fpsWindowModel.clear();
                m_fpsWindowStart = now;
            }
            m_results[modelPath] = dets;
            m_resultTime[modelPath] = now;
            m_resultMs[modelPath] = ms;
            updateRotationOverlay();
        } else {
            const int index = m_combo->currentIndex();
            if (index < 0 || m_models[index].path != modelPath) return;
            m_video->setDetections(dets, m_classes);
        }
        if (m_inferLabelTimer.elapsed() >= 400) {
            m_inferLabelTimer.restart();
            if (m_rotationEnabled) {
                /* 整体吞吐 + 每款模型各自的窗口帧率（名字取短名，完整名字在状态栏） */
                QStringList perModel;
                for (int i = 0; i < m_rotation.size(); ++i)
                    perModel << QString("%1 %2")
                                    .arg(shortModelName(m_rotation[i].path))
                                    .arg(m_resultFps.value(m_rotation[i].path), 0, 'f', 1);
                m_inferLabel->setText(QString("轮换 %1 款 | 整体 %2 fps | %3 fps | 本次 %4 ms | 检测 %5")
                                          .arg(m_rotation.size())
                                          .arg(m_rotInferFps, 0, 'f', 1)
                                          .arg(perModel.join("  "))
                                          .arg(ms, 0, 'f', 1)
                                          .arg(m_visibleDets));
            } else {
                m_inferLabel->setText(QString("infer: %1 ms / %2 fps   dets: %3")
                                          .arg(ms, 0, 'f', 1).arg(fps, 0, 'f', 1).arg(dets.size()));
            }
        }
        if (m_statsTimer.elapsed() >= 5000) {
            m_statsTimer.restart();
            fprintf(stderr, "[stats] cam=%.1ffps infer=%.1fms/%.1ffps dets=%d paints=%d paintAvg=%.2fms\n",
                    m_camFps, ms, fps, dets.size(), m_video->takePaintCount(),
                    m_video->takePaintAvgMs());
            fflush(stderr);
        }
    }
    void onLaneMask(QImage mask, double fps, double ms) {
        m_video->setLaneMask(mask);
        if (m_inferLabelTimer.elapsed() >= 400) {
            m_inferLabelTimer.restart();
            m_inferLabel->setText(QString("infer: %1 ms / %2 fps   lane mask")
                                      .arg(ms, 0, 'f', 1).arg(fps, 0, 'f', 1));
        }
    }
    void onModelLoaded(QString path, bool ok, QString info) {
        fprintf(stderr, "[model] %s %s %s\n", path.toLocal8Bit().constData(),
                ok ? "OK" : "FAIL", info.toLocal8Bit().constData());
        m_status->setText(QString("%1 -> %2  %3")
                              .arg(QFileInfo(path).fileName())
                              .arg(ok ? "OK" : "FAIL")
                              .arg(info));
    }
    void onModelChanged(int index) {
        if (index < 0 || index >= m_models.size())
            return;
        m_rotationEnabled = false;
        m_rotateBtn->setChecked(false);
        m_results.clear();
        m_classes = m_models[index].classes;
        m_video->setDetections({}, m_classes);
        m_video->setLaneMask({});
        m_fmtCombo->blockSignals(true);
        m_fmtCombo->setCurrentIndex(m_models[index].xyxy ? 1 : 0);
        m_fmtCombo->setEnabled(!m_models[index].lane);
        m_fmtCombo->blockSignals(false);
        m_infer->setModel(m_models[index]);
        m_infer->setFormat(m_models[index].xyxy);
        setWindowTitle(QString("detview - %1").arg(QFileInfo(m_models[index].path).fileName()));
    }
    void onRotateClicked(bool enabled) {
        if (!enabled) { onModelChanged(m_combo->currentIndex()); return; }
        m_fpsWindowStart = 0;
        m_fpsWindowTotal = 0;
        m_fpsWindowModel.clear();
        m_rotInferFps = 0;
        QVector<ModelInfo> selected;
        for (QAction *action : m_pickMenu->actions())
            if (action->isChecked()) selected.append(m_models[action->data().toInt()]);
        if (selected.size() < 2 || selected.size() > 4) {
            m_rotateBtn->setChecked(false);
            m_status->setText("请选择 2–4 款 YOLO 检测模型轮换");
            return;
        }
        m_rotation = selected;
        m_rotationEnabled = true;
        m_rotateBtn->setChecked(true);
        m_results.clear();
        m_resultTime.clear();
        m_resultMs.clear();
        m_resultFps.clear();
        m_video->setDetections({}, {});
        m_video->setLaneMask({});
        m_fmtCombo->setEnabled(false);
        m_infer->setModels(selected);
        setWindowTitle(QString("detview - %1 款 YOLO 轮换").arg(selected.size()));
        m_status->setText("加载轮换模型中...");
    }
    void updateRotationOverlay() {
        QVector<Detection> all;
        QStringList labels, summaries;
        const qint64 now = QDateTime::currentMSecsSinceEpoch();
        /* 状态栏：先给整体吞吐，再逐款给出耗时/检测数/该款窗口帧率/结果年龄 */
        summaries.append(QString("整体 %1 fps").arg(m_rotInferFps, 0, 'f', 1));
        for (const ModelInfo &model : m_rotation) {
            const QString name = shortModelName(model.path);
            if (!m_resultTime.contains(model.path) || now - m_resultTime[model.path] > 2000)
                continue;
            const int offset = labels.size();
            for (const QString &cls : model.classes)
                labels.append(QString("%1:%2").arg(name, cls));
            for (Detection det : m_results.value(model.path)) {
                det.cls += offset;
                all.append(det);
            }
            summaries.append(QString("%1 %2ms %3个 %4fps 更新%5ms前")
                .arg(name).arg(m_resultMs.value(model.path), 0, 'f', 0)
                .arg(m_results.value(model.path).size()).arg(m_resultFps.value(model.path), 0, 'f', 1)
                .arg(now - m_resultTime[model.path]));
        }
        m_visibleDets = all.size();
        m_video->setDetections(all, labels);
        m_status->setText(summaries.join(" | "));
    }
    void onFormatChanged(int index) { m_infer->setFormat(index == 1); }
    void onConfChanged(int value) {
        m_confLabel->setText(QString("Conf %1").arg(value / 100.0, 0, 'f', 2));
        m_infer->setConf(value / 100.0f);
    }
    void onScreenshot() {
        const QPixmap pm = m_video->grab();
        if (pm.isNull()) {
            m_status->setText("截屏失败: 无画面");
            return;
        }
        const QString dir = "/userdata/detview_shots";
        QDir().mkpath(dir);
        const QString model = m_combo->currentIndex() >= 0 && m_combo->currentIndex() < m_models.size()
                                  ? QFileInfo(m_models[m_combo->currentIndex()].path).completeBaseName()
                                  : QString("model");
        const QString ts = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
        QString path = QString("%1/shot_%2_%3.png").arg(dir).arg(model).arg(ts);
        if (!pm.save(path, "PNG")) {
            path = QString("%1/shot_%2_%3.jpg").arg(dir).arg(model).arg(ts);
            if (!pm.save(path, "JPG")) {
                m_status->setText("截屏保存失败");
                return;
            }
        }
        m_status->setText(QString("已保存: %1  (%2x%3)").arg(path).arg(pm.width()).arg(pm.height()));
    }

private:
    QVector<ModelInfo> m_models;
    QStringList m_classes;
    QComboBox *m_combo = nullptr;
    QPushButton *m_pickBtn = nullptr, *m_rotateBtn = nullptr;
    QMenu *m_pickMenu = nullptr;
    QVector<ModelInfo> m_rotation;
    bool m_rotationEnabled = false;
    QHash<QString, QVector<Detection>> m_results;
    QHash<QString, qint64> m_resultTime;
    QHash<QString, double> m_resultMs;
    QHash<QString, double> m_resultFps;
    int m_visibleDets = 0;
    /* 轮换帧率按窗口计数，避免排队信号造成的假高值 */
    qint64 m_fpsWindowStart = 0;
    int m_fpsWindowTotal = 0;
    QHash<QString, int> m_fpsWindowModel;
    double m_rotInferFps = 0;
    int m_sourceGeneration = 0;
    QComboBox *m_fmtCombo = nullptr;
    QComboBox *m_camCombo = nullptr;
    QSlider *m_confSlider = nullptr;
    QLabel *m_confLabel = nullptr;
    QLabel *m_camLabel = nullptr;
    QLabel *m_inferLabel = nullptr;
    QLabel *m_status = nullptr;
    QLabel *m_helpLabel = nullptr;
    bool m_full = false;
    bool m_paused = false;
    double m_camFps = 0;
    QElapsedTimer m_statsTimer, m_camLabelTimer, m_inferLabelTimer;
    QPushButton *m_shotBtn = nullptr;
    VideoWidget *m_video = nullptr;
    CameraThread *m_camera = nullptr;
    InferenceThread *m_infer = nullptr;
};

int main(int argc, char **argv) {
    /* 板端 XFCE 的“窗口缩放”会让 Qt 逻辑尺寸与 X 实际窗口不一致（例如 1.25x 时
       Qt 认为 1920x1080 的窗口只有 1536x864），全屏时画面只能铺满左上角。
       这是全屏 kiosk 程序，按物理像素 1:1 对齐。 */
    if (!qEnvironmentVariableIsSet("QT_SCALE_FACTOR"))
        qputenv("QT_SCALE_FACTOR", "1");
    qputenv("QT_AUTO_SCREEN_SCALE_FACTOR", "0");

    QApplication app(argc, argv);
    qRegisterMetaType<QVector<Detection>>("QVector<Detection>");
    if (app.arguments().contains("--dfl-selftest")) {
        const bool ok = InferenceThread::selfTestDfl() && InferenceThread::selfTestDfl(8, 29);
        fprintf(stderr, ok ? "DFL_SELFTEST_PASS\n" : "DFL_SELFTEST_FAIL\n");
        return ok ? 0 : 2;
    }
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
    const int rotateTest = args.indexOf("--rotate-selftest");
    if (rotateTest >= 0 && rotateTest + 2 < args.size()) {
        const QImage image(args[rotateTest + 1]);
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
            [&](QString path, int, QVector<Detection>, double, double ms) {
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
    MainWindow w(models, videoSource);
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
    const int rotateArg = args.indexOf("--rotate-model");
    if (rotateArg >= 0 && (rotateArg + 1 >= args.size() ||
        !w.setRotation(args[rotateArg + 1].split(',', Qt::SkipEmptyParts)))) {
        fprintf(stderr, "--rotate-model needs 2-4 unique YOLO model substrings\n");
        return 2;
    }
    const int durationArg = args.indexOf("--duration");
    if (durationArg >= 0 && durationArg + 1 < args.size()) {
        const int seconds = args[durationArg + 1].toInt();
        if (seconds < 1 || seconds > 3600) return 2;
        QTimer::singleShot(seconds * 1000, &app, &QCoreApplication::quit);
    }
    w.show();
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
