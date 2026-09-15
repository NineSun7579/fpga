// detview - OV5640 live detection UI for RK3568 + Pango FPGA + RKNN
// Cam path: OV5640 -> DDR3 ping-pong (0x00800000/0x00A00000, RGB565 640x480)
//           -> PCIe DMA read -> letterbox 640x640 -> RKNN model
#include <QApplication>
#include <QComboBox>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QImage>
#include <QLabel>
#include <QMutex>
#include <QPainter>
#include <QPushButton>
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
#include <fcntl.h>
#include <memory>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <vector>

#include "rknn_api.h"

static const int IMG_W = 640;
static const int IMG_H = 480;
static const size_t FRAME_BYTES = (size_t)IMG_W * IMG_H * 2;
static const uint32_t CAM_ADDR_1 = 0x00800000u;
static const uint32_t CAM_ADDR_2 = 0x00A00000u;
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
};

static QVector<ModelInfo> scanModels() {
    QVector<ModelInfo> list;
    const QStringList dirs = {"/root/npu", "/root/models/yolo26_rk3568"};
    for (const QString &d : dirs) {
        QDir dir(d);
        const QStringList files = dir.entryList(QStringList() << "*.rknn", QDir::Files, QDir::Name);
        for (const QString &f : files) {
            ModelInfo mi;
            mi.path = dir.absoluteFilePath(f);
            if (f.contains("zebra"))
                mi.classes = QStringList() << "zebra"
                                           << "vehicle"
                                           << "person";
            else
                mi.classes = QStringList() << "vehicle";
            list.append(mi);
        }
    }
    return list;
}

class PangoDev {
public:
    ~PangoDev() { close(); }

    bool openDev() {
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
        DmaOp op{};
        op.offset_addr = 0;
        op.ddr3_addr = addr;
        op.total_length = 16;
        if (ioctlTmo(F2H_CMD, &op, 3) != 0)
            return false;
        memcpy(&val, rx_, 4);
        return true;
    }

    bool ddrRead(uint32_t addr, uint32_t len, void *out) {
        DmaOp op{};
        op.offset_addr = 0;
        op.ddr3_addr = addr;
        op.total_length = len;
        if (ioctlTmo(F2H_CMD, &op, 4) != 0)
            return false;
        memcpy(out, rx_, len);
        return true;
    }

    const char *lastErr() const { return err_; }

private:
    int ioctlTmo(unsigned long cmd, DmaOp *op, unsigned sec) {
        timeoutHit_ = false;
        struct sigaction sa{}, old{};
        sa.sa_handler = &PangoDev::alarmHandler;
        sigaction(SIGALRM, &sa, &old);
        alarm(sec);
        int r = ::ioctl(fd_, cmd, op);
        alarm(0);
        sigaction(SIGALRM, &old, nullptr);
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
};

volatile sig_atomic_t PangoDev::timeoutHit_ = 0;

class CameraThread : public QThread {
    Q_OBJECT
public:
    void stop() { m_stop = true; }

signals:
    void frameReady(QImage img, double fps);
    void statusMsg(QString s);

protected:
    void run() override {
        PangoDev dev;
        if (!dev.openDev()) {
            emit statusMsg(QString("FATAL: ") + dev.lastErr());
            return;
        }
        uint32_t rb = 0;
        dev.regWrite(R_ADDR1, CAM_ADDR_1);
        dev.regRead(R_ADDR1, rb);
        QString st = (rb == CAM_ADDR_1) ? "reg-OK; " : "reg-warn; ";
        uint32_t id = 0;
        dev.regRead(R_I2C_ID, id);
        st += QString("camID=%1%2 nack=%3")
                  .arg((id >> 8) & 0xFF, 2, 16, QChar('0'))
                  .arg(id & 0xFF, 2, 16, QChar('0'))
                  .arg(id >> 16);
        emit statusMsg(st);

        dev.regWrite(R_ADDR1, CAM_ADDR_1);
        dev.regWrite(R_ADDR2, CAM_ADDR_2);
        dev.regWrite(R_ACK, 3);
        dev.regWrite(R_CAM_EN, 1);

        QByteArray raw(FRAME_BYTES, 0);
        QByteArray rgb(IMG_W * IMG_H * 3, 0);
        int buf = 0;
        int frames = 0;
        double fps = 0;
        QElapsedTimer timer;
        timer.start();
        while (!m_stop) {
            const uint32_t addr = (buf == 0) ? CAM_ADDR_1 : CAM_ADDR_2;
            if (!dev.ddrRead(addr, FRAME_BYTES, raw.data())) {
                msleep(10);
                continue;
            }
            dev.regWrite(R_ACK, 1u << buf);
            rgb565ToRgb888((const uint8_t *)raw.constData(), IMG_W * IMG_H, (uint8_t *)rgb.data());
            QImage img((const uchar *)rgb.constData(), IMG_W, IMG_H, IMG_W * 3,
                       QImage::Format_RGB888);
            frames++;
            const double el = timer.elapsed() / 1000.0;
            if (el >= 0.5) {
                fps = frames / el;
                frames = 0;
                timer.restart();
            }
            emit frameReady(img.copy(), fps);
            buf ^= 1;
            msleep(25);
        }
    }

private:
    static void rgb565ToRgb888(const uint8_t *src, size_t pixels, uint8_t *dst) {
        const uint16_t *s = reinterpret_cast<const uint16_t *>(src);
        for (size_t i = 0; i < pixels; i++) {
            const uint16_t v = s[i];
            const uint8_t r5 = (v >> 11) & 0x1F;
            const uint8_t g6 = (v >> 5) & 0x3F;
            const uint8_t b5 = v & 0x1F;
            dst[3 * i + 0] = (r5 << 3) | (r5 >> 2);
            dst[3 * i + 1] = (g6 << 2) | (g6 >> 4);
            dst[3 * i + 2] = (b5 << 3) | (b5 >> 2);
        }
    }
    std::atomic<bool> m_stop{false};
};

class InferenceThread : public QThread {
    Q_OBJECT
public:
    InferenceThread(QObject *parent = nullptr) : QThread(parent) {}

    void submit(const QImage &img) {
        QMutexLocker lock(&m_mutex);
        m_pending = img;
        m_hasPending = true;
        m_cond.wakeOne();
    }
    void setModel(const QString &path) {
        QMutexLocker lock(&m_mutex);
        m_modelPath = path;
        m_modelChanged = true;
        m_cond.wakeOne();
    }
    void stop() {
        m_stop = true;
        m_cond.wakeOne();
        wait(2000);
    }

signals:
    void detectionsReady(QVector<Detection> dets, double inferFps, double inferMs);
    void modelLoaded(QString path, bool ok, QString info);

protected:
    void run() override {
        QByteArray modelBuf;
        while (!m_stop) {
            QMutexLocker lock(&m_mutex);
            if (!m_hasPending && !m_modelChanged && !m_stop)
                m_cond.wait(&m_mutex, 200);
            if (m_stop)
                break;
            const bool reload = m_modelChanged;
            const QString path = m_modelPath;
            QImage frame;
            if (m_hasPending) {
                frame = m_pending;
                m_hasPending = false;
            }
            m_modelChanged = false;
            lock.unlock();

            if (reload) {
                if (m_ctx) {
                    rknn_destroy(m_ctx);
                    m_ctx = 0;
                }
                QFile file(path);
                if (!file.open(QIODevice::ReadOnly)) {
                    emit modelLoaded(path, false, "open failed");
                    continue;
                }
                modelBuf = file.readAll();
                file.close();
                int ret = rknn_init(&m_ctx, modelBuf.data(), (uint32_t)modelBuf.size(), 0, nullptr);
                if (ret != 0) {
                    m_ctx = 0;
                    emit modelLoaded(path, false, QString("rknn_init %1").arg(ret));
                    continue;
                }
                rknn_input_output_num ioNum;
                memset(&ioNum, 0, sizeof(ioNum));
                if (rknn_query(m_ctx, RKNN_QUERY_IN_OUT_NUM, &ioNum, sizeof(ioNum)) != 0) {
                    emit modelLoaded(path, false, "query failed");
                    continue;
                }
                m_nOutput = ioNum.n_output;
                QString shapes;
                for (uint32_t i = 0; i < m_nOutput && i < 4; i++) {
                    rknn_tensor_attr attr;
                    memset(&attr, 0, sizeof(attr));
                    attr.index = i;
                    if (rknn_query(m_ctx, RKNN_QUERY_OUTPUT_ATTR, &attr, sizeof(attr)) == 0) {
                        shapes += "[";
                        for (uint32_t d = 0; d < attr.n_dims; d++)
                            shapes += QString("%1%2").arg(d ? "," : "").arg(attr.dims[d]);
                        shapes += "] ";
                    }
                }
                emit modelLoaded(path, true, shapes.trimmed());
            }
            if (!frame.isNull() && m_ctx)
                runOnce(frame);
        }
        if (m_ctx) {
            rknn_destroy(m_ctx);
            m_ctx = 0;
        }
    }

private:
    void runOnce(const QImage &src) {
        const QImage rgb = src.convertToFormat(QImage::Format_RGB888);
        // letterbox 640x480 -> 640x640 (vertical pad, gray 114)
        if (m_input.size() != (int)MODEL_SIZE)
            m_input.resize((int)MODEL_SIZE);
        memset(m_input.data(), 114, 80 * MODEL_W * 3);
        const int copyBytes = IMG_W * 3;
        const uint8_t *sp = rgb.constBits();
        uint8_t *dp = (uint8_t *)m_input.data() + 80 * copyBytes;
        for (int y = 0; y < IMG_H; y++)
            memcpy(dp + y * copyBytes, sp + y * IMG_W * 3, copyBytes);
        memset((uint8_t *)m_input.data() + (80 + IMG_H) * copyBytes, 114,
               (MODEL_H - 80 - IMG_H) * copyBytes);

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
        QVector<Detection> dets = decode(outs, attrs);
        rknn_outputs_release(m_ctx, m_nOutput, outs.data());
        const double ms = timer.elapsed();
        m_accMs += ms;
        m_accCount++;
        if (m_accCount >= 10) {
            m_inferMs = m_accMs / m_accCount;
            m_inferFps = m_inferMs > 0 ? 1000.0 / m_inferMs : 0.0;
            m_accMs = 0;
            m_accCount = 0;
        }
        emit detectionsReady(dets, m_inferFps, m_inferMs);
    }

    static float sigmoidf(float x) { return 1.0f / (1.0f + std::exp(-x)); }

    QVector<Detection> decode(const std::vector<rknn_output> &outs,
                              const std::vector<rknn_tensor_attr> &attrs) {
        QVector<Detection> dets;
        if (outs.empty())
            return dets;
        const float *boxData = nullptr;
        int boxN = 0;
        const float *combined = nullptr;
        int combinedC = 0, combinedN = 0;
        std::vector<const float *> clsData;
        std::vector<int> clsN;
        bool e2e = false;
        int e2eN = 0;

        for (size_t i = 0; i < outs.size(); i++) {
            const uint32_t nDims = attrs[i].n_dims;
            const float *data = (const float *)outs[i].buf;
            if (nDims == 3 && attrs[i].dims[2] == 6) {
                e2e = true;
                e2eN = attrs[i].dims[1];
                boxData = data;
                continue;
            }
            if (nDims == 3 && attrs[i].dims[1] == 4) {
                boxData = data;
                boxN = attrs[i].dims[2];
            } else if (nDims == 3 && attrs[i].dims[1] > 4) {
                combined = data;
                combinedC = attrs[i].dims[1];
                combinedN = attrs[i].dims[2];
            } else if (nDims == 3) {
                clsData.push_back(data);
                clsN.push_back(attrs[i].dims[2]);
            }
        }
        if (!e2e && combined && combinedC > 4) {
            boxData = combined;
            boxN = combinedN;
            clsData.clear();
            clsN.clear();
            clsData.push_back(combined + (size_t)4 * combinedN);
            clsN.push_back(combinedN);
        }
        if (e2e && boxData) {
            for (int i = 0; i < e2eN; i++) {
                const float *r = boxData + (size_t)i * 6;
                if (r[4] < CONF_THRESH)
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
        if (!boxData || boxN <= 0 || clsData.empty())
            return dets;

        bool sigmoid = false;
        {
            const float *c0 = clsData[0];
            float mx = -1e9f, mn = 1e9f;
            for (int i = 0; i < clsN[0] && i < 1000; i++) {
                mx = std::max(mx, c0[i]);
                mn = std::min(mn, c0[i]);
            }
            sigmoid = (mx > 1.5f || mn < -0.5f);
        }

        struct Cand {
            float score, x1, y1, x2, y2;
            int cls;
        };
        std::vector<Cand> cands;
        for (int i = 0; i < boxN; i++) {
            float best = -1.0f;
            int bestCls = -1;
            for (size_t k = 0; k < clsData.size(); k++) {
                if (i >= clsN[k])
                    continue;
                float s = clsData[k][(size_t)i];
                if (sigmoid)
                    s = sigmoidf(s);
                if (s > best) {
                    best = s;
                    bestCls = (int)k;
                }
            }
            if (best < CONF_THRESH || bestCls < 0)
                continue;
            const float cx = boxData[i];
            const float cy = boxData[boxN + i];
            const float w = boxData[2 * boxN + i];
            const float h = boxData[3 * boxN + i];
            cands.push_back({best, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, bestCls});
        }
        std::sort(cands.begin(), cands.end(),
                  [](const Cand &a, const Cand &b) { return a.score > b.score; });
        std::vector<bool> removed(cands.size(), false);
        for (size_t i = 0; i < cands.size(); i++) {
            if (removed[i])
                continue;
            const Cand &a = cands[i];
            dets.append({a.cls, a.score, a.x1, a.y1, a.x2, a.y2});
            for (size_t j = i + 1; j < cands.size(); j++) {
                if (removed[j])
                    continue;
                const Cand &b = cands[j];
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
        return dets;
    }

    QMutex m_mutex;
    QWaitCondition m_cond;
    QImage m_pending;
    bool m_hasPending = false;
    bool m_modelChanged = false;
    QString m_modelPath;
    std::atomic<bool> m_stop{false};
    rknn_context m_ctx = 0;
    uint32_t m_nOutput = 0;
    QByteArray m_input;
    double m_inferFps = 0, m_inferMs = 0, m_accMs = 0;
    int m_accCount = 0;
};

class VideoWidget : public QWidget {
    Q_OBJECT
public:
    explicit VideoWidget(QWidget *parent = nullptr) : QWidget(parent) {
        setMinimumSize(640, 480);
        setAutoFillBackground(true);
        QPalette pal = palette();
        pal.setColor(QPalette::Window, Qt::black);
        setPalette(pal);
    }
    void setFrame(const QImage &img) {
        m_frame = img;
        update();
    }
    void setDetections(const QVector<Detection> &dets, const QStringList &classes) {
        m_dets = dets;
        m_classes = classes;
        update();
    }

protected:
    void paintEvent(QPaintEvent *) override {
        QPainter p(this);
        p.fillRect(rect(), Qt::black);
        if (m_frame.isNull())
            return;
        const QSize scaled = m_frame.size().scaled(size(), Qt::KeepAspectRatio);
        const QRect target((width() - scaled.width()) / 2, (height() - scaled.height()) / 2,
                           scaled.width(), scaled.height());
        p.drawImage(target, m_frame);
        const double sx = target.width() / (double)MODEL_W;
        const double sy = target.height() / (double)IMG_H;
        for (const Detection &d : m_dets) {
            const double x1 = d.x1 * sx;
            const double x2 = d.x2 * sx;
            const double y1 = (d.y1 - 80.0) * sy;
            const double y2 = (d.y2 - 80.0) * sy;
            if (y2 < 0 || y1 > target.height())
                continue;
            const QRectF r(target.left() + x1, target.top() + std::max(0.0, y1),
                           std::max(1.0, x2 - x1),
                           std::min((double)target.height(), y2) - std::max(0.0, y1));
            const QColor color =
                d.cls == 0 ? QColor(0, 255, 0) : (d.cls == 1 ? QColor(255, 60, 60) : QColor(255, 220, 0));
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
    }

private:
    QImage m_frame;
    QVector<Detection> m_dets;
    QStringList m_classes;
};

class MainWindow : public QWidget {
    Q_OBJECT
public:
    MainWindow(const QVector<ModelInfo> &models) : m_models(models) {
        auto *root = new QVBoxLayout(this);
        auto *bar = new QHBoxLayout();
        m_combo = new QComboBox(this);
        for (int i = 0; i < models.size(); i++)
            m_combo->addItem(QFileInfo(models[i].path).fileName(), i);
        m_camLabel = new QLabel("cam: -- fps", this);
        m_inferLabel = new QLabel("infer: -- ms / -- fps   dets: --", this);
        m_shotBtn = new QPushButton("截屏", this);
        bar->addWidget(new QLabel("Model:", this));
        bar->addWidget(m_combo, 1);
        bar->addWidget(m_camLabel);
        bar->addWidget(m_inferLabel);
        bar->addWidget(m_shotBtn);
        root->addLayout(bar);
        m_video = new VideoWidget(this);
        root->addWidget(m_video, 1);
        m_status = new QLabel("starting...", this);
        root->addWidget(m_status);

        m_camera = new CameraThread();
        m_infer = new InferenceThread();
        connect(m_camera, &CameraThread::frameReady, this, &MainWindow::onFrame);
        connect(m_camera, &CameraThread::statusMsg, this, [this](QString s) {
            m_status->setText(s);
        });
        connect(m_infer, &InferenceThread::detectionsReady, this, &MainWindow::onDets);
        connect(m_infer, &InferenceThread::modelLoaded, this, &MainWindow::onModelLoaded);
        connect(m_combo, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
                &MainWindow::onModelChanged);
        connect(m_shotBtn, &QPushButton::clicked, this, &MainWindow::onScreenshot);
        m_infer->start();
        m_camera->start();
        if (!models.isEmpty())
            m_infer->setModel(models[0].path);
        setWindowTitle("detview - OV5640 + RKNN");
        resize(1280, 800);
    }
    ~MainWindow() override {
        m_camera->stop();
        m_camera->wait(2000);
        m_infer->stop();
    }

private slots:
    void onFrame(QImage img, double fps) {
        m_video->setFrame(img);
        m_camLabel->setText(QString("cam: %1 fps").arg(fps, 0, 'f', 1));
        m_infer->submit(img);
    }
    void onDets(QVector<Detection> dets, double fps, double ms) {
        m_video->setDetections(dets, m_classes);
        m_inferLabel->setText(QString("infer: %1 ms / %2 fps   dets: %3")
                                  .arg(ms, 0, 'f', 1)
                                  .arg(fps, 0, 'f', 1)
                                  .arg(dets.size()));
    }
    void onModelLoaded(QString path, bool ok, QString info) {
        m_status->setText(QString("%1 -> %2  %3")
                              .arg(QFileInfo(path).fileName())
                              .arg(ok ? "OK" : "FAIL")
                              .arg(info));
    }
    void onModelChanged(int index) {
        if (index < 0 || index >= m_models.size())
            return;
        m_classes = m_models[index].classes;
        m_video->setDetections({}, m_classes);
        m_infer->setModel(m_models[index].path);
        setWindowTitle(QString("detview - %1").arg(QFileInfo(m_models[index].path).fileName()));
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
    QLabel *m_camLabel = nullptr;
    QLabel *m_inferLabel = nullptr;
    QLabel *m_status = nullptr;
    QPushButton *m_shotBtn = nullptr;
    VideoWidget *m_video = nullptr;
    CameraThread *m_camera = nullptr;
    InferenceThread *m_infer = nullptr;
};

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    qRegisterMetaType<QVector<Detection>>("QVector<Detection>");
    const QVector<ModelInfo> models = scanModels();
    MainWindow w(models);
    w.show();
    return app.exec();
}

#include "main.moc"
