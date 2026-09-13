// camview - OV5640 live viewer for RK3568 + Pango FPGA PCIe DMA driver
//
// 数据通路: OV5640 -> DDR3(乒乓 0x00800000/0x00A00000) -> PCIe DMA 读 -> QImage(RGB565) -> 屏幕
// 同步协议: 轮询 +0x38 xdma_req(bit0=addr_1 帧就绪, bit1=addr_2 帧就绪) -> 读帧 -> 写 +0x00 ACK 对应位
// 热键: B=字节序切换  C=红蓝交换  F=全屏  Q=退出
#include <QApplication>
#include <QWidget>
#include <QLabel>
#include <QImage>
#include <QPixmap>
#include <QThread>
#include <QMutex>
#include <QElapsedTimer>
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

#define IMG_W 640
#define IMG_H 480
#define FRAME_BYTES (IMG_W * IMG_H * 2)
#define CAM_ADDR_1 0x00800000u
#define CAM_ADDR_2 0x00A00000u
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
    bool regWrite(uint32_t addr, uint32_t val) {
        memcpy(tx_, &val, 4);
        DmaOp op{}; op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = 16;
        return ioctl(fd_, H2F_CMD, &op) == 0;
    }
    bool regRead(uint32_t addr, uint32_t &val) {
        DmaOp op{}; op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = 16;
        if (ioctl(fd_, F2H_CMD, &op) != 0) return false;
        memcpy(&val, rx_, 4);
        return true;
    }
    bool ddrRead(uint32_t addr, uint32_t len, void *out) {
        DmaOp op{}; op.offset_addr = 0; op.ddr3_addr = addr; op.total_length = len;
        if (ioctl(fd_, F2H_CMD, &op) != 0) return false;
        memcpy(out, rx_, len);
        return true;
    }
    const char *lastErr() const { return err_; }
private:
    const char *err_ = "ok";
    int fd_ = -1;
    uint8_t *tx_ = nullptr, *rx_ = nullptr;
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
    void setRBSwap(bool on)   { QMutexLocker l(&m_); swapC_ = on; }

signals:
    void frameReady(const QImage &img, double fps);
    void statusMsg(const QString &s);

protected:
    void run() override {
        if (!dev_->open()) { emit statusMsg(QString("FATAL: ") + dev_->lastErr()); return; }
        // 自检(仅一次性少量寄存器读): 地址回环 + 相机 SCCB ID
        uint32_t rb = 0;
        dev_->regWrite(R_ADDR1, CAM_ADDR_1);
        dev_->regRead(R_ADDR1, rb);
        QString st = (rb == CAM_ADDR_1) ? "reg-OK; " : "reg-FAIL; ";
        uint32_t id = 0;
        dev_->regRead(R_I2C_ID, id);
        uint32_t idh = (id >> 8) & 0xFF, idl = id & 0xFF, nack = id >> 16;
        st += QString("camID=%1%2 nack=%3")
                  .arg(idh, 2, 16, QChar('0')).arg(idl, 2, 16, QChar('0')).arg(nack);
        if (idh != 0x56 || idl != 0x40) st += " [ID!=5640 查相机/线]";
        emit statusMsg(st);
        // 启动采集: 乒乓地址 -> 全 ACK -> 使能
        dev_->regWrite(R_ADDR1, CAM_ADDR_1);
        dev_->regWrite(R_ADDR2, CAM_ADDR_2);
        dev_->regWrite(R_ACK, 3);
        dev_->regWrite(R_CAM_EN, 1);

        QByteArray bufA(FRAME_BYTES, 0), bufB(FRAME_BYTES, 0);
        QByteArray *cur = &bufA, *nxt = &bufB;
        int frames = 0;
        QElapsedTimer t0; t0.start();
        double fps = 0;
        // [FIX 2026-09-13] 热循环不读任何寄存器: 大量 M01 读会把 FPGA 读通道楔死
        // (楔死后不再 ACK → 引擎两帧后停写 → 画面冻结在 A1/A2 旧帧来回切)。
        // DDR 块读(M00)与 ACK 写(M01 写通道)全天验证稳定 → 固定节拍轮流读两缓冲+读后即 ACK。
        int buf = 0;
        while (run_) {
            uint32_t addr = (buf == 0) ? CAM_ADDR_1 : CAM_ADDR_2;
            if (!dev_->ddrRead(addr, FRAME_BYTES, cur->data())) { msleep(10); continue; }
            // [FREERUN] engine free-runs, no ACK needed (no M01 traffic in hot loop)
            if (paused_) { std::swap(cur, nxt); buf ^= 1; msleep(25); continue; }
            QImage im(reinterpret_cast<const uchar *>(cur->constData()), IMG_W, IMG_H,
                      IMG_W * 2, QImage::Format_RGB16);
            bool sb, sc; { QMutexLocker l(&m_); sb = swapB_; sc = swapC_; }
            QImage out = sc ? im.convertToFormat(QImage::Format_RGB32).rgbSwapped()
                            : (sb ? im.rgbSwapped() : im.copy());
            frames++;
            double el = t0.elapsed() / 1000.0;
            if (el >= 0.5) { fps = frames / el; frames = 0; t0.restart(); }
            emit frameReady(out, fps);
            std::swap(cur, nxt);
            buf ^= 1;
            msleep(25);   // ~40fps 节拍, 与相机帧率匹配, 降低读写碰撞撕裂概率
        }
    }
private:
    PangoDev *dev_;
    std::atomic_bool run_{true};
    bool swapB_ = false, swapC_ = false;
    std::atomic_bool paused_{false};
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
    void toggleByte() { bs_ = !bs_; g_->setByteSwap(bs_); }
    void toggleRB()   { rs_ = !rs_; g_->setRBSwap(rs_); }
    void toggleFull() { full_ = !full_; full_ ? showFullScreen() : showNormal(); }
    void togglePause() { paused_ = !paused_; g_->setPaused(paused_); }
    void toggleScale() { smooth_ = !smooth_; }
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
        default: break;
        }
    }
    void resizeEvent(QResizeEvent *) override { label_->setGeometry(rect()); }

private:
    QLabel *label_;
    Grabber *g_;
    bool full_ = false, bs_ = false, rs_ = false, paused_ = false, smooth_ = false, help_ = false;
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
        "  H         显示 / 隐藏本帮助\n"
        "\n"
        "按 H 关闭帮助";

    QObject::connect(grabber, &Grabber::frameReady,
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
            view->setWindowTitle(QString("camview  %1 fps%2  [F]ull [P]ause [S]cale [B]yte [C]RB [H]elp [Q]uit")
                                     .arg(fps, 0, 'f', 1)
                                     .arg(view->paused() ? "  PAUSED" : ""));
        });
    QObject::connect(grabber, &Grabber::statusMsg, [view](const QString &s) {
        view->label()->setText(s);
        view->setWindowTitle("camview  " + s);
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
