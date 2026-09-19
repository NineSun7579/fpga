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
#include <QKeyEvent>
#include <QLabel>
#include <QMutex>
#include <QPainter>
#include <QPushButton>
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
static const uint32_t CAM_B_ADDR_1 = 0x00C00000u;
static const uint32_t CAM_B_ADDR_2 = 0x00E00000u;
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
    int nc = 1;
    bool xyxy = false;
};

static QVector<ModelInfo> scanModels() {
    QVector<ModelInfo> list;
    const QStringList dirs = {"/root/npu", "/root/npu/yolo11n", "/root/models/yolo26_rk3568",
                              "/root/npu/tt100k"};
    for (const QString &d : dirs) {
        QDir dir(d);
        const QStringList files = dir.entryList(QStringList() << "*.rknn", QDir::Files, QDir::Name);
        for (const QString &f : files) {
            ModelInfo mi;
            mi.path = dir.absoluteFilePath(f);
            const QString lower = f.toLower();
            if (lower.contains("tt100k")) {
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
    void setMode(int mode) { m_mode = mode; }
    void setPaused(bool paused) { m_paused = paused; }

signals:
    void frameReady(QImage display, QImage infer, double fps);
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

        QByteArray rawA(FRAME_BYTES, 0), rawB(FRAME_BYTES, 0);
        QByteArray rgbA(IMG_W * IMG_H * 3, 0), rgbB(IMG_W * IMG_H * 3, 0);
        int buf = 0;
        int frames = 0;
        double fps = 0;
        QElapsedTimer timer;
        timer.start();
        while (!m_stop) {
            const int mode = m_mode.load();
            if (mode == 0 || mode == 2) {
                const uint32_t addr = (buf == 0) ? CAM_ADDR_1 : CAM_ADDR_2;
                if (!dev.ddrRead(addr, FRAME_BYTES, rawA.data())) {
                    msleep(10);
                    continue;
                }
                dev.regWrite(R_ACK, 1u << buf);
                rgb565ToRgb888((const uint8_t *)rawA.constData(), IMG_W * IMG_H,
                               (uint8_t *)rgbA.data());
            }
            if (mode == 1 || mode == 2) {
                const uint32_t addrB = (buf == 0) ? CAM_B_ADDR_1 : CAM_B_ADDR_2;
                dev.ddrRead(addrB, FRAME_BYTES, rawB.data());
                rgb565ToRgb888((const uint8_t *)rawB.constData(), IMG_W * IMG_H,
                               (uint8_t *)rgbB.data());
            }
            QImage left((const uchar *)rgbA.constData(), IMG_W, IMG_H, IMG_W * 3,
                        QImage::Format_RGB888);
            QImage right((const uchar *)rgbB.constData(), IMG_W, IMG_H, IMG_W * 3,
                         QImage::Format_RGB888);
            QImage display;
            QImage infer;
            if (mode == 2) {
                display = QImage(2 * IMG_W, IMG_H, QImage::Format_RGB888);
                QPainter painter(&display);
                painter.drawImage(0, 0, left);
                painter.drawImage(IMG_W, 0, right);
                painter.end();
                infer = left;
            } else if (mode == 1) {
                display = right;
                infer = right;
            } else {
                display = left;
                infer = left;
            }
            frames++;
            if (m_paused.load()) {
                buf ^= 1;
                msleep(25);
                continue;
            }
            const double el = timer.elapsed() / 1000.0;
            if (el >= 0.5) {
                fps = frames / el;
                frames = 0;
                timer.restart();
            }
            emit frameReady(display.copy(), infer.copy(), fps);
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
    std::atomic<int> m_mode{2};
    std::atomic<bool> m_paused{false};
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
    void setModel(const ModelInfo &info) {
        QMutexLocker lock(&m_mutex);
        m_model = info;
        m_modelChanged = true;
        m_cond.wakeOne();
    }
    void setFormat(bool xyxy) {
        QMutexLocker lock(&m_mutex);
        m_xyxy = xyxy;
    }
    void setConf(float c) { m_conf.store(c); }
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
            const ModelInfo info = m_model;
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
                QFile file(info.path);
                if (!file.open(QIODevice::ReadOnly)) {
                    emit modelLoaded(info.path, false, "open failed");
                    continue;
                }
                modelBuf = file.readAll();
                file.close();
                int ret = rknn_init(&m_ctx, modelBuf.data(), (uint32_t)modelBuf.size(), 0, nullptr);
                if (ret != 0) {
                    m_ctx = 0;
                    emit modelLoaded(info.path, false, QString("rknn_init %1").arg(ret));
                    continue;
                }
                rknn_input_output_num ioNum;
                memset(&ioNum, 0, sizeof(ioNum));
                if (rknn_query(m_ctx, RKNN_QUERY_IN_OUT_NUM, &ioNum, sizeof(ioNum)) != 0) {
                    emit modelLoaded(info.path, false, "query failed");
                    continue;
                }
                m_nOutput = ioNum.n_output;
                m_nc = info.nc;
                m_xyxy = info.xyxy;
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
                emit modelLoaded(info.path, true, shapes.trimmed());
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
        const float confThresh = m_conf.load();
        if (outs.empty())
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

        struct Cand {
            float score, x1, y1, x2, y2;
            int cls;
        };
        std::vector<Cand> cands;
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
    ModelInfo m_model;
    int m_nc = 1;
    bool m_xyxy = false;
    std::atomic<float> m_conf{0.25f};
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
        const double s = target.width() / (double)m_frame.width();
        for (const Detection &d : m_dets) {
            const double x1 = d.x1 * s;
            const double x2 = d.x2 * s;
            const double y1 = (d.y1 - 80.0) * s;
            const double y2 = (d.y2 - 80.0) * s;
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
        m_fmtCombo = new QComboBox(this);
        m_fmtCombo->addItem("cxcywh");
        m_fmtCombo->addItem("xyxy");
        m_camCombo = new QComboBox(this);
        m_camCombo->addItem("L");
        m_camCombo->addItem("R");
        m_camCombo->addItem("Both");
        m_camCombo->setCurrentIndex(2);
        m_confSlider = new QSlider(Qt::Horizontal, this);
        m_confSlider->setRange(5, 95);
        m_confSlider->setValue(25);
        m_confSlider->setFixedWidth(150);
        m_confSlider->setToolTip("置信度阈值");
        m_confLabel = new QLabel("Conf 0.25", this);
        m_shotBtn = new QPushButton("截屏", this);
        bar->addWidget(new QLabel("Model:", this));
        bar->addWidget(m_combo, 1);
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
        root->addWidget(m_status);
        m_helpLabel = new QLabel(
            "快捷键:  1-9 切换模型 | C 切换框格式(cxcywh/xyxy) | V 切换相机(L/R/Both) | "
            "+/- 置信度 | S 截屏 | P/空格 暂停 | F 全屏 | H 帮助 | Q/Esc 退出",
            this);
        m_helpLabel->setStyleSheet("background:#111; color:#0f0; font:13px monospace; padding:4px;");
        m_helpLabel->setWordWrap(true);
        m_helpLabel->setVisible(false);
        root->addWidget(m_helpLabel);
        setFocusPolicy(Qt::StrongFocus);

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
        connect(m_camCombo, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
                &MainWindow::onCamChanged);
        connect(m_fmtCombo, QOverload<int>::of(&QComboBox::currentIndexChanged), this,
                &MainWindow::onFormatChanged);
        connect(m_confSlider, &QSlider::valueChanged, this, &MainWindow::onConfChanged);
        connect(m_shotBtn, &QPushButton::clicked, this, &MainWindow::onScreenshot);
        m_infer->start();
        m_camera->start();
        if (!models.isEmpty())
            onModelChanged(0);
        setWindowTitle("detview - OV5640 + RKNN");
        resize(1280, 800);
    }
    ~MainWindow() override {
        m_camera->stop();
        m_camera->wait(2000);
        m_infer->stop();
    }

    void setModelIndex(int index) {
        if (index >= 0 && index < m_models.size())
            m_combo->setCurrentIndex(index);
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
            m_camCombo->setCurrentIndex((m_camCombo->currentIndex() + 1) % 3);
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
    void onFrame(QImage display, QImage infer, double fps) {
        m_video->setFrame(display);
        m_camLabel->setText(QString("cam: %1 fps").arg(fps, 0, 'f', 1));
        m_infer->submit(infer);
    }
    void onCamChanged(int index) { m_camera->setMode(index); }
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
        m_fmtCombo->blockSignals(true);
        m_fmtCombo->setCurrentIndex(m_models[index].xyxy ? 1 : 0);
        m_fmtCombo->blockSignals(false);
        m_infer->setModel(m_models[index]);
        m_infer->setFormat(m_models[index].xyxy);
        setWindowTitle(QString("detview - %1").arg(QFileInfo(m_models[index].path).fileName()));
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
    const QStringList args = app.arguments();
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
    w.show();
    return app.exec();
}

#include "main.moc"
