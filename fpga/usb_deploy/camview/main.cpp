// camview - OV5640 live viewer for RK3568 + Pango FPGA PCIe DMA driver
//
// 数据通路: OV5640 -> DDR3(乒乓 0x00800000/0x00A00000) -> PCIe DMA 读 -> QImage(RGB565) -> 屏幕
// 同步协议: 轮询 DDR frame tag -> 读已锁定的完整帧 -> 写 +0x00 ACK 释放缓冲区
// 热键: B=字节序切换  C=红蓝交换  F=全屏  Q=退出
#include <QApplication>
#include <QWidget>
#include <QLabel>
#include <QImage>
#include <QPixmap>
#include <QThread>
#include <QMutex>
#include <QElapsedTimer>
#include <QDateTime>
#include <QKeyEvent>
#include <QPainter>
#include <QTimer>
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
#define TAG_ADDR_1 (CAM_ADDR_1 + FRAME_BYTES)
#define TAG_ADDR_2 (CAM_ADDR_2 + FRAME_BYTES)
#define TAG2_ADDR_1 (CAM2_ADDR_1 + FRAME_BYTES)
#define TAG2_ADDR_2 (CAM2_ADDR_2 + FRAME_BYTES)
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
#define R_SHARP    (REG_BASE + 0xD0)   // [SHARP] [0]en [3:1]strength(2..6)
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
    bool ioctlTmo(int cmd, DmaOp *op, unsigned sec) {
        for (int attempt = 0; attempt < 3; attempt++) {
            timeoutHit_ = false;
            struct sigaction sa{}, old{};
            sa.sa_handler = &PangoDev::alarmHandler;
            sigaction(SIGALRM, &sa, &old);
            alarm(sec);
            int r = ioctl(fd_, cmd, op);
            alarm(0);
            sigaction(SIGALRM, &old, nullptr);
            if (timeoutHit_) { err_ = "ioctl timeout"; usleep(200000); continue; }
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
        DmaOp op{}; op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = len;
        if (!ioctlTmo(F2H_CMD, &op, 10)) return false;
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
};

volatile sig_atomic_t PangoDev::timeoutHit_ = 0;

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
    void setSharp(bool on, int strength) {   // [SHARP] runtime control
        QMutexLocker l(&m_);
        sharpOn_ = on;
        sharpStr_ = (strength < 2) ? 2 : ((strength > 6) ? 6 : strength);
        sharpDirty_ = true;
    }

signals:
    void frameReady(const QImage &img, double fps);
    void statusMsg(const QString &s);

protected:
    void run() override {
        if (!dev_->open()) ::_exit(2);
        // M01 reads are intentionally avoided: this bridge has a known stale-read
        // failure mode that can wedge the PCIe driver. Frame health is proven by
        // changing DDR tags instead.
        emit statusMsg("ACK-WAIT; DUAL 2 x 640x480 RGB565");
        // [LEDGER 2026-09-19] boot: clear pending on BOTH cams, then explicitly
        // enable both capture engines (never rely on reset defaults).
        dev_->regWrite(R_ACK, 3);
        dev_->regWrite(R_CAM2_ACK, 3);
        dev_->regWrite(R_CAM_EN, 1);
        dev_->regWrite(R_CAM2_EN, 1);
        msleep(80);

        QByteArray c1(FRAME_BYTES, 0), c2(FRAME_BYTES, 0);
        QByteArray comp(2 * FRAME_BYTES, 0);
        const int rowb = IMG_W * 2;
        int frames = 0;
        QElapsedTimer t0; t0.start();
        double fps = 0;
        // [LEDGER 2026-09-19] tag-driven ping-pong (was: blind expected^=1, which
        // permanently desynced from the FPGA after one dropped frame and froze
        // the stream). Poll the 4 FRTAG words in DDR; per camera read+ACK only
        // the buffer whose tag advanced. A completed buffer is frozen until its
        // ACK, so the data cannot change under us between tag poll and read.
        uint32_t t1a = 0, t1b = 0, t2a = 0, t2b = 0;
        uint32_t lt1a = 0, lt1b = 0, lt2a = 0, lt2b = 0;
        bool baselined = false;
        // [SELFHEAL 2026-09-19] the FPGA M00 write path wedges under sustained load
        // (infrastructure bug, see report). When no new frame arrives for 4 s, exit:
        // run_camview.sh then reloads the PCIe driver and restarts us, which revives
        // the engines. The display keeps cycling fresh dual frames unattended.
        qint64 lastFrameMs = 0;
        while (run_) {
            if (sharpDirty_) {                       // [SHARP] apply once
                sharpDirty_ = false;
                dev_->regWrite(R_SHARP, (sharpOn_ ? 1u : 0u) | ((uint32_t)sharpStr_ << 1));
            }
            if (!dev_->readTag(TAG_ADDR_1, t1a))  ::_exit(2);
            if (!dev_->readTag(TAG_ADDR_2, t1b))  ::_exit(2);
            if (!dev_->readTag(TAG2_ADDR_1, t2a)) ::_exit(2);
            if (!dev_->readTag(TAG2_ADDR_2, t2b)) ::_exit(2);
            if (!baselined) {
                lt1a = t1a; lt1b = t1b; lt2a = t2a; lt2b = t2b;
                baselined = true;
                msleep(40);
                continue;
            }
            const bool n1a = (t1a != lt1a), n1b = (t1b != lt1b);
            const bool n2a = (t2a != lt2a), n2b = (t2b != lt2b);
            // [STABLE-BUF 2026-09-19] with the FPGA free-running (ackless ping-pong),
            // the buffer whose tag JUST advanced is being read out by the engine right
            // now (it immediately starts the OTHER buffer and comes back a frame later).
            // Reading it showed mid-write tearing = the vertical stripes on screen.
            // Read the OTHER buffer instead: completed a full frame ago, untouched for
            // another frame -> wide safe window (read ~7 ms vs frame ~33-50 ms).
            int b1 = -1, b2 = -1;
            if (n1a && n1b)      b1 = 1 - (((int32_t)(t1a - t1b) >= 0) ? 0 : 1);
            else if (n1a)        b1 = 1;
            else if (n1b)        b1 = 0;
            if (n2a && n2b)      b2 = 1 - (((int32_t)(t2a - t2b) >= 0) ? 0 : 1);
            else if (n2a)        b2 = 1;
            else if (n2b)        b2 = 0;
            // first pass fallback: a never-written buffer has tag 0 -> use latest
            if (b1 == 0 && t1a == 0) b1 = 1;
            if (b1 == 1 && t1b == 0) b1 = 0;
            if (b2 == 0 && t2a == 0) b2 = 1;
            if (b2 == 1 && t2b == 0) b2 = 0;
            if (b1 < 0 && b2 < 0) {
                if (lastFrameMs == 0) lastFrameMs = QDateTime::currentMSecsSinceEpoch();
                else if (QDateTime::currentMSecsSinceEpoch() - lastFrameMs > 4000)
                    ::_exit(2);                       // [SELFHEAL] revive via script
                msleep(40); continue;
            }
            lastFrameMs = QDateTime::currentMSecsSinceEpoch();
            // [PACE 2026-09-19] the PCIe DMA engine wedges under high-rate descriptor
            // traffic; the proven 9-16 cadence was ~6 ops per 80ms. Keep to it.
            lt1a = t1a; lt1b = t1b; lt2a = t2a; lt2b = t2b;
            // [ACKLESS 2026-09-19] no M01 ACK writes during streaming: every M01
            // register write risks wedging the PCIe driver (axi_to_axi_lite bug).
            // The FPGA now free-runs its ping-pong; the tag tells us which buffer
            // just completed, so we read it while the engine writes the other one.
            if (b1 >= 0) {
                uint32_t addr1 = (edgeWrite_)
                    ? (b1 == 0 ? EDGE_ADDR_1 : EDGE_ADDR_2)
                    : (b1 == 0 ? CAM_ADDR_1 : CAM_ADDR_2);
                if (!dev_->ddrRead(addr1, FRAME_BYTES, c1.data())) ::_exit(2);
            }
            if (b2 >= 0) {
                uint32_t addr2 = (b2 == 0) ? CAM2_ADDR_1 : CAM2_ADDR_2;
                if (!dev_->ddrRead(addr2, FRAME_BYTES, c2.data())) ::_exit(2);
            }
            if (paused_) { msleep(80); continue; }
            // side-by-side composite: row y = cam1 row y | cam2 row y
            {
                uint8_t *d = reinterpret_cast<uint8_t *>(comp.data());
                const uint8_t *p1 = reinterpret_cast<const uint8_t *>(c1.constData());
                const uint8_t *p2 = reinterpret_cast<const uint8_t *>(c2.constData());
                for (int y = 0; y < IMG_H; ++y) {
                    memcpy(d + (size_t)y * 2 * rowb,        p1 + (size_t)y * rowb, rowb);
                    memcpy(d + (size_t)y * 2 * rowb + rowb, p2 + (size_t)y * rowb, rowb);
                }
            }
            bool sb, sc; { QMutexLocker l(&m_); sb = swapB_; sc = swapC_; }
            if (sb) {
                char *raw = comp.data();
                for (int i = 0; i < 2 * FRAME_BYTES; i += 2) {
                    char t = raw[i]; raw[i] = raw[i + 1]; raw[i + 1] = t;
                }
            }
            QImage im(reinterpret_cast<const uchar *>(comp.constData()), 2 * IMG_W, IMG_H,
                      2 * IMG_W * 2, QImage::Format_RGB16);
            QImage out = sc ? im.convertToFormat(QImage::Format_RGB32).rgbSwapped()
                            : im.copy();
            frames++;
            double el = t0.elapsed() / 1000.0;
            if (el >= 0.5) { fps = frames / el; frames = 0; t0.restart(); }
            emit frameReady(out, fps);
             msleep(1);    // no artificial frame-rate cap
        }
    }
private:
    PangoDev *dev_;
    std::atomic_bool run_{true};
    bool swapB_ = false, swapC_ = false;
    bool sharpOn_ = false;
    int  sharpStr_ = 3;
    bool sharpDirty_ = false;
    std::atomic_bool paused_{false};
    std::atomic_bool edgeWrite_{false};   // [RAW] default: unprocessed camera image
    std::atomic_bool edgePending_{false}; // [RAW] no prep-register write at all
    QMutex m_;
};

// ---------------- 主窗口 ----------------
class View : public QWidget {
public:
    explicit View(Grabber *g) : g_(g) {
        label_ = new QLabel(this);
        label_->setAlignment(Qt::AlignCenter);
        label_->setStyleSheet("background:black; color:#0f0; font:14px monospace;");
        setWindowTitle("camview");
        resize(1280, 720);
    }
    QLabel *label() const { return label_; }
    bool byteSwapped() const { return bs_; }
    bool rbSwapped() const { return rs_; }
    void toggleByte() { bs_ = !bs_; g_->setByteSwap(bs_); }
    void toggleRB()   { rs_ = !rs_; g_->setRBSwap(rs_); }
    void toggleFull() { full_ = !full_; full_ ? showFullScreen() : showNormal(); }
    void togglePause() { paused_ = !paused_; g_->setPaused(paused_); }
    // [EDGE] true = show Sobel edge stream, false = show RAW camera
    void toggleEdge() { edgeOn_ = !edgeOn_; edgeOn_ ? g_->requestEdge() : g_->requestRaw(); }
    void toggleScale() { smooth_ = !smooth_; }
    void toggleSharp() { sharpOn_ = !sharpOn_; g_->setSharp(sharpOn_, sharpStr_); }
    void sharpUp()   { if (sharpStr_ > 2) { sharpStr_--; g_->setSharp(sharpOn_, sharpStr_); } }
    void sharpDown() { if (sharpStr_ < 6) { sharpStr_++; g_->setSharp(sharpOn_, sharpStr_); } }
    bool sharpOn() const { return sharpOn_; }
    int  sharpStrength() const { return sharpStr_; }
    bool smoothScale() const { return smooth_; }
    bool paused() const { return paused_; }

    // 键盘帮助层(按 H 切换); 内容在 main() 里随 fps 一起刷新
    void setHelpVisible(bool on) { help_ = on; }
    bool helpVisible() const { return help_; }

protected:
    void keyPressEvent(QKeyEvent *e) override {
        switch (e->key()) {
        case Qt::Key_Q: case Qt::Key_Escape: close(); break;
        case Qt::Key_F: toggleFull(); break;
        case Qt::Key_B: toggleByte(); break;
        case Qt::Key_C: toggleRB(); break;
        case Qt::Key_P: case Qt::Key_Space: togglePause(); break;
        case Qt::Key_S: toggleScale(); break;
        case Qt::Key_H: help_ = !help_; break;
        case Qt::Key_E: toggleEdge(); break;
        case Qt::Key_R: toggleSharp(); break;      // [SHARP] on/off
        case Qt::Key_Plus: case Qt::Key_Equal: sharpUp(); break;
        case Qt::Key_Minus: sharpDown(); break;
        default: break;
        }
    }
    void resizeEvent(QResizeEvent *) override { label_->setGeometry(rect()); }

private:
    QLabel *label_;
    Grabber *g_;
    bool full_ = false, bs_ = false, rs_ = false, paused_ = false, smooth_ = false, help_ = false;
    bool edgeOn_ = false;  // [RAW] default: unprocessed camera image
    bool sharpOn_ = false; // [SHARP] default off
    int  sharpStr_ = 3;
};

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    qRegisterMetaType<QImage>("QImage");

    Grabber *grabber = new Grabber;
    View *view = new View(grabber);

    // 键盘帮助文字(按 H 叠加显示)
    const QString helpText =
        "键盘控制\n"
        "--------------------------------\n"
        "  Q / ESC   退出\n"
        "  F         全屏 / 窗口 切换\n"
        "  P / 空格  暂停 / 继续画面\n"
        "  S         平滑缩放 切换\n"
        "  B         字节序 切换\n"
        "  C         红蓝交换 切换\n"
        "  E         切换缓冲区(RAW/处理)\n"
        "  R         锐化 开/关 (cam1)\n"
        "  +/-       锐化强度 2..6\n"
        "  H         显示 / 隐藏本帮助\n"
        "\n"
        "按 H 关闭帮助";

    QObject::connect(grabber, &Grabber::frameReady, view,
        [view, helpText](const QImage &img, double fps) {
            QPixmap pm = QPixmap::fromImage(img).scaled(
                view->label()->size(), Qt::KeepAspectRatio,
                view->smoothScale() ? Qt::SmoothTransformation : Qt::FastTransformation);
            if (view->helpVisible()) {
                QPainter p(&pm);
                p.setRenderHint(QPainter::Antialiasing);
                QRect r(20, 20, 340, 250);
                p.fillRect(r, QColor(0, 0, 0, 200));
                p.setPen(QColor(0, 255, 120));
                QFont f = p.font(); f.setPointSize(13); f.setBold(true); p.setFont(f);
                p.drawText(r.adjusted(16, 12, -16, -12), Qt::AlignTop | Qt::AlignLeft, helpText);
            }
            view->label()->setPixmap(pm);
            view->setWindowTitle(QString("camview  %1 fps  sharp=%5/%6%2  byte=%3 rb=%4  [B]yte [C]RB [F]ull [P]ause [R]harp [H]elp [Q]uit")
                                     .arg(fps, 0, 'f', 1)
                                     .arg(view->paused() ? "  PAUSED" : "")
                                     .arg(view->byteSwapped() ? 1 : 0)
                                     .arg(view->rbSwapped() ? 1 : 0)
                                     .arg(view->sharpOn() ? 1 : 0)
                                     .arg(view->sharpStrength()));
        });
    QObject::connect(grabber, &Grabber::statusMsg, view, [&app, view](const QString &s) {
        view->label()->setText(s);
        view->setWindowTitle("camview  " + s);
        if (s.startsWith("FATAL:"))
            ::_exit(2);
    });

    view->showFullScreen();
    // [FOCUS] 强制抢键盘焦点: 全屏窗口在 X11 下不保证自动获焦, 键盘接在板上时必须确保焦点
    view->setWindowState(view->windowState() | Qt::WindowActive);
    view->activateWindow();
    view->raise();
    view->setFocus(Qt::OtherFocusReason);
    view->setAttribute(Qt::WA_ShowWithoutActivating, false);

    // 周期性重申焦点(有人误点桌面/别的窗口时自动夺回, 保证热键随时可用)
    QTimer focusTimer;
    QObject::connect(&focusTimer, &QTimer::timeout, [view]() {
        if (!view->isActiveWindow()) {
            view->activateWindow();
            view->raise();
            view->setFocus(Qt::OtherFocusReason);
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
