// detview -- OV5640 live viewer + YOLO26n(RK3568 NPU) object detection overlay.
//
// 数据通路: OV5640 -> FPGA DDR3(乒乓 0x00800000/0x00A00000, [FRTAG] 帧尾序号)
//           -> PCIe DMA 读 -> RGB565->RGB888 -> letterbox 640x640 -> RKNN
//           -> QPainter 画框 -> 屏幕
// 撕裂消除: 只读"序号最大"的缓冲(正在写的缓冲序号恒为次大, 读写永不相撞),
//           旧比特流自动退回双读稳定校验(STBL-FALLBACK)。
// 热键: 1-4 切换模型  B 字节序  C 红蓝交换  F 全屏  P 暂停  H 帮助  Q 退出
// 自检: ./detview --selftest [秒] [--model 0..3]  (无窗口, 输出统计 + PPM)
#include <QApplication>
#include <QWidget>
#include <QLabel>
#include <QImage>
#include <QPixmap>
#include <QThread>
#include <QMutex>
#include <QWaitCondition>
#include <QElapsedTimer>
#include <QKeyEvent>
#include <QPainter>
#include <QDir>
#include <QFile>
#include <QTimer>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <vector>
#include <string>

#include "frame_source.h"
#include "preprocess.h"
#include "yolo26_rknn.h"

// ---------------- models ----------------
struct ModelSpec {
    const char *file;
    std::vector<std::string> labels;
};
static const std::vector<ModelSpec> kModels = {
    // [YOLO11n SPLIT 2026-09-14] detection head exported as two outputs
    // (boxes [1,4,8400] + scores [1,nc,8400]) so the INT8 quantization keeps the
    // class-score domain separate (the single-Concat head quantized cls to 0).
    {"zebra_3cls_640_split.rknn",   {"zebra", "vehicle", "person"}},
    {"vehicles_1cls_640_split.rknn",{"vehicle"}},
};
static QString modelPath(int idx) {
    QDir d("/root/ov5640/models");
    if (!d.exists()) d.setPath("models");
    return d.filePath(kModels[(size_t)idx].file);
}
static QString modelShort(int idx) {
    QString f = kModels[(size_t)idx].file;
    return f.replace(".rknn", "");
}
static QColor clsColor(int cls) {
    static const QColor pal[] = {Qt::red, Qt::green, Qt::cyan, Qt::magenta,
                                 Qt::yellow, Qt::blue, Qt::white};
    return pal[cls % 7];
}
static void drawDets(QPainter &p, const std::vector<Det> &dets,
                     const std::vector<std::string> &labels) {
    p.setRenderHint(QPainter::Antialiasing);
    for (const Det &d : dets) {
        QRectF r(QPointF(d.x1, d.y1), QPointF(d.x2, d.y2));
        p.setPen(QPen(clsColor(d.cls), 2.5));
        p.setBrush(Qt::NoBrush);
        p.drawRect(r);
        QString tag = QString("%1 %2%")
                          .arg(d.cls >= 0 && (size_t)d.cls < labels.size()
                                   ? QString::fromStdString(labels[(size_t)d.cls])
                                   : QString::number(d.cls))
                          .arg((int)(d.score * 100));
        QFont f = p.font(); f.setPointSize(12); f.setBold(true); p.setFont(f);
        QRect tr = p.boundingRect(QRect(), 0, tag);
        tr.moveTopLeft(QPoint((int)d.x1, (int)d.y1 - tr.height() - 2 < 0
                                             ? (int)d.y1 + 2 : (int)d.y1 - tr.height() - 2));
        p.fillRect(tr, QColor(0, 0, 0, 180));
        p.setPen(clsColor(d.cls));
        p.drawText(tr, 0, tag);
    }
}
static bool savePpm(const QImage &im, const QString &path) {
    QImage rgb = im.convertToFormat(QImage::Format_RGB888);
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly)) return false;
    f.write(QString("P6\n%1 %2\n255\n").arg(rgb.width()).arg(rgb.height()).toUtf8());
    for (int y = 0; y < rgb.height(); ++y)
        f.write((const char *)rgb.constScanLine(y), rgb.width() * 3);
    return true;
}

// ---------------- latest-frame slot (source thread -> infer thread) ----------
class LatestFrame {
public:
    void push(const QImage &im, quint64 id) {
        QMutexLocker l(&m_);
        img_ = im; id_ = id;
        cv_.wakeAll();
    }
    bool take(QImage &out, quint64 &seen, unsigned long ms) {
        QMutexLocker l(&m_);
        if (id_ == seen) cv_.wait(&m_, ms);
        if (id_ == seen) return false;      // nothing newer (drops stale frames)
        out = img_; seen = id_;
        return true;
    }
    void wake() { QMutexLocker l(&m_); cv_.wakeAll(); }
private:
    QMutex m_; QWaitCondition cv_;
    QImage img_; quint64 id_ = 0;
};

// ---------------- inference worker ----------------
class InferWorker : public QThread {
    Q_OBJECT
public:
    LatestFrame latest;
    void requestModel(int idx) { QMutexLocker l(&m_); req_ = idx; }
    // [CONF] detection score threshold (adjustable at runtime with [ / ])
    void setConf(float c) { if (c < 0.0f) c = 0.0f; if (c > 0.95f) c = 0.95f; conf_.store(c); }
    float conf() const { return conf_.load(); }
    void snapshot(std::vector<Det> &out, QString &info, std::vector<std::string> &labels) {
        QMutexLocker l(&m_);
        out = results_; info = info_; labels = labels_;
    }
    void stop() { run_ = false; latest.wake(); wait(4000); }
    QString loadError() const { QMutexLocker l(&m_); return loadErr_; }

protected:
    void run() override {
        Yolo26Rknn net;
        int cur = -1;
        quint64 seen = 0;
        std::vector<uint8_t> lb;
        while (run_) {
            int req;
            { QMutexLocker l(&m_); req = req_; }
            if (req != cur) {
                std::string err;
                if (cur >= 0) { net.unload(); cur = -1; }
                if (net.load(modelPath(req).toStdString(), err)) {
                    net.setNumClasses((int)kModels[(size_t)req].labels.size());
                    cur = req;
                    lb.resize((size_t)net.modelW() * net.modelH() * 3);
                    QMutexLocker l(&m_); loadErr_.clear();
                } else {
                    QMutexLocker l(&m_);
                    loadErr_ = QString("model load failed: %1").arg(QString::fromStdString(err));
                    info_ = QString("MODEL LOAD FAILED: %1").arg(QString::fromStdString(err));
                    emit statusMsg(loadErr_);
                    msleep(1000);
                    continue;
                }
            }
            QImage img;
            if (!latest.take(img, seen, 200)) continue;
            if (img.format() != QImage::Format_RGB888) img = img.convertToFormat(QImage::Format_RGB888);

            int yPad = 0;
            bool geomOk = (img.width() == prep::CAM_W) && net.modelW() == prep::CAM_W;
            if (geomOk)
                yPad = prep::letterboxCamToModel(img.constBits(), lb.data(),
                                                 net.modelW(), net.modelH());
            const float conf = conf_.load();
            std::vector<Det> dets = net.infer(lb.data(), conf, 0.45f);
            // model space -> camera space (x unchanged, y minus top pad), clamp
            for (Det &d : dets) {
                d.y1 -= (float)yPad; d.y2 -= (float)yPad;
                d.x1 = std::min(std::max(d.x1, 0.0f), (float)prep::CAM_W - 1);
                d.x2 = std::min(std::max(d.x2, 0.0f), (float)prep::CAM_W - 1);
                d.y1 = std::min(std::max(d.y1, 0.0f), (float)prep::CAM_H - 1);
                d.y2 = std::min(std::max(d.y2, 0.0f), (float)prep::CAM_H - 1);
            }
            QString info;
            if (!geomOk)
                info = QString("geometry mismatch %1x%2").arg(img.width()).arg(img.height());
            else
                info = QString("%1 %2 %3ms  conf %4  max %5")
                           .arg(modelShort(cur).section('_', 0, 0),
                                net.split() ? "split" : (net.e2e() ? "e2e" : "std"))
                           .arg(net.lastInferMs(), 0, 'f', 1)
                           .arg(conf, 0, 'f', 2)
                           .arg(net.lastScoreMax(), 0, 'f', 2);
            { QMutexLocker l(&m_); results_ = dets; info_ = info; labels_ = kModels[(size_t)cur].labels; }
        }
    }
signals:
    void statusMsg(const QString &s);

private:
    std::atomic_bool run_{true};
    int req_ = 0;
    std::atomic<float> conf_{0.10f};   // [CONF] default lowered from 0.25
    mutable QMutex m_;
    std::vector<Det> results_;
    QString info_, loadErr_;
    std::vector<std::string> labels_;
};

// ---------------- GUI ----------------
class View : public QWidget {
public:
    View(FrameSource *src, InferWorker *inf) : src_(src), inf_(inf) {
        label_ = new QLabel(this);
        label_->setAlignment(Qt::AlignCenter);
        label_->setStyleSheet("background:black; color:#0f0; font:14px monospace;");
        setWindowTitle("detview");
        resize(1280, 720);
    }
    QLabel *label() const { return label_; }
    bool byteSwapped() const { return bs_; }
    void toggleByte() { bs_ = !bs_; src_->setByteSwap(bs_); }
    void toggleRB()   { rs_ = !rs_; src_->setRBSwap(rs_); }
    void toggleFull() { full_ = !full_; full_ ? showFullScreen() : showNormal(); }
    void togglePause(){ paused_ = !paused_; src_->setPaused(paused_); }
    void setHelp(bool on) { help_ = on; }
    bool help() const { return help_; }
    int model() const { return model_; }
    void drawFrame(const QImage &img, double fps, quint32 fid) {
        lastImg_ = img;
        std::vector<Det> dets; QString info; std::vector<std::string> labels;
        inf_->snapshot(dets, info, labels);
        curLabels_ = labels;
        QImage ann = lastImg_;
        {
            QPainter p(&ann);
            drawDets(p, dets, curLabels_);
            // [HUD] two lines so the model/score segment can never be clipped by
            // the window edge (the old single line ran off-screen).
            p.setPen(Qt::NoPen); p.fillRect(QRect(0, 0, ann.width(), 46), QColor(0,0,0,175));
            p.setPen(QColor(0, 255, 120));
            QFont f = p.font(); f.setPointSize(11); f.setBold(true); p.setFont(f);
            p.drawText(8, 17, QString("detview  %1fps  |  %2  |  frame#%3  |  obj %4")
                       .arg(fps, 0, 'f', 1).arg(src_->syncMode()).arg(fid).arg(dets.size()));
            p.drawText(8, 38, info.isEmpty() ? QString("(no inference yet)") : info);
            if (help_) {
                f.setPointSize(12); p.setFont(f);
                QRect hr(10, 40, 360, 220);
                p.fillRect(hr, QColor(0, 0, 0, 200));
                p.setPen(QColor(0, 255, 120));
                p.drawText(hr.adjusted(10, 8, -10, -8), Qt::AlignTop | Qt::AlignLeft, kHelp);
            }
        }
        QPixmap pm = QPixmap::fromImage(ann).scaled(
            label_->size(), Qt::KeepAspectRatio, Qt::FastTransformation);
        label_->setPixmap(pm);
        setWindowTitle(QString("detview  %1fps  [1-2]model [ [ ] ]conf(%3) [B]byte [C]RB [F]ull [P]ause [H]elp [Q]uit%2")
                       .arg(fps, 0, 'f', 1).arg(paused_ ? "  PAUSED" : "")
                       .arg(inf_->conf(), 0, 'f', 2));
    }

protected:
    void keyPressEvent(QKeyEvent *e) override {
        switch (e->key()) {
        case Qt::Key_Q: case Qt::Key_Escape: close(); break;
        case Qt::Key_F: toggleFull(); break;
        case Qt::Key_B: toggleByte(); break;
        case Qt::Key_C: toggleRB(); break;
        case Qt::Key_P: case Qt::Key_Space: togglePause(); break;
        case Qt::Key_H: help_ = !help_; break;
        case Qt::Key_1: case Qt::Key_2: case Qt::Key_3: case Qt::Key_4: case Qt::Key_5: case Qt::Key_6: {
            int idx = e->key() - Qt::Key_1;
            if (idx >= (int)kModels.size()) idx = (int)kModels.size() - 1;
            model_ = idx;
            inf_->requestModel(model_);
            break; }
        case Qt::Key_BracketLeft:  case Qt::Key_Minus:
            inf_->setConf(inf_->conf() - 0.05f); break;
        case Qt::Key_BracketRight: case Qt::Key_Equal:
            inf_->setConf(inf_->conf() + 0.05f); break;
        default: break;
        }
    }
    void resizeEvent(QResizeEvent *) override { label_->setGeometry(rect()); }

private:
    static inline const QString kHelp =
        "1-2 切换模型(zebra / vehicles, YOLO11n split)\n"
        "[ 调低置信度   ] 调高置信度\n"
        "B 字节序   C 红蓝交换\n"
        "F 全屏  P 暂停  H 帮助  Q 退出";
    QLabel *label_;
    FrameSource *src_;
    InferWorker *inf_;
    QImage lastImg_;
    std::vector<std::string> curLabels_;
    bool full_ = false, bs_ = false, rs_ = false, paused_ = false, help_ = false;
    int model_ = 0;
};

// ---------------- selftest ----------------
// [PROBE] generic model probe: load any .rknn, run on a synthetic input, report
// raw + float output statistics. Used to isolate device-side op behaviour
// (e.g. "does Sigmoid output zero on this NPU?").
static int probeMain(const char *modelPath) {
    int argc = 1;
    char arg0[] = "detview";
    char *argv[] = { arg0, nullptr };
    QApplication app(argc, argv);
    std::string err;
    Yolo26Rknn net;
    if (!net.load(modelPath, err)) { printf("PROBE FAIL: %s\n", err.c_str()); return 1; }
    int w = net.modelW(), h = net.modelH();
    printf("model=%s input=%dx%d e2e=%d nc=%d\n", modelPath, w, h, net.e2e() ? 1 : 0, net.numClasses());
    std::vector<uint8_t> dummy((size_t)w * h * 3, 128);
    std::vector<Det> d = net.infer(dummy.data(), 0.5f, 0.5f);
    printf("detections_at_0.5=%zu\n", d.size());
    for (const Det &x : d) printf("  cls=%d score=%.4f box=(%.1f,%.1f)-(%.1f,%.1f)\n", x.cls, x.score, x.x1, x.y1, x.x2, x.y2);
    printf("PROBE DONE\n");
    return 0;
}

static int selftestMain(int argc, char **argv, int secs, int modelIdx, const char *imgPath) {
    QApplication app(argc, argv);       // QImage/QPainter need the gui stack
    FrameSource src;
    InferWorker inf;
    inf.requestModel(modelIdx);
    // --image <ppm>: single-shot inference on a still image (decode verification)
    if (imgPath) {
        std::string err2;
        Yolo26Rknn net;
        if (!net.load(modelPath(modelIdx).toStdString(), err2)) {
            printf("SELFTEST FAIL: %s\n", err2.c_str()); return 1; }
        net.setNumClasses((int)kModels[(size_t)modelIdx].labels.size());
        QImage img(imgPath);
        if (img.isNull()) { printf("SELFTEST FAIL: cannot load %s\n", imgPath); return 1; }
        img = img.convertToFormat(QImage::Format_RGB888);
        printf("model: %s mode=%s nc=%d\n", modelShort(modelIdx).toUtf8().constData(),
               net.e2e() ? "e2e" : "std", net.numClasses());
        if (net.modelW() != img.width()) {
            img = img.scaled(net.modelW(), img.height() * net.modelW() / img.width(),
                             Qt::IgnoreAspectRatio, Qt::SmoothTransformation)
                     .convertToFormat(QImage::Format_RGB888);
        }
        // letterbox to model height (reuse camera path: pad top/bottom)
        QImage canvas(net.modelW(), net.modelH(), QImage::Format_RGB888);
        canvas.fill(0);
        int yOff = (net.modelH() - img.height()) / 2;
        for (int y = 0; y < img.height(); ++y)
            memcpy(canvas.scanLine(yOff + y), img.constScanLine(y), (size_t)img.width() * 3);
        std::vector<uint8_t> lb(canvas.constBits(), canvas.constBits() + (size_t)canvas.sizeInBytes());
        std::vector<Det> dets = net.infer(lb.data(), 0.25f, 0.45f);
        for (Det &d : dets) {
            d.y1 -= (float)yOff; d.y2 -= (float)yOff;
            d.x1 = std::min(std::max(d.x1, 0.0f), (float)prep::CAM_W - 1);
            d.x2 = std::min(std::max(d.x2, 0.0f), (float)prep::CAM_W - 1);
            d.y1 = std::min(std::max(d.y1, 0.0f), (float)prep::CAM_H - 1);
            d.y2 = std::min(std::max(d.y2, 0.0f), (float)prep::CAM_H - 1);
        }
        printf("image inference: %zu box(es)\n", dets.size());
        for (const Det &d : dets)
            printf("  cls=%d score=%.2f box=(%.0f,%.0f)-(%.0f,%.0f)\n",
                   d.cls, d.score, d.x1, d.y1, d.x2, d.y2);
        QPainter p(&img);
        drawDets(p, dets, kModels[(size_t)modelIdx].labels);
        savePpm(img, "/root/ov5640/detview_image_test.ppm");
        savePpm(img.scaled(320, 240, Qt::KeepAspectRatio, Qt::FastTransformation),
                "/root/ov5640/detview_image_test_half.ppm");
        printf("boxed image saved: detview_image_test.ppm (+_half)\n");
        printf("SELFTEST %s\n", !dets.empty() ? "PASS" : "FAIL(no boxes)");
        return dets.empty() ? 1 : 0;
    }

    std::string err;
    Yolo26Rknn net;
    if (!net.load(modelPath(modelIdx).toStdString(), err)) {
        printf("SELFTEST FAIL: %s\n", err.c_str());
        return 1;
    }
    printf("model: %s  mode=%s nc=%d  input=%dx%d\n", modelShort(modelIdx).toUtf8().constData(),
           net.e2e() ? "e2e" : "std", net.numClasses(), net.modelW(), net.modelH());
    if (net.modelW() != prep::CAM_W) { printf("SELFTEST FAIL: model width != 640 unsupported\n"); return 1; }

    std::vector<uint8_t> lb((size_t)net.modelW() * net.modelH() * 3);
    QElapsedTimer t; t.start();
    int frames = 0, infers = 0;
    double inferSum = 0;
    QImage boxed;
    bool boxedTaken = false;
    double preSum = 0;

    while (t.elapsed() < secs * 1000) {
        QImage img; double fps = 0; quint32 fid = 0;
        if (!src.grabOnce(img, fps, fid)) { QThread::msleep(4); continue; }
        ++frames;
        QElapsedTimer tp; tp.start();
        int yPad = prep::letterboxCamToModel(img.constBits(), lb.data(), net.modelW(), net.modelH());
        preSum += tp.elapsed();
        std::vector<Det> dets = net.infer(lb.data(), 0.25f, 0.45f);
        ++infers; inferSum += net.lastInferMs();
        for (Det &d : dets) {
            d.y1 -= (float)yPad; d.y2 -= (float)yPad;
            d.x1 = std::min(std::max(d.x1, 0.0f), (float)prep::CAM_W - 1);
            d.x2 = std::min(std::max(d.x2, 0.0f), (float)prep::CAM_W - 1);
            d.y1 = std::min(std::max(d.y1, 0.0f), (float)prep::CAM_H - 1);
            d.y2 = std::min(std::max(d.y2, 0.0f), (float)prep::CAM_H - 1);
        }
        printf("frame=%u sync=%s disp=%.1ffps pre=%.1fms infer=%.1fms boxes=%zu\n",
               fid, src.syncMode().toUtf8().constData(), fps, (double)tp.elapsed(),
               net.lastInferMs(), dets.size());
        if (!boxedTaken && frames >= (secs >= 10 ? 30 : 10)) {
            boxed = img.copy();
            QPainter p(&boxed);
            drawDets(p, dets, kModels[(size_t)modelIdx].labels);
            boxedTaken = true;
        }
    }

    printf("--- summary ---\n");
    printf("sync=%s  frames=%d  disp=%.1ffps  infer=%.1fms avg  pre=%.1fms avg\n",
           src.syncMode().toUtf8().constData(), frames,
           frames / (t.elapsed() / 1000.0), infers ? inferSum / infers : 0,
           frames ? preSum / frames : 0);
    if (boxedTaken) {
        savePpm(boxed, "/root/ov5640/detview_selftest.ppm");
        savePpm(boxed.scaled(320, 240, Qt::KeepAspectRatio, Qt::FastTransformation),
                "/root/ov5640/detview_selftest_half.ppm");
        printf("boxed frame saved: /root/ov5640/detview_selftest.ppm (+_half.ppm)\n");
    }
    bool ok = frames >= 3 && infers >= 3;
    printf("SELFTEST %s\n", ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}

int main(int argc, char **argv) {
    int secs = 10, modelIdx = 0;
    const char *imgPath = nullptr;
    bool selftest = false;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--selftest")) selftest = true;
        else if (!strcmp(argv[i], "--secs") && i + 1 < argc) secs = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--model") && i + 1 < argc) modelIdx = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--image") && i + 1 < argc) { imgPath = argv[++i]; selftest = true; }
        else if (!strcmp(argv[i], "--probe") && i + 1 < argc) { return probeMain(argv[++i]); }
    }
    if (selftest) return selftestMain(argc, argv, secs, modelIdx, imgPath);

    QApplication app(argc, argv);
    qRegisterMetaType<QImage>("QImage");

    FrameSource *src = new FrameSource;
    InferWorker *inf = new InferWorker;
    View *view = new View(src, inf);

    // [THREADFIX] The context object (`view`) is REQUIRED: without it these
    // functor connections default to Qt::DirectConnection, so the grabber and
    // infer QThreads call view->drawFrame()/setPixmap()/QPainter directly on a
    // non-GUI thread -> intermittent SIGSEGV in QLabel::paintEvent (seen on the
    // board). With a context object the slot runs queued in the GUI thread.
    QObject::connect(src, &FrameSource::frameReady, view,
                     [view](const QImage &img, double fps, quint32 fid) {
                         view->drawFrame(img, fps, fid);
                     });
    QObject::connect(src, &FrameSource::statusMsg, view, [view](const QString &s) {
        if (view->label()->pixmap() == nullptr)
            view->label()->setText(s);
        view->setWindowTitle("detview  " + s);
    });
    QObject::connect(inf, &InferWorker::statusMsg, view, [view](const QString &s) {
        view->setWindowTitle("detview  " + s);
    });

    inf->requestModel(0);
    src->start();
    inf->start();

    view->showFullScreen();
    view->activateWindow(); view->raise();
    QTimer focusTimer;
    QObject::connect(&focusTimer, &QTimer::timeout, [view]() {
        if (!view->isActiveWindow()) { view->activateWindow(); view->raise(); }
    });
    focusTimer.start(2000);

    int rc = app.exec();
    src->stop(); inf->stop();
    delete src; delete inf; delete view;
    return rc;
}
#include "main.moc"
