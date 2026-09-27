// camview - OV5640 live viewer for RK3568 + Pango FPGA PCIe DMA driver
//
// 数据通路: OV5640 -> DDR3(乒乓 0x00800000/0x00A00000) -> PCIe DMA 读 -> GPU(Mali GLES) -> 屏幕
// 同步协议: 轮询 DDR frame tag -> 读已锁定的完整帧 -> 写 +0x00 ACK 释放缓冲区
// 热键: B=字节序切换  C=红蓝交换  F=全屏  Q=退出
//
// [GPU 2026-09-27] 渲染改为 Mali GPU (OpenGL ES2) 纹理绘制: RGB565 帧直接
// glTexImage2D 上传, 缩放/letterbox/红蓝交换都在着色器里完成, CPU 不再做
// QPixmap 转换与 X11 软件贴图. 依赖 Qt 的 xcb-egl 集成 (链接 Mali EGL),
// 在 main() 里用 QT_XCB_GL_INTEGRATION=xcb_egl / QT_OPENGL=es2 强制指定.
#include <QApplication>
#include <QWidget>
#include <QImage>
#include <QByteArray>
#include <QThread>
#include <QMutex>
#include <QElapsedTimer>
#include <QDateTime>
#include <QKeyEvent>
#include <QPainter>
#include <QTimer>
#include <QSurfaceFormat>
#include <QGuiApplication>
#include <QScreen>
#include <QOpenGLWindow>
#include <QOpenGLFunctions>
#include <QOpenGLShaderProgram>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <csignal>
#include <cerrno>

#define IMG_W 640
#define IMG_H 480
// [LEDGER 2026-09-19] match RTL 640x480 (frame 0x96000, tag at base+0x96000)
#define FRAME_BYTES (IMG_W * IMG_H * 2)
#define CAM_ADDR_1 0x00800000u
#define CAM_ADDR_2 0x00A00000u
#define CAM2_ADDR_1 0x00C00000u
#define CAM2_ADDR_2 0x00E00000u
#define CAM3_ADDR_1 0x01000000u
#define CAM3_ADDR_2 0x01200000u
#define TAG_ADDR_1 (CAM_ADDR_1 + FRAME_BYTES)
#define TAG_ADDR_2 (CAM_ADDR_2 + FRAME_BYTES)
#define TAG2_ADDR_1 (CAM2_ADDR_1 + FRAME_BYTES)
#define TAG2_ADDR_2 (CAM2_ADDR_2 + FRAME_BYTES)
#define TAG3_ADDR_1 (CAM3_ADDR_1 + FRAME_BYTES)
#define TAG3_ADDR_2 (CAM3_ADDR_2 + FRAME_BYTES)
#define CAM4_ADDR_1 0x01400000u
#define CAM4_ADDR_2 0x01600000u
#define TAG4_ADDR_1 (CAM4_ADDR_1 + FRAME_BYTES)
#define TAG4_ADDR_2 (CAM4_ADDR_2 + FRAME_BYTES)
#define EDGE_ADDR_1 0x0A000000u   // [EDGE] prep2 write ping  (cam_prep_link BUFFER0)
#define EDGE_ADDR_2 0x0A100000u   // [EDGE] prep2 write pong  (cam_prep_link BUFFER1)
#define REG_BASE   0x20000000u
#define R_ACK      (REG_BASE + 0x00)
#define R_WORDS    (REG_BASE + 0x30)
#define R_VSYNCS   (REG_BASE + 0x34)
#define R_REQ      (REG_BASE + 0x38)
#define R_I2C_ID   (REG_BASE + 0x3C)
#define R_CAM_EN   (REG_BASE + 0x40)
#define R_PCLK     (REG_BASE + 0x44)
#define R_ADDR1    (REG_BASE + 0x80)
#define R_ADDR2    (REG_BASE + 0xC0)
// CAM2 register window (RTL ov5640_reg #2 @ BASE_ADDR 0x2000_0200)
#define R_CAM2_ACK   (REG_BASE + 0x200)
#define R_CAM2_EN    (REG_BASE + 0x240)
#define R_CAM2_ADDR1 (REG_BASE + 0x280)
#define R_CAM2_ADDR2 (REG_BASE + 0x2C0)
#define R_PREP_CTRL (0x20000100u)   // [EDGE] prep_regs +0x100: [0]bypass [2:1]mode [3]edge_en [4]color_en
#define R_PREP_STAT (0x20000130u)   // [EDGE] +0x130: [15:8] out_frame_cnt, [1] fifo near-full

struct DmaOp {
    uint32_t current_len, offset_addr, cmd, ddr3_addr, total_length;
    void *read_buf, *write_buf;
};
static const unsigned long MAP_CMD = 0xC0000000u | (4u << 16) | (0x53u << 8) | 2;
static const unsigned long H2F_CMD = 0xC0000000u | (4u << 16) | (0x53u << 8) | 4; // 主机->FPGA 写
static const unsigned long F2H_CMD = 0xC0000000u | (4u << 16) | (0x53u << 8) | 5; // FPGA->主机 读

class PangoDev {
public:
    bool open() {
        fd_ = ::open("/dev/pango_pci_driver", O_RDWR | O_SYNC);
        if (fd_ < 0) { err_ = "open driver failed"; return false; }
        DmaOp a{}; a.cmd = 0; a.total_length = 4 * 1024 * 1024;
        if (ioctl(fd_, MAP_CMD, &a) < 0) { err_ = "map tx failed"; return false; }
        DmaOp b{}; b.cmd = 1; b.total_length = 4 * 1024 * 1024;
        if (ioctl(fd_, MAP_CMD, &b) < 0) { err_ = "map rx failed"; return false; }
        tx_ = (uint8_t *)mmap(nullptr, 4 * 1024 * 1024, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
        rx_ = (uint8_t *)mmap(nullptr, 4 * 1024 * 1024, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 1024 * 1024);
        if (tx_ == MAP_FAILED || rx_ == MAP_FAILED) { err_ = "mmap failed"; return false; }
        return true;
    }
    // [TIMEOUT] Every ioctl is wrapped in a SIGALRM watchdog. The FPGA register
    // window (M01) can wedge and then an ioctl never returns; without this the
    // grabber thread would hang forever and the screen would stay blank.
    static void alarmHandler(int) { timeoutHit_ = true; }
    static volatile sig_atomic_t timeoutHit_;

    // [MSISTORM 2026-09-19] with both cameras streaming the FPGA push path can
    // saturate the MSI queue for seconds; the old 3 s single-shot timeout made
    // camview kill itself. Retry the (idempotent) descriptor ioctls instead.
    bool ioctlTmo(int cmd, DmaOp *op, unsigned sec, int attempts = 3) {
        for (int attempt = 0; attempt < attempts; attempt++) {
            timeoutHit_ = false;
            struct sigaction sa{}, old{};
            sa.sa_handler = &PangoDev::alarmHandler;
            sigaction(SIGALRM, &sa, &old);
            alarm(sec);
            int r = ioctl(fd_, cmd, op);
            alarm(0);
            sigaction(SIGALRM, &old, nullptr);
            if (timeoutHit_) { err_ = "ioctl timeout"; usleep(50000); continue; }
            if (r == 0) return true;
            usleep(50000);
        }
        return false;
    }

    bool regWrite(uint32_t addr, uint32_t val) {
        memcpy(tx_, &val, 4);
        DmaOp op{}; op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = 16;
        return ioctlTmo(H2F_CMD, &op, 8);
    }
    bool regRead(uint32_t addr, uint32_t &val) {
        DmaOp op{}; op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = 16;
        if (!ioctlTmo(F2H_CMD, &op, 8)) return false;
        memcpy(&val, rx_, 4);
        return true;
    }
    bool ddrRead(uint32_t addr, uint32_t len, void *out) {
        QMutexLocker dmaLock(&dmaMutex_);
        DmaOp op{}; op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = len;
        // A lost MSI must not hold the shared DMA mutex for tens of seconds.
        // The kernel driver already bounds one DMA wait to ~800 ms, so one
        // two-second userspace attempt is enough; the worker keeps its last
        // good frame and retries on the next tag.
        if (!ioctlTmo(F2H_CMD, &op, 2, 1)) return false;
        memcpy(out, rx_, len);
        return true;
    }
    bool readTag(uint32_t addr, uint32_t &val) {
        uint8_t raw[16] = {0};
        if (!ddrRead(addr, sizeof(raw), raw)) return false;
        memcpy(&val, raw, sizeof(val));
        return true;
    }
    const char *lastErr() const { return err_; }
private:
    const char *err_ = "ok";
    int fd_ = -1;
    uint8_t *tx_ = nullptr, *rx_ = nullptr;
    QMutex dmaMutex_;
};

volatile sig_atomic_t PangoDev::timeoutHit_ = 0;

struct LatestFrames {
    QMutex mutex;
    QByteArray c1, c2, c3, c4;
    bool have1 = false, have2 = false, have3 = false, have4 = false;
    uint64_t errors1 = 0, errors2 = 0, errors3 = 0, errors4 = 0;
    qint64 last1 = 0, last2 = 0, last3 = 0, last4 = 0;
    // [PACE 2026-09-27] bumped on every newly stored frame, so the display loop
    // can render only when the picture actually changed instead of free-running.
    uint64_t gen = 0;
    // [FPS3 2026-09-27] per-camera capture rate, measured by each worker so the
    // viewer can label every pane with its own fps.
    double fps1 = 0, fps2 = 0, fps3 = 0, fps4 = 0;
};

class CameraWorker : public QThread {
public:
    CameraWorker(PangoDev *dev, LatestFrames *frames, int camera)
        : dev_(dev), frames_(frames), camera_(camera) {}
    void stop() { running_ = false; }
protected:
    void run() override {
        const uint32_t ta = camera_ == 1 ? TAG_ADDR_1 : camera_ == 2 ? TAG2_ADDR_1 : camera_ == 3 ? TAG3_ADDR_1 : TAG4_ADDR_1;
        const uint32_t tb = camera_ == 1 ? TAG_ADDR_2 : camera_ == 2 ? TAG2_ADDR_2 : camera_ == 3 ? TAG3_ADDR_2 : TAG4_ADDR_2;
        const uint32_t ba = camera_ == 1 ? CAM_ADDR_1 : camera_ == 2 ? CAM2_ADDR_1 : camera_ == 3 ? CAM3_ADDR_1 : CAM4_ADDR_1;
        const uint32_t bb = camera_ == 1 ? CAM_ADDR_2 : camera_ == 2 ? CAM2_ADDR_2 : camera_ == 3 ? CAM3_ADDR_2 : CAM4_ADDR_2;
        uint32_t a = 0, b = 0, la = 0, lb = 0;
        bool base = false;
        QByteArray frame(FRAME_BYTES, 0);
        while (running_) {
            if (!dev_->readTag(ta, a) || !dev_->readTag(tb, b)) { msleep(10); continue; }
            if (!base) { la = a; lb = b; base = true; msleep(10); continue; }
            int which = (a != la) ? 0 : ((b != lb) ? 1 : -1);
            // Tags are only frame notifications; polling them at a tight loop
            // creates thousands of small PCIe DMA transactions and increases
            // MSI contention. A 10 ms cadence is still much faster than the
            // ~32 fps camera stream.
            if (which < 0) { msleep(6); continue; }
            la = a; lb = b;
            if (!dev_->ddrRead(which ? bb : ba, FRAME_BYTES, frame.data())) {
                QMutexLocker errorLock(&frames_->mutex);
                if (camera_ == 1) ++frames_->errors1;
                else if (camera_ == 2) ++frames_->errors2;
                else if (camera_ == 3) ++frames_->errors3;
                else ++frames_->errors4;
                msleep(25); continue;
            }
            QMutexLocker lock(&frames_->mutex);
            ++frames_->gen;
            if (camera_ == 1) { frames_->c1 = frame; frames_->have1 = true; frames_->last1 = QDateTime::currentMSecsSinceEpoch(); }
            else if (camera_ == 2) { frames_->c2 = frame; frames_->have2 = true; frames_->last2 = QDateTime::currentMSecsSinceEpoch(); }
            else if (camera_ == 3) { frames_->c3 = frame; frames_->have3 = true; frames_->last3 = QDateTime::currentMSecsSinceEpoch(); }
            else { frames_->c4 = frame; frames_->have4 = true; frames_->last4 = QDateTime::currentMSecsSinceEpoch(); }
            // [FPS3] measure this camera's capture rate over a 0.5 s window
            if (!fpsTimer_.isValid()) fpsTimer_.start();
            ++fpsFrames_;
            const double fel = fpsTimer_.elapsed() / 1000.0;
            if (fel >= 0.5) {
                const double f = fpsFrames_ / fel;
                if (camera_ == 1) frames_->fps1 = f;
                else if (camera_ == 2) frames_->fps2 = f;
                else if (camera_ == 3) frames_->fps3 = f;
                else frames_->fps4 = f;
                fpsFrames_ = 0;
                fpsTimer_.restart();
            }
            // The sensor is ~32 fps. Do not hammer the single PCIe DMA engine
            // with back-to-back tag/frame transactions from both workers.
            msleep(6);
        }
    }
private:
    PangoDev *dev_;
    LatestFrames *frames_;
    int camera_;
    std::atomic_bool running_{true};
    QElapsedTimer fpsTimer_;   // [FPS3] per-camera fps window
    int fpsFrames_ = 0;
};

// ---------------- 采集线程 ----------------
class Grabber : public QThread {
    Q_OBJECT
public:
    Grabber() : dev_(new PangoDev) {}
    ~Grabber() override { stop(); delete dev_; }
    void stop() { run_ = false; wait(3000); }
    void setByteSwap(bool on) { QMutexLocker l(&m_); swapB_ = on; }
    void setPaused(bool on)   { paused_ = on; }
    // [EDGE] request a one-shot write of the prep mode register
    // [RAW] E only switches which DDR buffer is read (no register write)
    void requestEdge()  { edgeWrite_ = true;  }
    void requestRaw()   { edgeWrite_ = false; }
    void setRBSwap(bool on)   { QMutexLocker l(&m_); swapC_ = on; }

signals:
    // [GPU 2026-09-27] emit the raw RGB565 composite (1920x480) instead of a
    // QImage: the GUI thread uploads it straight to a GL texture, so there is
    // no CPU-side format conversion or scaling any more.
    // [FPS3 2026-09-27] also carry each camera's own capture rate (fps1..3) so
    // every pane can be labelled with its individual frame rate.
    void frameReady(const QByteArray &rgb565, int w, int h, double fps,
                    double fps1, double fps2, double fps3, double fps4, const QString &status);
    void statusMsg(const QString &s);

protected:
    void run() override {
        if (!dev_->open()) { emit statusMsg("FATAL: open driver failed"); return; }
        LatestFrames latest;
        CameraWorker w1(dev_, &latest, 1), w2(dev_, &latest, 2), w3(dev_, &latest, 3), w4(dev_, &latest, 4);
        w1.start(); w2.start(); w3.start(); w4.start();
        QByteArray c1(FRAME_BYTES, 0), c2(FRAME_BYTES, 0), c3(FRAME_BYTES, 0), c4(FRAME_BYTES, 0),
                   comp(4 * FRAME_BYTES, 0);
        const int rowb = IMG_W * 2;
        QElapsedTimer timer; timer.start();
        int frames = 0; double fps = 0;
        // [TUNE 2026-09-27] Display-rate cap (ms between presented frames).
        // Default 33 ms => ~30 fps, matching the ~30-32 fps sensor; the frame
        // generation gate below already suppresses redundant redraws. Set the
        // env var to 0 for the old uncapped behaviour.
        const int minIntervalMs = qEnvironmentVariableIsSet("CAMVIEW_MIN_MS")
            ? qEnvironmentVariableIntValue("CAMVIEW_MIN_MS") : 33;
        emit statusMsg("QUAD THREAD VIEW");
        // [PACE 2026-09-27] MUST live outside the loop: it remembers the last
        // rendered frame generation so we only present when a camera actually
        // produced a new frame. It used to be declared inside the loop body,
        // which reset it to 0 every iteration, so `gen == lastGen` never held
        // and the display free-ran at ~230 fps.
        uint64_t lastGen = 0;
        while (run_) {
        bool ready; qint64 last1, last2, last3, last4; uint64_t err1, err2, err3, err4, gen;
        double cf1, cf2, cf3, cf4;
            { QMutexLocker lock(&latest.mutex);
              ready = latest.have1 || latest.have2 || latest.have3 || latest.have4;
              gen = latest.gen;
              if (latest.have1) c1 = latest.c1;
              if (latest.have2) c2 = latest.c2;
              if (latest.have3) c3 = latest.c3;
              if (latest.have4) c4 = latest.c4;
              last1 = latest.last1; last2 = latest.last2; last3 = latest.last3; last4 = latest.last4;
              err1 = latest.errors1; err2 = latest.errors2; err3 = latest.errors3; err4 = latest.errors4;
              cf1 = latest.fps1; cf2 = latest.fps2; cf3 = latest.fps3; cf4 = latest.fps4; }
            if (!ready) { msleep(2); continue; }
            // [PACE 2026-09-27] Only rebuild+present when a camera actually
            // produced a new frame. Previously the loop free-ran (msleep 6) and
            // redisplayed the same picture ~90x/s, wasting GPU/CPU and PCIe.
            if (gen == lastGen) { msleep(2); continue; }
            lastGen = gen;
            for (int y = 0; y < IMG_H; ++y) {
                // [QUAD 2026-09-27] 2x2 grid: top C1|C2, bottom C3|C4.
                memcpy(comp.data() + (size_t)y * 2 * rowb,                  c1.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)y * 2 * rowb + rowb,           c2.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)(y + IMG_H) * 2 * rowb,        c3.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)(y + IMG_H) * 2 * rowb + rowb, c4.constData() + (size_t)y * rowb, rowb);
            }
            frames++;
            double elapsed = timer.elapsed() / 1000.0;
            if (elapsed >= 0.5) { fps = frames / elapsed; frames = 0; timer.restart(); std::fprintf(stderr, "camview_fps=%.3f\n", fps); std::fflush(stderr); }
            bool sb; { QMutexLocker l(&m_); sb = swapB_; }
            if (sb) {
                // [GPU] byte order is a debug toggle; keep it on the CPU (rarely
                // used) so the GL upload can always take RGB565 directly.
                char *raw = comp.data();
                for (int i = 0; i < 4 * FRAME_BYTES; i += 2) {
                    char t = raw[i]; raw[i] = raw[i + 1]; raw[i + 1] = t;
                }
            }
            qint64 now = QDateTime::currentMSecsSinceEpoch();
            const QString status = QString("D:%1  C1:%2 C2:%3 C3:%4 C4:%5  E1:%6 E2:%7 E3:%8 E4:%9")
                                       .arg(fps, 0, 'f', 1)
                                       .arg(now - last1 < 500 ? "OK" : "WAIT")
                                       .arg(now - last2 < 500 ? "OK" : "WAIT")
                                       .arg(now - last3 < 500 ? "OK" : "WAIT")
                                       .arg(now - last4 < 500 ? "OK" : "WAIT")
                                       .arg(err1).arg(err2).arg(err3).arg(err4);
            emit frameReady(comp, 2 * IMG_W, 2 * IMG_H, fps, cf1, cf2, cf3, cf4, status);
            // No fixed display delay: the generation gate above already paces us
            // to the camera, and the idle branch (gen == lastGen) sleeps 2 ms.
            if (minIntervalMs > 0) msleep(minIntervalMs);
        }
        w1.stop(); w2.stop(); w3.stop(); w4.stop();
        w1.wait(3000); w2.wait(3000); w3.wait(3000); w4.wait(3000);
        return;
    }
private:
    PangoDev *dev_;
    std::atomic_bool run_{true};
    bool swapB_ = false, swapC_ = false;
    std::atomic_bool paused_{false};
    std::atomic_bool edgeWrite_{false};   // [RAW] default: unprocessed camera image
    std::atomic_bool edgePending_{false}; // [RAW] no prep-register write at all
    QMutex m_;
};

// ---------------- 主窗口 (GPU 渲染) ----------------
//
// [GPU 2026-09-27] 整个显示路径基于 OpenGL ES2:
//   RGB565 复合帧 --glTexImage2D--> 纹理 --quad 着色器--> 屏幕(letterbox)
// 缩放/红蓝换序/平滑滤波都在 GPU 上完成, CPU 只负责把帧内存交给驱动.
class View : public QOpenGLWindow, protected QOpenGLFunctions {
public:
    explicit View(Grabber *g) : g_(g) {
        setTitle("camview");
        // [SURF 2026-09-27] Create the GL surface at the final (screen) size.
        // resize(1280,720) here used to make the *first* EGL surface 1280x720;
        // after showFullScreen() the swap chain still held that stale buffer,
        // and the compositor occasionally presented it -> the picture jumped
        // up/clipped. Sizing to the screen up front removes that source.
        const QRect sg = QGuiApplication::primaryScreen()->geometry();
        resize(sg.size());
    }

    bool byteSwapped() const { return bs_; }
    bool rbSwapped() const { return rs_; }
    void toggleByte() { bs_ = !bs_; g_->setByteSwap(bs_); }
    void toggleRB()   { rs_ = !rs_; update(); }
    void toggleFull() { full_ = !full_; full_ ? showFullScreen() : showNormal(); }
    void togglePause() { paused_ = !paused_; g_->setPaused(paused_); if (!paused_) update(); }
    // [EDGE] true = show Sobel edge stream, false = show RAW camera
    void toggleEdge() { edgeOn_ = !edgeOn_; edgeOn_ ? g_->requestEdge() : g_->requestRaw(); }
    void toggleScale() { smooth_ = !smooth_; update(); }
    bool smoothScale() const { return smooth_; }
    bool paused() const { return paused_; }

    // 键盘帮助层(按 H 切换)
    void setHelpVisible(bool on) { help_ = on; update(); }
    bool helpVisible() const { return help_; }

    // 采集线程投递新帧 (GUI 线程调用, 跨线程走 queued connection)
    void submitFrame(const QByteArray &rgb565, int w, int h, double fps,
                     double fps1, double fps2, double fps3, double fps4, const QString &status) {
        frame_ = rgb565;          // QByteArray 隐式共享, 只是引用计数 +1
        fw_ = w; fh_ = h; fps_ = fps; status_ = status;
        fps1_ = fps1; fps2_ = fps2; fps3_ = fps3; fps4_ = fps4;
        frameDirty_ = true;
        statusOnly_ = false;
        if (!paused_) update();
    }
    void setStatusText(const QString &s) { status_ = s; statusOnly_ = true; update(); }

protected:
    void initializeGL() override;
    void paintGL() override;
    void resizeGL(int, int) override { hudImg_ = QImage(); }

    void keyPressEvent(QKeyEvent *e) override {
        switch (e->key()) {
        case Qt::Key_Q: case Qt::Key_Escape: close(); break;
        case Qt::Key_F: toggleFull(); break;
        case Qt::Key_B: toggleByte(); break;
        case Qt::Key_C: toggleRB(); break;
        case Qt::Key_P: case Qt::Key_Space: togglePause(); break;
        case Qt::Key_S: toggleScale(); break;
        case Qt::Key_H: help_ = !help_; update(); break;
        case Qt::Key_E: toggleEdge(); break;
        default: break;
        }
    }

private:
    void buildHudImage(int w, int h);
    Grabber *g_;
    QByteArray frame_;
    int fw_ = 0, fh_ = 0;
    double fps_ = 0;
    double fps1_ = 0, fps2_ = 0, fps3_ = 0, fps4_ = 0;   // [FPS3] per-camera capture rates
    QString status_;
    bool statusOnly_ = false;     // true => show status text without a frame
    bool frameDirty_ = false;
    bool texAlloc_ = false;
    GLuint tex_ = 0;
    QOpenGLShaderProgram prog_;
    bool full_ = false, bs_ = false, rs_ = false, paused_ = false, smooth_ = false, help_ = false;
    bool edgeOn_ = false;  // [RAW] default: unprocessed camera image
    bool testPat_ = false; // [GEO] CAMVIEW_TESTPAT: draw a gradient/marker pattern instead of the frame
    // [HUDIMG 2026-09-27] The HUD is rasterised on the CPU and blitted as an
    // image, rather than letting Qt's GL paint engine draw glyphs into its GL
    // texture atlas (that path produced smeared/blurry text on Mali ES2).
    QImage hudImg_;
    QString hudKey_;
};

static const char *kHelpText =
    "键盘控制\n"
    "--------------------------------\n"
    "  Q / ESC   退出\n"
    "  F         全屏 / 窗口 切换\n"
    "  P / 空格  暂停 / 继续画面\n"
    "  S         平滑缩放 切换\n"
    "  B         字节序 切换\n"
    "  C         红蓝交换 切换\n"
    "  E         切换缓冲区(RAW/处理)\n"
    "  H         显示 / 隐藏本帮助\n"
    "\n"
    "按 H 关闭帮助";

void View::initializeGL() {
    initializeOpenGLFunctions();
    testPat_ = qEnvironmentVariableIsSet("CAMVIEW_TESTPAT");
    const char *ren = (const char *)glGetString(GL_RENDERER);
    std::fprintf(stderr, "camview_gl_renderer=%s\n", ren ? ren : "?");
    std::fflush(stderr);

    static const char *vsrc =
        "attribute highp vec2 aPos;\n"
        "attribute highp vec2 aTex;\n"
        "varying highp vec2 vTex;\n"
        "void main() { vTex = aTex; gl_Position = vec4(aPos, 0.0, 1.0); }\n";
    // RGB565 -> sampler2D converts to float; uSwap does the R/B swap on the GPU.
    static const char *fsrc =
        "precision mediump float;\n"
        "varying mediump vec2 vTex;\n"
        "uniform sampler2D uTex;\n"
        "uniform int uSwap;\n"
        "uniform int uTest;\n"
        "void main() {\n"
        "  if (uTest == 1) {\n"
        "    float g = vTex.y;\n"
        "    vec3 c = vec3(vTex.x, g, 0.5);\n"
        "    float m = mod(g * 8.0, 1.0);\n"
        "    if (m < 0.06) c = vec3(1.0, 1.0, 1.0);\n"
        "    if (g < 0.06) c = vec3(1.0, 0.0, 0.0);\n"
        "    if (g > 0.94) c = vec3(0.0, 0.0, 1.0);\n"
        "    gl_FragColor = vec4(c, 1.0);\n"
        "    return;\n"
        "  }\n"
        "  vec4 c = texture2D(uTex, vTex);\n"
        "  if (uSwap == 1) gl_FragColor = vec4(c.b, c.g, c.r, 1.0);\n"
        "  else            gl_FragColor = vec4(c.rgb, 1.0);\n"
        "}\n";
    prog_.addShaderFromSourceCode(QOpenGLShader::Vertex, vsrc);
    prog_.addShaderFromSourceCode(QOpenGLShader::Fragment, fsrc);
    prog_.bindAttributeLocation("aPos", 0);
    prog_.bindAttributeLocation("aTex", 1);
    if (!prog_.link())
        std::fprintf(stderr, "camview_gl: shader link failed: %s\n", qPrintable(prog_.log()));

    glGenTextures(1, &tex_);
    glBindTexture(GL_TEXTURE_2D, tex_);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
}

void View::paintGL() {
    // [VP 2026-09-27] Log any change of the GL viewport / window size. The
    // "jitter" turned out to be the picture being drawn 360 px higher on some
    // frames, i.e. a stale/foreign viewport, so watch it explicitly.
    if (qEnvironmentVariableIsSet("CAMVIEW_GEO")) {
        GLint vp[4] = {0, 0, 0, 0};
        glGetIntegerv(GL_VIEWPORT, vp);
        static GLint lp[4] = {-1, -1, -1, -1};
        static int lw = -1, lh = -1;
        if (vp[0] != lp[0] || vp[1] != lp[1] || vp[2] != lp[2] || vp[3] != lp[3] ||
            width() != lw || height() != lh) {
            std::fprintf(stderr, "camview_vp CHANGE win=%dx%d dpr=%.2f vp=%d,%d,%d,%d\n",
                         width(), height(), (double)devicePixelRatioF(),
                         vp[0], vp[1], vp[2], vp[3]);
            std::fflush(stderr);
            lp[0] = vp[0]; lp[1] = vp[1]; lp[2] = vp[2]; lp[3] = vp[3];
            lw = width(); lh = height();
        }
    }
    // [FIX 2026-09-27] Always establish the full-surface viewport ourselves.
    // Relying on whatever the platform/paint-engine last left here is what let
    // the picture jump 360 px between frames.
    const int fbw = (int)(width()  * devicePixelRatioF());
    const int fbh = (int)(height() * devicePixelRatioF());
    glViewport(0, 0, fbw, fbh);

    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);

    const bool haveFrame = (fw_ > 0 && fh_ > 0 && frame_.size() >= fw_ * fh_ * 2);
    if ((haveFrame || testPat_) && !statusOnly_) {
        glBindTexture(GL_TEXTURE_2D, tex_);
        if (haveFrame && (frameDirty_ || !texAlloc_)) {
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, fw_, fh_, 0,
                         GL_RGB, GL_UNSIGNED_SHORT_5_6_5, frame_.constData());
            texAlloc_ = true;
            frameDirty_ = false;
        }
        const GLint filt = smooth_ ? GL_LINEAR : GL_NEAREST;
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, filt);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, filt);

        // letterbox: preserve the frame aspect ratio inside the widget
        const float ia = (float)fw_ / (float)fh_;
        const float wa = (float)width() / (float)qMax(1, height());
        float sx = 1.0f, sy = 1.0f;
        if (ia > wa) sy = wa / ia; else sx = ia / wa;
        // [GEO] kept for post-mortem; see the viewport log at the top of paintGL.
        const GLfloat verts[] = {
            -sx,  sy, 0.0f, 0.0f,   // top-left      -> frame top row
             sx,  sy, 1.0f, 0.0f,   // top-right
            -sx, -sy, 0.0f, 1.0f,   // bottom-left   -> frame bottom row
             sx, -sy, 1.0f, 1.0f,   // bottom-right
        };
        prog_.bind();
        prog_.enableAttributeArray(0);
        prog_.enableAttributeArray(1);
        prog_.setAttributeArray(0, GL_FLOAT, verts,     2, 4 * sizeof(GLfloat));
        prog_.setAttributeArray(1, GL_FLOAT, verts + 2, 2, 4 * sizeof(GLfloat));
        prog_.setUniformValue("uTex", 0);
        prog_.setUniformValue("uSwap", rs_ ? 1 : 0);
        prog_.setUniformValue("uTest", testPat_ ? 1 : 0);
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, tex_);
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
        prog_.disableAttributeArray(0);
        prog_.disableAttributeArray(1);
        prog_.release();
    }

    // ---- HUD overlay ----
    // [HUDIMG 2026-09-27] Build the overlay with the *raster* paint engine into
    // an ARGB image (crisp glyphs) and only blit it here. Drawing the text
    // directly with QPainter on this GL window sent it through Qt's GL glyph
    // atlas, which the Mali ES2 driver rendered smeared/blurry. Rebuild only
    // when the displayed text or the window size actually changes.
    if (qEnvironmentVariableIsSet("CAMVIEW_NOHUD")) {
        return;
    }
    const int dprW = (int)(width()  * devicePixelRatioF());
    const int dprH = (int)(height() * devicePixelRatioF());
    const QString key = QString("%1|%2|%3|%4|%5|%6x%7|%8|%9|%10|%11")
                            .arg(fps_, 0, 'f', 0).arg(status_).arg(help_).arg(statusOnly_)
                            .arg(dprW).arg(fw_).arg(fh_)
                            .arg(fps1_, 0, 'f', 0).arg(fps2_, 0, 'f', 0).arg(fps3_, 0, 'f', 0)
                            .arg(fps4_, 0, 'f', 0);
    if (hudImg_.size() != QSize(dprW, dprH) || key != hudKey_) {
        buildHudImage(dprW, dprH);
        hudKey_ = key;
    }
    QPainter p(this);
    p.drawImage(QPoint(0, 0), hudImg_);
    p.end();
}

void View::buildHudImage(int w, int h) {
    if (w <= 0 || h <= 0) return;
    hudImg_ = QImage(w, h, QImage::Format_ARGB32_Premultiplied);
    hudImg_.fill(Qt::transparent);
    QPainter p(&hudImg_);
    p.setRenderHint(QPainter::Antialiasing, true);
    p.setRenderHint(QPainter::TextAntialiasing, true);
    const float dpr = (float)devicePixelRatioF();
    p.scale(dpr, dpr);                       // draw in logical coordinates
    QFont f = p.font();
    f.setBold(true);
    const bool haveFrame = (fw_ > 0 && fh_ > 0 && frame_.size() >= fw_ * fh_ * 2);
    if (!haveFrame || statusOnly_) {
        p.setPen(QColor(0, 255, 120));
        f.setPointSize(16);
        p.setFont(f);
        p.drawText(QRect(QPoint(0, 0), size()), Qt::AlignCenter,
                   status_.isEmpty() ? "WAITING FOR FRAME" : status_);
    } else {
        QRect r(18, 18, 470, 44);
        p.fillRect(r, QColor(0, 0, 0, 180));
        p.setPen(QColor(0, 255, 120));
        f.setPointSize(14);
        p.setFont(f);
        p.drawText(r.adjusted(10, 4, -8, -4), Qt::AlignLeft | Qt::AlignVCenter,
                   QString("Quad FPS: %1   %2").arg(fps_, 0, 'f', 1).arg(status_));
    }
    if (help_) {
        QRect r(20, 20, 340, 250);
        p.fillRect(r, QColor(0, 0, 0, 200));
        p.setPen(QColor(0, 255, 120));
        f.setPointSize(13);
        p.setFont(f);
        p.drawText(r.adjusted(16, 12, -16, -12), Qt::AlignTop | Qt::AlignLeft, QString::fromUtf8(kHelpText));
    }
    // [FPS3 2026-09-27] Per-pane frame-rate label in the top-left corner of
    // each of the four camera images. The panes are the four quadrants of the
    // letterboxed 2x2 composite (fw_ x fh_ is 2*640 x 2*480).
    if (haveFrame && !statusOnly_ && fw_ > 0 && fh_ > 0) {
        const float ia = (float)fw_ / (float)fh_;
        const float wa = (float)width() / (float)qMax(1, height());
        float dw, dh;
        if (ia > wa) { dw = (float)width();  dh = (float)width() / ia; }
        else         { dh = (float)height(); dw = (float)height() * ia; }
        const float dx = ((float)width()  - dw) * 0.5f;
        const float dy = ((float)height() - dh) * 0.5f;
        const float pw = dw / 2.0f;
        const float ph = dh / 2.0f;
        const double cf[4] = { fps1_, fps2_, fps3_, fps4_ };
        f.setPointSize(12);
        p.setFont(f);
        for (int i = 0; i < 4; ++i) {
            const QRect box((int)(dx + (i % 2) * pw) + 6, (int)(dy + (i / 2) * ph) + 6, 150, 32);
            p.fillRect(box, QColor(0, 0, 0, 170));
            p.setPen(QColor(0, 255, 120));
            p.drawText(box.adjusted(8, 0, -6, 0), Qt::AlignLeft | Qt::AlignVCenter,
                       QString("C%1  %2 fps").arg(i + 1).arg(cf[i], 0, 'f', 1));
        }
    }
    p.end();
    if (qEnvironmentVariableIsSet("CAMVIEW_HUDDUMP")) {
        static int n = 0;
        if (++n % 200 == 1) hudImg_.save("/tmp/camview_hud.png", "PNG");
    }
}

int main(int argc, char **argv) {
    // [GPU 2026-09-27] Force Qt's xcb platform to use the Mali EGL integration
    // (libqxcb-egl-integration.so -> /usr/lib/aarch64-linux-gnu/mali/libEGL.so.1)
    // instead of the default GLX path, whose only driver here is Mesa llvmpipe
    // (software). Must be set before QApplication loads the platform plugin.
    qputenv("QT_XCB_GL_INTEGRATION", "xcb_egl");
    qputenv("QT_OPENGL", "es2");
    QSurfaceFormat fmt;
    fmt.setRenderableType(QSurfaceFormat::OpenGLES);
    fmt.setVersion(2, 0);
    fmt.setDepthBufferSize(0);
    fmt.setStencilBufferSize(0);
    fmt.setSwapInterval(1);   // [SURF] present on vblank; avoids torn frames
    QSurfaceFormat::setDefaultFormat(fmt);

    QApplication app(argc, argv);

    Grabber *grabber = new Grabber;
    View *view = new View(grabber);

    QObject::connect(grabber, &Grabber::frameReady, view,
        [view](const QByteArray &rgb565, int w, int h, double fps,
               double fps1, double fps2, double fps3, double fps4, const QString &status) {
            view->submitFrame(rgb565, w, h, fps, fps1, fps2, fps3, fps4, status);
        });
    QObject::connect(grabber, &Grabber::statusMsg, view, [view](const QString &s) {
        view->setStatusText(s);
        view->setTitle("camview  " + s);
        if (s.startsWith("FATAL:"))
            ::_exit(2);
    });

    view->showFullScreen();
    // [FOCUS] 强制抢键盘焦点: 全屏窗口在 X11 下不保证自动获焦, 键盘接在板上时必须确保焦点
    view->raise();
    view->requestActivate();

    // 周期性重申焦点(有人误点桌面/别的窗口时自动夺回, 保证热键随时可用)
    QTimer focusTimer;
    QObject::connect(&focusTimer, &QTimer::timeout, [view]() {
        if (!view->isActive()) {
            view->raise();
            view->requestActivate();
        }
    });
    focusTimer.start(2000);

    grabber->start();
    int rc = app.exec();
    grabber->stop();
    delete grabber;
    delete view;
    return rc;
}
#include "main.moc"
