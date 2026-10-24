#include <limits>
#include "../pair_publication.h"
// detview - OV5640 live detection UI for RK3568 + Pango FPGA + RKNN
// Cam path: OV5640 -> DDR3 ping-pong (0x00800000/0x00A00000, RGB565 640x480)
//           -> PCIe DMA read -> canonical 640x640 -> per-model RKNN input geometry
#include <QApplication>
#include <QAction>
#include <QComboBox>
#include <QCryptographicHash>
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
#include <QMouseEvent>
#include <QLabel>
#include <QMutex>
#include <QOpenGLFunctions>
#include <QOpenGLShaderProgram>
#include <QOpenGLWindow>
#include <QPainter>
#include <QProcess>
#include <QPushButton>
#include <QScreen>
#include <QSaveFile>
#include <QSlider>
#include <QSocketNotifier>
#include <QThread>
#include <QTemporaryDir>
#include <QVBoxLayout>
#include <QWaitCondition>
#include <QWidget>

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <csignal>
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cerrno>
#include <fcntl.h>
#include <functional>
#include <memory>
#include <map>
#include <stdexcept>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <unistd.h>
#include <time.h>
#include <vector>

#include "vision_types.h"
#include "vision_pipeline.h"
#include "motion_policy_selftest.h"
#include "view_capture_evidence.h"
#include "integrated_motion.h"
#include "startup_camera_geometry.h"
#include "capture_pacing.h"
#include "source_acceptance.h"
#include "infer_age.h"
#include "detection_temporal_filter.h"
#include "template_tracker.h"
#include "camera_dma.h"
#include "../runtime_camera_geometry.h"
#include "../c5_transaction.h"
#include "../c5_runtime_selftest.h"
#include "fair_dma.h"
#include "frame_metrics.h"
#include "display_perf.h"
#include "hdmi_view.h"
#include "cam34_six.h"
#include "inference_geometry.h"
#include "mvp_decode.h"
#include "mvp_round1_policy.h"
#include "calibration_capture.h"
#include "../cam1_runtime.h"
#include "cam1_runtime_safety.h"
int runCam1RuntimeSelfTest();
#include "stereo_demo/stereo_depth.h"

#include "rknn_api.h"
#include "scheme2_uapi.h"
#include "scheme2_verify.h"
#include "scheme2_contract.h"

/* ---- F4: the "please restart me" exit status -------------------------
   detview.service carries RestartPreventExitStatus=3 (drop-in
   80-normal-stop.conf), so exit(3) counts as a deliberate stop and is NOT
   restarted. Every self-heal path that wants the supervisor to bring the
   viewer back must use a different status; 3 stays reserved for the
   deliberate operator hold. */
static constexpr int kRestartExitCode = 4;
/* F1: how long a latched resolution error may freeze the UI before the
   process asks systemd for a restart. The error page stays visible. */
static constexpr int kResolutionErrorGraceMs = 30000;
/* F5: an unacknowledged six-camera overview ticket must not swallow keys. */
static constexpr int kOverviewTicketTimeoutMs = 5000;
/* F6: screenshot directory bound (the file about to be written is included). */
static constexpr int kShotKeep = 80;

/* ---- F2: SIGTERM/SIGINT -> Qt event loop -----------------------------
   The handler itself only writes one byte to a self-pipe (async-signal-safe);
   a QSocketNotifier then calls qApp->quit() from the event loop, so the
   normal destructors run and the VGA/pair restore teardown actually happens
   before the process dies. Before this, `systemctl stop/restart` killed the
   viewer outright and the next start aborted with "Runtime sensor left HD". */
static int g_termPipe[2] = {-1, -1};
static void termSignalHandler(int) {
    const char byte = 1;
    if (g_termPipe[1] >= 0) {
        const ssize_t ignored = ::write(g_termPipe[1], &byte, 1);
        (void)ignored;
    }
}
[[maybe_unused]] static void installTermHandlers(QCoreApplication *app) {
    if (::pipe(g_termPipe) != 0) return;
    for (int fd : g_termPipe)
        ::fcntl(fd, F_SETFL, ::fcntl(fd, F_GETFL) | O_NONBLOCK);
    struct sigaction sa{};
    sa.sa_handler = &termSignalHandler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART;
    sigaction(SIGTERM, &sa, nullptr);
    sigaction(SIGINT, &sa, nullptr);
    auto *notifier = new QSocketNotifier(g_termPipe[0], QSocketNotifier::Read, app);
    QObject::connect(notifier, &QSocketNotifier::activated, app, [app](int) {
        char buf[16];
        while (::read(g_termPipe[0], buf, sizeof buf) > 0) {}
        fprintf(stderr, "[shutdown] SIGTERM/SIGINT -> normal teardown\n");
        fflush(stderr);
        app->quit();
    });
}

/* ---- F6: atomic screenshot write -------------------------------------
   QSaveFile writes a temporary file and renames it on commit(), so a crash,
   killed process or full disk can never leave a truncated/0-byte shot behind.
   The target is unlinked explicitly when anything fails. */
[[maybe_unused]] static bool saveShotAtomic(const QPixmap &pm, const QString &path,
                                            const char *format) {
    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly)) {
        QFile::remove(path);
        return false;
    }
    if (!pm.save(&file, format)) {
        file.cancelWriting();
        QFile::remove(path);
        return false;
    }
    if (!file.commit()) {
        QFile::remove(path);
        return false;
    }
    return true;
}

/* ---- F6: keep at most `keep` shot_*.png files (oldest removed first). */
[[maybe_unused]] static void pruneShots(const QString &dirPath, int keep) {
    const QFileInfoList shots = QDir(dirPath).entryInfoList(
        QStringList{"shot_*.png"}, QDir::Files, QDir::Time | QDir::Reversed);
    for (int i = 0; i + keep < shots.size(); ++i)
        QFile::remove(shots[i].absoluteFilePath());
}

[[noreturn]] static void scheme2Quarantine(const char* reason) {
    fprintf(stderr, "[scheme2] QUARANTINE pid=%d: %s; parent must quiesce hardware\n", int(getpid()), reason);
    fflush(stderr);
    raise(SIGSTOP);
    for (;;) pause();
}

struct Scheme2Transport {
    int fd = -1, sharedFd = -1;
    uint8_t* tx = nullptr;
    uint8_t* rx = nullptr;
    size_t txBytes = 0x1000, rxBytes = scheme2::Window;
    std::shared_ptr<tdm::FairDmaMutex> mutex;
    bool consumerHeld = false;
    ~Scheme2Transport() {
        if (consumerHeld) scheme2Quarantine("transport teardown with active consumer");
        if (sharedFd >= 0) ::close(sharedFd);
        if (tx && tx != MAP_FAILED) munmap(tx, txBytes);
        if (rx && rx != MAP_FAILED) munmap(rx, rxBytes);
        if (fd >= 0) ::close(fd);
    }
};

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
static constexpr uint32_t CAM34_FRAME_BYTES = 320u * 240u * 2u;
static inline uint32_t frameBytesForCamera(int cameraNumber) {
    return runtime_camera::geometry(cameraNumber - 1).pixelBytes;
}
static inline int frameWidthForCamera(int cameraNumber) { return int(runtime_camera::geometry(cameraNumber - 1).width); }
static inline int frameHeightForCamera(int cameraNumber) { return int(runtime_camera::geometry(cameraNumber - 1).height); }
static const uint32_t REG_BASE = 0x20000000u;

// [C5-EPOCH 2026-10-21] Persistent monotonic C5 transaction epoch.
// The 50K sender silently drops a transaction whose epoch is not greater than the
// one it last armed, and the 100H mailbox never exposes that value. A receiver-only
// "max(registers)+1" therefore collapses to 1 after a bitstream reload and every
// request is ignored -> mailbox timeout 0x1001. Keep our own floor, base it well
// above any probe range and persist it across restarts.
static const uint32_t C5_EPOCH_BASE = 0xF8000000u;
static const char* const C5_EPOCH_FILE = "/userdata/detview_c5_epoch";
static uint32_t c5EpochPersisted() {
    QFile f(QString::fromUtf8(C5_EPOCH_FILE));
    if(!f.open(QIODevice::ReadOnly)) return 0;
    bool ok=false;
    const uint32_t v=f.read(32).trimmed().toUInt(&ok,16);
    return ok?v:0u;
}
static void c5EpochPersist(uint32_t v) {
    QFile f(QString::fromUtf8(C5_EPOCH_FILE));
    if(!f.open(QIODevice::WriteOnly|QIODevice::Truncate)) return;
    f.write(QByteArray::number(v,16).rightJustified(8,'0'));
    f.write("\n");
    f.close();
}
static const uint32_t R_ACK = REG_BASE + 0x00;
static const uint32_t R_I2C_ID = REG_BASE + 0x3C;
static const uint32_t R_CAM_EN = REG_BASE + 0x40;
static const uint32_t R_ADDR1 = REG_BASE + 0x80;
static const uint32_t R_ADDR2 = REG_BASE + 0xC0;

static const unsigned long MAP_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 2;
static const unsigned long UNMAP_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 7;
static const unsigned long H2F_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 4;
static const unsigned long F2H_CMD = 0xC0000000ul | (4ul << 16) | (0x53ul << 8) | 5;

static const int MODEL_W = 640;
static const int MODEL_H = 640;
static const float CONF_THRESH = 0.25f;
static const float IOU_THRESH = 0.45f;

static qint64 monotonicNs() {
    timespec stamp{};
    clock_gettime(CLOCK_MONOTONIC, &stamp);
    return stamp.tv_sec * 1000000000LL + stamp.tv_nsec;
}
static qint64 monotonicMs() { return monotonicNs() / 1000000; }

// Evidence only: eight generation buckets per camera; no admission/scheduler inputs.
// Geometry comes from the capture worker, never from a later runtime-mode lookup.
class VisionEvidence {
    struct Row {
        int camera = -1, generation = 0, width = 0, height = 0;
        bool hd = false;
        quint64 visionAttempts = 0, hdSkipped = 0, visionSent = 0;
        quint64 requests = 0, submitted = 0, completed = 0, detectorCompleted = 0;
        qint64 reportedMs = -1;
    };
    QMutex mutex_;
    std::map<std::pair<int, int>, Row> rows_;
    void snapshot(Row& r, qint64 now) {
        fprintf(stderr, "[vision-evidence] schema=1 kind=snapshot camera=%d generation=%d state=%s source_w=%d source_h=%d pipeline_w=640 pipeline_h=480 event_ms=%lld vision_attempts=%llu hd_skipped=%llu vision_sent=%llu inference_requests=%llu submitted=%llu completed=%llu detector_completed=%llu\n",
            r.camera + 1, r.generation, r.hd ? "hd_gated" : "running", r.width, r.height,
            (long long)now, (unsigned long long)r.visionAttempts, (unsigned long long)r.hdSkipped,
            (unsigned long long)r.visionSent, (unsigned long long)r.requests,
            (unsigned long long)r.submitted, (unsigned long long)r.completed,
            (unsigned long long)r.detectorCompleted);
        r.reportedMs = now;
    }
public:
    static VisionEvidence& instance() { static VisionEvidence value; return value; }
    void active(int camera, int generation, int width, int height, bool hd) {
        QMutexLocker lock(&mutex_);
        const auto key = std::make_pair(camera, generation);
        auto found = rows_.find(key);
        if (found == rows_.end()) {
            // Evict only this camera's oldest retained generation. Late worker
            // events remain identified, but cannot contaminate the current row.
            int count = 0;
            for (const auto& entry : rows_) if (entry.first.first == camera) ++count;
            if (count >= 8) {
                for (auto it = rows_.begin(); it != rows_.end(); ++it) {
                    if (it->first.first == camera) { rows_.erase(it); break; }
                }
            }
            Row row; row.camera = camera; row.generation = generation;
            row.width = width; row.height = height; row.hd = hd;
            found = rows_.emplace(key, row).first;
        }
        const qint64 now = monotonicMs();
        if (found->second.reportedMs < 0 || now - found->second.reportedMs >= 5000)
            snapshot(found->second, now);
    }
    void captureGate(int camera, int generation, bool hd) {
        QMutexLocker lock(&mutex_);
        auto found = rows_.find(std::make_pair(camera, generation));
        if (found == rows_.end()) return;
        ++found->second.visionAttempts;
        if (hd && ++found->second.hdSkipped == 1) snapshot(found->second, monotonicMs());
    }
    void event(const char* stage, const tdm::InferAge& age, bool laneOnly = false) {
        if (age.camera < 0 || age.camera >= CAM_COUNT || !age.id) return;
        QMutexLocker lock(&mutex_);
        auto found = rows_.find(std::make_pair(age.camera, age.generation));
        const bool tracked = found != rows_.end();
        if (tracked) {
            auto& r = found->second;
            if (!strcmp(stage, "vision_sent")) ++r.visionSent;
            else if (!strcmp(stage, "inference_request")) ++r.requests;
            else if (!strcmp(stage, "submitted")) ++r.submitted;
            else if (!strcmp(stage, "completed")) {
                ++r.completed;
                if (!laneOnly) ++r.detectorCompleted;
            }
        }
        fprintf(stderr, "[vision-evidence] schema=1 kind=event stage=%s camera=%d generation=%d frame=%llu tag=%u captured_ms=%lld event_ms=%lld lane_only=%d tracked=%d\n",
            stage, age.camera + 1, age.generation, (unsigned long long)age.id, age.tag,
            (long long)age.capturedMs, (long long)monotonicMs(), int(laneOnly), int(tracked));
    }
};

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
// Legacy ioctl encodes sizeof(int), but copies exactly this 20-byte prefix.
static_assert(offsetof(DmaOp, current_len) == 0 && offsetof(DmaOp, offset_addr) == 4 &&
              offsetof(DmaOp, cmd) == 8 && offsetof(DmaOp, ddr3_addr) == 12 &&
              offsetof(DmaOp, total_length) == 16, "driver 20-byte DMA prefix ABI");

struct ModelInfo {
    QString path;
    QStringList classes;
    int nc = 1;
    bool xyxy = false;
    bool lane = false;
    bool trafficlight = false;
    bool mvpDetect = false;
    bool sharedUfld = false;
    bool independentUfld = false;
    bool spatialLane = false;
    mvp::LaneContract laneContract;
    mvp::Round1Policy round1Policy;
    QString deploymentSha;
    QString deploymentError;
};

static QStringList mvpNames() { return {"person", "vehicle", "zebra", "traffic_light", "traffic_sign"}; }
static QStringList mvpR2Names() { return {"person", "vehicle", "zebra", "traffic_light_red",
    "traffic_light_yellow", "traffic_light_green", "traffic_sign"}; }

// Only the delivered R1 manifest is supported. An unknown sidecar fails closed.
static bool parseRound1Manifest(const QJsonObject& o, ModelInfo& info, QString& reason) {
    info.round1Policy.enabled = false;
    auto fail = [&](const char* message) { reason = message; return false; };
    if (o.value("name").toString() != "MVP accuracy-first round1")
        return fail("unsupported deployment profile name");
    if (!info.mvpDetect || info.sharedUfld || info.independentUfld || info.classes != mvpNames() || info.nc != 5)
        return fail("R1 profile requires the five-class MVP raw6 detector");
    QJsonArray classes;
    for (const auto& name : mvpNames()) classes.append(name);
    if (o.value("classes").toArray() != classes || o.value("input").toArray() != QJsonArray{1,3,480,640} ||
        o.value("reg_max").toDouble(-1) != 16 || o.value("architecture").toString() != "YOLOv8n" ||
        o.value("target").toString() != "rk3568" || o.value("precision").toString() != "int8" ||
        o.value("output_order").toArray() != QJsonArray{"box_p3","box_p4","box_p5","cls_p3","cls_p4","cls_p5"})
        return fail("R1 deployment input/classes/raw6 contract mismatch");
    info.deploymentSha = o.value("rknn_sha256").toString();
    if (info.deploymentSha != mvp::Round1Policy::rknnSha ||
        o.value("float_model_sha256").toString() != mvp::Round1Policy::floatSha)
        return fail("R1 deployment model SHA does not match supported release");
    const auto thresholds = o.value("thresholds").toObject();
    if (thresholds.size() != 5) return fail("R1 deployment requires exactly five numeric class thresholds");
    for (int c=0;c<5;++c) {
        const auto value = thresholds.value(QString::number(c));
        if (!value.isDouble() || !std::isfinite(value.toDouble()) ||
            value.toDouble() < 0 || value.toDouble() > 1 ||
            std::fabs(value.toDouble()-info.round1Policy.thresholds[c]) > 1e-7)
            return fail("R1 deployment threshold mismatch (expected .35/.45/.25/.35/.40)");
        info.round1Policy.thresholds[c] = float(value.toDouble());
    }
    info.round1Policy.enabled = true;
    reason.clear();
    return true;
}

static bool readRound1Deployment(ModelInfo& info, QString& reason) {
    info.round1Policy = mvp::Round1Policy{};
    info.deploymentSha.clear();
    reason.clear();
    QFile file(info.path + ".deployment.json");
    if (!file.exists()) {
        if (QFileInfo(info.path).fileName().toLower() == "mvp_accuracy_round1_rk3568_int8.rknn") {
            reason = "MVP-R1 requires its .deployment.json sidecar";
            return false;
        }
        return true;
    }
    if (!file.open(QIODevice::ReadOnly)) { reason = "cannot open deployment sidecar"; return false; }
    QJsonParseError error{};
    const auto doc = QJsonDocument::fromJson(file.readAll(),&error);
    if (error.error != QJsonParseError::NoError || !doc.isObject()) {
        reason = "invalid deployment sidecar JSON"; return false;
    }
    return parseRound1Manifest(doc.object(),info,reason);
}

static bool verifyRound1Bytes(const ModelInfo& info, const QByteArray& bytes, QString& reason) {
    if (!info.round1Policy.enabled) return true;
    const auto actual = QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex();
    if (mvp::Round1Policy::matchesSha(info.deploymentSha.toStdString(),actual.toStdString())) return true;
    reason = QString("MVP-R1 RKNN SHA256 mismatch: expected %1, got %2")
        .arg(info.deploymentSha,QString::fromLatin1(actual));
    return false;
}

static bool selfTestRound1Metadata() {
    QJsonArray classes;
    for (const auto& name : mvpNames()) classes.append(name);
    QJsonObject thresholds;
    const mvp::Round1Policy policy;
    for (int c=0;c<5;++c) thresholds.insert(QString::number(c),double(policy.thresholds[c]));
    const QJsonObject valid{{"name","MVP accuracy-first round1"},{"architecture","YOLOv8n"},
        {"input",QJsonArray{1,3,480,640}},{"classes",classes},{"target","rk3568"},
        {"precision","int8"},{"reg_max",16},
        {"output_order",QJsonArray{"box_p3","box_p4","box_p5","cls_p3","cls_p4","cls_p5"}},
        {"rknn_sha256",mvp::Round1Policy::rknnSha},{"float_model_sha256",mvp::Round1Policy::floatSha},
        {"thresholds",thresholds}};
    int failures=0;
    auto expect=[&](bool ok,const char* message) {
        fprintf(stderr,"[mvp-round1-metadata] %s %s\n",ok?"OK":"FAIL",message); failures+=!ok;
    };
    ModelInfo model; model.mvpDetect=true; model.classes=mvpNames(); model.nc=5;
    QString reason;
    expect(!model.round1Policy.enabled,"model default keeps legacy policy");
    expect(parseRound1Manifest(valid,model,reason) && model.round1Policy.enabled,"delivered manifest format accepted");
    expect(!verifyRound1Bytes(model,QByteArray("old RKNN model bytes"),reason) && reason.contains("SHA256 mismatch"),
           "actual model bytes hashed and wrong checksum rejected");
    auto reject=[&](const QJsonObject& object,const char* message) {
        expect(!parseRound1Manifest(object,model,reason) && !model.round1Policy.enabled && !reason.isEmpty(),message);
    };
    auto bad=valid; bad.insert("name","unknown profile"); reject(bad,"unknown profile rejected");
    bad=valid; bad.insert("rknn_sha256",QString(64,'0')); reject(bad,"old or unknown model identity rejected");
    bad=valid; bad.insert("input",QJsonArray{1,3,640,640}); reject(bad,"square input rejected");
    bad=valid; bad.insert("classes",QJsonArray{"vehicle","person","zebra","traffic_light","traffic_sign"});
    reject(bad,"class reordering rejected");
    bad=valid; bad.insert("reg_max",8); reject(bad,"wrong regmax rejected");
    auto badThresholds=thresholds; badThresholds.remove("2");
    bad=valid; bad.insert("thresholds",badThresholds); reject(bad,"missing threshold rejected without default");
    badThresholds=thresholds; badThresholds.insert("0","0.35");
    bad=valid; bad.insert("thresholds",badThresholds); reject(bad,"string threshold rejected");
    badThresholds=thresholds; badThresholds.insert("5",.5);
    bad=valid; bad.insert("thresholds",badThresholds); reject(bad,"extra class threshold rejected");
    badThresholds=thresholds; badThresholds.insert("1",.25);
    bad=valid; bad.insert("thresholds",badThresholds); reject(bad,"guessed uniform thresholds rejected");
    ModelInfo shared=model; shared.sharedUfld=true;
    expect(!parseRound1Manifest(valid,shared,reason),"R1 cannot be applied to old shared detector");
    QTemporaryDir directory;
    expect(directory.isValid(),"temporary metadata directory available");
    if (directory.isValid()) {
        model.path=directory.path()+"/MVP_accuracy_round1_rk3568_int8.rknn";
        expect(!readRound1Deployment(model,reason) && !model.round1Policy.enabled,"R1 missing sidecar rejected");
        QFile sidecar(model.path+".deployment.json");
        auto write=[&](const QByteArray& bytes) {
            if (!sidecar.open(QIODevice::WriteOnly|QIODevice::Truncate)) return false;
            const bool ok=sidecar.write(bytes)==bytes.size(); sidecar.close(); return ok;
        };
        expect(write(QJsonDocument(valid).toJson()) && readRound1Deployment(model,reason) && model.round1Policy.enabled,
               "sidecar file parsed in production reader");
        expect(write("{broken") && !readRound1Deployment(model,reason) && !model.round1Policy.enabled,
               "malformed sidecar rejected");
        model.path=directory.path()+"/MVP_rk3568_int8.rknn";
        expect(readRound1Deployment(model,reason) && !model.round1Policy.enabled &&
               verifyRound1Bytes(model,QByteArray("legacy bytes"),reason),"old model without sidecar stays unchanged");
    }
    fprintf(stderr,failures?"MVP_ROUND1_METADATA_SELFTEST_FAIL\n":"MVP_ROUND1_METADATA_SELFTEST_PASS\n");
    return failures==0;
}

static bool readMvpLaneContract(const QString& path, mvp::LaneContract& contract) {
    QFile file(path + ".lane.json");
    if (!file.exists()) return true; // Exact delivered anchors are also compiled in.
    if (!file.open(QIODevice::ReadOnly)) return false;
    QJsonParseError error{};
    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &error);
    if (error.error != QJsonParseError::NoError || !doc.isObject()) return false;
    const auto object = doc.object();
    if (object.value("input_hw").toArray() != QJsonArray{480,640} ||
        object.value("decode").toString() != "argmax_endpoint" ||
        object.value("grid_row").toInt() != 64 || object.value("grid_col").toInt() != 48 ||
        object.value("num_lanes").toInt() != 8) return false;
    auto load = [&](const char* key, auto& target) {
        const auto array = object.value(key).toArray();
        if (array.size() != int(target.size())) return false;
        for (int i=0;i<array.size();++i) {
            if (!array[i].isDouble() || !std::isfinite(array[i].toDouble()) ||
                std::fabs(array[i].toDouble()-target[i]) > 0.001) return false;
            target[i] = float(array[i].toDouble());
        }
        return true;
    };
    return load("row_anchors",contract.rows) && load("col_anchors",contract.cols);
}

static QStringList trafficlightNames() {
    // Exact package names.json order. Keep raw IDs stable for logs/metadata.
    return {"tlr_motor_red", "tly_motor_amber", "tlg_motor_green",
            "tlra_left_red", "tlya_left_amber", "tlga_left_green",
            "tsra_straight_red", "tsya_straight_amber", "tsga_straight_green",
            "trra_right_red", "trya_right_amber", "trga_right_green",
            "tura_uturn_red", "tuya_uturn_amber", "tuga_uturn_green", "tln_lamp_off"};
}

static QString displayClassName(const QString &name) {
    static const QStringList ids = trafficlightNames();
    static const QStringList labels = {"机动车红灯", "机动车黄灯", "机动车绿灯",
        "左转红灯", "左转黄灯", "左转绿灯", "直行红灯", "直行黄灯", "直行绿灯",
        "右转红灯", "右转黄灯", "右转绿灯", "掉头红灯", "掉头黄灯", "掉头绿灯", "信号灯熄灭"};
    const int id = ids.indexOf(name);
    return id >= 0 ? labels[id] : name;
}

static bool readModelNames(const QString &path, QStringList &names) {
    QFile file(path + ".names.json");
    if (!file.open(QIODevice::ReadOnly)) return false;
    QJsonParseError error{};
    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll(), &error);
    if (error.error != QJsonParseError::NoError || !doc.isArray() || doc.array().isEmpty()) return false;
    for (const auto &value : doc.array()) {
        if (!value.isString() || value.toString().trimmed().isEmpty()) return false;
        names.append(value.toString());
    }
    return true;
}

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
                              "/root/npu/lane_linknet", "/root/npu/whiteboard_3cls",
                              "/root/npu/trafficlight", "/root/npu/mvp"};
    for (const QString &d : dirs) {
        QDir dir(d);
        const QStringList files = dir.entryList(QStringList() << "*.rknn", QDir::Files, QDir::Name);
        for (const QString &f : files) {
            ModelInfo mi;
            mi.path = dir.absoluteFilePath(f);
            const QString lower = f.toLower();
            QStringList names;
            const bool hasNames = readModelNames(mi.path, names);
            const bool trafficlight = lower.contains("trafficlight") || (hasNames && names == trafficlightNames());
            if (lower == "mvp_rk3568_int8.rknn" || lower == "mvp_accuracy_round1_rk3568_int8.rknn" ||
                lower == "mvp_r2_rk3568_int8.rknn" || lower == "spatial_lane_rk3568_int8.rknn" ||
                lower == "mvp_plus_shared_rk3568_fp16.rknn" ||
                lower == "lane_ufldv2_480x640_rk3568_fp16.rknn") {
                mi.independentUfld = lower.startsWith("lane_ufldv2_");
                mi.sharedUfld = lower.startsWith("mvp_plus_shared_");
                mi.spatialLane = lower == "spatial_lane_rk3568_int8.rknn";
                mi.mvpDetect = !mi.independentUfld;
                const bool r2Names = (lower == "mvp_r2_rk3568_int8.rknn" || mi.spatialLane) &&
                                     hasNames && names == mvpR2Names();
                if ((lower == "mvp_r2_rk3568_int8.rknn" || mi.spatialLane) && !r2Names) {
                    fprintf(stderr,"[mvp] reject %s: R2 model requires exact seven-class names sidecar\n",
                            qPrintable(mi.path));
                    continue;
                }
                if (mi.mvpDetect && QFileInfo::exists(mi.path + ".names.json") &&
                    (!hasNames || (names != mvpNames() && !r2Names))) {
                    fprintf(stderr,"[mvp] reject %s: expected five coarse or R2 seven class IDs\n",qPrintable(mi.path));
                    continue;
                }
                if ((mi.sharedUfld || mi.independentUfld) && !readMvpLaneContract(mi.path,mi.laneContract)) {
                    fprintf(stderr,"[mvp] reject %s: invalid lane contract sidecar\n",qPrintable(mi.path));
                    continue;
                }
                mi.classes = mi.independentUfld ? QStringList{"lane0","lane1","lane2","lane3","lane4","lane5","lane6","lane7"}
                                                : (r2Names ? mvpR2Names() : mvpNames());
                mi.nc = mi.independentUfld ? 8 : (r2Names ? 7 : 5);
            } else if (lower.startsWith("seg-linknet-lane640-")) {
                mi.lane = true;
                mi.nc = lower.contains("multiclass") ? 9 : 2;
                mi.classes = mi.nc == 9
                    ? (QStringList() << "background" << "lane0" << "lane1" << "lane2"
                                     << "lane3" << "lane4" << "lane5" << "lane6" << "lane7")
                    : (QStringList() << "background" << "lane");
            } else if (trafficlight) {
                if (QFileInfo::exists(mi.path + ".names.json") && (!hasNames || names != trafficlightNames())) {
                    fprintf(stderr, "[trafficlight] reject %s: names sidecar must match package's 16 class IDs\n",
                            qPrintable(mi.path));
                    continue;
                }
                mi.trafficlight = true;
                mi.classes = hasNames ? names : trafficlightNames();
                mi.nc = 16;
                mi.xyxy = false;
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
            if (hasNames && !mi.trafficlight && !mi.lane && !mi.mvpDetect && !mi.independentUfld) {
                mi.classes = names;
                mi.nc = names.size();
            }
            readRound1Deployment(mi,mi.deploymentError);
            list.append(mi);
        }
    }
    return list;
}

static QVector<int> vehicleTrackingClasses(const ModelInfo& model) {
    QVector<int> result;
    // TT100K labels such as "机动车" describe signs, not vehicle observations.
    if (model.lane || model.independentUfld || model.path.contains("tt100k", Qt::CaseInsensitive)) return result;
    static const QStringList objects = {"vehicle", "car", "truck", "bus", "motorcycle"};
    for (int c = 0; c < model.classes.size(); ++c)
        if (objects.contains(model.classes[c].trimmed().toLower())) result.append(c);
    return result;
}

static bool selfTestVehiclePolicy() {
    ModelInfo mixed; mixed.path = "det-3cls-wb.rknn";
    mixed.classes = QStringList{"zebra", "vehicle", "person"};
    if (vehicleTrackingClasses(mixed) != QVector<int>{1}) return false;
    ModelInfo single; single.path = "det-vehicle.rknn"; single.classes = QStringList{"vehicle"};
    if (vehicleTrackingClasses(single) != QVector<int>{0}) return false;
    ModelInfo signs; signs.path = "det-tt100k.rknn";
    signs.classes = QStringList{"机动车", "非机动车", "禁止货车驶入", "vehicle"};
    if (!vehicleTrackingClasses(signs).isEmpty()) return false;
    mixed.lane = true;
    if (!vehicleTrackingClasses(mixed).isEmpty()) return false;
    fprintf(stderr, "VEHICLE_TRACKING_POLICY_SELFTEST_PASS\n");
    return true;
}

class PangoDev {
public:
    ~PangoDev() { close(); }
    void protectRuntimeSwitch() { runtimeProtected_=true; }

    bool openDev() {
        struct sigaction sa{};
        sa.sa_handler = &PangoDev::alarmHandler;
        sigaction(SIGALRM, &sa, nullptr);  // 只装一次，避免每次 ioctl 的 sigaction 开销
        fd_ = ::open("/dev/pango_pci_driver", O_RDWR | O_SYNC);
        if (fd_ < 0) {
            err_ = "open driver failed";
            return false;
        }
        if (scheme2::enabled()) {
            shared_ = std::make_shared<Scheme2Transport>();
            shared_->fd = fd_;
            shared_->mutex = dmaMutex_;
        }
        DmaOp a{};
        a.cmd = 0;
        a.total_length = txWindowBytes();
        if (ioctlTmo(MAP_CMD, &a, 3) != 0) {
            err_ = "map tx failed";
            return failOpen();
        }
        DmaOp b{};
        b.cmd = 1;
        b.total_length = windowBytes();
        if (ioctlTmo(MAP_CMD, &b, 3) != 0) {
            err_ = "map rx failed";
            return failOpen();
        }
        tx_ = (uint8_t *)mmap(nullptr, txWindowBytes(), PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
        rx_ = (uint8_t *)mmap(nullptr, windowBytes(), PROT_READ | PROT_WRITE, MAP_SHARED, fd_,
                              1024 * 1024);
        if (shared_) { shared_->tx = tx_; shared_->rx = rx_; }
        if (tx_ == MAP_FAILED || rx_ == MAP_FAILED) {
            err_ = "mmap failed";
            return false;
        }
        // Geometry must come from the bitstream. Never probe RAW tag offsets
        // or fall back to full-size C3/C4 transfers on incompatible hardware.
        uint32_t c1Signature=0;
        if(regRead(0x20000870u,c1Signature) && c1Signature==0x43314d31u) {
            uint32_t mode=0,dimensions=0,bytes=0,stride=0;
            if(!regRead(0x20000800u,mode) || mode!=0 ||
               !regRead(0x20000840u,dimensions) || dimensions!=(640u<<16|480u) ||
               !regRead(0x20000850u,bytes) || bytes!=614400u ||
               !regRead(0x20000860u,stride) || stride!=1280u) {
                err_="C1 startup runtime geometry mismatch; external recovery required";return false;
            }
            runtimeCameraSupported_[0]=true;
        }
        for(int camera=2;camera<4;++camera){
            uint32_t magic=0,dimensions=0,bytes=0,stride=0;
            const uint32_t base=0x20000000u+uint32_t(camera)*0x200u;
            uint32_t runtimeSignature=0,runtimeMode=0;
            const uint32_t alias=camera==2?0x20000900u:0x20000a00u;
            const bool runtime=regRead(alias+0x70,runtimeSignature) &&
                (runtimeSignature==(camera==2?0x43334d31u:0x43344d31u) ||
                 runtimeSignature==(camera==2?0x43334d32u:0x43344d32u));
            if(runtime) {
                if(!regRead(alias,runtimeMode) || runtimeMode>1 || !regRead(alias+0x40,dimensions) ||
                   !regRead(alias+0x50,bytes) || !regRead(alias+0x60,stride)) {
                    err_="FPGA runtime-camera metadata read failed";return false;
                }
                const auto g=runtime_camera::geometry(camera,runtimeMode?runtime_camera::Mode::Hd720:runtime_camera::Mode::Default);
                if(dimensions!=(g.width<<16|g.height) || bytes!=g.pixelBytes || stride!=g.stride) {
                    err_="FPGA runtime-camera geometry mismatch";return false;
                }
                // Startup must match the host's known default. An externally
                // left HD sensor has no exact VGA snapshot available to this process.
                if(runtimeMode) {err_="Runtime sensor left HD; external recovery required before startup";return false;}
                runtimeCameraSupported_[camera]=true;
            } else if(!regRead(base+0x140,magic)||!regRead(base+0x150,dimensions)||
               !regRead(base+0x160,bytes)||!regRead(base+0x170,stride)||
               magic!=0x43333432u||dimensions!=(uint32_t(frameHeightForCamera(camera+1))<<16|uint32_t(frameWidthForCamera(camera+1)))||
               bytes!=frameBytesForCamera(camera+1)||stride!=uint32_t(frameWidthForCamera(camera+1)*2)){
                err_="FPGA compressed-camera geometry mismatch";return false;
            }
            fprintf(stderr,"[wire-geometry] camera=%d width=%d height=%d frame_bytes=%u stride=%u raw_read=%d\n",
                    camera+1,frameWidthForCamera(camera+1),frameHeightForCamera(camera+1),bytes,stride,int(camera<2));
            // FPGA SRAM reconfiguration preserves DDR contents. Wait until
            // both compressed banks have received committed frames before
            // interpreting their new +153600 tag locations as frame counters.
            QElapsedTimer initialized;initialized.start();
            for(;;){
                uint32_t completed=0;
                if(!regRead(base+0xf0,completed)){err_="compressed frame commit counter read failed";return false;}
                if(completed>=2)break;
                if(initialized.elapsed()>8000){err_="compressed camera did not publish both banks";return false;}
                QThread::msleep(10);
            }
        }
        if (shared_) {
            pz_export_rx request{}; request.version = 1;
            shared_->sharedFd = ::ioctl(fd_, PZ_EXPORT_RX, &request);
            if (shared_->sharedFd < 0) { err_ = "8MiB RX DMA-BUF export required"; return false; }
        }
        return true;
    }

    static void alarmHandler(int) { timeoutHit_ = true; }
    static volatile sig_atomic_t timeoutHit_;

    bool regWrite(uint32_t addr, uint32_t val) {
        tdm::FairDmaGuard dmaLock(dmaMutex_.get());
        if (!tx_)
            return false;
        memcpy(tx_, &val, 4);
        DmaOp op{};
        op.offset_addr = 0;
        op.ddr3_addr = addr;
        op.total_length = 16;
        static const bool traceIo=qEnvironmentVariableIntValue("DETVIEW_SCCB_IO_TRACE")!=0;
        const bool diagnostic=traceIo && (addr==0x20000810u||addr==0x20000910u||addr==0x20000a10u);
        QElapsedTimer stamp;stamp.start();
        if(diagnostic) {fprintf(stderr,"SCCB_IO op=H2F stage=start monotonic-ns=%lld addr=%08x value=%08x\n",static_cast<long long>(stamp.msecsSinceReference())*1000000,addr,val);fflush(stderr);}
        const bool ok=ioctlTmo(H2F_CMD, &op, 3)==0;
        if(diagnostic) {fprintf(stderr,"SCCB_IO op=H2F stage=end monotonic-ns=%lld elapsed-ns=%lld addr=%08x ok=%d\n",static_cast<long long>(stamp.msecsSinceReference())*1000000+stamp.nsecsElapsed(),static_cast<long long>(stamp.nsecsElapsed()),addr,ok);fflush(stderr);}
        return ok;
    }

    bool regRead(uint32_t addr, uint32_t &val) {
        tdm::FairDmaGuard dmaLock(dmaMutex_.get());
        DmaOp op{};
        op.offset_addr = tdm::cameraScratchOffset;
        op.ddr3_addr = addr;
        op.total_length = 16;
        static const bool traceIo=qEnvironmentVariableIntValue("DETVIEW_SCCB_IO_TRACE")!=0;
        const bool diagnostic=traceIo && ((addr>=0x20000c00u&&addr<0x20000f00u)||
            (addr>=0x200008a0u&&addr<=0x200008f0u)||
            (addr>=0x200009a0u&&addr<=0x200009f0u)||
            (addr>=0x20000aa0u&&addr<=0x20000af0u)||
            addr==0x20000820u||addr==0x20000830u||addr==0x20000920u||addr==0x20000930u||addr==0x20000a20u||addr==0x20000a30u);
        QElapsedTimer stamp;stamp.start();
        if(diagnostic) {fprintf(stderr,"SCCB_IO op=F2H stage=start monotonic-ns=%lld addr=%08x\n",static_cast<long long>(stamp.msecsSinceReference())*1000000,addr);fflush(stderr);}
        const bool ok=ioctlTmo(F2H_CMD, &op, 3)==0;
        if(diagnostic) {
            char raw16[33]={0};
            if(ok) for(unsigned i=0;i<16;++i) snprintf(raw16+2*i,3,"%02x",static_cast<unsigned char>(rx_[op.offset_addr+i]));
            // Emit the entire record under one stdio lock so model logging
            // cannot split the transport bytes between separate writes.
            fprintf(stderr,"SCCB_IO op=F2H stage=end monotonic-ns=%lld elapsed-ns=%lld addr=%08x ok=%d raw16=%s\n",static_cast<long long>(stamp.msecsSinceReference())*1000000+stamp.nsecsElapsed(),static_cast<long long>(stamp.nsecsElapsed()),addr,ok,raw16);fflush(stderr);
        }
        if(!ok) return false;
        memcpy(&val, rx_ + op.offset_addr, 4);
        return true;
    }

    // Keep a diagnostic sequence together; frame copies must not interleave
    // between its before/after counters. Hardware may still advance, so callers
    // must validate the two sequence values and retry a torn snapshot.
    bool regReadBatch(const uint32_t *addresses, uint32_t *values, size_t count, qint64 *lockWaitMs=nullptr) {
        QElapsedTimer waiting;
        if(lockWaitMs) waiting.start();
        tdm::FairDmaGuard dmaLock(dmaMutex_.get());
        if(lockWaitMs) *lockWaitMs=waiting.elapsed();
        if (!rx_ || !addresses || !values || count > 8) return false;
        for (size_t i=0; i<count; ++i) {
            DmaOp op{};
            op.offset_addr=tdm::cameraScratchOffset;
            op.ddr3_addr=addresses[i]; op.total_length=16;
            if (ioctlTmo(F2H_CMD,&op,3)!=0) return false;
            memcpy(values+i,rx_+op.offset_addr,4);
        }
        return true;
    }

    /* 六路采集线程共用一条 DMA 通道与同一对 tx/rx 缓冲，必须串行化。
       单次等待上限取 2s（与 camview 一致）：丢 MSI 时不能让整块卡住几十秒，
       上层线程会保留上一帧并在下一次帧标签变化时重试。 */
    bool ddrRead(uint32_t addr, uint32_t len, void *out) {
        if (len > tdm::cameraAllocationBytes || (!out && len)) return false;
        tdm::FairDmaGuard dmaLock(dmaMutex_.get());
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

    // Shared RX staging remains owned through commit validation and CPU copy.
    uint64_t workerReadCalls(int camera) const { return workerReadCalls_[camera].load(); }
    bool configureCameraGeometry(const runtime_camera::Geometry& geometry) {
        if(!geometry.valid()) return false;
        tdm::FairDmaGuard lock(dmaMutex_.get());
        runtimeGeometries_[geometry.camera]=geometry;
        return true;
    }
    // Wire-guard decision for a C3/C4 transfer larger than the compressed frame.
    // `expected` is the target descriptor of an in-flight pair transaction when
    // one is registered, otherwise the committed descriptor. Both are the same
    // geometry contract and both are validated by the same predicate.
    static bool c34LargeTransferAdmitted(bool cameraSupported,
                                         const runtime_camera::Geometry& committed,
                                         bool expectedActive,
                                         const runtime_camera::Geometry& expected,
                                         uint32_t address, uint32_t totalLength, uint32_t offset) {
        if(!cameraSupported) return false;
        const runtime_camera::Geometry& geometry=expectedActive?expected:committed;
        return runtime_camera::admitsLargeTransfer(geometry,address,totalLength,offset);
    }
    // Register the target descriptor of an in-flight pair transaction. The mode
    // register and its geometry/bytes/stride readback are verified before the
    // transaction reads a frame, so the guard must admit that exact descriptor
    // while the committed table still describes the previous mode. Registration
    // fails closed: an unsupported or inexact descriptor leaves the committed one
    // in force, which is the pre-existing behaviour.
    bool expectCameraGeometry(const runtime_camera::Geometry& geometry) {
        if(!geometry.valid() || !runtimeCameraSupported_[geometry.camera]) return false;
        tdm::FairDmaGuard lock(dmaMutex_.get());
        expectedGeometries_[geometry.camera]=geometry;
        expectedGeometryActive_[geometry.camera]=true;
        return true;
    }
    void clearExpectedCameraGeometries() {
        tdm::FairDmaGuard lock(dmaMutex_.get());
        expectedGeometryActive_.fill(false);
    }
    // Pair verification owns RX across tag/frame/tag reads, including detach.
    template<class Work> bool withPairRead(Work work) {
        tdm::FairDmaGuard lock(dmaMutex_.get());
        cam34_pair::ReadBytes read=[&](uint32_t address,uint8_t* output,uint32_t bytes) {
            if(!output || bytes<16 || bytes>cam1::maxHostBytes) return false;
            DmaOp op{};op.offset_addr=bytes==16?tdm::cameraScratchOffset:0;
            op.ddr3_addr=address;op.total_length=bytes;
            if(ioctlTmo(F2H_CMD,&op,2)!=0)return false;
            std::memcpy(output,rx_+op.offset_addr,bytes);return true;
        };
        return work(read);
    }
    // All DMA submissions remain serialized; metadata uses a separate scratch.
    int cameraRead(int camera, uint32_t ping, uint32_t pong, uint32_t frameBytes,
                   bool delivered, uint32_t last, void* output, uint32_t& selected,
                   qint64& dmaNs, qint64& copyNs, qint64& capturedMs,
                   quint64& transferBytes, qint64& frameStartedNs) {
        transferBytes = 0; frameStartedNs = 0;
        if (camera < 0 || camera >= CAM_COUNT) return -1;
        if (!output || !frameBytes || frameBytes > cam1::maxHostBytes - 16) return -1;
        static const bool trace = qEnvironmentVariableIntValue("DETVIEW_CAPTURE_STAGES") != 0;
        static const bool probeCopy = qEnvironmentVariableIntValue("DETVIEW_COPY_PROBE") != 0;
        QString copyProbeResult;
        QElapsedTimer stages;
        qint64 waitNs = 0, tagNs = 0, frameNs = 0, pixelNs = 0;
        if (trace) stages.start();
        const int result = tdm::withCameraRxOwnership(dmaMutex_.get(), [&]() -> int {
            if (trace) { waitNs = stages.nsecsElapsed(); stages.restart(); }
            const auto geometry=runtimeGeometries_[camera];
            if(!geometry.valid() || frameBytes!=geometry.pixelBytes || ping!=geometry.ping || pong!=geometry.pong ||
               ((camera==2 || camera==3) && geometry.mode!=runtime_camera::Mode::Default && !runtimeCameraSupported_[camera])) return -1;
            uint32_t a = 0, b = 0;
            ++workerReadCalls_[camera];
            if (!cameraTagLocked(ping + frameBytes, a)) {
                if (trace) tagNs = stages.nsecsElapsed();
                return -1;
            }
            transferBytes += 16;
            if (!cameraTagLocked(pong + frameBytes, b)) {
                if (trace) tagNs = stages.nsecsElapsed();
                return -1;
            }
            transferBytes += 16;
            if (trace) {
                static thread_local int tagDbg = 0;
                if (tagDbg < 6) {
                    ++tagDbg;
                    fprintf(stderr, "[camera-tag] camera=%d ping=0x%08x pong=0x%08x a=0x%08x b=0x%08x last=0x%08x delivered=%d frameBytes=%u\n",
                        camera + 1, ping, pong, a, b, last, int(delivered), frameBytes);
                    fflush(stderr);
                }
            }
            if (trace) tagNs = stages.nsecsElapsed();
            const int bank = tdm::newestCameraBank(a, b, delivered, last);
            if (bank < 0) return 0;
            selected = bank == 0 ? a : b;
            DmaOp op{};
            // An uncompressed C3/C4 VGA/HD frame is a whole-window transfer: the
            // wire-guard admits it only at offset 0 (runtime_camera::admitsLargeTransfer).
            // The old threshold compared against C1's FRAME_BYTES (640x480 = 614400),
            // which equals the true-VGA byte count, so C3 VGA fell through to a slot
            // offset and the guard rejected the host's own read as a transport fault.
            if(!tdm::cameraLandingOffset(geometry,op.offset_addr)) return -1;
            op.ddr3_addr = bank == 0 ? ping : pong;
            op.total_length = frameBytes + 16;
            QElapsedTimer timer; timer.start();
            frameStartedNs = monotonicNs();
            const int dmaResult = ioctlTmo(F2H_CMD, &op, 2);
            if (trace) frameNs = timer.nsecsElapsed();
            if (dmaResult != 0) return -1;
            transferBytes += op.total_length;
            dmaNs = timer.nsecsElapsed();
            capturedMs = monotonicMs();
            const uint8_t* pixels = rx_ + op.offset_addr;
            timer.restart();
            const bool committed = tdm::copyCommittedCameraPixels(output, pixels, frameBytes, selected);
            copyNs = timer.nsecsElapsed();
            if (trace) pixelNs = copyNs;
            if (!committed) return 2;
            if (probeCopy) {
                // Diagnostic only: compare copy kernels on the actual coherent RX
                // mapping while retaining ownership. Never change published pixels.
                static thread_local std::array<bool, CAM_COUNT> measured{};
                if (!measured[camera]) {
                    measured[camera] = true;
                    QByteArray scratch(int(frameBytes), Qt::Uninitialized);
                    double manualMs = 0, libcMs = 0;
                    bool identical = true;
                    void* (* volatile libcCopy)(void*, const void*, size_t) = &std::memcpy;
                    for (int repeat = 0; repeat < 8; ++repeat) {
                        for (int step = 0; step < 2; ++step) {
                            const bool manual = ((repeat + step) % 2) == 0;
                            QElapsedTimer bench; bench.start();
                            if (manual) tdm::copyCameraPixels(scratch.data(), pixels, frameBytes);
                            else libcCopy(scratch.data(), pixels, frameBytes);
                            const double elapsed = bench.nsecsElapsed() / 1e6;
                            if (manual) manualMs += elapsed; else libcMs += elapsed;
                            identical &= std::memcmp(scratch.constData(), output, frameBytes) == 0;
                        }
                    }
                    copyProbeResult = QString("[capture-copy-probe] camera=%1 bytes=%2 manual_ms=%3 libc_ms=%4 identical=%5")
                        .arg(camera+1).arg(frameBytes).arg(manualMs/8,0,'f',6).arg(libcMs/8,0,'f',6).arg(int(identical));
                }
            }
            if(camera==2 || camera==3){
                const QString dir=qEnvironmentVariable("DETVIEW_CAM34_EVIDENCE_DIR");
                if(!dir.isEmpty() && !m_wireEvidenceWritten[camera-2]){
                    QFile proof(dir+QString("/cam%1_dma_identity.json").arg(camera+1));
                    QDir().mkpath(dir);
                    if(proof.open(QIODevice::WriteOnly)){
                        const QJsonObject row{{"camera",camera+1},{"frame_bytes",int(frameBytes)},
                            {"dma_bytes",int(op.total_length)},{"bank",bank},{"base",QString::number(op.ddr3_addr,16)},
                            {"tag",QString::number(selected)},{"host_ms",double(capturedMs)}};
                        proof.write(QJsonDocument(row).toJson());m_wireEvidenceWritten[camera-2]=true;
                    }
                }
            }
            return 1;
        });
        if (!copyProbeResult.isEmpty()) fprintf(stderr, "%s\n", copyProbeResult.toUtf8().constData());
        if (trace) {
            // Per-caller aggregates are updated and logged after RX ownership ends.
            struct Row {
                qint64 start = 0, wait = 0, tag = 0, dma = 0, copy = 0, maximumWait = 0;
                quint64 calls = 0, good = 0, noFrame = 0, rejected = 0, errors = 0, dmas = 0;
            };
            static thread_local std::array<Row, CAM_COUNT> rows{};
            auto& row = rows[camera];
            const qint64 now = monotonicMs();
            if (!row.start) row.start = now;
            ++row.calls; row.good += result == 1; row.noFrame += result == 0;
            row.rejected += result == 2; row.errors += result < 0; row.dmas += frameStartedNs != 0;
            row.wait += waitNs; row.tag += tagNs; row.dma += frameNs; row.copy += pixelNs;
            row.maximumWait = std::max(row.maximumWait, waitNs);
            if (now - row.start >= 5000) {
                fprintf(stderr, "[capture-stages] camera=%d seconds=%.3f calls=%llu good=%llu no_frame=%llu rejected=%llu errors=%llu dmas=%llu wait_ms=%.3f max_wait_ms=%.3f tags_ms=%.3f dma_ms=%.3f copy_ms=%.3f\n",
                    camera + 1, (now-row.start)/1000.0, (unsigned long long)row.calls,
                    (unsigned long long)row.good, (unsigned long long)row.noFrame,
                    (unsigned long long)row.rejected, (unsigned long long)row.errors,
                    (unsigned long long)row.dmas, row.wait/1e6, row.maximumWait/1e6,
                    row.tag/1e6, row.dma/1e6, row.copy/1e6);
                row = Row{}; row.start = now;
            }
        }
        return result;
    }

    int cameraReadFpga(int camera, int generation, int height, bool delivered, uint32_t last,
                       void* output, uint32_t& selected, qint64& dmaNs, qint64& copyNs,
                       qint64& capturedMs, std::shared_ptr<scheme2::Input>& input,
                         scheme2::PrefetchTiming* timing,
                         quint64& transferBytes, qint64& frameStartedNs) {
        transferBytes = 0; frameStartedNs = 0;
        if (camera < 0 || camera >= CAM_COUNT || !output) return -1;
        tdm::FairDmaGuard lock(dmaMutex_.get());
        if(camera==2 || camera==3 || runtimeGeometries_[camera].mode==runtime_camera::Mode::Hd720) return -1;
        ++workerReadCalls_[camera];
        if (!shared_ || shared_->consumerHeld) scheme2Quarantine("admission/transport mismatch");
        constexpr uint32_t base = 0x40020000;
        auto check = [](bool ok, const char* why) { if (!ok) scheme2Quarantine(why); };
        auto read = [&](uint32_t address, uint32_t size, uint32_t offset) {
            DmaOp op{}; op.ddr3_addr = address; op.total_length = size; op.offset_addr = offset;
            check(ioctlTmo(F2H_CMD, &op, 3) == 0, "F2H failed");
            std::atomic_thread_fence(std::memory_order_seq_cst);
        };
        auto reg = [&](uint32_t offset) { uint32_t value = 0;
            check(cameraTagLocked(base + offset, value), "register read failed"); return value; };
        auto write = [&](uint32_t offset, uint32_t value) {
            memset(tx_, 0, 16); memcpy(tx_, &value, 4);
            DmaOp op{}; op.ddr3_addr = base + offset; op.total_length = 16;
            check(ioctlTmo(H2F_CMD, &op, 3) == 0, "register write failed");
        };
        auto poll = [&](bool converted, uint32_t jobs) {
            QElapsedTimer deadline; deadline.start();
            for (;;) {
                const uint32_t status = reg(0x10);
                check(!(status & 0x70), "FPGA error/config/quarantine");
                if (converted ? ((status & 0x7f) == 0x0b && reg(0x90) == uint32_t(jobs + 1)) :
                    ((status & 0x77) == 3)) return true;
                if (deadline.elapsed() >= 3000) {
                    if (!converted && status == 1 && reg(0x120) == 2) {
                        write(0x20, 0);
                        check((reg(0x10) & 0x7f) == 0 && reg(0x120) == 0,
                              "unpublished hold release failed");
                        write(0xc0, 4); write(0xd0, 0);
                        check(reg(0xc0) == 4 && reg(0xd0) == 0 && reg(0xb0) == 0,
                              "unpublished selector restore failed");
                        return false;
                    }
                    scheme2Quarantine("uncertain FPGA admission/conversion deadline");
                }
                // Admission still owns the converter and its destination. Only
                // disjoint RAW/tag traffic can run while the FPGA drains.
                lock.unlock();
                QThread::msleep(1);
                lock.relock();
            }
        };
        check(reg(0) == 0x444c5632 && (reg(0xa0) & 7) == 7 && reg(0xf0) == 0x3f &&
              reg(0x80) == FRAME_BYTES && (reg(0x10) & 0x77) == 0 && reg(0xb0) == 0 &&
              reg(0xc0) == 4 && reg(0xd0) == 0 && reg(0x120) == 0, "six-camera idle contract mismatch");
        write(0xc0, camera); write(0xd0, 0);
        const uint32_t destination = camera == 4 ? 0x0a000000 : 0x0b000000 + camera * 0x400000;
        check(reg(0x40) == destination && reg(0x60) == scheme2::SquareBytes &&
              reg(0x100) == 0x00800000u + camera * 0x400000u &&
              reg(0x110) == 0x00a00000u + camera * 0x400000u, "mode0 selector readback mismatch");
        // Audit the writable physical camera-bank configuration as the validated host does.
        for (uint32_t c = 0; c < 4; ++c) for (uint32_t offset : {0x80u, 0xc0u}) {
            uint32_t address = 0;
            check(cameraTagLocked(0x20000000 + c * 0x200 + offset, address), "bank audit failed");
            const uint64_t end = uint64_t(address) + 0x200000;
            check(end <= 0x10000000 && (end <= destination || address >= destination + scheme2::SquareBytes),
                  "RGB destination overlaps writable camera bank");
        }
        const uint32_t epoch = reg(0x50);
        if (timing) timing->holdCommand = monotonicMs();
        write(0x20, 1);
        if (!poll(false, 0)) { scheme2::admission().retire(); return 0; }
        const uint32_t source = reg(0x30), sequence = reg(0xe0);
        auto validate = [&] {
            uint32_t tag = 0;
            check((reg(0x10) & 0x77) == 3 && reg(0x30) == source && reg(0x50) == uint32_t(epoch + 1) &&
                  reg(0xe0) == sequence && reg(0xc0) == uint32_t(camera) && reg(0xd0) == 0 &&
                  reg(0xb0) == 0 && reg(0x40) == destination && reg(0x60) == scheme2::SquareBytes &&
                  reg(0x120) == 4 && (source == 0x00800000u + camera * 0x400000u ||
                  source == 0x00a00000u + camera * 0x400000u) &&
                  cameraTagLocked(source + FRAME_BYTES, tag) && tag == sequence,
                  "same-frame lease identity changed");
        };
        validate();
        if (timing) timing->holdValidated = monotonicMs();
        if (delivered && !tdm::newerCameraTag(sequence, last)) {
            write(0x20, 0); write(0xc0, 4); write(0xd0, 0);
            scheme2::admission().retire(); return 0;
        }
        QElapsedTimer timer; timer.start();
        frameStartedNs = monotonicNs();
        read(source, FRAME_BYTES + 16, tdm::cameraSlotOffset(camera));
        transferBytes += FRAME_BYTES + 16;
        dmaNs = timer.nsecsElapsed(); capturedMs = monotonicMs();
        uint32_t rawTag = 0;
        memcpy(&rawTag, rx_ + tdm::cameraSlotOffset(camera) + FRAME_BYTES, 4);
        check(rawTag == sequence, "RAW commit tag differs from RGB lease");
        // Conversion polling temporarily releases the DMA mutex. Shared HD RX
        // staging overlaps these legacy slots, so detach RAW before any poll.
        timer.restart();
        check(tdm::copyCommittedCameraPixels(output, rx_ + tdm::cameraSlotOffset(camera),
              FRAME_BYTES, sequence), "RAW commit changed before copy");
        copyNs = timer.nsecsElapsed();
        const uint32_t jobs = reg(0x90);
        write(0x20, 3); poll(true, jobs); validate();
        // RGB destination is now immutable under this sole converter owner.
        // Retire the camera hold before BEGIN and restore converter defaults.
        // Single admission keeps this RGB destination immutable until retirement;
        // camera/scratch DMA may continue outside the reserved host RX slot.
        write(0x20, 0);
        check((reg(0x10) & 7) == 0, "camera release failed");
        write(0xc0, 4); write(0xd0, 0);
        check(reg(0xc0) == 4 && reg(0xd0) == 0 && reg(0x120) == 0 &&
               reg(0x40) == 0x0a000000, "camera defaults restore failed");
        if (timing) timing->release = monotonicMs();
        lock.unlock();
        // RAW is already detached. Construct Input outside DMA ownership: its
        // consumer callbacks acquire this same mutex. Admission remains occupied.
        input = std::make_shared<scheme2::Input>();
        if (timing) input->timing = *timing;
        input->fd = shared_->sharedFd; input->base = rx_; input->height = height;
        if (scheme2::verify()) input->goldenRgb = scheme2::golden(output, height);
        input->camera = camera; input->sourceGeneration = generation; input->tag = sequence;
        input->epoch = epoch + 1; input->source = source; input->backing = shared_;
        input->uncertain = [] { scheme2Quarantine("consumer unwound without verified completion"); };
        auto transport = shared_;
        auto lease = std::make_shared<pz_lease>();
        auto beganMs = std::make_shared<qint64>(0);
        std::weak_ptr<scheme2::Input> weak = input;
        input->begin = [transport, lease, beganMs, weak, destination, height, camera, sequence, epoch] {
            tdm::FairDmaGuard guard(transport->mutex.get());
            if (transport->consumerHeld) scheme2Quarantine("overlapping synchronous consumer");
            DmaOp op{}; op.ddr3_addr = destination + scheme2::crop(height);
            op.total_length = scheme2::bytes(height); op.offset_addr = scheme2::Offset;
            if (::ioctl(transport->fd, F2H_CMD, &op) != 0) scheme2Quarantine("deferred RGB F2H failed");
            std::atomic_thread_fence(std::memory_order_seq_cst);
            if (scheme2::verify()) {
            auto owner = weak.lock();
            if (!owner) scheme2Quarantine("input owner lost before consumption");
            const auto& goldenRgb = owner->goldenRgb;
            const size_t bad = scheme2::mismatch(goldenRgb.data(), transport->rx + scheme2::Offset, goldenRgb.size());
            if (bad != goldenRgb.size()) {
                fprintf(stderr, "[scheme2-verify-input] FAIL camera=%d tag=%u height=%d byte=%zu expected=%u actual=%u\n",
                    camera + 1, sequence, height, bad, goldenRgb[bad], transport->rx[scheme2::Offset + bad]);
                scheme2Quarantine("same-frame RGB input byte parity failed");
            }
            static std::atomic<unsigned> count{0};
            const unsigned passed = ++count;
            fprintf(stderr, "[scheme2-verify-input] PASS camera=%d tag=%u epoch=%u height=%d bytes=%zu count=%u performance_sample=0\n",
                    camera + 1, sequence, epoch + 1, height, goldenRgb.size(), passed);
            if (passed == scheme2::verifyCount())
                fprintf(stderr, "[scheme2-verify] INPUT_COUNT_REACHED count=%u required=%u output_parity_pending=1 performance_sample=0\n", passed, scheme2::verifyCount());
            }
            lease->version = 1; lease->offset = scheme2::Offset; lease->length = scheme2::SquareBytes;
            if (::ioctl(transport->fd, PZ_BEGIN, lease.get()) != 0 || !lease->token)
                scheme2Quarantine("deferred PZ_BEGIN failed");
            transport->consumerHeld = true; *beganMs = monotonicMs();
        };
        input->end = [transport, lease, beganMs, camera, sequence, epoch, height]() mutable {
            // Priority retirement waits only for the active transport section.
            // No queued userspace transfer can enter the driver's lock first.
            tdm::FairDmaGuard guard(transport->mutex.get(), true);
            if (::ioctl(transport->fd, PZ_END, lease.get()) != 0) scheme2Quarantine("PZ_END failed");
            transport->consumerHeld = false;
            if (!scheme2::verify()) fprintf(stderr, "[scheme2] camera=%d tag=%u epoch=%u height=%d payload_bytes=%u lease_hold_ms=%lld\n",
                    camera + 1, sequence, epoch + 1, height, scheme2::bytes(height),
                    static_cast<long long>(monotonicMs() - *beganMs));
        };
        selected = sequence;
        return 1;
    }

    const char *lastErr() const { return err_; }
#include "motion_device_members.inc"

private:
    bool failOpen() {
        if (!shared_) return false;
        // MAP performs allocation only: no H2F/F2H or consumer has started.
        // Explicit UNMAP confirms the driver is idle and frees any earlier MAP.
        DmaOp release{}; release.cmd = 3;
        if (ioctlTmo(UNMAP_CMD, &release, 3) != 0)
            scheme2Quarantine("preflight UNMAP could not confirm idle cleanup");
        fprintf(stderr, "[scheme2-preflight] FATAL %s; tx_bytes=%u rx_bytes=%u; idle UNMAP confirmed, quitting; allocation failure: inspect CMA free/fragmentation and DMA mask (no DMA submitted)\n",
                err_, txWindowBytes(), windowBytes());
        fflush(stderr);
        close();
        return false;
    }
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
        // Default C3/C4 never read VGA RAW. A transfer larger than the compressed
        // frame is admitted only against an exact HD/VGA descriptor: the target
        // descriptor of the in-flight pair transaction when one is registered
        // (its mode/geometry/bytes/stride were read back from the device first),
        // otherwise the committed one. No condition is relaxed by that choice.
        if(cmd==F2H_CMD && op && op->ddr3_addr>=0x01000000u && op->ddr3_addr<0x01800000u &&
           op->total_length>CAM34_FRAME_BYTES+16){
             const int camera=int((op->ddr3_addr-0x00800000u)/0x00400000u);
             const bool expectedActive=expectedGeometryActive_[camera];
             const bool admitted=c34LargeTransferAdmitted(runtimeCameraSupported_[camera],
                 runtimeGeometries_[camera],expectedActive,expectedGeometries_[camera],
                 op->ddr3_addr,op->total_length,op->offset_addr);
             if(!admitted) {
                 fprintf(stderr,"[wire-guard] incompatible C3/C4 DMA addr=0x%08x bytes=%u offset=%u committed_mode=%u target_active=%d\n",
                         op->ddr3_addr,op->total_length,op->offset_addr,
                         unsigned(runtimeGeometries_[camera].mode),int(expectedActive));
                 err_="C3/C4 transfer incompatible with verified runtime geometry";errno=EINVAL;return -1;
             }
        }
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
        if (r < 0 || timeoutHit_ || ms >= 30.0) {
            fprintf(stderr, "[diag] t=%lld.%03ld pango_ioctl tid=%ld cmd=%lx selector=%u offset=0x%08x addr=0x%08x len=%u ms=%.3f rc=%d errno=%d (%s) alarm=%d\n",
                    (long long)ts1.tv_sec, ts1.tv_nsec / 1000000, long(syscall(SYS_gettid)), cmd,
                    op ? op->cmd : 0, op ? op->offset_addr : 0,
                    op ? op->ddr3_addr : 0, op ? op->total_length : 0,
                    ms, r, r < 0 ? ioctlErrno : 0, r < 0 ? strerror(ioctlErrno) : "success", (int)timeoutHit_);
            fflush(stderr);
        }
        if (timeoutHit_) {
            err_ = "ioctl timeout";
            if (!shared_ || (cmd != MAP_CMD && cmd != UNMAP_CMD)) noteFailure();
            return -1;
        }
        if (r < 0) {
            if (!shared_ || (cmd != MAP_CMD && cmd != UNMAP_CMD)) noteFailure();
            return r;
        }
        failures_ = 0;
        return r;
    }
    /* 连续失败自愈：驱动的 pango_cdev_open 每次打开设备都会把 g_dma_flag 等状态清零，
       所以"退出进程 + 重新打开"本身就等于恢复，不需要 rmmod/insmod。连续失败到阈值就
       主动退出（硬退出，避免卡住的线程拖延），交给守护脚本 run_detview.sh 重启。 */
    void noteFailure() {
        if(runtimeProtected_) { ++failures_; err_="Runtime DMA failure: automatic reopen inhibited"; return; }
        if (scheme2::enabled()) scheme2Quarantine("DMA ioctl failed; automatic reopen prohibited");
        const int n = ++failures_;
        if (n < kRecoverAfterFailures)
            return;
        fprintf(stderr, "[recover] %d consecutive pango ioctl failures -> exit(%d) for supervisor restart\n", n, kRestartExitCode);
        fflush(stderr);
        ::_exit(kRestartExitCode);
    }
    void close() {
        if (shared_) shared_.reset();
        else if (fd_ >= 0)
            ::close(fd_);
        fd_ = -1;
    }
    const char *err_ = "ok";
    int fd_ = -1;
    uint8_t *tx_ = nullptr;
    uint8_t *rx_ = nullptr;
    std::shared_ptr<tdm::FairDmaMutex> dmaMutex_ = std::make_shared<tdm::FairDmaMutex>();
    std::array<std::atomic<uint64_t>,CAM_COUNT> workerReadCalls_{};
    std::array<bool,CAM_COUNT> runtimeCameraSupported_{};
    std::array<runtime_camera::Geometry,CAM_COUNT> runtimeGeometries_{};
    // Target descriptor of an in-flight C3/C4 pair transaction; only the
    // wire-guard reads it and only while that transaction is between its
    // verified mode write and its end.
    std::array<bool,CAM_COUNT> expectedGeometryActive_{};
    std::array<runtime_camera::Geometry,CAM_COUNT> expectedGeometries_{};
    std::shared_ptr<Scheme2Transport> shared_;
    bool m_wireEvidenceWritten[2] = {};
    uint32_t windowBytes() const { return scheme2::enabled() ? scheme2::Window : 0x400000; }
    uint32_t txWindowBytes() const { return scheme2::enabled() ? 0x1000 : 0x400000; }
    static const int kRecoverAfterFailures = 6;   // 连续失败几次就退出，让守护脚本重启
    std::atomic<int> failures_{0};
    std::atomic<bool> runtimeProtected_{false};
};

volatile sig_atomic_t PangoDev::timeoutHit_ = 0;

/* ---- C3/C4 large-transfer wire-guard regression (no device access) ----
   2026-10-16 board trial: the C3 HD transition rolled back because the
   publication hook had to read the HD frame while the committed descriptor still
   described mode A, so the guard rejected its own transaction. These cases pin
   both halves of the decision: the committed-only descriptor still refuses, and
   the in-flight target descriptor is admitted only for an exact uncompressed
   HD/VGA descriptor (mode, contract length, offset 0, documented bank). */
static bool selfTestC34WireGuard() {
    using runtime_camera::Geometry;
    using runtime_camera::Mode;
    int failures = 0, cases = 0;
    auto check = [&](bool ok, const char* what) {
        ++cases;
        if (!ok) { ++failures; fprintf(stderr, "WIRE_GUARD_DECISION_SELFTEST_FAIL %s\n", what); }
    };
    const Geometry committedA2 = runtime_camera::geometry(2);
    const Geometry committedA3 = runtime_camera::geometry(3);
    const Geometry hd2 = runtime_camera::geometry(2, Mode::Hd720);
    const Geometry hd3 = runtime_camera::geometry(3, Mode::Hd720);
    const Geometry vga2 = runtime_camera::geometry(2, Mode::FullVga);
    const Geometry bogus{};
    check(hd2.transferBytes() == 1843216u && hd2.pixelBytes == 1843200u &&
          hd2.ping == 0x01000000u && hd2.pong == 0x01200000u,
          "C3 HD descriptor must match the documented banks and length");
    check(hd3.ping == 0x01400000u && hd3.pong == 0x01600000u,
          "C4 HD descriptor must match the documented banks");
    // Pre-fix failure: the committed mode A descriptor refuses the target HD read.
    check(!PangoDev::c34LargeTransferAdmitted(true, committedA2, false, bogus, 0x01200000u, 1843216u, 0),
          "committed mode A must refuse");
    check(!PangoDev::c34LargeTransferAdmitted(true, committedA2, false, hd2, 0x01200000u, 1843216u, 0),
          "no in-flight descriptor leaves the committed mode A in force");
    // Fix: the exact in-flight target descriptor admits both documented banks.
    check(PangoDev::c34LargeTransferAdmitted(true, committedA2, true, hd2, 0x01000000u, 1843216u, 0),
          "C3 ping must be admitted");
    check(PangoDev::c34LargeTransferAdmitted(true, committedA2, true, hd2, 0x01200000u, 1843216u, 0),
          "C3 pong must be admitted");
    check(PangoDev::c34LargeTransferAdmitted(true, committedA3, true, hd3, 0x01400000u, 1843216u, 0),
          "C4 ping must be admitted");
    check(PangoDev::c34LargeTransferAdmitted(true, committedA3, true, hd3, 0x01600000u, 1843216u, 0),
          "C4 pong must be admitted");
    // Everything else is still refused.
    check(!PangoDev::c34LargeTransferAdmitted(true, committedA2, true, hd2, 0x01000000u, 1843200u, 0),
          "exact contract transfer length required");
    check(!PangoDev::c34LargeTransferAdmitted(true, committedA2, true, hd2, 0x01000000u, 1843216u, 16),
          "zero offset required");
    check(!PangoDev::c34LargeTransferAdmitted(true, committedA2, true, hd2, 0x011c2000u, 1843216u, 0),
          "a tag address is not a documented bank");
    check(!PangoDev::c34LargeTransferAdmitted(true, committedA2, true, hd2, 0x01300000u, 1843216u, 0),
          "an undocumented bank must be refused");
    check(PangoDev::c34LargeTransferAdmitted(true, committedA2, true, vga2, 0x01000000u, 614416u, 0),
          "mode B exact ping target must be admitted");
    check(PangoDev::c34LargeTransferAdmitted(true, committedA2, true, vga2, 0x01200000u, 614416u, 0),
          "mode B exact pong target must be admitted");
    check(!PangoDev::c34LargeTransferAdmitted(true, committedA2, true, vga2, 0x01000000u, 1843216u, 0),
          "mode B must refuse HD transfer length");
    check(!PangoDev::c34LargeTransferAdmitted(true, committedA2, true, committedA2, 0x01000000u, 153616u, 0),
          "mode A is not an HD descriptor");
    check(!PangoDev::c34LargeTransferAdmitted(true, committedA2, true, hd3, 0x01000000u, 1843216u, 0),
          "a C4 descriptor cannot admit a C3 read");
    check(!PangoDev::c34LargeTransferAdmitted(true, committedA2, true, bogus, 0x01000000u, 1843216u, 0),
          "an invalid in-flight descriptor must refuse");
    check(!PangoDev::c34LargeTransferAdmitted(false, committedA2, true, hd2, 0x01000000u, 1843216u, 0),
          "an unsupported camera must refuse");
    fprintf(stderr, failures ? "WIRE_GUARD_DECISION_SELFTEST_FAIL cases=%d failures=%d\n"
                             : "WIRE_GUARD_DECISION_SELFTEST_PASS cases=%d failures=%d\n",
            cases, failures);
    return failures == 0 && cases >= 17;
}

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
    runtime_camera::Geometry geometries[CAM_COUNT]; // Captured geometry, not UI state.
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
        : dev_(dev), frames_(frames), camera_(camera), geometry_(runtime_camera::geometry(camera - 1)) {}
    void stop() { running_ = false; }
    // Configure only after this reader joins. Its mode is independent of the
    // capture view; each restart invalidates publications from the previous run.
    void restartForResolution(bool hd,bool requireFresh=false,uint32_t priorSequence=0,
                               uint32_t staleTag0=0,uint32_t staleTag1=0) {
        restartForMode(hd ? runtime_camera::Mode::Hd720 : runtime_camera::Mode::Default,
                       requireFresh,priorSequence,staleTag0,staleTag1);
    }
    void restartForMode(runtime_camera::Mode mode,bool requireFresh=false,uint32_t priorSequence=0,
                        uint32_t staleTag0=0,uint32_t staleTag1=0) {
        if (isRunning() || !runtime_camera::supportsMode(camera_ - 1,mode) ||
            geometry_.generation==std::numeric_limits<uint64_t>::max()) return;
        const bool hd=mode==runtime_camera::Mode::Hd720;
        hd_ = hd;
        if (hd) fprintf(stderr,"[motion-capability] camera=%d HD unsupported; motion hint disabled, HD analytics gated\n",camera_);
        requireFresh_=requireFresh; priorSequence_=priorSequence;
        staleTags_[0]=staleTag0;staleTags_[1]=staleTag1;
        geometry_ = runtime_camera::geometry(camera_ - 1,mode,geometry_.generation + 1);
        running_ = true; start();
    }
    bool restartForGeometry(const runtime_camera::Geometry& geometry,uint32_t sequence,
                            uint32_t stale0=0,uint32_t stale1=0) {
        if(isRunning() || !geometry.valid() || geometry.camera!=camera_-1) return false;
        geometry_=geometry;hd_=geometry.mode==runtime_camera::Mode::Hd720;
        requireFresh_=true;priorSequence_=sequence;staleTags_[0]=stale0;staleTags_[1]=stale1;
        running_=true;start();return true;
    }
    /* Deliver owned camera pixels to a bounded analytics mailbox, not a GUI event queue. */
    void setVisionSink(const std::atomic<int> *pane, const std::atomic<int> *generation,
                       std::atomic<quint64> *sequence, std::function<void(const VisionFrame&)> sink,
                       int stereoMask, bool motionEnabled) {
        motionEnabled_ = motionEnabled;
        inferPane_ = pane;
        generation_ = generation;
        sequence_ = sequence;
        visionSink_ = std::move(sink);
        stereoMask_ = stereoMask;
    }
    /* 当前显示模式（0..5 = 单路，CAM_COUNT = 整幅）：单路时只采那一路，其余停采 */
    void setModePtr(const std::atomic<int> *mode) { mode_ = mode; }
    void setPausedPtr(const std::atomic<bool> *paused) { paused_ = paused; }
    void setHdmiPtr(const std::atomic<bool> *hdmi) { hdmi_ = hdmi; }
    void set720pModePtr(const std::atomic<bool>* mode) { native720_=mode; }
    void setResolutionBusyPtr(const std::atomic<bool>* busy) { resolutionBusy_=busy; }

protected:
    void run() override {
        const int idx = camera_ - 1;
        uint32_t deliveredTag = priorSequence_;
        bool delivered = requireFresh_;
        const auto geometry = geometry_;
        if (!geometry.valid()) return;
        const uint32_t frameBytes = geometry.pixelBytes;
        const int frameWidth = int(geometry.width);
        const int frameHeight = int(geometry.height);
        QByteArray frame(frameBytes, 0);
        if(idx==0) frame.reserve(cam1::maxHostBytes);
        tdm::FrameRate captureRate;
        captureRate.reset(monotonicMs());
        qint64 auditStartMs = monotonicMs(), readNs = 0, dmaNsTotal = 0, copyNsTotal = 0;
        uint64_t auditFrames = 0, sequenceAdvance = 0, unstable = 0;
        quint64 auditBytes = 0, auditFrameDmas = 0, auditPolls = 0, auditReadErrors = 0;
        // Source retires production frames far above 30 fps: the FPGA tag-advance
        // rate is ~45/s for C1/C2 and ~29/s for C3/C4. The cap only throttles the
        // host read loop, so a 30 default starved single- and six-camera display.
        // 60 leaves headroom to cover the two A5/A7 pairs while still bounding the
        // per-camera read rate; DETVIEW_CAPTURE_MAX_FPS still overrides it.
        const int captureMaximumFps = qEnvironmentVariableIsSet("DETVIEW_CAPTURE_MAX_FPS") ?
            qBound(0, qEnvironmentVariableIntValue("DETVIEW_CAPTURE_MAX_FPS"), 120) : 60;
        tdm::CapturePacing pacing(captureMaximumFps);
        qint64 trafficStartMs = monotonicMs();
        auto reportTraffic = [&](bool force) {
            const qint64 now = monotonicMs();
            if (now <= trafficStartMs || (!force && now - trafficStartMs < 5000)) return;
            fprintf(stderr, "[capture-traffic] camera=%d started_ms=%lld ended_ms=%lld seconds=%.3f polls=%llu frame_dmas=%llu dma_bytes=%llu read_errors=%llu maximum_fps=%d\n",
                idx+1, (long long)trafficStartMs, (long long)now, (now-trafficStartMs)/1000.0,
                (unsigned long long)auditPolls, (unsigned long long)auditFrameDmas,
                (unsigned long long)auditBytes, (unsigned long long)auditReadErrors, captureMaximumFps);
            trafficStartMs = now;
            auditBytes = auditFrameDmas = auditPolls = auditReadErrors = 0;
        };
        bool measuring = true;
        bool measureTagAdvance = false;
        auto suspendMeasurement = [&]() {
            if (!measuring) return;
            reportTraffic(true);
            measuring = false;
            measureTagAdvance = false;
            pacing.reset();
            QMutexLocker lock(&frames_->mutex);
            frames_->fps[idx] = 0;
            frames_->lastCapturedMs[idx] = 0;
        };
        while (running_) {
            if (measuring) reportTraffic(false);
            if (paused_ && paused_->load()) { suspendMeasurement(); msleep(20); continue; }
            // HDMI owns C5/C6 only. Park the other workers before any tag
            // polling, DMA or inference admission; F resumes these workers.
            if (hdmi_ && hdmi_->load() && idx != tdm::hdmiLeftCamera && idx != tdm::hdmiRightCamera) {
                if (measuring) fprintf(stderr, "[hdmi-capture] camera=%d suspended\n", idx + 1);
                suspendMeasurement(); msleep(20); continue;
            }
            // Park excluded cameras before tag polling and frame DMA.
            if(native720_ && native720_->load() && !(0x0du & (1u<<idx))) {
                suspendMeasurement(); msleep(20); continue;
            }
            const int sourceGeneration = generation_ ? generation_->load() : 0;
            /* 设备模式：整幅时六路全采；单选时只采那一路（其余不发 DMA、不轮询标签） */
            if (mode_) {
                const int mode = mode_->load();
                if (mode != CAM_COUNT && mode != idx) {
                    suspendMeasurement();
                    msleep(50);
                    continue;
                }
            }
            if (!measuring) {
                fprintf(stderr, "[capture-resume] camera=%d\n", idx + 1);
                measuring = true;
                captureRate.reset(monotonicMs());
                auditStartMs = monotonicMs(); auditFrames = sequenceAdvance = unstable = 0;
                readNs = dmaNsTotal = copyNsTotal = 0;
                trafficStartMs = monotonicMs();
            }
            VisionEvidence::instance().active(idx, sourceGeneration, frameWidth, frameHeight, hd_);
            QElapsedTimer readTimer; readTimer.start();
            const qint64 pacingWait = pacing.waitNs(monotonicNs());
            if (pacingWait > 0) {
                msleep(static_cast<unsigned long>(std::min<qint64>(10, (pacingWait + 999999) / 1000000)));
                continue;
            }
            // A display snapshot may still own this recycled buffer. Allocate
            // fresh writable storage instead of copying old pixels on detach;
            // cameraRead overwrites every pixel before publishing it.
            if (!frame.isDetached()) frame = QByteArray(frameBytes, Qt::Uninitialized);
            uint32_t selectedTag = 0;
            qint64 dmaNs = 0, copyNs = 0, capturedMs = 0;
            quint64 transferBytes = 0;
            qint64 frameStartedNs = 0;
            std::shared_ptr<scheme2::Input> fpgaInput;
            scheme2::PrefetchTiming timing;
            auto* timingPtr = scheme2::enabled() && scheme2::prefetchTimingEnabled() ? &timing : nullptr;
            const scheme2::Selection selection = !hd_ && !(resolutionBusy_ && resolutionBusy_->load()) && scheme2::enabled() && idx!=2 && idx!=3 && inferPane_ && inferPane_->load() == idx &&
                !(hdmi_ && hdmi_->load()) ? scheme2::admission().claim(idx, sourceGeneration, timingPtr) : scheme2::Selection{};
            if (selection && timingPtr) timing.claim = monotonicMs();
            const int result = selection ?
                dev_->cameraReadFpga(idx, sourceGeneration, selection.height, delivered, deliveredTag,
                    frame.data(), selectedTag, dmaNs, copyNs, capturedMs, fpgaInput, timingPtr, transferBytes, frameStartedNs) :
                dev_->cameraRead(idx, geometry.ping, geometry.pong, frameBytes,
                    delivered, deliveredTag, frame.data(), selectedTag, dmaNs, copyNs, capturedMs, transferBytes, frameStartedNs);
            // Failed/unstable full-frame attempts consume the same cap as successful reads.
            if (frameStartedNs) { pacing.delivered(frameStartedNs); ++auditFrameDmas; }
            auditBytes += transferBytes; ++auditPolls;
            if (fpgaInput) fpgaInput->selection = selection;
            if (result == 0) { msleep(6); continue; }
            if (result == 2) { ++unstable; msleep(1); continue; }
            if (result < 0) {
                ++auditReadErrors;
                { QMutexLocker lock(&frames_->mutex); ++frames_->errors[idx]; }
                msleep(25);
                continue;
            }
            if (delivered && measureTagAdvance) sequenceAdvance += uint32_t(selectedTag - deliveredTag);
            if(requireFresh_ && (selectedTag==staleTags_[0] || selectedTag==staleTags_[1])) {
                ++unstable;msleep(1);continue;
            }
            measureTagAdvance = true;
            deliveredTag = selectedTag;
            delivered = true;
            readNs += readTimer.nsecsElapsed();
            dmaNsTotal += dmaNs; copyNsTotal += copyNs; ++auditFrames;
            const qint64 completedMs = monotonicMs();
            captureRate.add(completedMs);
            if (visionSink_) VisionEvidence::instance().captureGate(idx, sourceGeneration, hd_);
            const bool sendVision = !hd_ && !(resolutionBusy_ && resolutionBusy_->load()) && visionSink_ && !(hdmi_ && hdmi_->load()) &&
                ((inferPane_ && inferPane_->load() == idx) || (stereoMask_ & (1 << idx))) &&
                generation_ && sourceGeneration == generation_->load();
            // Keep an owning reference before swapping the display buffer.
            // Display publication must not wait on RGB conversion or motion metadata.
            const QByteArray visionRaw = sendVision ? frame : QByteArray();
            QMutexLocker lock(&frames_->mutex);
            if (!geometry.acceptsPublication(geometry_.generation, size_t(frame.size()))) continue;
            /* 零拷贝交接：与槽位互换缓冲。原来 `frames_->c[idx] = frame` 会因
               QByteArray 隐式共享在下一次写入时 detach（每帧每路白拷 0.6MB，
               4~6 路 × 25fps ≈ 60~90MB/s 的 DDR 流量）。交换后采集线程拿回旧缓冲继续用。 */
            qSwap(frame, frames_->c[idx]);
            if (uint32_t(frame.size()) != frameBytes)
                frame.resize(frameBytes);
            frames_->have[idx] = true;
            frames_->lastCapturedMs[idx] = completedMs;
            frames_->rawCapturedMs[idx] = capturedMs;
            frames_->tags[idx] = selectedTag;
            frames_->sourceGenerations[idx] = sourceGeneration;
            frames_->geometries[idx] = geometry;
            ++frames_->gen;
            ++frames_->camGen[idx];
            frames_->fps[idx] = captureRate.rate(completedMs);
            lock.unlock();
            if (sendVision) {
                QImage pixels(frameWidth, frameHeight, QImage::Format_RGB888);
                const uint16_t *src = reinterpret_cast<const uint16_t *>(visionRaw.constData());
                for (int y = 0; y < frameHeight; ++y)
                    rgb565ToRgb888Line(reinterpret_cast<const uint8_t *>(src + (size_t)y * frameWidth),
                                       frameWidth, pixels.scanLine(y));
                if (frameWidth != IMG_W || frameHeight != IMG_H)
                    pixels = pixels.scaled(IMG_W, IMG_H, Qt::IgnoreAspectRatio, Qt::FastTransformation);
                VisionFrame packet;
                packet.fpgaInput = std::move(fpgaInput);
                packet.cameraAcquisition = true;
                packet.image = std::move(pixels);
                packet.frameId = sequence_->fetch_add(1) + 1;
                packet.camera = idx;
                packet.sourceGeneration = sourceGeneration;
                packet.tag = selectedTag;
                packet.capturedMs = capturedMs;
                if (motionEnabled_ && inferPane_ && inferPane_->load() == idx)
                    packet.motion = dev_->motionHint(idx, sourceGeneration);
                const tdm::InferAge age{packet.frameId, sourceGeneration, idx, selectedTag, capturedMs};
                tdm::inferAgeEvent("capture_RAW_DMA_complete", age, capturedMs);
                tdm::inferAgeEvent("publish", age);
                if (packet.fpgaInput && timingPtr) packet.fpgaInput->timing.publish = monotonicMs();
                VisionEvidence::instance().event("vision_sent", age);
                visionSink_(packet);
            }
            const qint64 auditNow = monotonicMs();
            if (auditNow - auditStartMs >= 5000) {
                const double seconds = (auditNow - auditStartMs) / 1000.0;
                if (!scheme2::verify()) fprintf(stderr, "[capture] camera=%d width=%d height=%d wire_pixels_bytes=%u transfer_bytes=%u frames=%llu delivered_fps=%.2f tag_advance_rate=%.2f read_ms=%.3f frame_dma_ms=%.3f copy_ms=%.3f unstable=%llu\n",
                        idx + 1, frameWidth, frameHeight, frameBytes, frameBytes+16, (unsigned long long)auditFrames, auditFrames / seconds, sequenceAdvance / seconds,
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
    runtime_camera::Geometry geometry_;
    bool hd_ = false;
    bool requireFresh_=false;
    uint32_t priorSequence_=0;
    uint32_t staleTags_[2]={};
    std::atomic_bool running_{true};
    const std::atomic<int> *inferPane_ = nullptr;
    const std::atomic<int> *generation_ = nullptr;
    const std::atomic<bool> *paused_ = nullptr;
    const std::atomic<bool> *hdmi_ = nullptr;
    const std::atomic<bool> *native720_ = nullptr;
    const std::atomic<bool> *resolutionBusy_ = nullptr;
    std::atomic<quint64> *sequence_ = nullptr;
    int stereoMask_ = 0;
    bool motionEnabled_ = false;
    const std::atomic<int> *mode_ = nullptr;
    std::function<void(const VisionFrame&)> visionSink_;
};

// Asynchronous UI queue: only the matching successful completion advances it.
// A failure (including recovered prior modes) discards all remaining requests.
struct StartupC2Delay {
    // Board image sweeps: 144 is inside the verified clean 128..176 window.
    // +0x30 is write-only delay control; reads there are pixel diagnostics.
    template<class Read,class Write,class Tick>
    static bool apply(Read read,Write write,Tick tick,uint32_t step,std::string& error) {
        auto fail=[&](const char* text){error=text;return false;};
        if(step>255) return fail("C2 delay step outside 0..255");
        for(int camera:{0,2,3}) {
            const uint32_t alias=camera==0?0x20000800u:camera==2?0x20000900u:0x20000a00u;
            const uint32_t signature=camera==0?0x43314d31u:camera==2?0x43334d31u:0x43344d31u;
            const uint32_t width=camera==0?640u:320u,height=camera==0?480u:240u;
            uint32_t value=0;
            if(!read(alias+0x70,value) || (value!=signature && (camera==0 || value!=signature+1)))
                return fail("C2 delay requires runtime-camera signatures");
            if(!read(alias,value) || value!=0 ||
               !read(alias+0x40,value) || value!=(width<<16|height) ||
               !read(alias+0x50,value) || value!=width*height*2 ||
               !read(alias+0x60,value) || value!=width*2)
                return fail("C2 delay requires exact default startup geometry");
        }
        uint32_t saved=0,actual=0,idle=0;
        if(!read(0x20000880u,saved) || (saved&~0x3fu)) return fail("C2 delay original mask read failed");
        const uint32_t parked=saved&~2u;
        if(!write(0x20000880u,parked) || !read(0x20000880u,actual) || actual!=parked)
            return fail("C2 delay capture hold unverified; workers remain stopped");
        bool stopped=false;
        for(unsigned poll=0;poll<3000;++poll) {
            if(!read(0x20000890u,idle)) return fail("C2 delay idle read failed; C2 remains masked");
            if(idle&2u) {stopped=true;break;}
            tick();
        }
        if(!stopped) return fail("C2 delay idle timeout; C2 remains masked");
        if(!write(0x20000230u,step)) return fail("C2 delay write failed; C2 remains masked");
        if(!write(0x20000880u,saved) || !read(0x20000880u,actual) || actual!=saved)
            return fail("C2 delay mask restore unverified; workers remain stopped");
        fprintf(stderr,"C2_STARTUP_DELAY step=%u saved_mask=0x%02x held_mask=0x%02x idle=0x%02x restored_mask=0x%02x result=ok delay_readback=not_applicable\n",
            step,saved,parked,idle,actual);fflush(stderr);
        return true;
    }
};

struct RuntimeResolutionQueue {
    std::vector<std::pair<int,bool>> requests;
    int awaiting=-1;
    bool failed=false;
    void clear() { requests.clear(); awaiting=-1; failed=false; }
    int next(const std::array<bool,CAM_COUNT>& hd) {
        if(failed || awaiting>=0) return -1;
        while(!requests.empty()) {
            const auto request=requests.front(); requests.erase(requests.begin());
            if(!runtime_camera::supportsHd(request.first) || hd[request.first]==request.second) continue;
            awaiting=request.first; return request.first;
        }
        return -1;
    }
    bool complete(int camera,bool ok) {
        if(!ok) { requests.clear(); awaiting=-1; failed=true; return false; }
        if(camera!=awaiting || awaiting<0) return false;
        awaiting=-1; return true;
    }
    bool idle() const { return awaiting<0 && requests.empty(); }
    static bool selfTest() {
        std::array<bool,CAM_COUNT> hd{};
        RuntimeResolutionQueue q; q.requests={{0,true},{2,true},{3,true}};
        if(q.next(hd)!=0 || q.next(hd)!=-1 || q.complete(2,true)) return false;
        hd[0]=true;
        if(!q.complete(0,true) || q.complete(0,true) || q.next(hd)!=2) return false;
        hd[2]=true;
        if(!q.complete(2,true) || q.next(hd)!=3 || q.idle()) return false;
        hd[3]=true;
        if(!q.complete(3,true) || q.next(hd)!=-1 || !q.idle() || q.failed) return false;
        for(int failedCamera:{0,2,3}) {
            hd.fill(false); q.clear(); q.requests={{0,true},{2,true},{3,true}};
            for(int camera:{0,2,3}) {
                if(q.next(hd)!=camera) return false;
                if(camera==failedCamera) {
                    if(q.complete(camera,false) || !q.failed || !q.idle() ||
                       q.complete(camera,true) || q.next(hd)!=-1) return false;
                    break;
                }
                hd[camera]=true; if(!q.complete(camera,true)) return false;
            }
        }
        q.clear(); hd.fill(true); q.requests={{0,true},{2,true},{3,true}};
        return q.next(hd)==-1 && q.idle() && !q.failed;
    }
};

struct RuntimeOverviewBarrier {
    static bool matches(quint64 expected,quint64 actual,unsigned mask) {
        return expected && expected==actual && mask==0x3f;
    }
    static bool ready(quint64 requested,quint64 verified,bool reporting,bool fault,
                      bool busy,bool deferred,bool readers,unsigned applied,unsigned selected) {
        return matches(requested,verified,applied) && selected==0x3f &&
            !reporting && !fault && !busy && !deferred && readers;
    }
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
        std::array<quint32, CAM_COUNT> tags{};
        std::array<int, CAM_COUNT> cameraGenerations{};
        std::array<qint64, CAM_COUNT> rawCapturedMs{};
        bool hdmiFull = false;
        bool cam34Shared = false;   // HDMI 满屏视图（仅 6 路 3x2 布局下由显示端采用）
        bool cam1Hd = false;
        std::array<runtime_camera::Geometry,CAM_COUNT> geometries=[] {
            std::array<runtime_camera::Geometry,CAM_COUNT> values;
            for(int c=0;c<CAM_COUNT;++c) values[c]=runtime_camera::geometry(c);
            return values;
        }();
    };
    DisplayFrame takeDisplay() {
        QMutexLocker lock(&m_displayMutex);
        DisplayFrame frame = m_latestDisplay;
        m_latestDisplay = {};
        m_displayPending = false;
        return frame;
    }
    DisplayFrame rawSnapshot() {
        QMutexLocker lock(&m_displayMutex);
        return m_rawSnapshot;
    }
    void enableRawCapture(bool enabled) { m_rawCaptureEnabled = enabled; }
    static bool selfTestDisplay() {
        CameraThread source;
        source.enableRawCapture(true);
        int notifications = 0;
        QObject::connect(&source, &CameraThread::displayAvailable, &source,
                         [&] { ++notifications; }, Qt::DirectConnection);
        DisplayFrame frame;
        frame.generation = 1; frame.paneMask = 0x3F; frame.changedMask = 1;
        frame.cameraPixels[0] = QByteArray(FRAME_BYTES, char(0x11));
        frame.tags[0] = 123;
        frame.cameraGenerations[0] = 1;
        frame.rawCapturedMs[0] = 100;
        frame.cameraSequences[0] = 1;
        source.publishDisplay(frame);
        if (source.takeDisplay().changedMask != 0x3F) return false;
        const auto raw = source.rawSnapshot();
        if (raw.cameraPixels[0][0] != char(0x11) || raw.tags[0] != 123 ||
            raw.cameraGenerations[0] != 1 || raw.rawCapturedMs[0] != 100 || raw.cameraSequences[0] != 1) return false;
        source.publishDisplay(frame);
        // A writer taking a new buffer must not overwrite the GUI's snapshot.
        frame.cameraPixels[0].fill(char(0x22));
        if (raw.cameraPixels[0][0] != char(0x11)) return false;
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
        if (notifications != 4 || switched.generation != 2 || switched.changedMask != 0x3F ||
            !source.takeDisplay().cameraPixels[0].isEmpty()) return false;
        frame.geometries[0]=runtime_camera::geometry(0,runtime_camera::Mode::Default,2);
        source.publishDisplay(frame);source.takeDisplay();
        auto staleGeometry=frame;staleGeometry.geometries[0]=runtime_camera::geometry(0);
        source.publishDisplay(staleGeometry);
        if(!source.takeDisplay().cameraPixels[0].isEmpty()) return false;
        auto malformedGeometry=frame;malformedGeometry.cameraPixels[0].resize(4);
        source.publishDisplay(malformedGeometry);
        if(!source.takeDisplay().cameraPixels[0].isEmpty() || source.rawSnapshot().geometries[0].generation!=2) return false;
        VisionFrame packet;
        int submissions = 0;
        source.m_visionSink = [&](const VisionFrame &value) { packet = value; ++submissions; };
        source.setSourceGeneration(3);
        QImage video(IMG_W, IMG_H, QImage::Format_RGB888);
        video.fill(Qt::black);
        if (!source.publishVideoFrame(video, 3, 200, 30)) return false;
        const auto firstVideo = source.takeDisplay();
        if (!firstVideo.video || firstVideo.generation != packet.sourceGeneration ||
            firstVideo.videoSequence != packet.frameId || firstVideo.capturedMs[0] != packet.capturedMs ||
            packet.capturedMs != 200 || submissions != 1) return false;
        source.setPaused(true);
        if (source.publishVideoFrame(video, 3, 201, 30)) return false;
        source.setPaused(false);
        source.setSourceGeneration(4);
        if (source.publishVideoFrame(video, 3, 202, 30) || submissions != 1) return false;
        if (!source.publishVideoFrame(video, 4, 203, 30)) return false;
        const auto nextVideo = source.takeDisplay();
        source.m_hdModes=(1u<<0)|(1u<<2)|(1u<<3);
        source.setMode(CAM_COUNT);source.setHdmiOverride(0);
        if(source.captureMask()!=0x3f || !source.cameraHd(0) || !source.cameraHd(2) || !source.cameraHd(3)) return false;
        source.setMode(3);
        if(source.captureMask()!=8 || !source.cameraHd(0) || !source.cameraHd(2)) return false;
        for(int camera=0;camera<CAM_COUNT;++camera) {
            source.setMode(camera);
            if(source.captureMask()!=(1u<<camera) || source.m_hdModes.load()!=0x0d) return false;
        }
        source.setMode(CAM_COUNT);source.setHdmiOverride(1);
        if(source.captureMask()!=0x30 || !source.cameraHd(3)) return false;
        source.setMode(CAM_COUNT+1);
        if(source.captureMask()!=0x0d || source.m_hdmiActive.load() || !RuntimeResolutionQueue::selfTest()) return false;
        // Every ordinary selection clears the special mask, including HDMI.
        for(int camera=0;camera<=CAM_COUNT;++camera) {
            source.setMode(CAM_COUNT+1); source.setMode(camera);
            if(source.captureMask()!=(camera==CAM_COUNT?0x30u:1u<<camera)) return false;
        }
        source.setHdmiOverride(0);
        if(source.captureMask()!=0x3f) return false;
        source.requestResolution(2,true);
        if(source.m_pairRequest.load()!=25 || !source.m_resolutionBusy.load()) return false;
        source.requestResolution(3,false); // One pending transaction cannot be overwritten.
        if(source.m_pairRequest.load()!=25) return false;
        source.m_resolutionBusy=false;source.m_resolutionRequest=-1;source.m_pairRequest=-1;
        source.requestResolution(1,true);
        if(source.m_resolutionRequest.load()!=-1 || source.m_resolutionBusy.load()) return false;
        for(int camera:{2,3}) {
            if(!source.requestCam34Mode(camera,runtime_camera::Mode::FullVga) ||
               source.m_pairRequest.load()!=16+camera*4+2) return false;
            if(source.requestCam34Mode(camera==2?3:2,runtime_camera::Mode::Default) ||
               source.m_pairRequest.load()!=16+camera*4+2) return false;
            source.m_resolutionBusy=false;source.m_pairRequest=-1;
        }
        if(source.requestCam34Mode(0,runtime_camera::Mode::FullVga) ||
           source.requestCam34Mode(2,runtime_camera::Mode(3)) || source.m_resolutionBusy.load()) return false;
        fprintf(stderr,"CAM134_RUNTIME_UI_STATE_SELFTEST_PASS: independent modes, overview=3f, single=C4, HDMI=C5+C6, target request admission\n");
        return submissions == 2 && nextVideo.generation == 4 && packet.sourceGeneration == 4 &&
               nextVideo.videoSequence > firstVideo.videoSequence && nextVideo.videoSequence == packet.frameId &&
               nextVideo.capturedMs[0] == packet.capturedMs && packet.capturedMs == 203;
    }
    void stop() { m_stop = true; }
    bool requestResolution(int camera,bool hd) {
        if(camera==4) {
            if(!m_c5Capable.load() || m_resolutionBusy.exchange(true)) return false;
            m_c5Request=hd?1:0; return true;
        }
        if(camera==2 || camera==3) {
            if(m_resolutionBusy.exchange(true))return false;
            m_pairRequest=16+camera*4+(hd?1:0);
            return true;
        }
        if(!runtime_camera::supportsHd(camera) || m_resolutionBusy.exchange(true)) return false;
        m_resolutionRequest = camera*2+(hd?1:0);
        return true;
    }
    void requestResolution(bool hd) { requestResolution(0,hd); }
    bool requestCam34Mode(runtime_camera::Mode mode) {
        if(!runtime_camera::supportsMode(2,mode) || m_resolutionBusy.exchange(true)) return false;
        m_pairRequest=int(mode);return true;
    }
    bool requestCam34Mode(int camera,runtime_camera::Mode mode) {
        if((camera!=2 && camera!=3) || !runtime_camera::supportsMode(camera,mode) ||
           m_resolutionBusy.exchange(true)) return false;
        m_pairRequest=16+camera*4+int(mode);return true;
    }
    void requestOverviewReady(quint64 ticket) { m_overviewReadyRequest=ticket; }
    bool resolutionHeldSafe() const { return m_resolutionBusy.load(); }
    bool cam1Hd() const { return m_hdModes.load()!=0; } // Legacy watchdog: any runtime HD mode.
    bool cameraHd(int camera) const { return (m_hdModes.load() & (1u<<camera))!=0; }
    bool c5Supported() const { return m_c5Capable.load(); }
    // HDMI fullscreen shows only C5/C6. Entering it while the optical link is
    // dead is guaranteed to trip the no-frame watchdog (readers stopped, latch).
    bool opticalStreaming(qint64 maxAgeMs=1500) const {
        const qint64 now=monotonicMs();
        for(int i=0;i<2;++i) {
            const qint64 at=m_opticalCaptureMs[i].load(std::memory_order_relaxed);
            if(at<=0 || now-at>maxAgeMs) return false;
        }
        return true;
    }
    unsigned captureMask() const {
        if(m_native720.load()) return 0x0du;
        const int selected=m_mode.load();
        if(selected>=0 && selected<CAM_COUNT) return 1u<<selected;
        return m_hdmiActive.load() ? ((1u<<tdm::hdmiLeftCamera)|(1u<<tdm::hdmiRightCamera)) : 0x3fu;
    }
    void requestRuntimeHold() { m_runtimeHoldRequest=true; m_resolutionBusy=true; }
    void setMode(int mode) {
        QMutexLocker lock(&m_configMutex);
        m_native720 = mode == CAM_COUNT+1;
        if(mode==CAM_COUNT+1) mode=CAM_COUNT;
        m_selectedCamera = mode == CAM_COUNT ? (m_options.stereoEnabled() ? m_options.primaryStereoLeft() : 0) : mode;
        m_mode = mode;
        updateHdmiActive();
    }
    void setSourceGeneration(int generation) {
        QMutexLocker lock(&m_configMutex);
        m_sourceGeneration = generation;
    }
    void setVisionSink(VisionOptions options, std::function<void(const VisionFrame&)> sink) {
        m_options = options;
        m_visionSink = std::move(sink);
        setMode(m_native720.load()?CAM_COUNT+1:m_mode.load());
    }
    void setPaused(bool paused) {
        QMutexLocker lock(&m_configMutex);
        m_paused = paused;
    }
    void setVideoSource(const QString &source) {
        QMutexLocker lock(&m_configMutex);
        m_videoSource = source;
    }
    void setVideoLoop(bool loop) {
        QMutexLocker lock(&m_configMutex);
        m_videoLoop = loop;
    }
    /* auto has no trustworthy source-mode signal: wait for explicit F selection. */
    void setHdmiPrefer(int mode) { m_hdmiPrefer.store(mode); updateHdmiActive(); }
    // 手动覆盖（HDMI 满屏热切换）：-1=不覆盖（按 prefer/auto），1=强制满屏，0=强制 6 路
    void setHdmiOverride(int mode) { m_hdmiOverride.store(mode); updateHdmiActive(); }
    /* 控件尺寸：相机线程据此决定 RGA 缩放目标（letterbox 后的内容尺寸） */
    void setDisplaySize(int w, int h) { m_dispW = w; m_dispH = h; }

signals:
    void displayAvailable();
    void overviewReady(quint64 ticket,unsigned mask);
    void resolutionChanged(int camera, bool hd, bool ok, QString message);
    void pairModeChanged(int wireMode,bool ok,QString message);
    void resolutionAcceptanceStarted(int camera);
    /* 四路：已按控件尺寸缩放好的内容帧（RGB888）；ox>=0 表示直接在 (ox,oy) 1:1 贴图，
       ox<0 表示未缩放、由控件自行缩放铺满。paneMask/pane 同前 */
    void frameReady(QImage content, int paneMask, int pane, double fps, QVector<double> camFps,
                    int changedMask);
    /* 视频源路径：单路 RGB888 帧 */
    void imageReady(QImage frame, double fps);
    void statusMsg(QString s);

protected:
    void run() override {
        bool videoMode;
        {
            QMutexLocker lock(&m_configMutex);
            videoMode = !m_videoSource.isEmpty();
        }
        if (videoMode) { runVideo(); return; }
        PangoDev dev;
        if (!dev.openDev()) { fprintf(stderr,"[cam34-device] FATAL %s errno=%d (%s)\n",dev.lastErr(),errno,strerror(errno)); emit statusMsg(QString("FATAL: ") + dev.lastErr()); return; }
        // Preserve the six-camera DDR layout; candidate producer masks follow the selected view.
        LatestFrames latest;
        uint32_t priorTags[CAM_COUNT][2]={};
        uint8_t sensorOutput[4]={};
        unsigned sensorOutputValid=0;
        int resolutionCamera=0;
        bool targetPublicationPending=false;
        uint32_t heldTargetTags[2]={};
        std::array<runtime_camera::Geometry,CAM_COUNT> geometries;
        for(int c=0;c<CAM_COUNT;++c) geometries[c]=runtime_camera::geometry(c);
        // BEGIN bounded startup/default observations. Sequential reads, never an
        // atomic hardware snapshot. Each getter uses the existing I/O mutex.
        const bool startupCaptureDiagnostics=qEnvironmentVariableIsSet("DETVIEW_CAPTURE_EVIDENCE");
        bool captureDiagnosticReadFailed=false;
        unsigned captureDiagnosticSample=0;
        QElapsedTimer captureDiagnosticClock; captureDiagnosticClock.start();
        auto observeCapture=[&](const char* phase,int onlyCamera) {
            if(!startupCaptureDiagnostics || captureDiagnosticReadFailed) return;
            const unsigned sample=++captureDiagnosticSample;
            const qint64 beginMs=captureDiagnosticClock.elapsed();
            auto read=[&](int camera,const char* field,uint32_t address,bool tag=false) {
                if(captureDiagnosticReadFailed) return;
                uint32_t value=0;
                const bool ok=tag ? dev.readTag(address,value) : dev.regRead(address,value);
                fprintf(stderr,"CAM134_CAPTURE_DIAG sample=%u phase=%s camera=%d elapsed_ms=%lld field=%s addr=0x%08x value=0x%08x read_ok=%d correlation=sequential overhead=unmeasured\n",
                    sample,phase,camera+1,(long long)captureDiagnosticClock.elapsed(),field,address,value,int(ok));
                // One transport failure disables further diagnostic I/O. There
                // are no retries and this flag never controls capture behavior.
                if(!ok) captureDiagnosticReadFailed=true;
            };
            read(-1,"allowed_mask",0x20000880);
            read(-1,"idle_ack",0x20000890);
            read(-1,"lease_status",0x40020010);
            read(-1,"hold",0x40020020);
            read(-1,"lease_camera",0x400200c0);
            for(int c:{0,1,2,3}) {
                if(onlyCamera>=0 && c!=onlyCamera) continue;
                const uint32_t base=0x20000000u+uint32_t(c)*0x200u;
                // Actual startup alias reads through the same owned RX/mutex.
                // Keep these bounded to startup; cached host geometry is not evidence.
                if((c==0 || c==2 || c==3) && (!strcmp(phase,"startup_before_freeze") || !strcmp(phase,"startup_after_release"))) {
                    const uint32_t alias=c==0?0x20000800u:(c==2?0x20000900u:0x20000a00u);
                    read(c,"runtime_signature",alias+0x70);
                    read(c,"runtime_mode",alias);
                    read(c,"runtime_dimensions",alias+0x40);
                    read(c,"runtime_bytes",alias+0x50);
                    read(c,"runtime_stride",alias+0x60);
                }
                fprintf(stderr,"CAM134_CAPTURE_DIAG_GEOMETRY sample=%u camera=%d mode=%s width=%u height=%u tag_offset=%u generation=%llu\n",
                    sample,c+1,geometries[c].mode==runtime_camera::Mode::Default?"default":"720P",
                    geometries[c].width,geometries[c].height,geometries[c].tagOffset,
                    (unsigned long long)geometries[c].generation);
                read(c,"tag0",geometries[c].tagAddress(0),true);
                read(c,"tag1",geometries[c].tagAddress(1),true);
                read(c,"sensor_vsync",base+0x20);
                read(c,"post_downsample_pixels",base+0x30);
                read(c,"wd_state_commands",base+0x60);
                read(c,"b_aw",base+0x70);
                read(c,"reject_counts",base+0xa0);
                read(c,"sensor_sys",base+0xd0);
                read(c,"publication_f0",base+0xf0);
                // Sequence brackets label source metadata correlation only;
                // even matching values do not make tags/writer/global atomic.
                read(c,"source_seq_before",base+0x1c0);
                read(c,"source_input",base+0x190);
                read(c,"source_output",base+0x1a0);
                read(c,"source_drop",base+0x1b0);
                read(c,"source_seq_after",base+0x1c0);
            }
            fprintf(stderr,"CAM134_CAPTURE_DIAG_END sample=%u phase=%s begin_ms=%lld end_ms=%lld read_failed=%d correlation=sequential overhead=unmeasured\n",
                sample,phase,(long long)beginMs,(long long)captureDiagnosticClock.elapsed(),int(captureDiagnosticReadFailed));
            fflush(stderr);
        };
        // Wrap the existing guarded operation without changing its predicates,
        // timeouts, writes, failure hold or rollback. Startup has no workers.
        class ObservedStartupSwitch : public cam1::Switch {
            std::function<void(const char*,int)> observe;
            int camera;
        public:
            ObservedStartupSwitch(cam1::Io io,int c,std::function<void(const char*,int)> o)
                :cam1::Switch(io,c),observe(o),camera(c) {}
            bool readStartupGeometry(uint8_t (&output)[4],std::string& error) {
                observe("startup_before_freeze",camera);
                const bool ok=cam1::Switch::readStartupGeometry(output,error);
                observe(ok?"startup_after_release":"startup_failed_hold",camera);
                return ok;
            }
        };
        // END bounded startup/default observation definitions.
        std::array<std::unique_ptr<ObservedStartupSwitch>,CAM_COUNT> resolutions;
        std::array<uint32_t,CAM_COUNT> startupSccbTransactions{};
        for(int target:{0,2,3}) resolutions[target].reset(new ObservedStartupSwitch({[&](uint32_t a,uint32_t& v){return dev.regRead(a,v);},
            [&](uint32_t a,uint32_t v){return dev.regWrite(a,v);}, []{QThread::msleep(1);},
            [&](bool hd){
                for(int c=0;c<CAM_COUNT;++c) {
                    if(c==resolutionCamera) {
                        if(!targetPublicationPending &&
                           (!dev.readTag(geometries[c].tagAddress(0),priorTags[c][0]) ||
                            !dev.readTag(geometries[c].tagAddress(1),priorTags[c][1]))) return false;
                        const auto targetGeometry=runtime_camera::geometry(c,hd?runtime_camera::Mode::Hd720:runtime_camera::Mode::Default);
                        if(!dev.readTag(targetGeometry.tagAddress(0),heldTargetTags[0]) ||
                           !dev.readTag(targetGeometry.tagAddress(1),heldTargetTags[1])) return false;
                        continue; // Held/drained prior geometry's sequence, never the new tag offset.
                    }
                    const auto bytes=c==resolutionCamera?runtime_camera::geometry(c,hd?runtime_camera::Mode::Hd720:runtime_camera::Mode::Default).pixelBytes:geometries[c].pixelBytes;
                    if(!dev.readTag(CAM_BASE[c][0]+bytes,priorTags[c][0]) ||
                       !dev.readTag(CAM_BASE[c][1]+bytes,priorTags[c][1])) return false;
                }
                return true; },
            [&](const std::string& text){
                unsigned startupTransaction=0;
                if(std::sscanf(text.c_str(),"SCCB tx=%u",&startupTransaction)==1)
                    startupSccbTransactions[resolutionCamera]=startupTransaction;
                fprintf(stderr,"CAM134_RUNTIME camera=%d alias=0x%08x %s\n",resolutionCamera+1,resolutionCamera==0?0x20000800u:resolutionCamera==2?0x20000900u:0x20000a00u,text.c_str()); fflush(stderr);
                unsigned tx,addr,command,first,status,data;
                int busy,polls;
                char op[8]={},result[40]={};
                if(std::sscanf(text.c_str(),
                    "SCCB tx=%u op=%7s sensor=0x%x command=0x%x status-first=0x%x status=0x%x busy-seen=%d polls=%d data=0x%x result=%39s",
                    &tx,op,&addr,&command,&first,&status,&busy,&polls,&data,result)==10 &&
                    std::strcmp(op,"read")==0 && std::strcmp(result,"ok")==0 &&
                    addr>=0x3808 && addr<=0x380b) {
                    sensorOutput[addr-0x3808]=uint8_t(data);
                    sensorOutputValid |= 1u<<(addr-0x3808);
                }
            },true},target,observeCapture));
        auto controller=[&]() -> ObservedStartupSwitch& { return *resolutions[resolutionCamera]; };
        // Default startup evidence comes from true sensor reads, before any
        // worker can own DMA or a resolution request can change geometry.
        dev.protectRuntimeSwitch();
        for(int target:{0,2,3}) {
            resolutionCamera=target;
            sensorOutputValid=0;
            uint8_t output[4]={};
            std::string error;
            if(!controller().readStartupGeometry(output,error)) {
                fprintf(stderr,"CAM134_STARTUP_SENSOR camera=%d alias=0x%08x result=failed detail=%s\n",
                    target+1,controller().base(),error.c_str());
                fflush(stderr);
                m_resolutionBusy=true;
                emit resolutionChanged(target,false,false,
                    QString("FATAL startup sensor readback: ")+QString::fromStdString(error));
                return;
            }
            fprintf(stderr,"CAM134_STARTUP_SENSOR camera=%d alias=0x%08x sensor_regs=%02x/%02x/%02x/%02x sensor=%ux%u result=ok\n",
                target+1,controller().base(),unsigned(output[0]),unsigned(output[1]),unsigned(output[2]),unsigned(output[3]),
                (unsigned(output[0])<<8)|output[1],(unsigned(output[2])<<8)|output[3]);
            fflush(stderr);
        }
        resolutionCamera=0;
        sensorOutputValid=0;
        CameraWorker workers[CAM_COUNT] = {
            CameraWorker(&dev, &latest, 1), CameraWorker(&dev, &latest, 2),
            CameraWorker(&dev, &latest, 3), CameraWorker(&dev, &latest, 4),
            CameraWorker(&dev, &latest, 5), CameraWorker(&dev, &latest, 6)};
        const int geometryFailure=runtime_camera::bindStartupGeometries(dev,geometries);
        if(geometryFailure!=CAM_COUNT) {
            fprintf(stderr,"CAM134_STARTUP_GEOMETRY camera=%d result=failed\n",geometryFailure+1);
            fflush(stderr);
            m_resolutionBusy=true;
            emit statusMsg(QString("FATAL startup geometry binding C%1").arg(geometryFailure+1));
            return;
        }
        bool delayValid=true;
        const bool delayOverride=qEnvironmentVariableIsSet("DETVIEW_C2_DELAY_STEP");
        const int c2Delay=delayOverride?qEnvironmentVariableIntValue("DETVIEW_C2_DELAY_STEP",&delayValid):144;
        std::string c2DelayError;
        fprintf(stderr,"C2_STARTUP_DELAY_BEGIN step=%d source=%s workers_started=0\n",c2Delay,delayOverride?"environment":"measured_default");fflush(stderr);
        if(!delayValid || c2Delay<0 || c2Delay>255 ||
           !StartupC2Delay::apply([&](uint32_t address,uint32_t& value){return dev.regRead(address,value);},
               [&](uint32_t address,uint32_t value){return dev.regWrite(address,value);},
               []{QThread::msleep(1);},uint32_t(c2Delay),c2DelayError)) {
            if(c2DelayError.empty()) c2DelayError="Invalid DETVIEW_C2_DELAY_STEP; expected integer 0..255";
            fprintf(stderr,"C2_STARTUP_DELAY result=failed step=%d detail=%s workers_started=0\n",c2Delay,c2DelayError.c_str());fflush(stderr);
            m_resolutionBusy=true;
            emit resolutionChanged(1,false,false,QString("FATAL startup C2 delay: ")+QString::fromStdString(c2DelayError));
            return;
        }
        const int stereoMask = m_options.stereoCameraMask();
        for (CameraWorker &w : workers) {
            w.setVisionSink(&m_selectedCamera, &m_sourceGeneration, &m_frameSequence, m_visionSink, stereoMask, m_options.motionEnabled);
            w.setModePtr(&m_mode);
            w.setPausedPtr(&m_paused);
            w.setHdmiPtr(&m_hdmiActive);
            w.set720pModePtr(&m_native720);
            w.setResolutionBusyPtr(&m_resolutionBusy);
        }
        for (CameraWorker &w : workers) w.start();
        emit statusMsg("Six-camera DMA ready; 3x2 view, inference uses the selected pane");
        // Same owned per-camera snapshot path as optimized camview: no CPU
        // composite, row copies, or GLES2 tile packing in the display pipeline.
        std::array<QByteArray, CAM_COUNT> cameraPixels;
        uint64_t lastCamGen[CAM_COUNT] = {};
        // Pace owned display snapshots near the 40 fps cameras. Publishing
        // faster adds mailbox replacements without making GPU paints fresher.
        const int minIntervalMs = qEnvironmentVariableIsSet("DETVIEW_MIN_MS")
                                       ? std::max(0, qEnvironmentVariableIntValue("DETVIEW_MIN_MS")) : 24;
        uint64_t lastGen = 0;
        int lastMode = -1, lastDisplayGeneration = -1;
        uint64_t hdmiLeftSequence = 0, hdmiRightSequence = 0;
        quint64 hdmiSubmissions = 0;
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
        bool resolutionFault = false;
        bool reportResolution = false;
        bool previousResolution = false;
        struct PendingDelivery {
            bool pending=false, previous=false;
            uint32_t prior[2]={};
            uint32_t stale[2]={};
            uint8_t sensor[4]={};
        } pendingDelivery[CAM_COUNT];
        auto workersHealthy=[&]() {
            QMutexLocker lock(&latest.mutex);
            for(int c=0;c<CAM_COUNT;++c) if(latest.errors[c]) return false;
            return true;
        };
        QElapsedTimer deliveryDeadline;
        uint64_t auditReads[CAM_COUNT]={},auditPublications[CAM_COUNT]={},auditErrors[CAM_COUNT]={};
        uint64_t readDeltas[CAM_COUNT]={},publicationDeltas[CAM_COUNT]={},errorDeltas[CAM_COUNT]={};
        uint64_t previousPublications[CAM_COUNT]={};
        uint32_t auditTags[CAM_COUNT][2]={},previousTags[CAM_COUNT][2]={};
        qint64 lastTagAdvanceMs[CAM_COUNT][2],lastPublicationAdvanceMs[CAM_COUNT];
        qint64 tagAgeMs[CAM_COUNT][2],publicationAgeMs[CAM_COUNT],captureAgeMs[CAM_COUNT];
        qint64 lastAuditMs=-100;
        unsigned appliedCaptureMask=0xffffffffu;
        // Cameras in the applied mask that were already frozen BEFORE this
        // switch. They are excluded from the freshness evidence so that a dead
        // producer cannot veto a target-only switch. A producer that was
        // advancing at switch entry stays in the gate and still fails it if it
        // dies during the switch. Bit index = camera index.
        unsigned staleProducerMask=0;
        quint64 verifiedOverviewTicket=0;
        auto advanceAge=[](qint64 now,qint64 advanced) { return advanced<0 ? qint64(-1) : now-advanced; };
        auto recentProducerEvidence=[&](qint64 now) {
            if(lastAuditMs<0 || now-lastAuditMs>500) return false;
            for(int c=0;c<CAM_COUNT;++c) {
                if(!(appliedCaptureMask & (1u<<c))) continue;
                // Already frozen before the switch: no advance is ever expected.
                if(c!=resolutionCamera && (staleProducerMask & (1u<<c))) continue;
                for(int bank=0;bank<2;++bank)
                    if(lastTagAdvanceMs[c][bank]<0 || now-lastTagAdvanceMs[c][bank]>500) return false;
                if(lastPublicationAdvanceMs[c]<0 || now-lastPublicationAdvanceMs[c]>500) return false;
            }
            return true;
        };
        uint32_t auditMode=0,auditDimensions=0,auditBytes=0,auditStride=0,auditMask=0,auditIdle=0;
        unsigned freshBanks=0,auditSamples=0,acceptanceTransaction=0;
        bool producerEvidencePassed=false;
        const bool captureMaskSupported=controller().supported();
        if(captureMaskSupported) dev.protectRuntimeSwitch();
        tdm::ViewCaptureEvidence<QElapsedTimer,CAM_COUNT> viewEvidence;
        auto& viewTransaction=viewEvidence.transaction;
        const bool viewEvidenceEnabled=qEnvironmentVariableIsSet("DETVIEW_CAPTURE_EVIDENCE");
        // BEGIN bounded default sample budget (not reset by view changes).
        unsigned defaultCaptureDiagnosticSamples=0;
        // END bounded default sample budget.
        auto& viewEvidenceClock=viewEvidence.clock;
        auto& viewLastSample=viewEvidence.lastSample;
        auto& viewBaselineTags=viewEvidence.tags;
        auto& viewBaselineReads=viewEvidence.reads;
        auto& viewBaselinePublications=viewEvidence.publications;
        auto& viewBaselineErrors=viewEvidence.errors;
        auto selectedCaptureMask=[&]() -> unsigned {
            return captureMask();
        };
        using SourceEvidence=source_acceptance::Evidence;
        SourceEvidence source;
        QElapsedTimer sourceClock;
        qint64 sourceSnapshotStartMs=-1,sourceSnapshotEndMs=-1,sourceSnapshotLockWaitMs=0;
        auto readSourceSnapshot=[&]() -> QString {
            sourceSnapshotStartMs=sourceClock.elapsed();
            sourceSnapshotLockWaitMs=0;
            source.stable=false;
            for(unsigned attempt=1;attempt<=3;++attempt) {
                source.attempts=attempt;
                uint32_t input=0,drop=0;
                const uint32_t sourceBase=0x20000000u+uint32_t(resolutionCamera)*0x200u;
                const uint32_t addresses[]={sourceBase+0x1c0,sourceBase+0x190,sourceBase+0x1b0,sourceBase+0x1c0};
                uint32_t values[4]={};
                qint64 lockWaitMs=0;
                const bool readOk=dev.regReadBatch(addresses,values,4,&lockWaitMs);
                sourceSnapshotLockWaitMs+=lockWaitMs;
                sourceSnapshotEndMs=sourceClock.elapsed();
                if(!readOk)
                     return "Acceptance source snapshot MMIO read failed";
                source.before=values[0]; input=values[1]; drop=values[2]; source.after=values[3];
                if(source.before==source.after) {
                    source.seq=source.after; source.input=input; source.drop=drop;
                    source.stable=true;
                    source.lastStableMs=sourceClock.elapsed();
                    return {};
                }
            }
            return "Acceptance source snapshot unstable after 3 attempts";
        };
        auto observeSource=[&]() -> QString {
            const auto g=cam1::geometry(m_cam1Hd.load());
            const uint32_t expected=uint32_t(g.width)*uint32_t(g.height);
            auto evaluate=[&]() -> QString {
                if(!sourceClock.isValid() || !source.baselineValid)
                    return "Acceptance source baseline unavailable";
                const uint32_t previous=source.seq;
                const QString readFailure=readSourceSnapshot();
                if(!readFailure.isEmpty()) return readFailure;
                const qint64 now=sourceClock.elapsed();
                const auto result=source_acceptance::observe(source,previous,now,expected);
                if(result==source_acceptance::Result::Reset)
                    return "Acceptance source sequence moved backward/reset";
                if(result==source_acceptance::Result::BadFrame)
                    return QString("Acceptance source frame mismatch seq=%1 input=%2 expected=%3 drop=%4")
                        .arg(source.seq).arg(source.input).arg(expected).arg(source.drop);
                if(result==source_acceptance::Result::Deadline)
                    return QString("Acceptance source did not settle within 500 ms baseline=%1 seq=%2 input=%3 expected=%4 drop=%5")
                        .arg(source.baseline).arg(source.seq).arg(source.input).arg(expected).arg(source.drop);
                return {};
            };
            const QString failure=evaluate();
            const qint64 now=sourceClock.isValid()?sourceClock.elapsed():-1;
            const char* state=!failure.isEmpty()?"failed":source.settledMs>=0?"settled":"settling";
            fprintf(stderr,"CAM134_SOURCE_SAMPLE transaction=%u camera=%d source_base=0x%08x mode=%d expected_sensor_pixels=%u source_seq=%u source_input=%u source_drop=%u stable=%d advances=%u elapsed_ms=%lld state=%s result=%s snapshot_start_ms=%lld snapshot_end_ms=%lld snapshot_duration_ms=%lld snapshot_lock_wait_ms=%lld\n",
                acceptanceTransaction,resolutionCamera+1,0x20000000u+uint32_t(resolutionCamera)*0x200u,int(m_cam1Hd.load()),expected,
                source.seq,source.input,source.drop,int(source.stable),source.advances,(long long)now,state,failure.isEmpty()?"ok":qPrintable(failure),
                (long long)sourceSnapshotStartMs,(long long)sourceSnapshotEndMs,
                (long long)(sourceSnapshotEndMs-sourceSnapshotStartMs),(long long)sourceSnapshotLockWaitMs);
            // Runs during the commit wait too, before reportResolution or worker restart.
            fprintf(stderr,"CAM1_SOURCE_SAMPLE transaction=%u target=%s elapsed_ms=%lld expected=%u source_baseline_valid=%d source_baseline=%u source_baseline_ms=%lld source_seq=%u source_input=%u source_drop=%u source_stable=%d source_attempts=%u source_seq_before=%u source_seq_after=%u source_advances=%u source_settled_ms=%lld source_age_ms=%lld state=%s result=%s\n",
                acceptanceTransaction,m_cam1Hd.load()?"720P":"480P",(long long)now,expected,
                int(source.baselineValid),source.baseline,(long long)source.baselineMs,
                source.seq,source.input,source.drop,int(source.stable),source.attempts,
                source.before,source.after,source.advances,(long long)source.settledMs,
                (long long)(now>=0?advanceAge(now,source.lastAdvanceMs):-1),state,
                failure.isEmpty()?"ok":qPrintable(failure));
            fflush(stderr);
            return failure;
        };
        auto recentSourceEvidence=[&]() {
            if(!sourceClock.isValid() || !source.baselineValid || !source.stable ||
               source.settledMs<0 || source.advances<2) return false;
            const qint64 now=sourceClock.elapsed();
            const auto g=cam1::geometry(m_cam1Hd.load());
            return now-source.settledMs>=2000 &&
                source.input==uint32_t(g.width)*uint32_t(g.height) && source.drop==0 &&
                source.lastAdvanceMs>=0 && now-source.lastAdvanceMs<=500 &&
                source.lastStableMs>=0 && now-source.lastStableMs<=500;
        };
        auto failAcceptance=[&](const QString& reason) {
            // Preserve pre-rollback evidence; failure can precede timer initialization.
            const qint64 failedElapsed=deliveryDeadline.isValid()?deliveryDeadline.elapsed():-1;
            const qint64 sourceElapsed=sourceClock.isValid()?sourceClock.elapsed():-1;
            const qint64 sourceAge=sourceElapsed>=0 && source.lastAdvanceMs>=0 ?
                sourceElapsed-source.lastAdvanceMs : -1;
            for(auto& w:workers) w.stop();
            for(auto& w:workers) w.wait();
            const bool rollback=controller().rollbackSafe();
            { QMutexLocker lock(&latest.mutex);
              for(int c=0;c<CAM_COUNT;++c) {latest.c[c].clear();latest.have[c]=false;latest.fps[c]=0;}
              ++latest.gen; }
            { QMutexLocker lock(&m_displayMutex);m_latestDisplay={};m_rawSnapshot={};m_displayPending=false; }
            cameraPixels={};
            m_cam1Hd=cam1::modeAfterRollback(previousResolution,m_cam1Hd.load(),rollback);
            if(rollback) {
                unsigned modes=m_hdModes.load();
                m_hdModes=previousResolution?modes|(1u<<resolutionCamera):modes&~(1u<<resolutionCamera);
            }
            resolutionFault=true; reportResolution=false; producerEvidencePassed=false;
            staleProducerMask=0;
            fprintf(stderr,"CAM134_ACCEPT_FAIL transaction=%u camera=%d rollback_verified=%d readers_stopped=1 automatic_restart=0 reason=%s\n",
                acceptanceTransaction,resolutionCamera+1,int(rollback),qPrintable(reason));
            fprintf(stderr,"CAM1_ACCEPT_FAIL transaction=%u elapsed_ms=%lld reason=%s rollback_verified=%d source_baseline_valid=%d source_baseline=%u source_baseline_ms=%lld source_seq=%u source_input=%u source_drop=%u source_stable=%d source_attempts=%u source_seq_before=%u source_seq_after=%u source_advances=%u source_elapsed_ms=%lld source_settled_ms=%lld source_age_ms=%lld\n",
                acceptanceTransaction,(long long)failedElapsed,qPrintable(reason),int(rollback),
                int(source.baselineValid),source.baseline,(long long)source.baselineMs,
                source.seq,source.input,source.drop,int(source.stable),source.attempts,
                source.before,source.after,source.advances,(long long)sourceElapsed,
                (long long)source.settledMs,(long long)sourceAge);
            fflush(stderr);
            emit resolutionChanged(resolutionCamera,m_cam1Hd,false,reason+(rollback ?
                "; prior mode restored, capture held safe" : "; rollback/hold unverified, readers stopped"));
        };
        // One long-lived pair controller owns C3/C4 VGA originals for every
        // independent and paired request; startup observers are read-only.
        bool pairOperationOwned=false,pairCommitFailed=false;
        uint64_t pairTransaction=0;
        std::array<cam34_pair::Baseline,2> pairBaselines;
        std::array<uint32_t,2> pairReadFloor{{0,0}};
        std::array<uint32_t,2> pairPriorFloor{{0,0}};
        std::array<source_acceptance::Evidence,2> pairSource;
        std::array<QElapsedTimer,2> pairSourceClock;
        auto pairSourceSnapshot=[&](int i) {
            const uint32_t base=0x20000000u+uint32_t(i+2)*0x200u;
            const uint32_t addresses[]={base+0x1c0,base+0x190,base+0x1b0,base+0x1c0};
            for(int attempt=0;attempt<3;++attempt){
                uint32_t values[4]={};
                if(!dev.regReadBatch(addresses,values,4))return false;
                if(values[0]!=values[3])continue;
                auto& evidence=pairSource[i];evidence.seq=values[3];evidence.input=values[1];
                evidence.drop=values[2];evidence.stable=true;return true;
            }
            return false;
        };
        std::array<cam1_pair::Io,2> pairIo;
        for(int i=0;i<2;++i) {
            pairIo[i].transactionSeed=startupSccbTransactions[i+2];
            pairIo[i].read=[&](uint32_t a,uint32_t& v){return dev.regRead(a,v);};
            pairIo[i].write=[&](uint32_t a,uint32_t v){return dev.regWrite(a,v);};
            pairIo[i].tick=[]{QThread::msleep(1);};
            pairIo[i].completionWitness=true;
            pairIo[i].diagnostic=[i](const std::string& text){
                fprintf(stderr,"CAM34_PAIR_RUNTIME camera=%d %s\n",i+3,text.c_str());fflush(stderr);
            };
        }
        cam34_pair::Hooks pairHooks;
        pairHooks.acquire=[&]{
            if(pairOperationOwned || reportResolution || resolutionFault || selectedCaptureMask()!=0x3f) return false;
            pairOperationOwned=true;dev.protectRuntimeSwitch();return true;
        };
        pairHooks.unlock=[&]{pairOperationOwned=false;};
        pairHooks.stopJoin=[&]{
            for(auto& w:workers)w.stop();for(auto& w:workers)w.wait();
            scheme2::admission().disarm();QElapsedTimer elapsed;elapsed.start();
            while(!scheme2::admission().idle()&&elapsed.elapsed()<10000)msleep(5);
            return scheme2::admission().idle();
        };
        pairHooks.current=[&](int c,cam34_pair::Current& value){
            uint32_t tags[2]={};
            if(!dev.readTag(geometries[c].tagAddress(0),tags[0]) || !dev.readTag(geometries[c].tagAddress(1),tags[1]))return false;
            value={geometries[c].mode,geometries[c].generation,tdm::newerCameraTag(tags[0],tags[1])?tags[0]:tags[1]};
            pairPriorFloor[c-2]=value.sequence;return true;
        };
        pairHooks.prepare=[&](const runtime_camera::Geometry& g,bool,cam34_pair::Baseline& baseline){
            const int i=g.camera-2;
            baseline.floor=pairPriorFloor[i];
            const bool ok=dev.withPairRead([&](const cam34_pair::ReadBytes& read){return cam34_pair::snapshotTags(g,read,baseline);});
            if(!ok)return false;
            // The device has already reported this exact target geometry (+0x40/
            // +0x50/+0x60 readback) before the baseline snapshot. Publish it as the
            // in-flight descriptor so the frame read below is judged against the
            // target mode and not against the still-committed previous one.
            if(!dev.expectCameraGeometry(g))return false;
            pairSource[i]={};pairSourceClock[i].invalidate();
            if(!pairSourceSnapshot(i))return false;
            pairSource[i].baseline=pairSource[i].seq;pairSource[i].baselineValid=true;
            pairBaselines[i]=baseline;pairReadFloor[i]=baseline.floor;
            fprintf(stderr,"CAM34_PAIR_BASELINE transaction=%llu camera=%d mode=%u generation=%llu floor=%u stale0=%u stale1=%u bytes=%u\n",
                (unsigned long long)pairTransaction,g.camera+1,unsigned(g.mode),(unsigned long long)g.generation,
                baseline.floor,baseline.stale[0],baseline.stale[1],g.pixelBytes);fflush(stderr);return true;
        };
        pairHooks.publication=[&](const runtime_camera::Geometry& g,cam34_pair::Publication& publication){
            QElapsedTimer wait;wait.start();const int i=g.camera-2;
            if(!pairSourceClock[i].isValid())pairSourceClock[i].start();
            while(!m_stop && wait.elapsed()<5000) {
                // Private full-frame attempts use the same <=30fps ceiling.
                msleep(34);auto baseline=pairBaselines[i];baseline.floor=pairReadFloor[i];
                const uint32_t previous=pairSource[i].seq;
                if(!pairSourceSnapshot(i))return false;
                const uint32_t expected=g.mode==runtime_camera::Mode::Hd720?1280u*720u:640u*480u;
                const auto sourceResult=source_acceptance::observe(pairSource[i],previous,pairSourceClock[i].elapsed(),expected);
                fprintf(stderr,"CAM34_PAIR_SOURCE camera=%d mode=%u seq=%u input=%u drop=%u elapsed_ms=%lld advances=%u result=%d\n",
                    g.camera+1,unsigned(g.mode),pairSource[i].seq,pairSource[i].input,pairSource[i].drop,
                    (long long)pairSourceClock[i].elapsed(),pairSource[i].advances,int(sourceResult));
                if(sourceResult!=source_acceptance::Result::Ok)return false;
                if(!source_acceptance::readyForRestart(true,pairSource[i]))continue;
                std::vector<uint8_t> pixels;
                const bool copied=dev.withPairRead([&](const cam34_pair::ReadBytes& read){return cam34_pair::copyFresh(g,baseline,read,pixels,publication);});
                if(copied){
                    fprintf(stderr,"CAM34_PAIR_PUBLICATION transaction=%llu camera=%d mode=%u generation=%llu bank=%d sequence=%u prior=%u bytes=%u source_seq=%u source_input=%u source_drop=%u source_advances=%u verified_commit=%d\n",
                        (unsigned long long)pairTransaction,g.camera+1,unsigned(g.mode),(unsigned long long)g.generation,
                        publication.bank,publication.sequence,pairReadFloor[i],publication.bytes,pairSource[i].seq,
                        pairSource[i].input,pairSource[i].drop,pairSource[i].advances,int(publication.verifiedCommit));
                    fflush(stderr);pairReadFloor[i]=publication.sequence;return true;
                }
            }
            return false;
        };
        pairHooks.commit=[&](const std::array<runtime_camera::Geometry,2>& next,
                             const std::array<cam34_pair::Publication,2>& publications,bool){
            for(int i=0;i<2;++i)if(!dev.configureCameraGeometry(next[i]))pairCommitFailed=true;
            if(pairCommitFailed)return;
            for(int i=0;i<2;++i){
                const int c=i+2;geometries[c]=next[i];cameraPixels[c].clear();lastCamGen[c]=0;
                pendingDelivery[c].pending=false;
                {QMutexLocker lock(&latest.mutex);latest.c[c].clear();latest.have[c]=false;latest.fps[c]=0;++latest.gen;}
                unsigned modes=m_hdModes.load();m_hdModes=next[i].mode==runtime_camera::Mode::Hd720?modes|(1u<<c):modes&~(1u<<c);
                fprintf(stderr,"CAM34_PAIR_COMMIT transaction=%llu camera=%d mode=%u generation=%llu sequence=%u bytes=%u\n",(unsigned long long)pairTransaction,c+1,unsigned(next[i].mode),(unsigned long long)next[i].generation,publications[i].sequence,next[i].pixelBytes);
            }
            m_pairOwnsC34=next[0].mode!=runtime_camera::Mode::Default || next[1].mode!=runtime_camera::Mode::Default;
            {QMutexLocker lock(&m_displayMutex);m_latestDisplay={};m_rawSnapshot={};m_displayPending=false;}
            viewEvidenceClock.invalidate();
        };
        pairHooks.resume=[&]{
            if(pairCommitFailed)return;
            ++viewTransaction;
            for(int c=0;c<CAM_COUNT;++c){
                uint32_t a=0,b=0;
                if(!dev.readTag(geometries[c].tagAddress(0),a)||!dev.readTag(geometries[c].tagAddress(1),b)){pairCommitFailed=true;break;}
                viewBaselineTags[c][0]=a;viewBaselineTags[c][1]=b;
                viewBaselineReads[c]=dev.workerReadCalls(c);
                {QMutexLocker lock(&latest.mutex);
                 viewBaselinePublications[c]=latest.camGen[c];viewBaselineErrors[c]=latest.errors[c];}
                if(!workers[c].restartForGeometry(geometries[c],tdm::newerCameraTag(a,b)?a:b)){pairCommitFailed=true;break;}
            }
            if(pairCommitFailed){for(auto& w:workers)w.stop();for(auto& w:workers)w.wait();}
            else {viewEvidenceClock.start();viewLastSample=-500;}
        };
        cam34_pair::Coordinator pairController(pairIo,pairHooks);
        uint32_t c5Epoch=0;
        bool c5Recovery=false;
        c5::Board optical{
            [&](uint32_t a,uint32_t& v){return dev.regRead(a,v);},
            [&](uint32_t a,uint32_t v){return dev.regWrite(a,v);},
            []{return uint64_t(monotonicMs());}, []{QThread::msleep(5);},
            [&]{
                dev.protectRuntimeSwitch();
                for(int c:{4,5}) workers[c].stop();
                for(int c:{4,5}) workers[c].wait();
                QElapsedTimer drain;drain.start();
                while(!scheme2::admission().idle() && drain.elapsed()<10000) msleep(5);
                return scheme2::admission().idle();
            },
            [&](uint32_t a,uint32_t& v){return dev.readTag(a,v);}
        };
        m_c5Capable=c5::capable(optical);
        if(m_c5Capable.load()) {
            c5::Snapshot s;
            const unsigned snapshotAttempts=c5::snapshotWithRetry(optical,s,8);
            const bool snapshotOk=snapshotAttempts!=0;
            if(snapshotAttempts>1)
                fprintf(stderr,"[c5] startup snapshot coherent after %u attempts\n",snapshotAttempts);
            const bool defaultGeometry=snapshotOk && s.dimensions==0x028001e0u &&
               s.bytes==614400u && s.stride==1280u && s.c6==0x028001e0u;
            if(defaultGeometry) {
                const uint32_t persisted=c5EpochPersisted();
                if(s.state!=5 && !s.error) {
                    // Normal path: still start above anything ever issued, so a
                    // bitstream reload (which zeroes the mailbox registers) cannot
                    // drag the epoch back under the sender's armed value.
                    uint32_t seen=s.completed>persisted?s.completed:persisted;
                    if(seen<C5_EPOCH_BASE) seen=C5_EPOCH_BASE;
                    c5Epoch=seen;
                    if(c5Epoch!=persisted) c5EpochPersist(c5Epoch);
                }
                else {
                    // The 100H mailbox resets to FAILED (REQUIRE_REQUEST=1): no
                    // transaction, geometry or publication state survives, but the
                    // retained anti-replay floor does. Keep C5 reachable and seed
                    // one epoch above every value the mailbox exposes. Bounded: one
                    // operator-triggered attempt, never an automatic retry.
                    const uint32_t recorded=s.epoch>s.completed?s.epoch:s.completed;
                    const uint32_t floor=recorded>s.banks?recorded:s.banks;
                    uint32_t highest=floor>s.doorbell?floor:s.doorbell;
                    if(persisted>highest) highest=persisted;
                    if(highest<C5_EPOCH_BASE) highest=C5_EPOCH_BASE;
                    if(highest==0xffffffffu) {
                        m_c5Capable=false;
                        fprintf(stderr,"[c5] mailbox failed but epoch space is exhausted: doorbell=%u epoch=%u completed=%u banks=%u; C5 stays disabled\n",
                            s.doorbell,s.epoch,s.completed,s.banks);
                    } else {
                        c5Recovery=true;
                        c5Epoch=highest+1;
                        fprintf(stderr,"[c5] mailbox failed state=%u error=0x%08x doorbell=%u epoch=%u completed=%u banks=%u -> recovery armed, next_epoch=%u\n",
                            s.state,s.error,s.doorbell,s.epoch,s.completed,s.banks,c5Epoch);
                    }
                }
            }
            else {
                m_c5Capable=false; // verify default geometry before admission
                if(snapshotOk)
                    fprintf(stderr,"[c5] mailbox geometry %ux%u bytes=%u stride=%u c6=0x%08x state=%u is not the VGA default; C5 stays disabled\n",
                        s.dimensions>>16,s.dimensions&0xffffu,s.bytes,s.stride,s.c6,s.state);
                else
                    fprintf(stderr,"[c5] mailbox snapshot unavailable; C5 stays disabled\n");
            }
            fflush(stderr);
        }
        while (!m_stop) {
            // Publish the optical pair's last capture time for the UI freshness gate.
            { QMutexLocker lock(&latest.mutex);
              m_opticalCaptureMs[0].store(latest.lastCapturedMs[4],std::memory_order_relaxed);
              m_opticalCaptureMs[1].store(latest.lastCapturedMs[5],std::memory_order_relaxed); }
            const int opticalRequest=m_c5Request.exchange(-1);
            if(opticalRequest>=0) {
                // State4 requires both optical producers. Reject before draining
                // workers or issuing command writes; preserve the original mask.
                // A FAILED mailbox is recovered by exactly one bounded attempt,
                // and that attempt republishes the retained default (VGA) because
                // it is the only geometry the mailbox still describes. The
                // operator's next request applies the direction they picked.
                const bool recovering=c5Recovery;
                const bool admitted=captureMaskSupported && c5::captureAdmitted(appliedCaptureMask);
                if(!admitted || (resolutionFault && !recovering)) {
                    m_resolutionBusy=resolutionFault;
                    emit resolutionChanged(4,cameraHd(4),false,admitted?
                        "C5 unavailable: readers stopped; recovery requires a viewer restart":
                        "Select overview or HDMI (C5+C6) before C5 switch");
                    continue;
                }
                const bool targetHd=recovering?false:(opticalRequest!=0);
                if(recovering) {
                    fprintf(stderr,"[c5] recovery attempt requested=%s published=VGA next_epoch=%u\n",
                        opticalRequest?"720P":"480P",c5Epoch+1u);
                    fflush(stderr);
                }
                // Step by a wide stride so a concurrent probe can never outrun us,
                // and persist before issuing so a restart continues ascending.
                if(c5Epoch>0xFFFFFF00u) c5Epoch=C5_EPOCH_BASE;
                c5Epoch+=0x10u;
                c5EpochPersist(c5Epoch);
                emit resolutionAcceptanceStarted(4);
                const auto result=c5::transact(optical,targetHd,c5Epoch,geometries[4]);
                bool ok=result.ok;
                if(ok) {
                    // Committed host descriptor changes only after published ACK,
                    // coherent metadata and both-bank stale-tag fences pass.
                    ok=dev.configureCameraGeometry(result.geometry);
                    if(ok) {
                        geometries[4]=result.geometry;
                        {QMutexLocker lock(&latest.mutex);
                         for(int c:{4,5}) {latest.c[c].clear();latest.have[c]=false;latest.fps[c]=0;}}
                        {QMutexLocker lock(&m_displayMutex);m_latestDisplay={};m_rawSnapshot={};m_displayPending=false;}
                        for(int c:{4,5}) {cameraPixels[c].clear();lastCamGen[c]=0;}
                        for(int c:{4,5}) {
                            uint32_t a=0,b=0;
                            if(!dev.readTag(geometries[c].tagAddress(0),a) ||
                               !dev.readTag(geometries[c].tagAddress(1),b)) {ok=false;break;}
                            const uint32_t sequence=tdm::newerCameraTag(a,b)?a:b;
                            ok=workers[c].restartForGeometry(geometries[c],sequence) && ok;
                        }
                        if(ok) {
                            const unsigned modes=m_hdModes.load();
                            m_hdModes=targetHd?modes|16u:modes&~16u;
                        }
                    }
                }
                if(ok) {
                    if(recovering) {
                        c5Recovery=false;
                        fprintf(stderr,"[c5] recovered: mailbox published %ux%u bytes=%u stride=%u epoch=%u\n",
                            result.geometry.width,result.geometry.height,result.geometry.pixelBytes,
                            result.geometry.stride,result.epoch);
                    }
                    if(resolutionFault) {
                        resolutionFault=false;
                        fprintf(stderr,"[c5] resolution fault cleared after committed C5 transaction\n");
                    }
                    fflush(stderr);
                }
                if(!ok && result.readersStopped) {
                    resolutionFault=true;
                    for(auto& w:workers)w.stop();for(auto& w:workers)w.wait();
                }
                m_resolutionBusy=resolutionFault;
                if(!ok && result.recovery) {
                    c5::Snapshot after;
                    const bool have=c5::snapshot(optical,after);
                    if(have)
                        fprintf(stderr,"[c5] recovery failed: sent_epoch=%u error=%s mailbox_state=%u error_code=0x%08x doorbell=%u epoch=%u completed=%u banks=%u\n",
                            c5Epoch,result.error.c_str(),after.state,after.error,after.doorbell,after.epoch,after.completed,after.banks);
                    else
                        fprintf(stderr,"[c5] recovery failed: sent_epoch=%u error=%s mailbox snapshot unavailable\n",
                            c5Epoch,result.error.c_str());
                    fflush(stderr);
                }
                emit resolutionChanged(4,cameraHd(4),ok,ok?
                    (recovering?"C5 recovered at 640×480 (retained default); request again for 1280×720":
                                "C5 native geometry committed"):
                    QString::fromStdString(result.error.empty()?"C5 host restart failed":result.error)+
                    (resolutionFault?"; all six host readers stopped; external recovery required; remote hold unverified":""));
                continue;
            }
            const int pairRequest=m_pairRequest.exchange(-1);
            if(pairRequest>=0) {
                ++pairTransaction;
                pairCommitFailed=false;
                std::array<runtime_camera::Mode,2> targets{{geometries[2].mode,geometries[3].mode}};
                if(pairRequest>=16){
                    const int camera=(pairRequest-16)/4;
                    if(camera<2||camera>3){m_resolutionBusy=false;continue;}
                    targets[camera-2]=runtime_camera::Mode((pairRequest-16)%4);
                }else targets={{runtime_camera::Mode(pairRequest),runtime_camera::Mode(pairRequest)}};
                fprintf(stderr,"CAM34_PAIR_BEGIN transaction=%llu target3=%u target4=%u prior3=%u prior4=%u\n",
                    (unsigned long long)pairTransaction,unsigned(targets[0]),unsigned(targets[1]),unsigned(geometries[2].mode),unsigned(geometries[3].mode));fflush(stderr);
                const auto result=pairController.apply(targets);
                // The in-flight target descriptors end with the transaction pass or
                // fail; the committed table is the only authority afterwards.
                dev.clearExpectedCameraGeometries();
                const bool completed=(result.state==cam34_pair::State::Committed || result.state==cam34_pair::State::Recovered)&&!pairCommitFailed;
                if(result.state==cam34_pair::State::HeldSafe || pairCommitFailed) {
                    resolutionFault=true;for(auto& w:workers)w.stop();for(auto& w:workers)w.wait();
                }
                m_resolutionBusy=resolutionFault;
                fprintf(stderr,"CAM34_PAIR_END transaction=%llu state=%d host_commit_failed=%d mode3=%u mode4=%u generation3=%llu generation4=%llu\n",
                    (unsigned long long)pairTransaction,int(result.state),int(pairCommitFailed),unsigned(geometries[2].mode),unsigned(geometries[3].mode),
                    (unsigned long long)geometries[2].generation,(unsigned long long)geometries[3].generation);fflush(stderr);
                emit pairModeChanged(pairRequest,completed&&result.state==cam34_pair::State::Committed,
                    completed?QString("C3/C4 %1").arg(result.state==cam34_pair::State::Committed?"mode committed":"prior modes recovered"):
                    QString::fromStdString(result.error)+(pairCommitFailed?"; host geometry/restart failed":""));
                continue;
            }
            if(captureMaskSupported && !resolutionFault && !reportResolution &&
               (!m_resolutionBusy.load() || appliedCaptureMask==0xffffffffu)) {
                const unsigned wanted=selectedCaptureMask();
                // A readiness ticket forces the existing verified mask/restart
                // transaction even if a previous view already used this mask.
                const quint64 readyTicket=m_overviewReadyRequest.load();
                if(wanted!=appliedCaptureMask || (readyTicket && readyTicket!=verifiedOverviewTicket)) {
                    for(auto& w:workers) w.stop();
                    for(auto& w:workers) w.wait();
                    scheme2::admission().disarm();
                    QElapsedTimer drain; drain.start();
                    while(!scheme2::admission().idle() && drain.elapsed()<10000) msleep(5);
                    uint32_t mask=0,idle=0;
                    bool ok=scheme2::admission().idle() && dev.regWrite(0x20000880,wanted) &&
                        dev.regRead(0x20000880,mask) && mask==wanted;
                    drain.restart();
                    while(ok && drain.elapsed()<3000) {
                        ok=dev.regRead(0x20000890,idle);
                        if(!ok || (idle & (0x3fu^wanted))==(0x3fu^wanted)) break;
                        msleep(1);
                    }
                    ok=ok && (idle & (0x3fu^wanted))==(0x3fu^wanted);
                    fprintf(stderr,"VIEW_CAPTURE_MASK requested=0x%02x actual=0x%02x idle=0x%02x result=%s\n",wanted,mask,idle,ok?"ok":"failed");
                    fflush(stderr);
                    if(!ok) {
                        const bool held=controller().holdSafe();
                        resolutionFault=true;
                        emit resolutionChanged(resolutionCamera,m_cam1Hd,false,held ? "Capture selection failed; readers stopped, target held" : "Capture selection failed; hardware hold unverified, readers stopped");
                        continue;
                    }
                    appliedCaptureMask=wanted;
                    ++viewTransaction;
                    bool baselineOk=true;
                    for(int c=0;c<CAM_COUNT;++c) {
                        viewBaselineReads[c]=dev.workerReadCalls(c);
                        const auto bytes=geometries[c].pixelBytes;
                        for(int bank=0;bank<2;++bank)
                            baselineOk=dev.readTag(CAM_BASE[c][bank]+bytes,viewBaselineTags[c][bank]) && baselineOk;
                    }
                    if(!baselineOk) {
                        const bool held=controller().holdSafe();
                        resolutionFault=true;
                        emit resolutionChanged(resolutionCamera,m_cam1Hd,false,held ? "Capture evidence read failed; target held" : "Capture evidence read failed; hardware hold unverified");
                        continue;
                    }
                    { QMutexLocker lock(&latest.mutex);
                      for(int c=0;c<CAM_COUNT;++c) {
                          viewBaselinePublications[c]=latest.camGen[c]; viewBaselineErrors[c]=latest.errors[c];
                          latest.c[c].clear(); latest.have[c]=false; latest.fps[c]=0;
                      }
                      ++latest.gen; }
                    { QMutexLocker lock(&m_displayMutex); m_latestDisplay={}; m_rawSnapshot={}; m_displayPending=false; }
                    cameraPixels={};
                    std::fill(lastCamGen,lastCamGen+CAM_COUNT,0);
                    for(int c=0;c<CAM_COUNT;++c) {
                        ++geometries[c].generation;
                        const auto& pending=pendingDelivery[c];
                        const uint32_t* tags=pending.pending?pending.prior:viewBaselineTags[c];
                        const uint32_t sequence=tdm::newerCameraTag(tags[1],tags[0])?tags[1]:tags[0];
                        if(!dev.configureCameraGeometry(geometries[c])) {resolutionFault=true;break;}
                        if(!workers[c].restartForGeometry(geometries[c],sequence,pending.stale[0],pending.stale[1])) {
                            resolutionFault=true;break;
                        }
                    }
                    for(auto& w:workers) if(!w.isRunning()) resolutionFault=true;
                    if(!workersHealthy()) resolutionFault=true;
                    if(resolutionFault) {
                        for(auto& w:workers)w.stop();for(auto& w:workers)w.wait();
                        controller().holdSafe();
                        emit resolutionChanged(resolutionCamera,m_cam1Hd,false,"Capture geometry restart failed; readers stopped, recovery required");
                        continue;
                    }
                    viewEvidenceClock.start(); viewLastSample=-500;
                    verifiedOverviewTicket=readyTicket;
                }
            }
            // A parked target has no publication while its view mask excludes it.
            // Configuration is acknowledged separately; acceptance starts on its
            // next admission and retains the pre-switch sequence floor.
            if(!reportResolution && !resolutionFault && !m_resolutionBusy.load() && workersHealthy()) {
                for(int c:{0,2,3}) if(pendingDelivery[c].pending && (appliedCaptureMask & (1u<<c))) {
                    resolutionCamera=c; m_cam1Hd=cameraHd(c); previousResolution=pendingDelivery[c].previous;
                    std::copy(pendingDelivery[c].stale,pendingDelivery[c].stale+2,heldTargetTags);
                    std::copy(pendingDelivery[c].sensor,pendingDelivery[c].sensor+4,sensorOutput);sensorOutputValid=15;
                    for(int i=0;i<CAM_COUNT;++i) for(int bank=0;bank<2;++bank)
                        priorTags[i][bank]=i==c?pendingDelivery[c].prior[bank]:viewBaselineTags[i][bank];
                    source=SourceEvidence{};sourceClock.start();deliveryDeadline.start();
                    const QString baselineFailure=readSourceSnapshot();
                    if(!baselineFailure.isEmpty()) {failAcceptance(baselineFailure);break;}
                    source.baseline=source.seq;source.baselineMs=source.lastStableMs;source.baselineValid=true;
                    for(int i=0;i<CAM_COUNT;++i) {
                        auditReads[i]=dev.workerReadCalls(i);
                        QMutexLocker lock(&latest.mutex);
                        auditPublications[i]=previousPublications[i]=latest.camGen[i];auditErrors[i]=latest.errors[i];
                        readDeltas[i]=publicationDeltas[i]=errorDeltas[i]=0;
                        lastPublicationAdvanceMs[i]=-1;publicationAgeMs[i]=captureAgeMs[i]=-1;
                        for(int bank=0;bank<2;++bank) {
                            auditTags[i][bank]=previousTags[i][bank]=priorTags[i][bank];
                            lastTagAdvanceMs[i][bank]=tagAgeMs[i][bank]=-1;
                        }
                    }
                    freshBanks=0;auditSamples=0;lastAuditMs=-100;producerEvidencePassed=false;
                    ++acceptanceTransaction; reportResolution=true;m_resolutionBusy=true;
                    emit resolutionAcceptanceStarted(c);
                    fprintf(stderr,"CAM134_ACCEPT_DEFERRED_START transaction=%u camera=%d mask=0x%02x\n",acceptanceTransaction,c+1,appliedCaptureMask);
                    break;
                }
            }
            if(viewEvidenceEnabled && viewEvidenceClock.isValid() && !resolutionFault && !reportResolution &&
               !m_resolutionBusy.load() && viewEvidenceClock.elapsed()-viewLastSample>=500) {
                viewLastSample=viewEvidenceClock.elapsed();
                // BEGIN bounded default capture sample. Share the existing
                // evidence cadence; no new poll loop, timer or capture gate.
                if(captureDiagnosticClock.elapsed()<=40000 && defaultCaptureDiagnosticSamples<80) {
                    ++defaultCaptureDiagnosticSamples;
                    fprintf(stderr,"CAM134_CAPTURE_DIAG_CONTEXT next_sample=%u view_transaction=%u view_elapsed_ms=%lld\n",
                        captureDiagnosticSample+1,viewTransaction,(long long)viewLastSample);
                    observeCapture("default_running",-1);
                }
                // END bounded default capture sample.
                uint32_t mask=0,idle=0;
                bool ok=dev.regRead(0x20000880,mask) && dev.regRead(0x20000890,idle);
                for(int c=0;c<CAM_COUNT;++c) {
                    uint32_t tags[2]={};
                    const auto bytes=geometries[c].pixelBytes;
                    for(int bank=0;bank<2;++bank) ok=dev.readTag(CAM_BASE[c][bank]+bytes,tags[bank]) && ok;
                    uint64_t pubs=0,errors=0; qint64 age=-1; double fpsNow=0;
                    { QMutexLocker lock(&latest.mutex);
                      pubs=latest.camGen[c]-viewBaselinePublications[c]; errors=latest.errors[c]-viewBaselineErrors[c];
                      fpsNow=latest.fps[c];
                      if(latest.lastCapturedMs[c]>0) age=monotonicMs()-latest.lastCapturedMs[c]; }
                    fprintf(stderr,"VIEW_CAPTURE_SAMPLE transaction=%u elapsed_ms=%lld camera=%d mask=0x%02x idle=0x%02x baseline0=%u baseline1=%u tag0=%u tag1=%u reads=%llu publications=%llu errors=%llu capture_age_ms=%lld fps=%.2f result=%s\n",
                        viewTransaction,(long long)viewLastSample,c+1,mask,idle,viewBaselineTags[c][0],viewBaselineTags[c][1],tags[0],tags[1],
                        (unsigned long long)(dev.workerReadCalls(c)-viewBaselineReads[c]),(unsigned long long)pubs,(unsigned long long)errors,
                        (long long)age,fpsNow,ok?"ok":"failed");
                }
                fflush(stderr);
            }
            if(m_runtimeHoldRequest.exchange(false)) {
                for(auto& w:workers) w.stop();
                for(auto& w:workers) w.wait();
                const bool held=controller().holdSafe();
                resolutionFault=true; reportResolution=false;
                emit resolutionChanged(resolutionCamera,m_cam1Hd,false,held ?
                    "720P no-frame timeout: readers stopped, capture held safe; automatic restart inhibited" :
                    "720P no-frame timeout: readers stopped, hardware hold unverified; automatic restart inhibited");
                continue;
            }
            const int request = m_resolutionRequest.exchange(-1);
            const int requested=request<0?-1:(request&1);
            if(request>=0) { resolutionCamera=request/2; m_cam1Hd=cameraHd(resolutionCamera); }
            if(request>=0 && bool(requested)==m_cam1Hd.load()) m_resolutionBusy=false;
            if (requested >= 0 && !resolutionFault && bool(requested) != m_cam1Hd.load() && workersHealthy()) {
                if (!controller().supported()) {
                    m_resolutionBusy=false;
                    emit resolutionChanged(resolutionCamera,m_cam1Hd, false, "Camera resolution unavailable: FPGA candidate required");
                } else {
                    dev.protectRuntimeSwitch();
                    emit statusMsg(QString("C%1 resolution switching: target held").arg(resolutionCamera+1));
                    workers[resolutionCamera].stop();
                    workers[resolutionCamera].wait();
                    bool beforeSwitchHealthy=true;
                    for(int c=0;c<CAM_COUNT;++c) auditReads[c]=dev.workerReadCalls(c);
                    { QMutexLocker lock(&latest.mutex);
                      for(int c=0;c<CAM_COUNT;++c) {
                          auditPublications[c]=latest.camGen[c];auditErrors[c]=latest.errors[c];
                          beforeSwitchHealthy=beforeSwitchHealthy && latest.errors[c]==0;
                      } }
                    if(!beforeSwitchHealthy) continue; // Next loop latches the transport fault without changing the sensor.
                    scheme2::admission().disarm();
                    QElapsedTimer consumers; consumers.start();
                    while(!scheme2::admission().idle() && consumers.elapsed()<10000) msleep(5);
                    if(!scheme2::admission().idle()) {
                        resolutionFault=true;
                        for(auto& w:workers) w.stop();
                        for(auto& w:workers) w.wait();
                        controller().holdSafe();
                        emit resolutionChanged(resolutionCamera,m_cam1Hd,false,"Analytics DMA did not drain: readers stopped, recovery required");
                        continue;
                    }
                    { QMutexLocker lock(&latest.mutex);
                      const int c=resolutionCamera; latest.c[c].clear(); latest.have[c]=false; latest.fps[c]=0;
                      ++latest.gen; }
                    { QMutexLocker lock(&m_displayMutex); m_latestDisplay={}; m_rawSnapshot={}; m_displayPending=false; }
                    cameraPixels[resolutionCamera].clear();
                    lastCamGen[resolutionCamera]=0;
                    std::string error;
                    previousResolution=m_cam1Hd.load();
                    reportResolution=false; producerEvidencePassed=false;
                    sensorOutputValid=0;
                    source=SourceEvidence{}; sourceClock.invalidate(); deliveryDeadline.invalidate();
                    ++acceptanceTransaction;
                    targetPublicationPending=pendingDelivery[resolutionCamera].pending;
                    bool targetBaseline=true;
                    if(pendingDelivery[resolutionCamera].pending) {
                        std::copy(pendingDelivery[resolutionCamera].prior,pendingDelivery[resolutionCamera].prior+2,priorTags[resolutionCamera]);
                    } else targetBaseline=dev.readTag(geometries[resolutionCamera].tagAddress(0),priorTags[resolutionCamera][0]) &&
                        dev.readTag(geometries[resolutionCamera].tagAddress(1),priorTags[resolutionCamera][1]);
                    if(!targetBaseline) {
                        for(auto& w:workers) w.stop();
                        for(auto& w:workers) w.wait();
                        controller().holdSafe();resolutionFault=true;
                        emit resolutionChanged(resolutionCamera,m_cam1Hd,false,"Prior target sequence read failed; capture held, external recovery required");
                        continue;
                    }
                    // Pre-switch entry classification (read-only). Two clean
                    // samples taken strictly before the runtime table is
                    // applied decide whether each masked non-target producer was
                    // already advancing. The existing view baseline extends the
                    // horizon for slow producers. A read failure can only ADD
                    // producers to the gate (conservative), never remove them.
                    staleProducerMask=0;
                    uint32_t entryTags[CAM_COUNT][2]={},entryTagsLater[CAM_COUNT][2]={};
                    bool entryReadsOk=true;
                    auto readEntryTags=[&](uint32_t (&dst)[CAM_COUNT][2]) {
                        for(int c=0;c<CAM_COUNT;++c) {
                            if(c==resolutionCamera) continue;
                            const auto bytes=geometries[c].pixelBytes;
                            for(int bank=0;bank<2;++bank)
                                entryReadsOk=dev.readTag(CAM_BASE[c][bank]+bytes,dst[c][bank]) && entryReadsOk;
                        }
                    };
                    readEntryTags(entryTags);
                    if(entryReadsOk) msleep(120);
                    readEntryTags(entryTagsLater);
                    if(!controller().apply(bool(requested),m_cam1Hd,error)) {
                        resolutionFault=true;
                        for(auto& w:workers) w.stop();
                        for(auto& w:workers) w.wait();
                        controller().holdSafe();
                        emit resolutionChanged(resolutionCamera,m_cam1Hd,false,QString::fromStdString(error));
                    } else {
                        m_cam1Hd=bool(requested);
                        const unsigned modes=m_hdModes.load();
                        m_hdModes=requested?modes|(1u<<resolutionCamera):modes&~(1u<<resolutionCamera);
                        geometries[resolutionCamera]=runtime_camera::geometry(resolutionCamera,requested?runtime_camera::Mode::Hd720:runtime_camera::Mode::Default,geometries[resolutionCamera].generation+1);
                        if(!dev.configureCameraGeometry(geometries[resolutionCamera])) {
                            failAcceptance("Host target geometry configuration failed");continue;
                        }
                        appliedCaptureMask=selectedCaptureMask();
                        // Classify from the entry samples only: an already
                        // frozen producer does not fail this switch, a producer
                        // that dies after entry still does.
                        unsigned advancingMask=0;
                        for(int c=0;c<CAM_COUNT;++c) {
                            if(c==resolutionCamera || !(appliedCaptureMask & (1u<<c))) continue;
                            bool advancing=!entryReadsOk; // unreadable entry evidence keeps the gate strict
                            for(int bank=0;bank<2 && !advancing;++bank) {
                                const uint32_t entry=uint32_t(entryTagsLater[c][bank]-entryTags[c][bank]);
                                const uint32_t baseline=uint32_t(entryTags[c][bank]-viewBaselineTags[c][bank]);
                                if((entry>0 && entry<0x80000000u) ||
                                   (baseline>0 && baseline<0x80000000u)) advancing=true;
                            }
                            if(advancing) advancingMask|=1u<<c;
                            else staleProducerMask|=1u<<c;
                        }
                        fprintf(stderr,"[accept] switch entry target=C%d masked=0x%02x advancing_mask=0x%02x stale_mask=0x%02x entry_window_ms=%d excluded_from_gate=%u\n",
                            resolutionCamera+1,appliedCaptureMask,advancingMask,staleProducerMask,
                            entryReadsOk?120:0,unsigned(__builtin_popcount(staleProducerMask)));
                        fflush(stderr);
                        viewEvidenceClock.invalidate();
                        if(!(appliedCaptureMask & (1u<<resolutionCamera))) {
                            auto& pending=pendingDelivery[resolutionCamera];
                            pending.pending=true;pending.previous=previousResolution;
                            std::copy(sensorOutput,sensorOutput+4,pending.sensor);
                            std::copy(priorTags[resolutionCamera],priorTags[resolutionCamera]+2,pending.prior);
                            std::copy(heldTargetTags,heldTargetTags+2,pending.stale);
                            const uint32_t sequence=int32_t(pending.prior[1]-pending.prior[0])>0?pending.prior[1]:pending.prior[0];
                            if(!workers[resolutionCamera].restartForGeometry(geometries[resolutionCamera],sequence,pending.stale[0],pending.stale[1])) {
                                failAcceptance("Target reader rejected committed geometry");continue;
                            }
                            m_resolutionBusy=false;
                            fprintf(stderr,"CAM134_CONFIGURED_PENDING transaction=%u camera=%d mode=%d mask=0x%02x delivery_accepted=0\n",acceptanceTransaction,resolutionCamera+1,requested,appliedCaptureMask);
                            emit resolutionChanged(resolutionCamera,m_cam1Hd,true,QString("C%1 resolution set; select this camera or overview to receive fresh frames").arg(resolutionCamera+1));
                            continue;
                        }
                        // Start source grace after apply, before waiting for DDR commits.
                        // Workers remain joined; regRead uses the existing device mutex.
                        deliveryDeadline.start();
                        sourceClock.start();
                        const QString sourceBaselineFailure=readSourceSnapshot();
                        if(!sourceBaselineFailure.isEmpty()) {
                            failAcceptance(sourceBaselineFailure);
                            continue;
                        }
                        source.baseline=source.seq;
                        source.baselineMs=source.lastStableMs;
                        source.baselineValid=true;
                        uint32_t tagsNow[CAM_COUNT][2]={};
                        bool readsOk=true,fresh=false;
                        QElapsedTimer commits; commits.start();
                        // Independent read-only observations: never feed these values or
                        // read failures into the acceptance predicate below. Samples are
                        // sequential, not an atomic hardware snapshot; bit=2*camera+bank.
                        unsigned commitDiagnosticSamples=0;
                        qint64 lastCommitDiagnosticMs=0;
                        const auto logCommitWait=[&](const char* phase) {
                            const qint64 sampleMs=commits.elapsed();
                            const unsigned sample=++commitDiagnosticSamples;
                            unsigned failingBanks=0,readFailedBanks=0;
                            for(int c=0;c<CAM_COUNT;++c) {
                                if(!(appliedCaptureMask & (1u<<c))) continue;
                                for(int bank=0;bank<2;++bank) {
                                    const uint32_t address=CAM_BASE[c][bank]+geometries[c].pixelBytes;
                                    uint32_t current=0;
                                    const bool ok=dev.readTag(address,current);
                                    const uint32_t advance=uint32_t(current-priorTags[c][bank]);
                                    const bool bankFresh=ok && advance>0 && advance<0x80000000u &&
                                        (c!=resolutionCamera || cam1::freshTargetSequence(current,priorTags[c][bank],heldTargetTags[bank]));
                                    if(!bankFresh) failingBanks|=1u<<(2*c+bank);
                                    if(!ok) readFailedBanks|=1u<<(2*c+bank);
                                    fprintf(stderr,"CAM134_COMMIT_WAIT_BANK transaction=%u target=%d phase=%s sample=%u elapsed_ms=%lld camera=%d bank=%d address=0x%08x prior=%u current=%u held=%u held_applicable=%d read_ok=%d fresh=%d\n",
                                        acceptanceTransaction,resolutionCamera+1,phase,sample,(long long)sampleMs,c+1,bank,address,
                                        priorTags[c][bank],current,c==resolutionCamera?heldTargetTags[bank]:0u,
                                        int(c==resolutionCamera),int(ok),int(bankFresh));
                                }
                            }
                            fprintf(stderr,"CAM134_COMMIT_WAIT transaction=%u target=%d phase=%s sample=%u elapsed_ms=%lld mask=0x%02x failing_bank_mask=0x%03x read_failed_bank_mask=0x%03x loop_reads_ok=%d loop_fresh=%d\n",
                                acceptanceTransaction,resolutionCamera+1,phase,sample,(long long)sampleMs,appliedCaptureMask,
                                failingBanks,readFailedBanks,int(readsOk),int(fresh));
                            // Frozen aligned run 20261014_102943_662630:
                            // +30=offered writer pixels at SOF; +a0={overflow16,short16}.
                            // ov5640_reg.v +60={wd8,state8,cmd16}, +70={b16,aw16},
                            // +d0=sys_status, +f0=last_cnt; +190..1c0=CDC counters.
                            const uint32_t writerBase=resolutionCamera==0?0x20000000u:
                                (resolutionCamera==2?0x20000400u:0x20000600u);
                            const uint32_t offsets[]={0x30,0x60,0x70,0xa0,0xd0,0xf0,0x190,0x1a0,0x1b0,0x1c0};
                            for(uint32_t offset:offsets) {
                                uint32_t value=0;
                                const bool ok=dev.regRead(writerBase+offset,value);
                                fprintf(stderr,"CAM134_COMMIT_WAIT_WRITER transaction=%u target=%d phase=%s sample=%u elapsed_ms=%lld address=0x%08x value=0x%08x read_ok=%d\n",
                                    acceptanceTransaction,resolutionCamera+1,phase,sample,(long long)sampleMs,writerBase+offset,value,int(ok));
                            }
                            fflush(stderr);
                            lastCommitDiagnosticMs=commits.elapsed();
                        };
                        logCommitWait("entry");
                        while(readsOk && commits.elapsed()<8000) {
                            const QString sourceFailure=observeSource();
                            if(!sourceFailure.isEmpty()) {
                                logCommitWait("before_source_failure");
                                failAcceptance(sourceFailure);
                                readsOk=false;
                                break;
                            }
                            fresh=true;
                            for(int c=0;c<CAM_COUNT;++c) {
                                if(!(appliedCaptureMask & (1u<<c))) continue;
                                const auto bytes=geometries[c].pixelBytes;
                                if(!dev.readTag(CAM_BASE[c][0]+bytes,tagsNow[c][0]) ||
                                   !dev.readTag(CAM_BASE[c][1]+bytes,tagsNow[c][1])) { readsOk=false;break; }
                                for(int bank=0;bank<2;++bank) {
                                    const uint32_t advance=uint32_t(tagsNow[c][bank]-priorTags[c][bank]);
                                    // Frozen before the switch: not this gate's business.
                                    if(c!=resolutionCamera && (staleProducerMask & (1u<<c))) continue;
                                    fresh=fresh && advance>0 && advance<0x80000000u &&
                                        (c!=resolutionCamera || cam1::freshTargetSequence(tagsNow[c][bank],priorTags[c][bank],heldTargetTags[bank]));
                                }
                            }
                            // Complete distinct post-grace source evidence before
                            // restarting the target and entering expensive full audits.
                            if(source_acceptance::readyForRestart(fresh,source)) break;
                            if(commitDiagnosticSamples<33 && commits.elapsed()-lastCommitDiagnosticMs>=250)
                                logCommitWait("poll");
                            msleep(5);
                        }
                        if(resolutionFault) continue;
                        fresh=source_acceptance::readyForRestart(fresh,source) && readsOk;
                        if(fresh && staleProducerMask)
                            fprintf(stderr,"[accept] target fresh, %u masked producer(s) already stale (mask=0x%02x) excluded from the freshness gate\n",
                                unsigned(__builtin_popcount(staleProducerMask)),staleProducerMask);
                        if(!fresh) {
                            logCommitWait("before_commit_failure");
                            failAcceptance(readsOk ? "No fresh target commits within 8000 ms" :
                                "Target commit tag read failed");
                        } else {
                            { QMutexLocker lock(&latest.mutex);
                              // Preserve counters from before the target hold. Other
                              // readers run throughout apply and their errors must count.
                              for(int c=0;c<CAM_COUNT;++c) {
                                  previousPublications[c]=latest.camGen[c];
                                  readDeltas[c]=publicationDeltas[c]=errorDeltas[c]=0;
                                  lastPublicationAdvanceMs[c]=-1;
                                  publicationAgeMs[c]=captureAgeMs[c]=-1;
                                  for(int bank=0;bank<2;++bank) {
                                      // Start from the fresh committed tags, not the pre-switch tags.
                                       auditTags[c][bank]=previousTags[c][bank]=tagsNow[c][bank];
                                      lastTagAdvanceMs[c][bank]=tagAgeMs[c][bank]=-1;
                                  }
                              } }
                            freshBanks=0; auditSamples=0; lastAuditMs=-100;
                            const uint32_t sequence=int32_t(priorTags[resolutionCamera][1]-priorTags[resolutionCamera][0])>0?priorTags[resolutionCamera][1]:priorTags[resolutionCamera][0];
                            if(!workers[resolutionCamera].restartForGeometry(geometries[resolutionCamera],sequence,heldTargetTags[0],heldTargetTags[1])) {
                                failAcceptance("Target reader rejected committed geometry");continue;
                            }
                            reportResolution=true;
                            deliveryDeadline.start();
                        }
                    }
                }
            }
            if(resolutionFault) { msleep(25); continue; }
            if(captureMaskSupported && !reportResolution) {
                int failedCamera=-1;
                { QMutexLocker lock(&latest.mutex);
                  for(int c=0;c<CAM_COUNT;++c) if(latest.errors[c]) {failedCamera=c;break;} }
                if(failedCamera>=0) {
                    for(auto& w:workers) w.stop();
                    for(auto& w:workers) w.wait();
                    scheme2::admission().disarm();
                    QElapsedTimer drain;drain.start();
                    while(!scheme2::admission().idle() && drain.elapsed()<10000) msleep(5);
                    bool held=false;
                    // Optical errors must never instantiate a local SCCB switch.
                    // ABI v1 has no explicit HOLD command: host readers stay
                    // stopped and remote hold requires external verification.
                    if(failedCamera<4) {
                        cam1::Switch emergency({[&](uint32_t a,uint32_t& v){return dev.regRead(a,v);},
                            [&](uint32_t a,uint32_t v){return dev.regWrite(a,v);},[]{QThread::msleep(1);},{},
                            [&](const std::string& text){fprintf(stderr,"CAM134_ERROR_HOLD camera=%d %s\n",failedCamera+1,text.c_str());}},failedCamera);
                        held=emergency.holdSafe();
                    }
                    resolutionFault=true;m_resolutionBusy=true;
                    { QMutexLocker lock(&m_displayMutex);m_latestDisplay={};m_rawSnapshot={};m_displayPending=false; }
                    cameraPixels={};
                    fprintf(stderr,"CAM134_TRANSPORT_FAULT camera=%d held_verified=%d analytics_drained=%d automatic_restart=0\n",failedCamera+1,int(held),int(scheme2::admission().idle()));
                    emit resolutionChanged(failedCamera,cameraHd(failedCamera),false,
                        QString("C%1 transport error: readers stopped; %2; external recovery required").arg(failedCamera+1).arg(held?"target held":"target hold unverified"));
                    continue;
                }
            }
            if(reportResolution && deliveryDeadline.elapsed()-lastAuditMs>=100) {
                const bool hd=m_cam1Hd.load();
                const auto g=cam1::geometry(hd);
                const auto transport=geometries[resolutionCamera];
                const uint32_t runtimeBase=controller().base();
                unsigned enabledBanks=0;
                for(int c=0;c<CAM_COUNT;++c) {
                    if(!(appliedCaptureMask & (1u<<c))) continue;
                    // A producer already frozen before the switch is not part of
                    // this transaction's freshness evidence.
                    if(c!=resolutionCamera && (staleProducerMask & (1u<<c))) continue;
                    enabledBanks|=3u<<(2*c);
                }
                const qint64 sampleMs=deliveryDeadline.elapsed();
                QString failure;
                // Readback proves configuration; source snapshots count offered pixels
                // between VSYNCs independently of quota. No per-line geometry is measured.
                const bool registersOk=dev.regRead(runtimeBase,auditMode) &&
                    dev.regRead(runtimeBase+0x40,auditDimensions) && dev.regRead(runtimeBase+0x50,auditBytes) &&
                    dev.regRead(runtimeBase+0x60,auditStride) && dev.regRead(0x20000880,auditMask) &&
                    dev.regRead(0x20000890,auditIdle);
                const unsigned configuredSensorWidth=(unsigned(sensorOutput[0])<<8)|sensorOutput[1];
                const unsigned configuredSensorHeight=(unsigned(sensorOutput[2])<<8)|sensorOutput[3];
                if(!registersOk) failure="Acceptance MMIO read failed";
                else if(sensorOutputValid!=15 || configuredSensorWidth!=g.width || configuredSensorHeight!=g.height ||
                    auditMode!=uint32_t(hd) || auditDimensions!=(transport.width<<16|transport.height) ||
                    auditBytes!=transport.pixelBytes || auditStride!=transport.stride) failure="Acceptance configured sensor/FPGA geometry mismatch";
                else if((auditMask&0x3f)!=appliedCaptureMask || (auditIdle&(0x3fu^appliedCaptureMask))!=(0x3fu^appliedCaptureMask))
                    failure="Acceptance producer mask/disabled idle mismatch";
                for(int c=0;c<CAM_COUNT && failure.isEmpty();++c) {
                    const uint32_t bytes=geometries[c].pixelBytes;
                    for(int bank=0;bank<2;++bank) {
                        if(!dev.readTag(CAM_BASE[c][bank]+bytes,auditTags[c][bank])) {
                            failure=QString("Acceptance tag read failed C%1 bank%2").arg(c+1).arg(bank); break;
                        }
                        if(!(appliedCaptureMask & (1u<<c)) && auditTags[c][bank]!=priorTags[c][bank]) {
                            failure=QString("Acceptance disabled tag advanced C%1 bank%2 prior=%3 actual=%4")
                                .arg(c+1).arg(bank).arg(priorTags[c][bank]).arg(auditTags[c][bank]); break;
                        }
                        if((appliedCaptureMask & (1u<<c)) && auditTags[c][bank]!=priorTags[c][bank] &&
                           (c!=resolutionCamera || cam1::freshTargetSequence(auditTags[c][bank],priorTags[c][bank],heldTargetTags[bank])))
                            freshBanks |= 1u<<(2*c+bank);
                        if(auditTags[c][bank]!=previousTags[c][bank])
                            lastTagAdvanceMs[c][bank]=deliveryDeadline.elapsed();
                        previousTags[c][bank]=auditTags[c][bank];
                    }
                }
                for(int c=0;c<CAM_COUNT;++c) readDeltas[c]=dev.workerReadCalls(c)-auditReads[c];
                { QMutexLocker lock(&latest.mutex);
                  const qint64 captureNow=monotonicMs();
                  for(int c=0;c<CAM_COUNT;++c) {
                      publicationDeltas[c]=latest.camGen[c]-auditPublications[c];
                      errorDeltas[c]=latest.errors[c]-auditErrors[c];
                      if(latest.camGen[c]!=previousPublications[c]) lastPublicationAdvanceMs[c]=deliveryDeadline.elapsed();
                      previousPublications[c]=latest.camGen[c];
                      captureAgeMs[c]=latest.lastCapturedMs[c]>0 ? captureNow-latest.lastCapturedMs[c] : -1;
                  } }
                // Timestamp each observation when it is actually received, not
                // before a potentially contended audit. Refresh source evidence
                // last so later tag I/O cannot consume its entire freshness budget.
                if(failure.isEmpty()) failure=observeSource();
                for(int c=0;c<CAM_COUNT;++c) {
                    for(int bank=0;bank<2;++bank)
                        tagAgeMs[c][bank]=advanceAge(deliveryDeadline.elapsed(),lastTagAdvanceMs[c][bank]);
                    publicationAgeMs[c]=advanceAge(deliveryDeadline.elapsed(),lastPublicationAdvanceMs[c]);
                    if(errorDeltas[c] && failure.isEmpty())
                        failure=QString("Acceptance worker error increment C%1 errors=%2")
                            .arg(c+1).arg(qulonglong(errorDeltas[c]));
                }
                for(int c=0;c<CAM_COUNT && failure.isEmpty();++c)
                    if(!(appliedCaptureMask & (1u<<c)) && (readDeltas[c] || publicationDeltas[c]))
                        failure=QString("Acceptance disabled worker active C%1 reads=%2 publications=%3")
                            .arg(c+1).arg(qulonglong(readDeltas[c])).arg(qulonglong(publicationDeltas[c]));
                lastAuditMs=deliveryDeadline.elapsed(); ++auditSamples;
                fprintf(stderr,"CAM134_ACCEPT_TARGET transaction=%u camera=%d alias=0x%08x source_base=0x%08x geometry_generation=%llu mode=%u sensor=%ux%u transport=%ux%u tag_offset=0x%08x mask=0x%02x audit_start_ms=%lld audit_end_ms=%lld audit_duration_ms=%lld\n",
                    acceptanceTransaction,resolutionCamera+1,runtimeBase,0x20000000u+uint32_t(resolutionCamera)*0x200u,
                    (unsigned long long)transport.generation,auditMode,g.width,g.height,transport.width,transport.height,transport.tagOffset,auditMask,
                    (long long)sampleMs,(long long)lastAuditMs,(long long)(lastAuditMs-sampleMs));
                fprintf(stderr,"CAM1_ACCEPT_SAMPLE transaction=%u elapsed_ms=%lld samples=%u sensor_regs=%02x/%02x/%02x/%02x sensor=%ux%u mode=%u dimensions=0x%08x payload=%u transfer=%u stride=%u mask=0x%02x idle=0x%02x disabled_idle=0x%02x fresh_banks=0x%03x source_expected=%u source_baseline_valid=%d source_baseline=%u source_baseline_ms=%lld source_seq=%u source_input=%u source_drop=%u source_stable=%d source_attempts=%u source_advances=%u source_elapsed_ms=%lld source_settled_ms=%lld source_age_ms=%lld result=%s\n",
                    acceptanceTransaction,(long long)lastAuditMs,auditSamples,unsigned(sensorOutput[0]),unsigned(sensorOutput[1]),unsigned(sensorOutput[2]),unsigned(sensorOutput[3]),configuredSensorWidth,configuredSensorHeight,
                    auditMode,auditDimensions,auditBytes,auditBytes+16,auditStride,auditMask,auditIdle,auditIdle&0x3e,freshBanks,
                    uint32_t(g.width)*uint32_t(g.height),int(source.baselineValid),source.baseline,
                    (long long)source.baselineMs,source.seq,source.input,source.drop,
                    int(source.stable),source.attempts,source.advances,(long long)sourceClock.elapsed(),
                    (long long)source.settledMs,(long long)advanceAge(sourceClock.elapsed(),source.lastAdvanceMs),
                    failure.isEmpty()?"ok":qPrintable(failure));
                for(int c=0;c<CAM_COUNT;++c)
                    fprintf(stderr,"CAM1_ACCEPT_CAMERA transaction=%u camera=%d payload=%u transfer=%u prior_tags=%u/%u actual_tags=%u/%u worker_read_delta=%llu publication_delta=%llu error_delta=%llu tag_age_ms=%lld/%lld publication_age_ms=%lld capture_age_ms=%lld\n",
                        acceptanceTransaction,c+1,geometries[c].pixelBytes,geometries[c].transferBytes(),
                        priorTags[c][0],priorTags[c][1],auditTags[c][0],auditTags[c][1],
                        (unsigned long long)readDeltas[c],(unsigned long long)publicationDeltas[c],(unsigned long long)errorDeltas[c],
                        (long long)tagAgeMs[c][0],(long long)tagAgeMs[c][1],(long long)publicationAgeMs[c],(long long)captureAgeMs[c]);
                if(!failure.isEmpty()) { failAcceptance(failure); continue; }
                // A 100 ms sample need not advance at 5 fps; every bank/publication
                // must instead have advanced within the bounded 500 ms window.
                producerEvidencePassed=lastAuditMs>=2000 && (freshBanks&enabledBanks)==enabledBanks &&
                    recentProducerEvidence(lastAuditMs) && recentSourceEvidence();
                for(int c=0;c<CAM_COUNT;++c) {
                    if(!(appliedCaptureMask & (1u<<c))) continue;
                    if(c!=resolutionCamera && (staleProducerMask & (1u<<c))) continue;
                    producerEvidencePassed=producerEvidencePassed && captureAgeMs[c]>=0 && captureAgeMs[c]<=500;
                }
            }
            if(reportResolution && deliveryDeadline.elapsed()>8000) {
                failAcceptance("Target producer evidence/frame delivery timeout");
                continue;
            }
            const quint64 readyTicket=m_overviewReadyRequest.load();
            bool readersReady=workersHealthy();
            for(auto& w:workers) readersReady=readersReady && w.isRunning();
            bool deferredDelivery=false;
            for(int c:{0,2,3}) deferredDelivery=deferredDelivery || pendingDelivery[c].pending;
            if(RuntimeOverviewBarrier::ready(readyTicket,verifiedOverviewTicket,reportResolution,
               resolutionFault,m_resolutionBusy.load(),deferredDelivery,readersReady,
               appliedCaptureMask,selectedCaptureMask())) {
                quint64 expected=readyTicket;
                if(m_overviewReadyRequest.compare_exchange_strong(expected,0)) {
                    fprintf(stderr,"VIEW_CAPTURE_READY ticket=%llu mask=0x%02x workers_ready=1\n",
                        (unsigned long long)readyTicket,appliedCaptureMask);fflush(stderr);
                    emit overviewReady(readyTicket,appliedCaptureMask);
                }
            }
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
            const bool hdmiFull = mode == CAM_COUNT && m_hdmiActive.load();
            const int paneMask = mode == CAM_COUNT ? 0x3F : (1 << pane);
            const int visibleMask = hdmiFull ? ((1 << tdm::hdmiLeftCamera) | (1 << tdm::hdmiRightCamera)) : paneMask;
            bool ready = false;
            uint64_t gen = 0;
            uint64_t camGen[CAM_COUNT] = {};
            uint64_t errors[CAM_COUNT] = {};
            bool have[CAM_COUNT] = {};
            double camFps[CAM_COUNT] = {};
            std::array<qint64, CAM_COUNT> captureTimes{};
            std::array<qint64, CAM_COUNT> rawCaptureTimes{};
            std::array<quint32, CAM_COUNT> tags{};
            std::array<int, CAM_COUNT> cameraGenerations{};
            {
                QMutexLocker lock(&latest.mutex);
                for (int i = 0; i < CAM_COUNT; i++)
                    ready = ready || latest.have[i];
                gen = latest.gen;
                if (gen == lastGen && mode == lastMode && displayGeneration == lastDisplayGeneration) {
                    lock.unlock(); msleep(2); continue;
                }
                for (int i = 0; i < CAM_COUNT; i++) {
                    have[i] = latest.have[i] && latest.sourceGenerations[i]==displayGeneration &&
                        geometries[i].acceptsPublication(latest.geometries[i].generation,size_t(latest.c[i].size()));
                    errors[i] = latest.errors[i];
                    camFps[i] = latest.fps[i];
                    captureTimes[i] = latest.lastCapturedMs[i];
                    rawCaptureTimes[i] = latest.rawCapturedMs[i];
                    tags[i] = latest.tags[i];
                    cameraGenerations[i] = latest.sourceGenerations[i];
                    if (monotonicMs() - captureTimes[i] > 1000) camFps[i] = 0;
                    camGen[i] = latest.camGen[i];
                }
                for (int i = 0; i < CAM_COUNT; ++i)
                    if (have[i]) cameraPixels[i] = latest.c[i]; else cameraPixels[i].clear();
            }
            if (hdmiFull) pane = tdm::hdmiInferenceCamera;
            if (hdmiFull && m_visionSink && camGen[tdm::hdmiLeftCamera] != hdmiLeftSequence && camGen[tdm::hdmiRightCamera] != hdmiRightSequence &&
                tdm::hdmiPairReady(monotonicMs(), rawCaptureTimes[tdm::hdmiLeftCamera], rawCaptureTimes[tdm::hdmiRightCamera],
                                   displayGeneration, cameraGenerations[tdm::hdmiLeftCamera], cameraGenerations[tdm::hdmiRightCamera])) {
                VisionFrame packet;
                packet.image = tdm::hdmiAnalyticsImage(cameraPixels[tdm::hdmiLeftCamera], cameraPixels[tdm::hdmiRightCamera]);
                packet.camera = tdm::hdmiInferenceCamera;
                packet.sourceGeneration = displayGeneration;
                packet.frameId = m_frameSequence.fetch_add(1) + 1;
                packet.tag = tags[tdm::hdmiLeftCamera];
                packet.capturedMs = qMin(rawCaptureTimes[tdm::hdmiLeftCamera], rawCaptureTimes[tdm::hdmiRightCamera]);
                if (!packet.image.isNull() && m_hdmiActive.load() && displayGeneration == m_sourceGeneration.load()) {
                    const QString proofDir=qEnvironmentVariable("DETVIEW_CAM34_EVIDENCE_DIR");
                    if(!proofDir.isEmpty() && hdmiSubmissions==0) {
                        QDir().mkpath(proofDir);
                        packet.image.save(proofDir+"/cam34_input_640x480.png");
                         QImage(reinterpret_cast<const uchar*>(cameraPixels[tdm::hdmiLeftCamera].constData()),640,480,1280,QImage::Format_RGB16).save(proofDir+"/cam5_hdmi_640x480.png");
                         QImage(reinterpret_cast<const uchar*>(cameraPixels[tdm::hdmiRightCamera].constData()),640,480,1280,QImage::Format_RGB16).save(proofDir+"/cam6_hdmi_640x480.png");
                    }
                    m_visionSink(packet);
                    hdmiLeftSequence = camGen[tdm::hdmiLeftCamera]; hdmiRightSequence = camGen[tdm::hdmiRightCamera];
                    if (++hdmiSubmissions % 60 == 1)
                         fprintf(stderr, "[hdmi-pair] generation=%d frames=%llu host_ms=%lld sources=C5+C6 input=640x480 filter=2x2-mean content=640x240 network_pad=120 canonical_pad=80 skew_ms=%lld tags=%u/%u\n",
                                displayGeneration, (unsigned long long)hdmiSubmissions, (long long)monotonicMs(),
                                (long long)qAbs(rawCaptureTimes[tdm::hdmiLeftCamera] - rawCaptureTimes[tdm::hdmiRightCamera]), tags[tdm::hdmiLeftCamera], tags[tdm::hdmiRightCamera]);
                }
            }
            if (!ready) { msleep(2); continue; }

            bool freshVisible = false;
            for (int camera = 0; camera < CAM_COUNT; ++camera)
                if ((visibleMask & (1 << camera)) && have[camera] && camGen[camera] != lastCamGen[camera])
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
                if (!(visibleMask & (1 << c))) continue;
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
                    const int w=int(geometries[c].width),h=int(geometries[c].height);
                    if(uint32_t(cameraPixels[c].size())!=geometries[c].pixelBytes)continue;
                    QImage image(reinterpret_cast<const uchar*>(cameraPixels[c].constData()),w,h,w*2,QImage::Format_RGB16);
                    if(w!=IMG_W||h!=IMG_H)image=image.scaled(IMG_W,IMG_H,Qt::IgnoreAspectRatio,Qt::FastTransformation);
                    for(int y=0;y<IMG_H;++y)memcpy(compImg.scanLine((c/GRID_COLS)*IMG_H+y)+(c%GRID_COLS)*IMG_W*2,image.constScanLine(y),IMG_W*2);
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
            display.rawCapturedMs = rawCaptureTimes;
            display.tags = tags;
            display.cameraGenerations = cameraGenerations;
             display.hdmiFull = hdmiFull;
            display.cam34Shared = true; // Legacy overlay mapping; tile geometry comes from descriptors.
            display.cam1Hd = cameraHd(0);
            display.geometries=geometries;
            bool targetFramesReady=true;
            for(int c=0;c<CAM_COUNT;++c) {
                if(!(appliedCaptureMask & (1u<<c))) continue;
                if(reportResolution && c!=resolutionCamera && (staleProducerMask & (1u<<c))) continue;
                targetFramesReady=targetFramesReady && have[c] && uint32_t(cameraPixels[c].size())==geometries[c].pixelBytes;
            }
            if(reportResolution) {
                const qint64 frameNow=monotonicMs();
                for(int c=0;c<CAM_COUNT;++c) {
                    targetFramesReady=targetFramesReady && errors[c]==auditErrors[c] && errorDeltas[c]==0;
                    if((appliedCaptureMask & (1u<<c)) &&
                       !(c!=resolutionCamera && (staleProducerMask & (1u<<c))))
                        targetFramesReady=targetFramesReady && captureTimes[c]>0 &&
                            frameNow-captureTimes[c]>=0 && frameNow-captureTimes[c]<=500;
                }
            }

            QString mailboxFailure;
            {
                QMutexLocker lock(&m_configMutex);
                if (mode == m_mode.load() && hdmiFull == m_hdmiActive.load() &&
                    (hdmiFull || pane == m_selectedCamera.load()) &&
                    displayGeneration == m_sourceGeneration.load() && !m_paused) {
                    // Keep error counters stable through mailbox publication and PASS;
                    // the earlier display snapshot alone cannot exclude a new worker error.
                    QMutexLocker acceptanceLock(reportResolution ? &latest.mutex : nullptr);
                    const qint64 mailboxMs=deliveryDeadline.elapsed();
                    const qint64 captureNow=monotonicMs();
                    if(reportResolution) for(int c=0;c<CAM_COUNT;++c) {
                        readDeltas[c]=dev.workerReadCalls(c)-auditReads[c];
                        publicationDeltas[c]=latest.camGen[c]-auditPublications[c];
                        errorDeltas[c]=latest.errors[c]-auditErrors[c];
                        for(int bank=0;bank<2;++bank)
                            tagAgeMs[c][bank]=advanceAge(mailboxMs,lastTagAdvanceMs[c][bank]);
                        publicationAgeMs[c]=advanceAge(mailboxMs,lastPublicationAdvanceMs[c]);
                        captureAgeMs[c]=latest.lastCapturedMs[c]>0 ? captureNow-latest.lastCapturedMs[c] : -1;
                        if(errorDeltas[c] && mailboxFailure.isEmpty())
                            mailboxFailure=QString("Acceptance worker error before mailbox C%1 errors=%2")
                                .arg(c+1).arg(qulonglong(errorDeltas[c]));
                        if(!(appliedCaptureMask & (1u<<c)) && (readDeltas[c] || publicationDeltas[c]) && mailboxFailure.isEmpty())
                            mailboxFailure=QString("Acceptance disabled worker active before mailbox C%1").arg(c+1);
                        if((appliedCaptureMask & (1u<<c)) &&
                           !(c!=resolutionCamera && (staleProducerMask & (1u<<c))))
                            targetFramesReady=targetFramesReady && latest.have[c] &&
                                latest.sourceGenerations[c]==displayGeneration &&
                                geometries[c].acceptsPublication(latest.geometries[c].generation,size_t(latest.c[c].size())) &&
                                captureAgeMs[c]>=0 && captureAgeMs[c]<=500 &&
                                captureTimes[c]>0 && captureNow-captureTimes[c]>=0 && captureNow-captureTimes[c]<=500;
                    }
                    bool acceptanceReady=reportResolution && producerEvidencePassed && targetFramesReady &&
                        recentProducerEvidence(mailboxMs) && recentSourceEvidence() && mailboxFailure.isEmpty();
                    if(mailboxFailure.isEmpty()) publishDisplay(std::move(display));
                    if(acceptanceReady) {
                        // Publication can wait for the mailbox mutex. Recheck after it
                        // completes so cached evidence cannot age past 500 ms into PASS.
                        const qint64 publishedMs=deliveryDeadline.elapsed();
                        const qint64 publishedCaptureNow=monotonicMs();
                        acceptanceReady=recentProducerEvidence(publishedMs) && recentSourceEvidence();
                        for(int c=0;c<CAM_COUNT;++c) {
                            for(int bank=0;bank<2;++bank)
                                tagAgeMs[c][bank]=advanceAge(publishedMs,lastTagAdvanceMs[c][bank]);
                            publicationAgeMs[c]=advanceAge(publishedMs,lastPublicationAdvanceMs[c]);
                            captureAgeMs[c]=latest.lastCapturedMs[c]>0 ? publishedCaptureNow-latest.lastCapturedMs[c] : -1;
                            acceptanceReady=acceptanceReady && errorDeltas[c]==0 && latest.errors[c]==auditErrors[c];
                            if((appliedCaptureMask & (1u<<c)) &&
                               !(c!=resolutionCamera && (staleProducerMask & (1u<<c))))
                                acceptanceReady=acceptanceReady && captureAgeMs[c]>=0 && captureAgeMs[c]<=500 &&
                                    publishedCaptureNow-captureTimes[c]>=0 && publishedCaptureNow-captureTimes[c]<=500;
                        }
                    }
                    if(acceptanceReady) {
                        // auditTags were read using the accepted geometries. The
                        // existing acceptanceLock protects latest counters here;
                        // do not acquire latest.mutex recursively or reuse the
                        // pre-switch view baseline at a different tag offset.
                        uint64_t acceptedReads[CAM_COUNT]={};
                        for(int c=0;c<CAM_COUNT;++c) acceptedReads[c]=dev.workerReadCalls(c);
                        viewEvidence.rearm(auditTags,acceptedReads,latest.camGen,latest.errors);
                        reportResolution=false; m_resolutionBusy=false;
                        pendingDelivery[resolutionCamera].pending=false;
                        const auto acceptedGeometry=geometries[resolutionCamera];
                        fprintf(stderr,"CAM134_ACCEPT_PASS transaction=%u camera=%d mode=%d sensor=%ux%u transport=%ux%u payload=%u stride=%u tag_offset=0x%08x banks=0x%08x/0x%08x geometry_generation=%llu mask=0x%02x fresh_banks=0x%03x mailbox_published=1\n",
                            acceptanceTransaction,resolutionCamera+1,int(m_cam1Hd.load()),m_cam1Hd?1280u:640u,m_cam1Hd?720u:480u,
                            acceptedGeometry.width,acceptedGeometry.height,acceptedGeometry.pixelBytes,acceptedGeometry.stride,
                            acceptedGeometry.tagOffset,acceptedGeometry.ping,acceptedGeometry.pong,(unsigned long long)acceptedGeometry.generation,auditMask,freshBanks);
                        fprintf(stderr,"CAM1_ACCEPT_PASS transaction=%u target=%s elapsed_ms=%lld observed_ms=%lld samples=%u sensor_regs=%02x/%02x/%02x/%02x sensor=%ux%u mode=%u dimensions=0x%08x payload=%u transfer=%u stride=%u mask=0x%02x idle=0x%02x disabled_idle=0x%02x fresh_banks=0x%03x source_expected=%u source_baseline_valid=%d source_baseline=%u source_baseline_ms=%lld source_seq=%u source_input=%u source_drop=%u source_stable=%d source_attempts=%u source_advances=%u source_elapsed_ms=%lld source_settled_ms=%lld source_age_ms=%lld mailbox_published=1\n",
                            acceptanceTransaction,m_cam1Hd?"720P":"480P",(long long)deliveryDeadline.elapsed(),(long long)lastAuditMs,auditSamples,
                            unsigned(sensorOutput[0]),unsigned(sensorOutput[1]),unsigned(sensorOutput[2]),unsigned(sensorOutput[3]),
                            (unsigned(sensorOutput[0])<<8)|sensorOutput[1],(unsigned(sensorOutput[2])<<8)|sensorOutput[3],
                            auditMode,auditDimensions,auditBytes,auditBytes+16,auditStride,auditMask,auditIdle,auditIdle&0x3e,freshBanks,
                            uint32_t(cam1::geometry(m_cam1Hd.load()).width)*uint32_t(cam1::geometry(m_cam1Hd.load()).height),
                            int(source.baselineValid),source.baseline,(long long)source.baselineMs,
                            source.seq,source.input,source.drop,int(source.stable),source.attempts,
                            source.advances,(long long)sourceClock.elapsed(),(long long)source.settledMs,
                            (long long)advanceAge(sourceClock.elapsed(),source.lastAdvanceMs));
                        for(int c=0;c<CAM_COUNT;++c)
                            fprintf(stderr,"CAM1_ACCEPT_PASS_CAMERA transaction=%u camera=%d prior_tags=%u/%u actual_tags=%u/%u worker_read_delta=%llu publication_delta=%llu error_delta=%llu tag_age_ms=%lld/%lld publication_age_ms=%lld capture_age_ms=%lld\n",
                                acceptanceTransaction,c+1,priorTags[c][0],priorTags[c][1],auditTags[c][0],auditTags[c][1],
                                (unsigned long long)readDeltas[c],(unsigned long long)publicationDeltas[c],(unsigned long long)errorDeltas[c],
                                (long long)tagAgeMs[c][0],(long long)tagAgeMs[c][1],(long long)publicationAgeMs[c],(long long)captureAgeMs[c]);
                        fflush(stderr);
                        acceptanceLock.unlock();
                        emit resolutionChanged(resolutionCamera,m_cam1Hd,true,QString("C%1 %2×%3").arg(resolutionCamera+1).arg(geometries[resolutionCamera].width).arg(geometries[resolutionCamera].height));
                    }
                }
            }
            if(!mailboxFailure.isEmpty()) { failAcceptance(mailboxFailure); continue; }
        }
        for (CameraWorker &w : workers)
            w.stop();
        for (CameraWorker &w : workers)
            w.wait();
        scheme2::admission().disarm();
        QElapsedTimer shutdownDrain;shutdownDrain.start();
        while(!scheme2::admission().idle() && shutdownDrain.elapsed()<10000) msleep(5);
        if(!scheme2::admission().idle()) {
            controller().holdSafe();resolutionFault=true;
            fprintf(stderr,"[runtime-shutdown] analytics drain failed; target held, external recovery required\n");
        }
        if(!resolutionFault) for(int c:{0}) if(cameraHd(c)) {
            resolutionCamera=c;
            std::string error;
            const bool restored=controller().apply(false,true,error);
            fprintf(stderr,"[runtime-shutdown] camera=%d exact_vga_restored=%d detail=%s\n",c+1,int(restored),error.c_str());
            if(!restored) {resolutionFault=true;break;}
        }
        if(!resolutionFault) {
            std::string error;
            const bool restored=pairController.restoreForShutdown(
                {{geometries[2].mode,geometries[3].mode}},error);
            fprintf(stderr,"[runtime-shutdown] pair_exact_default_restored=%d detail=%s\n",int(restored),error.c_str());
            if(!restored) resolutionFault=true;
        }
        if(captureMaskSupported && !resolutionFault) {
            uint32_t mask=0;
            const bool restored=dev.regWrite(0x20000880,0x3f) && dev.regRead(0x20000880,mask) && mask==0x3f;
            fprintf(stderr,"[view-shutdown] six-producer mask restored=%d\n",int(restored));
        }
    }

private:
    void updateHdmiActive() {
        const int overrideMode = m_hdmiOverride.load();
        m_hdmiActive = !m_native720.load() && m_mode.load() == CAM_COUNT &&
                       (overrideMode >= 0 ? overrideMode == 1 : m_hdmiPrefer.load() == 1);
    }
    void runVideo() {
        QString source;
        bool loop;
        {
            QMutexLocker lock(&m_configMutex);
            source = m_videoSource;
            loop = m_videoLoop;
        }
        bool validFps = false;
        const int requestedFps = qEnvironmentVariableIntValue("DETVIEW_VIDEO_FPS", &validFps);
        const int expectedFps = validFps && requestedFps >= 1 && requestedFps <= 60 ? requestedFps : 30;
        const qint64 minPeriodNs = (1000000000LL + expectedFps - 1) / expectedFps;
        const bool localFile = !source.startsWith("/dev/video") && !source.contains("://");
        QProcess decoder;
        QStringList args = {"-nostdin", "-loglevel", "error"};
        if (source.startsWith("/dev/video"))
            args += {"-f", "v4l2"};
        else if (localFile) {
            if (loop) args += {"-stream_loop", "-1"};
            args.append("-re");
        }
        args += {"-i", source, "-an", "-vf",
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
        QElapsedTimer presentationClock; presentationClock.start();
        qint64 nextFrameNs = 0;
        quint64 sourceFrameIndex = 0;
        qint64 lastCapturedMs = 0;
        bool suspended = false, signalFailed = false;
        const pid_t decoderPid = static_cast<pid_t>(decoder.processId());
        // Only this owning thread touches QProcess or signals its exact child PID.
        // While stopped, do not pump QProcess: its internal buffer must not grow.
        const auto pausePoint = [&]() -> bool {
            if (m_stop) return false;
            if (!m_paused) return true;
            if (!suspended && decoder.state() != QProcess::NotRunning) {
                if (::kill(decoderPid, SIGSTOP) == 0) suspended = true;
                else if (errno != ESRCH) {
                    signalFailed = true;
                    fprintf(stderr, "[video] decoder SIGSTOP failed: %s\n", strerror(errno));
                    return false;
                }
            }
            while (m_paused && !m_stop) msleep(10);
            if (m_stop) return false; // Cleanup resumes the child before killing it.
            if (suspended) {
                if (::kill(decoderPid, SIGCONT) != 0 && errno != ESRCH) {
                    signalFailed = true;
                    fprintf(stderr, "[video] decoder SIGCONT failed: %s\n", strerror(errno));
                    return false;
                }
                suspended = false;
            }
            nextFrameNs = 0;
            videoCaptureRate.reset(monotonicMs());
            audit.restart();
            return true;
        };
        fprintf(stderr, "[video] width=%d height=%d expected_fps=%d loop=%d local_file=%d source=%s\n",
                IMG_W, IMG_H, expectedFps, loop, localFile, qPrintable(source));
        while (!m_stop) {
            if (!pausePoint()) break;
            int generation;
            {
                QMutexLocker lock(&m_configMutex);
                generation = m_sourceGeneration.load();
            }
            while (frame.size() < bytes && !m_stop) {
                if (!pausePoint()) break;
                if (decoder.bytesAvailable() == 0) {
                    if (decoder.state() == QProcess::NotRunning) break;
                    if (!decoder.waitForReadyRead(20)) continue;
                }
                // waitForReadyRead may have overlapped a pause request.
                if (!pausePoint()) break;
                frame += decoder.read(bytes - frame.size());
            }
            if (m_stop || signalFailed || frame.size() != bytes) break;
            ++sourceFrameIndex;
            // Never catch up missed deadlines after slow decoding or a pause.
            // Retain this frame and pace output instead of dropping video frames.
            while (!m_stop && !signalFailed) {
                if (!pausePoint()) break;
                if (presentationClock.nsecsElapsed() >= nextFrameNs) break;
                msleep(1);
            }
            if (m_stop || signalFailed || !pausePoint()) break;
            QImage rgb(reinterpret_cast<const uchar *>(frame.constData()),
                       IMG_W, IMG_H, IMG_W * 3, QImage::Format_RGB888);
            // rgb 只是包装解码缓冲，跨线程投递前必须深拷贝
            const QImage owned = rgb.copy();
            // A pause between copying and committing retains this decoded frame.
            for (;;) {
                if (!pausePoint()) break;
                const qint64 capturedMs = monotonicMs();
                if (publishVideoFrame(owned, generation, capturedMs, 0, &videoCaptureRate)) {
                    lastCapturedMs = capturedMs;
                    break;
                }
                // A very short pause may have ended already; do not drop that
                // frame just because the commit observed its paused state.
                QMutexLocker lock(&m_configMutex);
                if (m_stop || generation != m_sourceGeneration.load()) break;
            }
            if (m_stop || signalFailed) break;
            nextFrameNs = presentationClock.nsecsElapsed() + minPeriodNs;
            if (audit.elapsed() >= 1000) {
                audit.restart();
                fprintf(stderr, "[video] width=%d height=%d expected_fps=%d capture_fps=%.1f source_index=%llu sequence=%llu captured_ms=%lld loop=%d eof=0\n",
                        IMG_W, IMG_H, expectedFps, videoCaptureRate.rate(monotonicMs()),
                        (unsigned long long)sourceFrameIndex, (unsigned long long)m_videoSequence,
                        (long long)lastCapturedMs, loop);
            }
            frame.clear();
        }
        if (suspended) ::kill(decoderPid, SIGCONT);
        const bool exited = decoder.state() == QProcess::NotRunning;
        const bool eof = !m_stop && !signalFailed && exited && frame.isEmpty() &&
                         decoder.exitStatus() == QProcess::NormalExit && decoder.exitCode() == 0;
        if (!exited) {
            decoder.kill();
            decoder.waitForFinished(2000);
        }
        fprintf(stderr, "[video] width=%d height=%d expected_fps=%d source_index=%llu sequence=%llu captured_ms=%lld loop=%d eof=%d stopped=%d exit_code=%d\n",
                IMG_W, IMG_H, expectedFps, (unsigned long long)sourceFrameIndex,
                (unsigned long long)m_videoSequence, (long long)lastCapturedMs, loop, eof,
                m_stop.load(), decoder.exitCode());
        if (m_stop) emit statusMsg("视频源已停止");
        else if (eof && !(localFile && loop)) emit statusMsg("视频源结束");
        else {
            const QByteArray errors = decoder.readAllStandardError().right(2048);
            fprintf(stderr, "[video] decoder error: %s\n", errors.constData());
            emit statusMsg("视频解码异常结束");
        }
    }
    bool publishVideoFrame(const QImage &owned, int generation, qint64 capturedMs, double fps,
                           tdm::FrameRate *captureRate = nullptr) {
        QMutexLocker lock(&m_configMutex);
        if (m_stop || m_paused || generation != m_sourceGeneration.load()) return false;
        if (captureRate) {
            captureRate->add(capturedMs);
            fps = captureRate->rate(capturedMs);
        }
        // One identity and timestamp for display and inference, committed against
        // the same configuration. Sequence counters survive pause and switches.
        m_videoSequence = m_frameSequence.fetch_add(1) + 1;
        DisplayFrame display{owned, generation, 1, 0, 1, fps, {}, true};
        display.videoSequence = m_videoSequence;
        display.cameraSequences[0] = m_videoSequence;
        display.capturedMs[0] = display.rawCapturedMs[0] = capturedMs;
        display.cameraGenerations[0] = generation;
        publishDisplay(std::move(display));
        if (m_visionSink) {
            VisionFrame packet;
            packet.image = owned;
            packet.frameId = m_videoSequence;
            packet.sourceGeneration = generation;
            packet.capturedMs = capturedMs;
            m_visionSink(packet);
        }
        return true;
    }
    void publishDisplay(DisplayFrame frame) {
        frame.publishedMs = monotonicMs();
        bool notify = false;
        {
            QMutexLocker lock(&m_displayMutex);
            if(!frame.video) {
                for(int c=0;c<CAM_COUNT;++c) {
                    const auto& geometry=frame.geometries[c];
                    if(!geometry.valid() || geometry.generation<m_displayGeometryGenerations[c] ||
                       (geometry.generation==m_displayGeometryGenerations[c] && m_displayGeometries[c].valid() && geometry.mode!=m_displayGeometries[c].mode) ||
                       (!frame.cameraPixels[c].isEmpty() && !geometry.acceptsPublication(geometry.generation,size_t(frame.cameraPixels[c].size())))) return;
                }
                for(int c=0;c<CAM_COUNT;++c) {
                    m_displayGeometryGenerations[c]=frame.geometries[c].generation;
                    m_displayGeometries[c]=frame.geometries[c];
                }
            }
            if (frame.generation != m_lastDisplayGeneration) {
                frame.changedMask = frame.video ? 1 : 0x3F;
                m_lastDisplayGeneration = frame.generation;
            }
            if (m_displayPending && m_latestDisplay.generation == frame.generation)
                frame.changedMask |= m_latestDisplay.changedMask;
            if (m_displayPending) frame.replacedBeforeTake = m_latestDisplay.replacedBeforeTake + 1;
            if (m_rawCaptureEnabled && !frame.video) m_rawSnapshot = frame;
            m_latestDisplay = std::move(frame);
            notify = !m_displayPending;
            m_displayPending = true;
        }
        if (notify) emit displayAvailable();
    }
    QMutex m_displayMutex;
    QMutex m_configMutex;
    DisplayFrame m_latestDisplay;
    DisplayFrame m_rawSnapshot;
    std::array<uint64_t,CAM_COUNT> m_displayGeometryGenerations{};
    std::array<runtime_camera::Geometry,CAM_COUNT> m_displayGeometries{};
    std::atomic<bool> m_rawCaptureEnabled{false};
    bool m_displayPending = false;
    int m_lastDisplayGeneration = -1;
    quint64 m_videoSequence = 0;
    std::atomic<bool> m_stop{false};
    std::atomic<bool> m_cam1Hd{false}; // Current serialized target transaction; mode ownership is m_hdModes.
    std::atomic<unsigned> m_hdModes{0};
    std::atomic<int> m_pairRequest{-1};
    std::atomic<bool> m_pairOwnsC34{false};
    std::atomic<int> m_resolutionRequest{-1};
    std::atomic<int> m_c5Request{-1};
    std::atomic<qint64> m_opticalCaptureMs[2]{{0},{0}};
    std::atomic<bool> m_c5Capable{false};
    std::atomic<bool> m_resolutionBusy{false};
    std::atomic<bool> m_runtimeHoldRequest{false};
    std::atomic<int> m_mode{CAM_COUNT};
    std::atomic<bool> m_native720{false};
    std::atomic<quint64> m_overviewReadyRequest{0};
    std::atomic<int> m_selectedCamera{0};
    std::atomic<int> m_sourceGeneration{0};
    std::atomic<quint64> m_frameSequence{0};
    std::atomic<int> m_hdmiPrefer{2};   // 0=off 1=on 2=auto（--prefer-hdmifull）
    std::atomic<int> m_hdmiOverride{-1}; // F 键手动覆盖：-1 无 1 满屏 0 六路
    std::atomic<bool> m_hdmiActive{false};
    VisionOptions m_options;
    std::function<void(const VisionFrame&)> m_visionSink;
    QString m_videoSource;
    bool m_videoLoop = false;
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

    static bool selfTestTrafficlight() {
        InferenceThread t;
        t.m_nc = 16; t.m_trafficlight = true; t.m_geometry.height = 480;
        t.m_conf.store(0.65f);
        const int heights[] = {60, 30, 15}, widths[] = {80, 40, 20};
        std::vector<std::vector<float>> buffers(6);
        std::vector<rknn_tensor_attr> attrs(6);
        std::vector<rknn_output> outs(6);
        for (int i = 0; i < 6; ++i) {
            const int s = i % 3, c = i < 3 ? 64 : 16;
            buffers[i].assign(c * heights[s] * widths[s], -10.0f);
            attrs[i].index = i; attrs[i].n_dims = 4; attrs[i].fmt = RKNN_TENSOR_NCHW;
            attrs[i].dims[0] = 1; attrs[i].dims[1] = c;
            attrs[i].dims[2] = heights[s]; attrs[i].dims[3] = widths[s];
            attrs[i].n_elems = buffers[i].size();
            outs[i].buf = buffers[i].data(); outs[i].want_float = 1;
        }
        // First class probe has only 0..1 values. The package still requires
        // sigmoid; detecting logits from this probe would be incorrect.
        std::fill(buffers[3].begin(), buffers[3].begin() + 60 * 80, 0.05f);
        const int distances[] = {1, 2, 3, 4};
        auto candidate = [&](int s, int x, int y, int cls, float logit) {
            const int plane = heights[s] * widths[s], off = y * widths[s] + x;
            for (int side = 0; side < 4; ++side)
                buffers[s][(side * 16 + distances[side]) * plane + off] = 10.0f;
            buffers[s + 3][cls * plane + off] = logit;
        };
        candidate(0, 20, 10, 15, 0.9f);
        candidate(0, 21, 10, 6, 1.2f); // Overlaps class 15: both must survive.
        candidate(0, 22, 10, 6, 1.0f); // Same-class overlap must be suppressed.
        candidate(1, 20, 10, 2, 1.1f);
        candidate(2, 18, 8, 14, 1.0f);
        // Deliberately shuffle heads: pairing must use shape, never index.
        std::swap(attrs[0], attrs[4]); std::swap(outs[0], outs[4]);
        int failures = 0;
        auto expect = [&](bool ok, const char *name) {
            fprintf(stderr, "%s %s\n", ok ? "[ok]" : "[FAIL]", name);
            failures += !ok;
        };
        expect(trafficlightNames().size() == 16 && trafficlightNames()[15] == "tln_lamp_off",
               "trafficlight metadata retains all 16 stable class IDs");
        expect(validTrafficlightOutputs(attrs), "shuffled raw DFL6 box64/cls16 shapes are accepted");
        auto bad = attrs;
        bad[0].dims[1] = 1;
        expect(!validTrafficlightOutputs(bad), "class count mismatch is rejected before inference");
        bad = attrs; bad[0].fmt = RKNN_TENSOR_NHWC;
        expect(!validTrafficlightOutputs(bad), "unsupported output layout fails closed");
        bad = attrs; bad[0] = bad[3];
        expect(!validTrafficlightOutputs(bad), "duplicate head and missing scale are rejected");
        bad = attrs; bad[0].n_elems = 1;
        expect(!validTrafficlightOutputs(bad), "inconsistent output element count is rejected");
        QVector<Detection> dets = t.decode(outs, attrs);
        expect(dets.size() == 4, "production decoder preserves overlapping different classes and suppresses same class");
        auto findClass = [&](int cls) -> const Detection * {
            for (const auto &d : dets) if (d.cls == cls) return &d;
            return nullptr;
        };
        const Detection *off = findClass(15), *p4 = findClass(2), *p5 = findClass(14);
        expect(off && std::fabs(off->score - sigmoidf(0.9f)) < 1e-5f &&
               std::fabs(off->x1 - 156) < 0.01f && std::fabs(off->y1 - 68) < 0.01f &&
               std::fabs(off->x2 - 188) < 0.01f && std::fabs(off->y2 - 116) < 0.01f,
               "class 15 logits use sigmoid and regmax16 DFL at stride 8");
        expect(p4 && std::fabs(p4->x1 - 312) < 0.01f && std::fabs(p4->y1 - 136) < 0.01f &&
               p5 && std::fabs(p5->x1 - 560) < 0.01f && std::fabs(p5->y1 - 208) < 0.01f,
               "rectangular grids decode stride 16 and 32 without square-height scaling");
        tdm::restoreCanonicalDetections(dets, t.m_geometry);
        off = findClass(15);
        expect(off && std::fabs(off->y1 - 148) < 0.01f && std::fabs(off->y2 - 196) < 0.01f,
               "production decode result returns to canonical viewer space");
        std::vector<CandD> overlap = {{0.9f, 10, 20, 30, 40, 0},
                                      {0.8f, 10, 20, 30, 40, 1}, {0.7f, 10, 20, 30, 40, 1}};
        QVector<Detection> aware, legacy;
        auto legacyCands = overlap;
        nmsAppend(aware, overlap, true); nmsAppend(legacy, legacyCands);
        expect(aware.size() == 2 && legacy.size() == 1, "trafficlight NMS is class aware; legacy default remains class agnostic");
        // Candidate limiting must happen after NMS for trafficlight. A cluster
        // of duplicates must not consume the entire 300-candidate budget.
        for (auto &buffer : buffers) std::fill(buffer.begin(), buffer.end(), -10.0f);
        for (int y = 10; y < 25; ++y)
            for (int x = 5; x < 25; ++x) candidate(0, x, y, 6, 2.0f);
        candidate(0, 70, 50, 15, 1.0f);
        dets = t.decode(outs, attrs);
        expect(findClass(15) && dets.size() <= 300,
               "production decoder retains lower-score distinct detection after more than 300 candidates");
        fprintf(stderr, failures ? "TRAFFICLIGHT_DECODER_SELFTEST_FAIL\n" : "TRAFFICLIGHT_DECODER_SELFTEST_PASS\n");
        return failures == 0;
    }

    static bool selfTestMvp() {
        InferenceThread t;
        t.m_nc=5; t.m_mvpDetect=true; t.m_geometry.height=480; t.m_conf.store(0.65f);
        std::vector<std::vector<float>> buffers(10);
        std::vector<rknn_tensor_attr> attrs(10);
        std::vector<rknn_output> outs(10);
        const unsigned dims[10][3]={{64,60,80},{64,30,40},{64,15,20},{5,60,80},{5,30,40},{5,15,20},{64,24,8},{48,32,8},{2,24,8},{2,32,8}};
        for(int i=0;i<10;++i) {
            auto& a=attrs[i]; a.n_dims=4; a.fmt=RKNN_TENSOR_NCHW; a.dims[0]=1; a.n_elems=1;
            for(int d=0;d<3;++d) {a.dims[d+1]=dims[i][d];a.n_elems*=dims[i][d];}
            buffers[i].assign(a.n_elems,-10);
            outs[i].buf=buffers[i].data(); outs[i].want_float=1;
        }
        // The first class is entirely 0..1, defeating the old logits heuristic.
        std::fill(buffers[3].begin(),buffers[3].begin()+60*80,0.05f);
        auto candidate=[&](int x,int cls,float score) {
            const int plane=60*80,off=10*80+x;
            const int distance[4]={1,2,3,4};
            for(int side=0;side<4;++side) buffers[0][(side*16+distance[side])*plane+off]=10;
            buffers[3][cls*plane+off]=score;
        };
        candidate(20,4,0.9f); candidate(21,1,1.2f); candidate(22,1,1.0f);
        // Lane rank4 tensors would be wrongly paired by generic spatial DFL search.
        std::fill(buffers[6].begin(),buffers[6].end(),20);
        std::fill(buffers[8].begin(),buffers[8].end(),20);
        int failures=0;
        auto expect=[&](bool ok,const char* text) { if(!ok) { ++failures;fprintf(stderr,"[mvp-selftest] FAIL %s\n",text); } };
        expect(mvpNames()==QStringList({"person","vehicle","zebra","traffic_light","traffic_sign"}),"stable coarse five names");
        expect(mvp::validOutputs(attrs,mvp::Kind::Shared),"box-first runtime shapes accepted");
        auto dets=t.decode(outs,attrs);
        expect(dets.size()==2,"raw10 ignores lane heads; class-aware NMS retains two classes");
        for(const auto& d:dets) if(d.cls==4) {
            expect(std::fabs(d.score-sigmoidf(0.9f))<1e-5f && std::fabs(d.x1-156)<0.01f &&
                   std::fabs(d.y1-68)<0.01f && std::fabs(d.y2-116)<0.01f,"raw sigmoid/DFL exact coordinates");
        }
        tdm::restoreCanonicalDetections(dets,t.m_geometry);
        for(const auto& d:dets) if(d.cls==4) expect(std::fabs(d.y1-148)<0.01f,"DFL canonical +80");
        // Shared compiler's interleaved detector order must give identical values.
        const int order[6]={0,3,1,4,2,5};
        auto reorderedAttrs=attrs; auto reorderedOuts=outs;
        for(int i=0;i<6;++i) {reorderedAttrs[i]=attrs[order[i]];reorderedOuts[i]=outs[order[i]];}
        expect(mvp::validOutputs(reorderedAttrs,mvp::Kind::Shared),"interleaved shared shapes accepted");
        const auto shared=t.decode(reorderedOuts,reorderedAttrs);
        expect(shared.size()==2,"interleaved shared decoder retains detections");
        const auto raw6=t.decode(std::vector<rknn_output>(outs.begin(),outs.begin()+6),
                                 std::vector<rknn_tensor_attr>(attrs.begin(),attrs.begin()+6));
        expect(raw6.size()==shared.size(),"raw6 and raw10 detection counts agree");
        fprintf(stderr,failures?"MVP_DFL_SELFTEST_FAIL\n":"MVP_DFL_SELFTEST_PASS\n");
        return failures==0;
    }

    static bool selfTestRound1() {
        InferenceThread t;
        t.m_nc=5; t.m_mvpDetect=true; t.m_geometry.height=480;
        t.m_mvpPolicy.enabled=true; t.m_conf.store(.95f); // UI uniform value must be ignored.
        const unsigned dims[6][3]={{64,60,80},{64,30,40},{64,15,20},{5,60,80},{5,30,40},{5,15,20}};
        std::vector<std::vector<float>> buffers(6);
        std::vector<rknn_tensor_attr> attrs(6);
        std::vector<rknn_output> outs(6);
        for(int i=0;i<6;++i) {
            auto& a=attrs[i]; a.n_dims=4; a.fmt=RKNN_TENSOR_NCHW; a.dims[0]=1; a.n_elems=1;
            for(int d=0;d<3;++d) {a.dims[d+1]=dims[i][d];a.n_elems*=dims[i][d];}
            buffers[i].assign(a.n_elems,-20);
            outs[i].buf=buffers[i].data(); outs[i].want_float=1;
        }
        auto clear=[&]() {for(auto& b:buffers) std::fill(b.begin(),b.end(),-20);};
        auto candidate=[&](int x,int y,int cls,float probability,int distance=1) {
            const int plane=60*80,off=y*80+x;
            for(int side=0;side<4;++side) buffers[0][(side*16+distance)*plane+off]=20;
            buffers[3][cls*plane+off]=std::log(probability/(1-probability));
        };
        int failures=0;
        auto expect=[&](bool ok,const char* message) {
            fprintf(stderr,"[mvp-round1-selftest] %s %s\n",ok?"OK":"FAIL",message); failures+=!ok;
        };
        candidate(10,10,0,.4f); candidate(10,10,1,.39f); // One argmax, never multilabel.
        candidate(20,10,1,.4f); candidate(30,10,2,.3f);
        candidate(40,10,3,.36f); candidate(50,10,4,.41f);
        auto dets=t.decode(outs,attrs);
        expect(dets.size()==4 && std::none_of(dets.begin(),dets.end(),[](const auto& d){return d.cls==1;}),
               ".4 person passes, .4 vehicle fails, .3 zebra passes; all five thresholds and full argmax");
        t.m_mvpPolicy.enabled=false; t.m_conf.store(.25f);
        dets=t.decode(outs,attrs);
        expect(dets.size()==5,"old MVP retains uniform .25 policy");
        clear(); candidate(10,10,2,.0012f); candidate(20,10,2,.0009f);
        dets.clear(); t.tryDecodeDfl(outs,attrs,mvp::Round1Policy::candidateFloor,dets);
        expect(dets.size()==1 && std::fabs(dets[0].score-.0012f)<1e-7f,
               "production raw candidate stage retains .0012 and rejects .0009");
        t.m_mvpPolicy.enabled=true;
        dets=t.decode(outs,attrs);
        expect(dets.empty(),"rare low-score candidate filtered only after NMS");
        std::vector<CandD> boxes={{.8f,0,0,10,10,0},{.7f,2.5f,0,12.5f,10,0},{.6f,0,0,10,10,1}};
        auto oldBoxes=boxes; QVector<Detection> r1,old;
        nmsAppend(r1,boxes,true,mvp::Round1Policy::nmsIou); nmsAppend(old,oldBoxes,true);
        expect(r1.size()==3 && old.size()==2,"R1 IoU .7 preserves .6 overlap and different classes; legacy IoU .45");
        clear();
        for(int y=0;y<15;++y) for(int x=0;x<20;++x) candidate(x*3,y*3,1,.4f);
        candidate(75,55,2,.3f);
        dets=t.decode(outs,attrs);
        expect(dets.empty(),"global NMS top300 occurs BEFORE class thresholds (no replenishment)");
        clear();
        for(int y=10;y<25;++y) for(int x=5;x<30;++x) candidate(x,y,1,.8f,15);
        candidate(75,55,2,.3f);
        dets=t.decode(outs,attrs);
        expect(std::any_of(dets.begin(),dets.end(),[](const auto& d){return d.cls==2;}) && dets.size()<=300,
               "more than 300 overlapping candidates never truncate before NMS");
        expect(!mvp::Round1Policy::matchesSha(mvp::Round1Policy::rknnSha,std::string(64,'0')) &&
               !mvp::Round1Policy::matchesSha(std::string(64,'0'),std::string(64,'0')) &&
               mvp::Round1Policy::matchesSha(mvp::Round1Policy::rknnSha,mvp::Round1Policy::rknnSha),
               "SHA binding rejects wrong bytes and wrong manifest identity");
        fprintf(stderr,failures?"MVP_ROUND1_DECODER_SELFTEST_FAIL\n":"MVP_ROUND1_DECODER_SELFTEST_PASS\n");
        return failures==0;
    }

    void submit(const QImage &img, int sourceGeneration = 0, quint64 frameId = 0,
                std::shared_ptr<scheme2::Input> fpgaInput = {}, tdm::InferAge age = {}) {
        QMutexLocker lock(&m_mutex);
        m_pending = img;
        if (m_pendingFpga) m_pendingFpga->complete(); // superseded before synchronous run starts
        m_pendingFpga = std::move(fpgaInput);
        m_pendingGeneration = sourceGeneration;
        m_pendingFrameId = frameId;
        m_pendingAge = age;
        m_hasPending = true;
        VisionEvidence::instance().event("submitted", age);
        m_cond.wakeOne();
    }
    void setModel(const ModelInfo &info) {
        QMutexLocker lock(&m_mutex);
        if (scheme2::enabled()) scheme2::admission().publish({0, {}, ++m_modelRevision});
        m_selection = {info};
        m_manualFormat = info.xyxy;
        m_modelChanged = true;
        m_cond.wakeOne();
    }
    void setModels(const QVector<ModelInfo> &models) {
        QMutexLocker lock(&m_mutex);
        if (scheme2::enabled()) scheme2::admission().publish({0, {}, ++m_modelRevision});
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
    // Emitted from the inference worker and consumed directly by VisionPipeline;
    // the GUI receives the presentation signals separately.
    void observationReady(QString modelPath, int sourceGeneration, quint64 frameId,
                          QVector<Detection> dets, double inferMs, bool laneOnly);
    void laneMaskReady(QImage mask, int sourceGeneration, quint64 frameId, double inferFps, double inferMs);
    void mvpResultReady(QString modelPath, QImage points, int sourceGeneration, quint64 frameId,
                        QVector<Detection> dets, int pointCount, double inferFps, double inferMs);
    void inferenceFailed(int sourceGeneration, quint64 frameId);
    void modelLoaded(QString path, bool ok, QString info);

protected:
    void run() override {
        struct CachedModel {
            ModelInfo info;
            QByteArray bytes;
            rknn_context context = 0;
            uint32_t outputs = 0;
            tdm::InferenceGeometry geometry;
            std::vector<rknn_tensor_attr> outputAttrs;
            rknn_context sharedContext = 0;
            rknn_tensor_attr inputAttr{};
            rknn_tensor_mem* inputMem = nullptr;
            std::shared_ptr<void> backing;
            uint64_t revision = 0;
        };
        QVector<CachedModel> cache;
        int next = 0;
        /* 诊断（DET_BENCH）：每秒统计“等帧时间”与“单次运行时间”，判断推理线程是否被饿着 */
        const bool diag = qEnvironmentVariableIsSet("DET_BENCH") && !scheme2::verify();
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
            const uint64_t revision = m_modelRevision;
            if (reload)
                selected = m_selection;
            QImage frame;
            std::shared_ptr<scheme2::Input> fpgaInput;
            int sourceGeneration = m_pendingGeneration;
            const quint64 frameId = m_pendingFrameId;
            m_runningAge = m_pendingAge;
            if (m_hasPending) {
                frame = m_pending;
                fpgaInput = std::move(m_pendingFpga);
                m_hasPending = false;
            }
            m_modelChanged = false;
            lock.unlock();
            if (diag && !frame.isNull())
                diagWaitMs += QDateTime::currentMSecsSinceEpoch() - waitStart;

            if (reload) {
                scheme2::admission().publish({0, {}, revision});
                for (CachedModel &old : cache) {
                    if (old.inputMem) rknn_destroy_mem(old.sharedContext, old.inputMem);
                    if (old.sharedContext) rknn_destroy(old.sharedContext);
                    rknn_destroy(old.context);
                }
                cache.clear();
                next = 0;
                for (const ModelInfo &info : selected) {
                    CachedModel item;
                    item.info = info;
                    item.revision = revision;
                    QFile file(info.path);
                    if (!file.open(QIODevice::ReadOnly)) {
                        emit modelLoaded(info.path, false, "open failed");
                        continue;
                    }
                    item.bytes = file.readAll();
                    QString deploymentReason;
                    // Re-read metadata and hash the exact bytes passed to rknn_init.
                    if (!readRound1Deployment(item.info,deploymentReason) ||
                        !verifyRound1Bytes(item.info,item.bytes,deploymentReason)) {
                        emit modelLoaded(info.path,false,deploymentReason);
                        continue;
                    }
                    const int ret = rknn_init(&item.context, item.bytes.data(),
                                              (uint32_t)item.bytes.size(), 0, nullptr);
                    if (ret != 0) {
                        emit modelLoaded(info.path, false, QString("rknn_init %1").arg(ret));
                        continue;
                    }
                    rknn_input_output_num ioNum{};
                    if (rknn_query(item.context, RKNN_QUERY_IN_OUT_NUM, &ioNum, sizeof(ioNum)) != 0 ||
                        ioNum.n_input != 1 || ioNum.n_output == 0 || (info.lane && ioNum.n_output != 1)) {
                        rknn_destroy(item.context);
                        emit modelLoaded(info.path, false, "unsupported input/output count");
                        continue;
                    }
                    rknn_tensor_attr inputAttr{};
                    if (rknn_query(item.context, RKNN_QUERY_INPUT_ATTR, &inputAttr, sizeof(inputAttr)) != 0 ||
                        !tdm::queryInputGeometry(inputAttr, item.geometry) ||
                        (info.lane && item.geometry.height != MODEL_H) ||
                        ((info.trafficlight || info.mvpDetect || info.independentUfld) && item.geometry.height != 480)) {
                        rknn_destroy(item.context);
                        emit modelLoaded(info.path, false, "unsupported input: require 1x3x640x640 or 1x3x480x640 (trafficlight: 480 high)");
                        continue;
                    }
                    logTensor(info.path, "input", inputAttr);
                    item.inputAttr = inputAttr;
                    bool attrsOk = true;
                    item.outputAttrs.resize(ioNum.n_output);
                    for (uint32_t i = 0; i < ioNum.n_output; ++i) {
                        rknn_tensor_attr &attr = item.outputAttrs[i];
                        attr.index = i;
                        if (rknn_query(item.context, RKNN_QUERY_OUTPUT_ATTR, &attr, sizeof(attr)) != 0) {
                            attrsOk = false;
                            break;
                        }
                        logTensor(info.path, "output", attr);
                    }
                    if (!attrsOk || (info.trafficlight && !validTrafficlightOutputs(item.outputAttrs))) {
                        rknn_destroy(item.context);
                        emit modelLoaded(info.path, false, "unsupported outputs: trafficlight requires box64/cls16 at 60x80,30x40,15x20 NCHW");
                        continue;
                    }
                    if ((info.mvpDetect || info.independentUfld) &&
                        !mvp::validOutputs(item.outputAttrs, info.independentUfld ? mvp::Kind::Independent :
                            (info.sharedUfld ? mvp::Kind::Shared :
                             (info.spatialLane ? mvp::Kind::Spatial : mvp::Kind::Detection)))) {
                        rknn_destroy(item.context);
                        emit modelLoaded(info.path,false,"MVP output contract mismatch: require exact NCHW raw6/raw10/raw8/raw4 shapes");
                        continue;
                    }
                    item.outputs = ioNum.n_output;
                    if (scheme2::enabled()) {
                        bool supported = rknn_init(&item.sharedContext, item.bytes.data(), uint32_t(item.bytes.size()),
                            RKNN_FLAG_DISABLE_FLUSH_INPUT_MEM_CACHE, nullptr) == 0;
                        rknn_input_output_num sharedIo{};
                        rknn_tensor_attr sharedInput{};
                        supported = supported && rknn_query(item.sharedContext, RKNN_QUERY_IN_OUT_NUM, &sharedIo, sizeof(sharedIo)) == 0 &&
                            sharedIo.n_input == 1 && sharedIo.n_output == item.outputs &&
                            rknn_query(item.sharedContext, RKNN_QUERY_INPUT_ATTR, &sharedInput, sizeof(sharedInput)) == 0 &&
                            scheme2::sameTensor(item.inputAttr, sharedInput) && scheme2::packedInput(sharedInput, item.geometry.height);
                        for (uint32_t i = 0; supported && i < item.outputs; ++i) {
                            rknn_tensor_attr attr{}; attr.index = i;
                            supported = rknn_query(item.sharedContext, RKNN_QUERY_OUTPUT_ATTR, &attr, sizeof(attr)) == 0 &&
                                scheme2::sameTensor(item.outputAttrs[i], attr);
                        }
                        if (!supported) {
                            if (item.sharedContext) rknn_destroy(item.sharedContext);
                            item.sharedContext = 0;
                            fprintf(stderr, "[scheme2] CPU_ROUTE model=%s reason=coherent-contract-unsupported\n", qPrintable(info.path));
                        }
                    }
                    cache.append(std::move(item));
                    m_completed.remove(info.path);
                    emit modelLoaded(info.path, true, QString("640x%1 RGB, %2 outputs cached")
                                     .arg(cache.last().geometry.height).arg(ioNum.n_output));
                }
            }
            auto selectionFor = [&](int index) {
                const auto& model = cache[index];
                return scheme2::Selection{model.sharedContext ? model.geometry.height : 0,
                    model.info.path.toStdString(), model.revision};
            };
            if (reload && !cache.isEmpty()) scheme2::admission().publish(selectionFor(next));
            if (!frame.isNull() && !cache.isEmpty()) {
                CachedModel &item = cache[next];
                m_ctx = item.context;
                m_boundInput = false;
                if (fpgaInput) {
                    if (fpgaInput->height != item.geometry.height || fpgaInput->sourceGeneration != sourceGeneration ||
                        fpgaInput->selection.model != item.info.path.toStdString() || fpgaInput->selection.revision != item.revision ||
                        fpgaInput->selection.revision != m_modelRevision.load() ||
                        !item.sharedContext) {
                        fprintf(stderr, "[scheme2] rejecting model/source change during acquisition\n");
                        fpgaInput->complete();
                        emit inferenceFailed(sourceGeneration, frameId);
                        continue;
                    }
                    // Keep the conventional context for video/HDMI. The coherent
                    // context uses the exact same model and output decoder contract.
                    if (!item.inputMem) {
                        item.backing = fpgaInput->backing;
                        item.inputMem = rknn_create_mem_from_fd(item.sharedContext, fpgaInput->fd,
                            fpgaInput->base, scheme2::bytes(fpgaInput->height), scheme2::Offset);
                        if (!item.inputMem) {
                            rknn_destroy(item.sharedContext); item.sharedContext = 0;
                            scheme2::admission().publish({0, item.info.path.toStdString(), item.revision});
                            fpgaInput->complete(); emit inferenceFailed(sourceGeneration, frameId); continue;
                        }
                        auto attr = scheme2::userInput(item.inputAttr);
                        if (rknn_set_io_mem(item.sharedContext, item.inputMem, &attr) != 0) {
                            rknn_destroy_mem(item.sharedContext, item.inputMem); item.inputMem = nullptr;
                            rknn_destroy(item.sharedContext); item.sharedContext = 0;
                            scheme2::admission().publish({0, item.info.path.toStdString(), item.revision});
                            fpgaInput->complete(); emit inferenceFailed(sourceGeneration, frameId); continue;
                        }
                    }
                    if (item.backing != fpgaInput->backing) scheme2Quarantine("DMA-BUF generation changed");
                    m_ctx = item.sharedContext;
                    m_boundInput = true;
                }
                m_nOutput = item.outputs;
                m_nc = item.info.nc;
                m_xyxy = cache.size() == 1 ? m_manualFormat.load() : item.info.xyxy;
                m_lane = item.info.lane;
                m_trafficlight = item.info.trafficlight;
                 m_mvpDetect = item.info.mvpDetect;
                m_spatialLane = item.info.spatialLane;
                m_mvpPolicy = item.info.round1Policy;
                m_sharedUfld = item.info.sharedUfld;
                m_independentUfld = item.info.independentUfld;
                m_laneContract = item.info.laneContract;
                m_geometry = item.geometry;
                m_outputAttrs = &item.outputAttrs;
                m_classNames = item.info.classes;
                const qint64 runStart = diag ? QDateTime::currentMSecsSinceEpoch() : 0;
                recordMetric(sourceGeneration, item.info.path, 0);
                m_verifyOutputs.clear();
                if (fpgaInput && scheme2::verify()) {
                    rknn_input reference{};
                    reference.buf = fpgaInput->goldenRgb.data();
                    reference.size = uint32_t(fpgaInput->goldenRgb.size());
                    reference.type = RKNN_TENSOR_UINT8; reference.fmt = RKNN_TENSOR_NHWC;
                    if (reference.size != uint32_t(item.geometry.rgbBytes()) ||
                        rknn_inputs_set(item.context, 1, &reference) != 0 || rknn_run(item.context, nullptr) != 0)
                        scheme2Quarantine("CPU golden reference run failed");
                    m_verifyOutputs = verifyNativeOutputs(item.context, item.outputAttrs);
                    m_verifyCamera = fpgaInput->camera;
                    m_verifyTag = fpgaInput->tag;
                }
                if (fpgaInput) {
                    QMutexLocker admissionLock(&m_mutex);
                    // Setters cannot publish a new model revision between this
                    // final acceptance and synchronous F2H+BEGIN consumption.
                    if (fpgaInput->selection.revision != m_modelRevision.load() || m_stop ||
                        (m_runningAge.capturedMs >= 0 && (monotonicMs() < m_runningAge.capturedMs ||
                         monotonicMs() - m_runningAge.capturedMs > 1000))) {
                        fpgaInput->complete(); emit inferenceFailed(sourceGeneration, frameId); continue;
                    }
                    fpgaInput->consume(); fpgaInput->start();
                }
                if (!runOnce(frame, item.info.path, sourceGeneration, frameId)) {
                    if (fpgaInput) scheme2Quarantine("bound RKNN operation failed; cannot assert consumer completion");
                    recordMetric(sourceGeneration, item.info.path, 2);
                    emit inferenceFailed(sourceGeneration, frameId);
                }
                next = (next + 1) % cache.size();
                if (fpgaInput) { fpgaInput->nextSelection = selectionFor(next); fpgaInput->complete(); }
                else scheme2::admission().publish(selectionFor(next));
                if (diag) {
                    diagRunMs += QDateTime::currentMSecsSinceEpoch() - runStart;
                    ++diagRuns;
                }
            } else if (!frame.isNull()) {
                if (fpgaInput) fpgaInput->complete();
                emit inferenceFailed(sourceGeneration, frameId);
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
        m_pendingFpga.reset();
        scheme2::admission().publish({0, {}, m_modelRevision});
        for (CachedModel &item : cache) {
            if (item.inputMem) rknn_destroy_mem(item.sharedContext, item.inputMem);
            if (item.sharedContext) rknn_destroy(item.sharedContext);
            rknn_destroy(item.context);
        }
        m_ctx = 0;
    }

private:
    static void logTensor(const QString &path, const char *kind, const rknn_tensor_attr &attr) {
        QStringList dims;
        for (uint32_t i = 0; i < attr.n_dims; ++i) dims << QString::number(attr.dims[i]);
        fprintf(stderr, "[model-tensor] model=%s %s[%u] shape=[%s] fmt=%s type=%s quant=%d zp=%d scale=%.9g elems=%u bytes=%u\n",
                qPrintable(path), kind, attr.index, qPrintable(dims.join(',')),
                get_format_string(attr.fmt), get_type_string(attr.type), attr.qnt_type,
                attr.zp, attr.scale, attr.n_elems, attr.size);
    }

    static bool validTrafficlightOutputs(const std::vector<rknn_tensor_attr> &attrs) {
        if (attrs.size() != 6) return false;
        int seen[3][2] = {};
        const int heights[] = {60, 30, 15}, widths[] = {80, 40, 20};
        for (const auto &attr : attrs) {
            if (attr.n_dims != 4 || attr.dims[0] != 1 || attr.fmt != RKNN_TENSOR_NCHW) return false;
            const int head = attr.dims[1] == 64 ? 0 : (attr.dims[1] == 16 ? 1 : -1);
            if (head < 0) return false;
            int scale = -1;
            for (int s = 0; s < 3; ++s)
                if (attr.dims[2] == (uint32_t)heights[s] && attr.dims[3] == (uint32_t)widths[s]) scale = s;
            if (scale < 0 || ++seen[scale][head] != 1 ||
                attr.n_elems != attr.dims[1] * attr.dims[2] * attr.dims[3]) return false;
        }
        for (const auto &scale : seen) if (scale[0] != 1 || scale[1] != 1) return false;
        return true;
    }

    static std::vector<std::vector<uint8_t>> verifyNativeOutputs(rknn_context context,
                                                               const std::vector<rknn_tensor_attr>& attrs) {
        std::vector<rknn_output> outputs(attrs.size());
        for (size_t i = 0; i < outputs.size(); ++i) outputs[i].index = uint32_t(i);
        // want_float=0: exact allocated native bytes, no float tolerance.
        if (rknn_outputs_get(context, uint32_t(outputs.size()), outputs.data(), nullptr) != 0)
            scheme2Quarantine("native parity outputs_get failed");
        std::vector<std::vector<uint8_t>> result;
        for (size_t i = 0; i < outputs.size(); ++i) {
            if (!outputs[i].buf || !outputs[i].size || outputs[i].size != attrs[i].size) {
                fprintf(stderr, "[scheme2-verify-output] UNSUPPORTED output=%zu returned_bytes=%u attr_bytes=%u\n",
                        i, outputs[i].size, attrs[i].size);
                scheme2Quarantine("native packed output size unsupported; parity not passed");
            }
            const auto* data = static_cast<const uint8_t*>(outputs[i].buf);
            result.emplace_back(data, data + outputs[i].size);
        }
        if (rknn_outputs_release(context, uint32_t(outputs.size()), outputs.data()) != 0)
            scheme2Quarantine("native parity outputs_release failed");
        return result;
    }

    double recordMetric(int generation, const QString& model, int event) {
        if (scheme2::verify()) return 0; // parity overhead is never a performance sample
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
    bool runOnce(const QImage &src, const QString &modelPath, int sourceGeneration, quint64 frameId) {
        const int inputBytes = m_geometry.rgbBytes();
        /* DET_BENCH 分段计时：定位应用内比纯 NPU 慢在哪一段
           prep=输入拷贝, set=rknn_inputs_set, run=NPU, get=输出反量化,
           query=输出属性查询, decode=DFL+NMS, release=释放 */
        const bool bench = qEnvironmentVariableIsSet("DET_BENCH") && !scheme2::verify();
        const bool int8In = !m_trafficlight && !m_mvpDetect && !m_independentUfld && qEnvironmentVariableIsSet("DET_INT8_IN");
        QElapsedTimer lap;
        double tPrep = 0, tSet = 0, tRun = 0, tGet = 0, tQuery = 0, tDecode = 0, tRel = 0;
        if (bench)
            lap.start();
        // The square producer contract stays unchanged. Only the network feed
        // is cropped; restoreCanonicalDetections reverses this after decode.
        const QImage rgb = m_boundInput ? QImage() : tdm::networkRgbFrame(src, m_geometry);
        if (!m_boundInput && rgb.isNull()) return false;
        if (!m_boundInput && m_lastDumpedGeneration != sourceGeneration && !qEnvironmentVariable("DETVIEW_CAM34_EVIDENCE_DIR").isEmpty()) {
            const QString proofDir=qEnvironmentVariable("DETVIEW_CAM34_EVIDENCE_DIR");
            QDir().mkpath(proofDir);
            rgb.save(proofDir+"/actual_rknn_input.png");
            fprintf(stderr,"[cam34-network] frame=%llu generation=%d input=%dx%d rgb_bytes=%d source=shared_C3_C4\n",(unsigned long long)frameId,sourceGeneration,m_geometry.width,m_geometry.height,m_geometry.rgbBytes());
            m_lastDumpedGeneration=sourceGeneration;
        }
        const QImage *feed = nullptr;
        if (m_boundInput) {
            // FPGA already produced packed RGB888 in the imported RX slot.
        } else if (!int8In && rgb.bytesPerLine() == m_geometry.width * 3) {
            feed = &rgb;
        } else {
            m_input.resize(inputBytes);
            for (int y = 0; y < m_geometry.height; ++y)
                memcpy(m_input.data() + y * m_geometry.width * 3,
                       rgb.constScanLine(y), m_geometry.width * 3);
        }

        /* 实测：输入按 INT8 直传反而慢得多（inputs_set 1.4ms → 16.9ms，整体 +58%），
           驱动对 UINT8 输入是快路径；默认走 UINT8，DET_INT8_IN=1 仅用于对照。 */
        if (int8In && !m_boundInput) {
            uint8_t *p = reinterpret_cast<uint8_t *>(m_input.data());
            for (int i = 0; i < inputBytes; ++i)
                p[i] = (uint8_t)(p[i] - 128);
        }
        if (bench) markLap(lap, tPrep);
        rknn_input input;
        memset(&input, 0, sizeof(input));
        input.index = 0;
        input.buf = feed ? (void *)feed->constBits() : (void *)m_input.constData();
        input.size = (uint32_t)inputBytes;
        input.type = int8In ? RKNN_TENSOR_INT8 : RKNN_TENSOR_UINT8;
        input.fmt = RKNN_TENSOR_NHWC;
        QElapsedTimer timer;
        timer.start();
        if (!m_boundInput && rknn_inputs_set(m_ctx, 1, &input) != 0)
            return false;
        if (bench) markLap(lap, tSet);
        tdm::inferAgeEvent("RKNN_start", m_runningAge);
        if (rknn_run(m_ctx, nullptr) != 0)
            return false;
        if (m_boundInput && scheme2::verify()) {
            const auto actual = verifyNativeOutputs(m_ctx, *m_outputAttrs);
            if (actual.size() != m_verifyOutputs.size()) scheme2Quarantine("native output count mismatch");
            size_t total = 0;
            for (size_t i = 0; i < actual.size(); ++i) {
                if (actual[i].size() != m_verifyOutputs[i].size()) scheme2Quarantine("native output byte size mismatch");
                const size_t bad = scheme2::mismatch(actual[i].data(), m_verifyOutputs[i].data(), actual[i].size());
                if (bad != actual[i].size()) {
                    fprintf(stderr, "[scheme2-verify-output] FAIL model=%s camera=%d tag=%u frame=%llu output=%zu byte=%zu expected=%u actual=%u\n",
                        qPrintable(modelPath), m_verifyCamera + 1, m_verifyTag, (unsigned long long)frameId,
                        i, bad, m_verifyOutputs[i][bad], actual[i][bad]);
                    scheme2Quarantine("exact native output parity failed");
                }
                total += actual[i].size();
            }
            const unsigned count = ++m_verifyCompleted;
            fprintf(stderr, "[scheme2-verify-output] PASS model=%s camera=%d tag=%u frame=%llu height=%d outputs=%zu bytes=%zu want_float=0 exact=1 count=%u performance_sample=0\n",
                qPrintable(modelPath), m_verifyCamera + 1, m_verifyTag, (unsigned long long)frameId,
                m_geometry.height, actual.size(), total, count);
            if (count == scheme2::verifyCount())
                fprintf(stderr, "[scheme2-verify] OUTPUT_COUNT_REACHED count=%u required=%u input_and_native_exact=1 performance_sample=0\n", count, scheme2::verifyCount());
            // A separate run supplies the unchanged want_float=1 decoder path.
            if (rknn_run(m_ctx, nullptr) != 0) scheme2Quarantine("decoder run after native parity failed");
        }
        if (bench) markLap(lap, tRun);
        std::vector<rknn_output> outs(m_nOutput);
        for (uint32_t i = 0; i < m_nOutput; i++) {
            memset(&outs[i], 0, sizeof(rknn_output));
            outs[i].index = i;
            outs[i].want_float = 1;
        }
        if (rknn_outputs_get(m_ctx, m_nOutput, outs.data(), nullptr) != 0)
            return false;
        if (bench) markLap(lap, tGet);
        const std::vector<rknn_tensor_attr> &attrs = *m_outputAttrs;
        if (m_mvpDetect || m_independentUfld) {
            for(size_t i=0;i<outs.size();++i) {
                if(!outs[i].buf || outs[i].size < attrs[i].n_elems*sizeof(float)) {
                    fprintf(stderr,"[mvp] invalid want_float output[%zu] buffer\n",i);
                    rknn_outputs_release(m_ctx,m_nOutput,outs.data());
                    return false;
                }
            }
        }
        if (bench) markLap(lap, tQuery);
        QImage laneMask;
        QVector<Detection> dets;
        int lanePointCount = 0;
        bool laneOk = true;
        if (m_lane)
            laneMask = decodeLaneMask(outs[0], attrs[0], m_nc);
        else if (!m_independentUfld) {
            dets = decode(outs, attrs);
            tdm::restoreCanonicalDetections(dets, m_geometry);
        }
        if (m_sharedUfld || m_independentUfld) {
            const int offset = m_sharedUfld ? 6 : 0;
            std::array<const float*,4> tensors{};
            for(int i=0;i<4;++i) {
                if (!outs[offset+i].buf || outs[offset+i].size < attrs[offset+i].n_elems*sizeof(float)) laneOk=false;
                tensors[i] = static_cast<const float*>(outs[offset+i].buf);
            }
            std::vector<mvp::Point> points;
            laneOk = laneOk && mvp::decodePoints(tensors,m_laneContract,points);
            if (laneOk) {
                laneMask = QImage(640,640,QImage::Format_ARGB32_Premultiplied);
                laneMask.fill(Qt::transparent);
                QPainter painter(&laneMask);
                painter.setRenderHint(QPainter::Antialiasing);
                const QColor colors[8] = {QColor(255,80,80),QColor(80,255,80),QColor(80,180,255),QColor(255,220,60),QColor(255,80,255),QColor(60,255,255),QColor(255,150,60),QColor(180,130,255)};
                for(const auto& point:points) {
                    painter.setPen(QPen(colors[point.lane],1.5));
                    painter.setBrush(Qt::NoBrush);
                    if(point.row) painter.drawEllipse(QPointF(point.x,point.y),2.5,2.5);
                    else {
                        painter.drawLine(QPointF(point.x-3,point.y),QPointF(point.x+3,point.y));
                        painter.drawLine(QPointF(point.x,point.y-3),QPointF(point.x,point.y+3));
                    }
                }
                lanePointCount = int(points.size());
            }
        } else if (m_spatialLane) {
            // MVP-R2 spatial lane heads: heatmap logits [1,1,120,160] and
            // xy offsets [1,2,120,160]. Keep the canonical 640x640 mask
            // contract by restoring the 80-pixel camera crop.
            std::vector<mvp::SpatialPoint> points;
            laneOk = mvp::decodeSpatialPoints(static_cast<const float*>(outs[6].buf),
                                              static_cast<const float*>(outs[7].buf), points);
            if (laneOk && (!points.empty() || qEnvironmentVariableIsSet("DETVIEW_LEGACY_LANE_HUD"))) {
                laneMask = QImage(640, 640, QImage::Format_ARGB32_Premultiplied);
                laneMask.fill(Qt::transparent);
                QPainter painter(&laneMask);
                painter.setRenderHint(QPainter::Antialiasing);
                painter.setPen(QPen(QColor(80, 255, 80), 1.5));
                painter.setBrush(Qt::NoBrush);
                for (const auto& point : points)
                    painter.drawEllipse(QPointF(point.x, point.y + 80.f), 2.5, 2.5);
                lanePointCount = int(points.size());
            }
        }
        if (bench) markLap(lap, tDecode);
        const int releaseResult = rknn_outputs_release(m_ctx, m_nOutput, outs.data());
        if (m_boundInput && releaseResult != 0) scheme2Quarantine("bound output release failed");
        if (bench) markLap(lap, tRel);
        const double ms = scheme2::verify() ? 0 : timer.nsecsElapsed() / 1e6;
        const int completed = ++m_completed[modelPath];
        if ((m_mvpDetect || m_independentUfld) && (completed == 1 || completed % 20 == 0))
            fprintf(stderr,"[mvp] model=%s frame=%llu input=640x480 RGB uint8 /255 crop_y=80 detections=%d lane_points=%d decode_ok=%d\n",
                    qPrintable(modelPath),(unsigned long long)frameId,dets.size(),lanePointCount,int(laneOk));
        if (qEnvironmentVariableIsSet("DET_BENCH") && !scheme2::verify()) {
            timespec stamp{};
            clock_gettime(CLOCK_MONOTONIC, &stamp);
            fprintf(stderr, "[tdm_bench] t=%.6f model=%s ms=%.3f\n",
                    stamp.tv_sec + stamp.tv_nsec / 1e9, qPrintable(modelPath), ms);
        }
        if (completed == 1 || completed % 20 == 0)
            fprintf(stderr, "[tdm] model=%s completed=%d ms=%.2f source_generation=%d\n",
                    qPrintable(modelPath), completed, ms, sourceGeneration);
        if (m_trafficlight && (completed == 1 || completed % 20 == 0)) {
            fprintf(stderr, "[trafficlight] completed=%d frame=%llu input=640x480 RGB uint8 crop_y=80 canonical_y=network_y+80 detections=%d\n",
                    completed, (unsigned long long)frameId, dets.size());
            for (int i = 0; i < std::min(10, dets.size()); ++i) {
                const auto &d = dets[i];
                fprintf(stderr, "[trafficlight] cls=%d name=%s score=%.4f canonical_xyxy=(%.2f,%.2f,%.2f,%.2f)\n",
                        d.cls, qPrintable(m_classNames.value(d.cls)), d.score, d.x1, d.y1, d.x2, d.y2);
            }
        }
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
        if (!laneOk || (m_lane && laneMask.isNull())) return false;
        const double completedFps = recordMetric(sourceGeneration, modelPath, 1);
        VisionEvidence::instance().event("completed", m_runningAge, m_lane || m_independentUfld);
        emit observationReady(modelPath, sourceGeneration, frameId, dets, ms,
                              m_lane || m_independentUfld);
        if (m_sharedUfld || m_independentUfld || m_spatialLane) {
            emit mvpResultReady(modelPath,laneMask,sourceGeneration,frameId,dets,lanePointCount,completedFps,ms);
        } else if (m_lane) {
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

    static void nmsAppend(QVector<Detection> &dets, std::vector<CandD> &cands, bool classAware = false,
                          float iouThresh = IOU_THRESH) {
        std::sort(cands.begin(), cands.end(),
                  [](const CandD &a, const CandD &b) { return a.score > b.score; });
        std::vector<bool> removed(cands.size(), false);
        for (size_t i = 0; i < cands.size(); i++) {
            if (removed[i])
                continue;
            const CandD &a = cands[i];
            Detection detection;
            detection.cls = a.cls; detection.score = a.score;
            detection.x1 = a.x1; detection.y1 = a.y1; detection.x2 = a.x2; detection.y2 = a.y2;
            dets.append(detection);
            if (classAware && dets.size() >= 300) break;
            for (size_t j = i + 1; j < cands.size(); j++) {
                if (removed[j])
                    continue;
                const CandD &b = cands[j];
                if (classAware && a.cls != b.cls) continue;
                const float xx1 = std::max(a.x1, b.x1);
                const float yy1 = std::max(a.y1, b.y1);
                const float xx2 = std::min(a.x2, b.x2);
                const float yy2 = std::min(a.y2, b.y2);
                const float w = std::max(0.0f, xx2 - xx1);
                const float h = std::max(0.0f, yy2 - yy1);
                const float inter = w * h;
                const float ai = (a.x2 - a.x1) * (a.y2 - a.y1);
                const float bj = (b.x2 - b.x1) * (b.y2 - b.y1);
                if (inter / (ai + bj - inter + 1e-6f) > iouThresh)
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
            if (m_mvpDetect && i >= 6) break; // raw10 lane tensors are never DFL candidates.
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

        bool sigmoid = m_trafficlight || m_mvpDetect; // Delivered raw heads always contain logits.
        if (!m_trafficlight && !m_mvpDetect) {
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
        if (!m_trafficlight && !m_mvpDetect && cands.size() > 300)
            cands.resize(300);

        std::vector<CandD> boxes;
        boxes.reserve(cands.size());
        for (const AC &c : cands) {
            const Scale &sc = scales[c.s];
            const int plane = sc.h * sc.w;
            const float stride = m_geometry.width / (float)sc.w;
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
        nmsAppend(dets, boxes, m_trafficlight || m_mvpDetect,
                  m_mvpPolicy.enabled ? mvp::Round1Policy::nmsIou : IOU_THRESH);
        m_mvpPolicy.filterAfterNms(dets);
        return true;
    }

    QVector<Detection> decode(const std::vector<rknn_output> &outs,
                              const std::vector<rknn_tensor_attr> &attrs) {
        QVector<Detection> dets;
        const float confThresh = m_mvpPolicy.enabled ? mvp::Round1Policy::candidateFloor : m_conf.load();
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
    std::shared_ptr<scheme2::Input> m_pendingFpga;
    bool m_boundInput = false;
    std::vector<std::vector<uint8_t>> m_verifyOutputs;
    int m_verifyCamera = -1;
    uint32_t m_verifyTag = 0;
    unsigned m_verifyCompleted = 0;
    std::atomic<uint64_t> m_modelRevision{0};
    int m_pendingGeneration = 0;
    quint64 m_pendingFrameId = 0;
    tdm::InferAge m_pendingAge, m_runningAge;
    bool m_hasPending = false;
    bool m_modelChanged = false;
    QVector<ModelInfo> m_selection;
    QHash<QString, int> m_completed;
    int m_nc = 1;
    bool m_xyxy = false;
    std::atomic<bool> m_manualFormat{false};
    bool m_lane = false;
    bool m_trafficlight = false;
    bool m_mvpDetect = false, m_sharedUfld = false, m_independentUfld = false;
    bool m_spatialLane = false;
    mvp::Round1Policy m_mvpPolicy;
    mvp::LaneContract m_laneContract;
    tdm::InferenceGeometry m_geometry;
    int m_lastDumpedGeneration = -1;
    const std::vector<rknn_tensor_attr> *m_outputAttrs = nullptr;
    QStringList m_classNames;
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
        m_hudStatsIntervalMs = qEnvironmentVariableIsSet("DETVIEW_HUD_STATS_MS") ?
            qBound(100, qEnvironmentVariableIntValue("DETVIEW_HUD_STATS_MS"), 5000) : 1000;
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
        view.setLaneMask(mask);
        view.setDetections({d}, {"a", "b"});
        if (view.m_laneMask.cacheKey() != mask.cacheKey()) return false;
        view.setDetections({}, {"a", "b"});
        if (view.m_laneMask.cacheKey() != mask.cacheKey()) return false;
        view.setCalibrationLine("单车辆试用 Z=2.00 米", monotonicMs() - 1);
        view.refreshExpiredContent();
        if (view.m_calibrationLine.contains("Z=") || view.m_calibrationExpiresMs != 0) return false;
        fprintf(stderr, "DISPLAY_REFRESH_SELFTEST_PASS\n");
        return true;
    }

    struct PaintStats { int count; double averageMs; };
    static bool selfTestTouch() {
        DetView view; view.resize(1920,1080);
        QVector<int> keys;
        view.setKeyHook([&](QKeyEvent* e) { keys.push_back(e->key()); });
        auto event = [&](QEvent::Type type, QPoint p, Qt::MouseButton button) {
            QMouseEvent e(type,p,button,type==QEvent::MouseButtonRelease ? Qt::NoButton : Qt::LeftButton,Qt::NoModifier);
            QCoreApplication::sendEvent(&view,&e);
        };
        auto tap = [&](QPoint p) { event(QEvent::MouseButtonPress,p,Qt::LeftButton); event(QEvent::MouseButtonRelease,p,Qt::LeftButton); };
        for (const auto& b:view.touchButtons()) {
            if (b.rect.height()<48 || b.rect.width()<48) return false;
            const int n=keys.size(); tap(b.rect.center());
            if (keys.size()!=n+1 || keys.back()!=b.key) return false;
        }
        const QPoint p=view.touchButtons()[3].rect.center(); const int count=keys.size();
        event(QEvent::MouseButtonPress,p,Qt::LeftButton);
        event(QEvent::MouseMove,p+QPoint(50,0),Qt::NoButton);
        event(QEvent::MouseButtonRelease,p,Qt::LeftButton);
        if(keys.size()!=count) return false;
        event(QEvent::MouseButtonPress,p,Qt::RightButton);
        event(QEvent::MouseButtonRelease,p,Qt::RightButton);
        if(keys.size()!=count) return false;
        view.setSettingsVisible(true);
        unsigned pairButtons=0;
        for(const auto& b:view.touchButtons()) {
            const int n=keys.size(); tap(b.rect.center());
            if(keys.size()!=n+1 || keys.back()!=b.key || (b.row>=0 && view.settingRow()!=b.row)) return false;
            if(b.key>=Qt::Key_F7 && b.key<=Qt::Key_F9)++pairButtons;
        }
        if(pairButtons!=3)return false;
        view.setSettingsVisible(false); view.m_hdmiFull=false; view.m_paneMask=0x3F;
        int selected=-1; view.setCameraHook([&](int c){selected=c;});
        tap(QPoint(1600,800)); if(selected!=5) return false;
        view.m_hdmiFull=true; selected=-1; tap(QPoint(1600,800)); if(selected!=-1) return false;
        view.resize(720,1280);
        for(const auto& b:view.touchButtons()) if(b.rect.height()<48 || b.rect.width()<48 || !QRect(QPoint(),view.size()).contains(b.rect)) return false;
        view.setSettingsVisible(true);
        for(const auto& b:view.touchButtons()) if(b.rect.height()<48 || b.rect.width()<48 || !QRect(QPoint(),view.size()).contains(b.rect)) return false;
        const auto portraitButtons=view.touchButtons();pairButtons=0;
        for(int i=0;i<portraitButtons.size();++i){
            const auto& b=portraitButtons[i];
            if(b.key<Qt::Key_F7 || b.key>Qt::Key_F9)continue;
            ++pairButtons;const int n=keys.size();tap(b.rect.center());
            if(keys.size()!=n+1 || keys.back()!=b.key)return false;
            for(int j=0;j<portraitButtons.size();++j)
                if(i!=j && b.rect.intersects(portraitButtons[j].rect))return false;
        }
        if(pairButtons!=3)return false;
        view.setSettingsVisible(false);
        view.setSettingsVisible(true);
        if(view.settingRow()!=0) return false;
        for(int i=0;i<6;++i) view.moveSetting(1);
        if(view.settingRow()!=6) return false;
        view.setSettingsVisible(false);
        view.setSettingsVisible(true);
        if(view.settingRow()!=0) return false;
        fprintf(stderr,"TOUCH_SELFTEST_PASS: toolbar/settings/reset-row/single activation/drag/right-button/tiles/portrait\n");
        return true;
    }
    static bool selfTestResolutionDisplay() {
        DetView view;
        CameraThread::DisplayFrame frame;
        for(int c=0;c<CAM_COUNT;++c) frame.geometries[c]=runtime_camera::geometry(c);
        frame.geometries[0]=runtime_camera::geometry(0,runtime_camera::Mode::Hd720,2);
        frame.cam1Hd=true; frame.paneMask=1; frame.pane=0; frame.changedMask=1;
        frame.cameraPixels[0]=QByteArray(cam1::geometry(true).bytes(),0);
        for(int slot=0;slot<kTextureRing;++slot) view.m_cameraTextureAllocated[0][slot]=true;
        view.submitCameras(frame);
        if(!view.m_cam1Hd || view.m_paneMask!=1 || !view.m_haveFrame) return false;
        for(int slot=0;slot<kTextureRing;++slot) {
            if(view.m_cameraTextureAllocated[0][slot]) return false;
            view.m_cameraTextureAllocated[0][slot]=true;
        }
        frame.cam1Hd=false;frame.cam34Shared=true;frame.paneMask=0x3f;
        frame.geometries[0]=runtime_camera::geometry(0,runtime_camera::Mode::Default,3);
        frame.cameraPixels[0]=QByteArray(FRAME_BYTES,0);
        view.submitCameras(frame);
        if(view.m_cam1Hd || !view.m_cam34Shared || view.m_cameraPixels[0].size()!=int(FRAME_BYTES)) return false;
        for(int slot=0;slot<kTextureRing;++slot) if(view.m_cameraTextureAllocated[0][slot]) return false;
        uint64_t generation=3;
        for(unsigned modes=0;modes<8;++modes) {
            ++generation;
            int bit=0;
            for(int c=0;c<CAM_COUNT;++c) {
                const bool hd=(c==0 || c==2 || c==3) && (modes & (1u<<bit));
                if(c==0 || c==2 || c==3) ++bit;
                frame.geometries[c]=runtime_camera::geometry(c,hd?runtime_camera::Mode::Hd720:runtime_camera::Mode::Default,generation);
                frame.cameraPixels[c]=QByteArray(int(frame.geometries[c].pixelBytes),char(c+1));
                for(int slot=0;slot<kTextureRing;++slot) view.m_cameraTextureAllocated[c][slot]=true;
            }
            view.submitCameras(frame);
            for(int c=0;c<CAM_COUNT;++c) {
                if(view.m_cameraGeometry[c].generation!=generation || view.m_cameraPixels[c].size()!=int(frame.geometries[c].pixelBytes)) return false;
                for(int slot=0;slot<kTextureRing;++slot) if(view.m_cameraTextureAllocated[c][slot]) return false;
            }
            auto stale=frame;
            stale.geometries[2]=runtime_camera::geometry(2,runtime_camera::Mode::Default,generation-1);
            stale.cameraPixels[2]=QByteArray(153600,0);
            view.submitCameras(stale);
            if(view.m_cameraGeometry[2].generation!=generation || view.m_paneMask!=0x3f) return false;
            auto wrong=frame;wrong.cameraPixels[3].resize(4);view.submitCameras(wrong);
            if(view.m_cameraPixels[3].size()!=frame.cameraPixels[3].size()) return false;
        }
        for(int c=0;c<CAM_COUNT;++c) for(int slot=0;slot<kTextureRing;++slot) view.m_cameraTextureAllocated[c][slot]=true;
        frame.geometries[2]=runtime_camera::geometry(2,runtime_camera::Mode::Default,generation+1);
        frame.cameraPixels[2]=QByteArray(153600,0);view.submitCameras(frame);
        for(int c=0;c<CAM_COUNT;++c) for(int slot=0;slot<kTextureRing;++slot)
            if(view.m_cameraTextureAllocated[c][slot]!=(c!=2)) return false;
        if(view.m_cameraGeometry[3].mode!=runtime_camera::Mode::Hd720 || view.m_cameraGeometry[3].generation!=generation) return false;
        for(auto left:{runtime_camera::Mode::Default,runtime_camera::Mode::FullVga,runtime_camera::Mode::Hd720})
            for(auto right:{runtime_camera::Mode::Default,runtime_camera::Mode::FullVga,runtime_camera::Mode::Hd720}) {
                ++generation;
                for(int c=0;c<CAM_COUNT;++c){
                    const auto mode=c==2?left:c==3?right:runtime_camera::Mode::Default;
                    frame.geometries[c]=runtime_camera::geometry(c,mode,generation);
                    frame.cameraPixels[c]=QByteArray(int(frame.geometries[c].pixelBytes),0);
                }
                frame.paneMask=0x3f;frame.changedMask=0x3f;view.submitCameras(frame);
                if(view.m_cameraGeometry[2].mode!=left || view.m_cameraGeometry[3].mode!=right ||
                   view.m_cameraPixels[2].size()!=int(frame.geometries[2].pixelBytes) ||
                   view.m_cameraPixels[3].size()!=int(frame.geometries[3].pixelBytes))return false;
            }
        view.clearResolutionFrame();
        if(view.m_haveFrame || !view.m_cameraPixels[0].isEmpty()) return false;
        fprintf(stderr,"CAM134_DISPLAY_SELFTEST_PASS: eight mixed modes, six tiles, all texture slots, stale generation/size rejection, queue clear\n");
        return true;
    }
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
        for(int c=0;c<CAM_COUNT;++c) {
            const auto& incoming=frame.geometries[c];
            if(!incoming.valid() || (m_cameraGeometry[c].valid() &&
               (incoming.generation<m_cameraGeometry[c].generation ||
                (incoming.generation==m_cameraGeometry[c].generation && incoming.mode!=m_cameraGeometry[c].mode)))) return;
            if(!frame.cameraPixels[c].isEmpty() && !incoming.acceptsPublication(incoming.generation,size_t(frame.cameraPixels[c].size()))) return;
        }
        for(int c=0;c<CAM_COUNT;++c) {
            const auto& incoming=frame.geometries[c];
            if(m_cameraGeometry[c].generation!=incoming.generation || m_cameraGeometry[c].mode!=incoming.mode) {
                m_overlayUpdatedMs=0;
                for(int slot=0;slot<kTextureRing;++slot) {
                    m_cameraTextureAllocated[c][slot]=false;
                    m_cameraTextureGeneration[c][slot]=0;
                }
                m_changedMask|=1<<c;
            }
            m_cameraGeometry[c]=incoming;
        }
        m_cam1Hd=frame.geometries[0].mode==runtime_camera::Mode::Hd720;
        if (m_videoMode || m_paneMask != frame.paneMask || m_pane != frame.pane) m_overlayUpdatedMs = 0;
        const bool hdmiFull = frame.hdmiFull && frame.paneMask == 0x3F;
        if (m_hdmiFull != hdmiFull) { m_hdmiFull = hdmiFull; m_overlayUpdatedMs = 0; }
        if(m_cam34Shared != frame.cam34Shared) {
            m_cam34Shared=frame.cam34Shared; m_overlayUpdatedMs=0; m_changedMask|=12;
            fprintf(stderr,"[cam34-six-display] shared=%d layout=3x2 capture=all-six widths=%d/%d/%d/%d/%d/%d\n",int(m_cam34Shared),cam34::displayWidth(0,m_cam34Shared),cam34::displayWidth(1,m_cam34Shared),cam34::displayWidth(2,m_cam34Shared),cam34::displayWidth(3,m_cam34Shared),cam34::displayWidth(4,m_cam34Shared),cam34::displayWidth(5,m_cam34Shared));
            for(int c:{2,3})for(int slot=0;slot<kTextureRing;++slot)m_cameraTextureAllocated[c][slot]=false;
        }
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
    void clearResolutionFrame() { m_haveFrame=false; m_cameraPixels={}; m_dirty=true; update(); }

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
                   a.depthCapturedMs == b.depthCapturedMs && a.depthAgeMs == b.depthAgeMs &&
                   a.depthTrial == b.depthTrial && a.depthStatus == b.depthStatus;
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
        if (m_calibrationExpiresMs > 0 && monotonicMs() > m_calibrationExpiresMs)
            setCalibrationLine("单车辆试用 · 旧距离已过期，等待新测量");
        if (m_settingsVisible) {
            if (!m_overlaySettings || m_overlaySize != size() || m_overlayRevision != m_settingsRevision) update();
            return;
        }
        const qint64 now = monotonicMs();
        const bool expired = m_overlayExpiresMs > 0 && now > m_overlayExpiresMs;
        const bool periodic = now - m_overlayUpdatedMs >= m_hudStatsIntervalMs;
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
    enum class CaptureState { Ready, Switching, Error };
    void setCaptureState(CaptureState state, const QString &reason = QString()) {
        QMutexLocker lock(&m_uiMutex);
        if (m_captureState == CaptureState::Error && state == CaptureState::Switching) return;
        m_captureState = state;
        m_captureReason = state == CaptureState::Ready ? QString() : reason;
        if (!reason.isEmpty()) m_statusLine = reason;
        ++m_settingsRevision;
        m_overlayUpdatedMs = 0;
        lock.unlock();
        update();
    }
    void setStatusLine(const QString &s) {
        QMutexLocker lock(&m_uiMutex);
        if (m_captureState == CaptureState::Error) return;
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
        if (m_help == on) return;
        m_help = on;
        m_overlayUpdatedMs = 0;
        update();
    }
    bool settingsVisible() const { return m_settingsVisible; }
    void setSettingsVisible(bool visible) {
        m_settingsVisible = visible;
        // Every fresh settings interaction starts at a known row. Otherwise
        // Down/Right shortcuts depend on the row left by the previous visit.
        if (visible) m_settingRow = 0;
        // Keep pending pixels/masks until monitoring resumes. Old content is
        // uploaded once; opening settings never pauses capture or inference.
        resetRates();
        update();
    }
    void moveSetting(int direction) {
        m_settingRow = (m_settingRow + direction + 8) % 8;
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
    void setCalibrationLine(const QString& text, qint64 expiresMs = 0) {
        if (qEnvironmentVariableIsSet("DETVIEW_STEREO_VEHICLE_TRIAL") && expiresMs == 0 &&
            text == QString("单车辆试用 · 等待同帧双目") &&
            m_calibrationExpiresMs > monotonicMs()) return;
        if (m_calibrationLine == text && m_calibrationExpiresMs == expiresMs) return;
        m_calibrationExpiresMs = expiresMs;
        m_calibrationLine = text; m_overlayUpdatedMs = 0; ++m_settingsRevision; update();
    }
    void setStereoPreview(const QImage &image, const QString &status) {
        if (qEnvironmentVariableIsSet("DETVIEW_STEREO_TRIAL_METERS") &&
            !qEnvironmentVariableIsSet("DETVIEW_STEREO_VEHICLE_TRIAL"))
            setCalibrationLine(QString("试用测距 · %1").arg(status));
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
    void setCameraHook(std::function<void(int)> hook) { m_cameraHook = std::move(hook); }
    /* 截屏：直接抓 GL 帧缓冲 */
    QImage grabFrame() { return grabFramebuffer(); }

    /* ---- C1 俯视图（bird's eye）----------------------------------------
       LUT 是 int16 对 (sx, sy)，语义与 camview 的 /userdata/c1_bird_lut_i16.bin
       完全一致：sx = lut[i*2+0]，sy = lut[i*2+1]；越界填黑。
       LUT 由 CPU 重映射 C1 的 RGB565 帧，结果当"视频源"全屏显示。

       俯视 LUT 是按 C1 480P（640x480）标定的。C1 切到 720P（1280x720）时源图
       几何不同，因此按 sensor 坐标换算出一份 720P LUT：两者水平窗口相同
       （0..2623），竖向窗口分别为 4..1947 / 250..1705。换算在加载时一次完成，
       不依赖运行时帧数据。 */
    bool birdReady() const { return m_birdReady; }
    bool birdActive() const { return m_birdActive; }

    // C1 传感器几何（ov5640 寄存器，480P=默认、720P=HD），用于 480P->720P 换算。
    struct SensorWindow { double h0, w, v0, h; };
    static SensorWindow birdWindow(bool hd) {
        return hd ? SensorWindow{0.0, 2624.0, 250.0, 1456.0}
                  : SensorWindow{0.0, 2624.0, 4.0, 1944.0};
    }

    // 把 480P 的俯视 LUT 换算成 720P 版本：out[i] = 720P 源像素坐标。
    static std::vector<qint16> deriveHdBirdLut(const std::vector<qint16>& lut480, int bw, int bh) {
        const SensorWindow s480 = birdWindow(false), s720 = birdWindow(true);
        std::vector<qint16> out(lut480.size(), -1);
        for (int i = 0; i < bw * bh; ++i) {
            const int sx = lut480[size_t(i) * 2 + 0];
            const int sy = lut480[size_t(i) * 2 + 1];
            if (sx < 0 || sy < 0 || sx >= IMG_W || sy >= IMG_H) continue;
            // 480P 像素中心 -> sensor 坐标 -> 720P 像素坐标。
            const double sensorX = s480.h0 + (sx + 0.5) * (s480.w / IMG_W);
            const double sensorY = s480.v0 + (sy + 0.5) * (s480.h / IMG_H);
            const double hx = (sensorX - s720.h0) * (1280.0 / s720.w) - 0.5;
            const double hy = (sensorY - s720.v0) * (720.0 / s720.h) - 0.5;
            const int ix = int(std::llround(hx));
            const int iy = int(std::llround(hy));
            if (ix < 0 || iy < 0 || ix >= 1280 || iy >= 720) continue;
            out[size_t(i) * 2 + 0] = qint16(ix);
            out[size_t(i) * 2 + 1] = qint16(iy);
        }
        return out;
    }

    bool loadBirdLut(const QString& path) {
        QFile f(path);
        if (!f.open(QIODevice::ReadOnly)) {
            fprintf(stderr, "[bird] open failed %s\n", path.toUtf8().constData());
            return false;
        }
        const QByteArray d = f.readAll();
        f.close();
        const int w = 640, h = 472;
        if (d.size() != w * h * 2 * 2) {
            fprintf(stderr, "[bird] bad size %d (want %d)\n", int(d.size()), w * h * 4);
            return false;
        }
        m_birdW = w; m_birdH = h;
        m_birdLut.resize(size_t(w) * size_t(h) * 2);
        std::memcpy(m_birdLut.data(), d.constData(), size_t(d.size()));
        m_birdLutHd = deriveHdBirdLut(m_birdLut, w, h);
        size_t hdValid = 0;
        for (size_t i = 0; i < m_birdLutHd.size(); i += 2)
            if (m_birdLutHd[i] >= 0) ++hdValid;
        m_birdReady = true;
        m_birdBuilt = false;
        m_birdTextureValid = false;
        fprintf(stderr, "[bird] lut loaded %s (%dx%d) hd_valid=%zu/%d\n",
                path.toUtf8().constData(), w, h, hdValid, w * h);
        return true;
    }
    void setBirdActive(bool on) {
        if (on && !m_birdReady) {
            const QString path = qEnvironmentVariable("BIRD_LUT_PATH", "/userdata/c1_bird_lut_i16.bin");
            if (!loadBirdLut(path)) {
                setStatusLine(QString("俯视 LUT 载入失败: %1").arg(path));
                return;
            }
        }
        m_birdActive = on;
        m_birdTextureValid = false;
        m_dirty = true;
        setStatusLine(on ? QString("C1 俯视（B 键返回 · 480P/720P）")
                         : QString("返回常规监看"));
        update();
    }

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
        m_texAlloc = false;
        m_videoTextureAllocated = false;
        m_birdTextureValid = false;
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
        const bool birdActive = m_birdActive && m_birdReady && m_birdW > 0 &&
                                (m_cameraPixels[0].size() == IMG_W * IMG_H * 2 ||
                                 m_cameraPixels[0].size() == 1280 * 720 * 2);
        const bool videoMode = m_videoMode || birdActive;
        const int paneMask = birdActive ? (1 << 0) : m_paneMask;
        const int pane = birdActive ? 0 : m_pane;
        QVector<double> camFps = m_camFps;
        QVector<Detection> dets = birdActive ? QVector<Detection>() : m_dets;
        QStringList classes = m_classes;
        QImage video = birdActive ? buildBirdFrame() : (m_videoMode ? m_image : QImage());
        QImage laneMask = birdActive ? QImage() : m_laneMask;
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
            /* HDMI 满屏：内容区是 C5+C6 拼合的 1280x480，而不是 3x2 的 1920x960 */
            const bool hdmi = paneMask == 0x3F && m_hdmiFull;
            cw = (paneMask == 0x3F) ? (hdmi ? IMG_W : GRID_COLS * IMG_W) : IMG_W;
            ch = (paneMask == 0x3F) ? (hdmi ? IMG_H : GRID_ROWS * IMG_H) : IMG_H;
            if(m_pane>=0 && m_pane<CAM_COUNT && m_cameraGeometry[m_pane].valid()) {
                cw=int(m_cameraGeometry[m_pane].width); ch=int(m_cameraGeometry[m_pane].height);
            }
        }
        if (cw > 0 && ch > 0) {
            // HDMI fills the available display area. Use the same content
            // rectangle for the camera textures, detections and lane mask;
            // this is display-only stretching and leaves RKNN input unchanged.
            const bool hdmiAspect = !videoMode && paneMask == 0x3F && m_hdmiFull;
            const int top = std::min(56, height() / 8);
            const int bottom = touchBarHeight();
            const int viewHeight = qMax(1, height() - top - bottom);
            const float wa = (float)width() / viewHeight;
            const float ia = hdmiAspect ? wa : (float)cw / (float)ch;
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
                    const bool needsUpload = !birdActive || !m_birdTextureValid ||
                        m_birdTextureSequence != m_sequences[0] ||
                        m_birdTextureGeneration != m_cameraGeometry[0].generation;
                    if (needsUpload) {
                        const GLenum type = birdActive ? GL_UNSIGNED_SHORT_5_6_5 : GL_UNSIGNED_BYTE;
                        if (!m_videoTextureAllocated || m_texW != video.width() ||
                            m_texH != video.height() || m_videoTextureType != type) {
                            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, video.width(), video.height(), 0,
                                         GL_RGB, type, video.constBits());
                            m_videoTextureAllocated = true;
                            m_videoTextureType = type;
                        } else {
                            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, video.width(), video.height(),
                                            GL_RGB, type, video.constBits());
                        }
                        m_birdTextureValid = birdActive;
                        m_birdTextureSequence = m_sequences[0];
                        m_birdTextureGeneration = m_cameraGeometry[0].generation;
                    }
                    m_texW = video.width();
                    m_texH = video.height();
                    if (birdActive) {
                        freshVisibleFrame = needsUpload && m_sequences[0] != 0 &&
                            m_sequences[0] != m_uploadedSequences[0];
                        m_uploadedSequences[0] = m_sequences[0];
                    } else {
                        freshVisibleFrame = m_videoSequence != 0 && m_videoSequence != m_uploadedVideoSequence;
                        m_uploadedVideoSequence = m_videoSequence;
                    }
                } else {
                    const int visibleMask = m_hdmiFull ? ((1 << tdm::hdmiLeftCamera) | (1 << tdm::hdmiRightCamera)) : paneMask;
                    const int mask = (m_changedMask ? m_changedMask : 0x3F) & visibleMask;
                    for (int c = 0; c < CAM_COUNT; ++c) {
                        if (!(mask & (1 << c)))
                            continue;
                        const auto& geometry=m_cameraGeometry[c];
                        if(!geometry.valid() || !geometry.acceptsPublication(geometry.generation,size_t(m_cameraPixels[c].size()))) continue;
                        const int pixelWidth=int(geometry.width);
                        const int pixelHeight=int(geometry.height);
                        const size_t pixelBytes=size_t(pixelWidth)*pixelHeight*2;
                        if(size_t(m_cameraPixels[c].size())!=pixelBytes)continue;
                        const int slot = (m_cameraTextureSlot[c] + 1) % m_textureRing;
                        glBindTexture(GL_TEXTURE_2D, m_cameraTextures[c][slot]);
                        if (!m_cameraTextureAllocated[c][slot]) {
                            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, pixelWidth, pixelHeight, 0, GL_RGB,
                                         GL_UNSIGNED_SHORT_5_6_5, m_cameraPixels[c].constData());
                            m_cameraTextureAllocated[c][slot] = true;
                        } else {
                            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, pixelWidth, pixelHeight, GL_RGB,
                                            GL_UNSIGNED_SHORT_5_6_5, m_cameraPixels[c].constData());
                        }
                        m_cameraTextureSlot[c] = slot;
                        m_cameraTextureGeneration[c][slot]=geometry.generation;
                        if (m_perfEnabled) {
                            ++m_perf.cameraUploads[c]; m_perf.cameraUploadBytes[c] += pixelBytes;
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
                const auto& geometry=m_cameraGeometry[camera];
                if(!geometry.valid() || !m_cameraTextureAllocated[camera][m_cameraTextureSlot[camera]] ||
                   m_cameraTextureGeneration[camera][m_cameraTextureSlot[camera]]!=geometry.generation) return;
                const double scale=std::min(tile.width()/geometry.width,tile.height()/geometry.height);
                const QSizeF fittedSize(geometry.width*scale,geometry.height*scale);
                const QRectF fitted(tile.center()-QPointF(fittedSize.width()/2,fittedSize.height()/2),fittedSize);
                const float tx0 = float((fitted.left() - content.left()) / content.width());
                const float tx1 = float((fitted.right() - content.left()) / content.width());
                const float ty0 = float((fitted.top() - content.top()) / content.height());
                const float ty1 = float((fitted.bottom() - content.top()) / content.height());
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
                if (quad && m_hdmiFull) {
                    // HDMI 满屏：C5/C6 各占内容区一半（1280x480 合成帧的左右半幅）
                    const double half = content.width() / 2.0;
                    drawCamera(tdm::hdmiLeftCamera,
                               QRectF(content.left(), content.top(), half, content.height()));
                    drawCamera(tdm::hdmiRightCamera,
                               QRectF(content.left() + half, content.top(), half, content.height()));
                } else {
                for (int c = 0; c < CAM_COUNT; ++c) {
                    if (!quad && c != pane) continue;
                    const QRectF tile = quad ? QRectF(content.left() + (c % GRID_COLS) * content.width() / GRID_COLS,
                                                      content.top() + (c / GRID_COLS) * content.height() / GRID_ROWS,
                                                      content.width() / GRID_COLS, content.height() / GRID_ROWS)
                                             : content;
                    drawCamera(c, tile);
                }
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
            if (m_hdmiFull || (m_cam34Shared && pane==tdm::hdmiInferenceCamera)) {
                // Shared inference spans both optical halves.
                paneRect = content;
            } else {
                const double pw = content.width() / GRID_COLS, ph = content.height() / GRID_ROWS;
                paneRect = QRectF(content.left() + (pane % GRID_COLS) * pw,
                                  content.top() + (pane / GRID_COLS) * ph, pw, ph);
            }
        }
        auto placeDetection=[&](const Detection&d) -> cam34::Placement {
            if(m_cam34Shared && !m_hdmiFull && m_pane==tdm::hdmiInferenceCamera && paneMask==0x3F)
                return cam34::mapBox(d.x1,d.y1,d.x2,d.y2,content);
            const double sx=paneRect.width()/MODEL_W;
            const double sy=paneRect.height()/(m_hdmiFull?tdm::hdmiAnalyticsHeight:IMG_H);
            const double by=paneRect.top()-(m_hdmiFull?tdm::hdmiModelPad:80)*sy;
            return {pane,paneRect,QRectF(paneRect.left()+d.x1*sx,by+d.y1*sy,
                        std::max(1.0,(d.x2-d.x1)*sx),std::max(1.0,(d.y2-d.y1)*sy))};
        };
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
        const int top = std::min(56, height() / 8), bottom = touchBarHeight();
        hudRegions << QRect(0, 0, width(), top) << QRect(0, height() - bottom, width(), bottom);
        if (!content.isEmpty()) {
            const bool quad = !videoMode && paneMask == 0x3F;
            const bool hdmi = quad && m_hdmiFull;
            if(quad && m_cam34Shared && !m_hdmiFull && pane==tdm::hdmiInferenceCamera)
                for(int c:{2,3})borderRegions(cam34::tileFor(c,content).adjusted(1,1,-1,-1),2);
            else if(quad && !paneRect.isEmpty())borderRegions(paneRect.adjusted(1,1,-1,-1),2);
            for (int c = 0; c < (hdmi ? 2 : (quad ? CAM_COUNT : 1)); ++c) {
                const int camera = hdmi ? (c == 0 ? tdm::hdmiLeftCamera : tdm::hdmiRightCamera) : c;
                const double pw = content.width() / (hdmi ? 2 : (quad ? GRID_COLS : 1));
                const double ph = content.height() / (hdmi ? 1 : (quad ? GRID_ROWS : 1));
                const int col = hdmi ? (camera == tdm::hdmiRightCamera ? 1 : 0)
                                     : (quad ? camera % GRID_COLS : 0);
                const int row = hdmi ? 0 : (quad ? camera / GRID_COLS : 0);
                hudRegions << QRect(int(content.left() + col * pw + 6),
                                    int(content.top() + row * ph + 6),
                                    int(std::min(360.0, pw - 12)), cameraLabelHeight);
            }
            if (!laneMask.isNull()) {
                if (!paneRect.isEmpty()) hudRegions << paneRect.toAlignedRect();
            }
            else if (!paneRect.isEmpty()) {
                const double sx = paneRect.width() / MODEL_W;
                const double sy = paneRect.height() / (m_hdmiFull ? tdm::hdmiAnalyticsHeight : IMG_H);
                const double bx = paneRect.left();
                const double by = paneRect.top() - (m_hdmiFull ? tdm::hdmiModelPad : 80) * sy;
                for (const auto& d : dets) {
                    if (d.validUntilMs > 0 && metricNow > d.validUntilMs) continue;
                    const auto mapped=placeDetection(d);
                    const QRectF box=mapped.box,clip=mapped.tile;
                    const int firstRegion = hudRegions.size();
                    borderRegions(box, 3);
                    hudRegions << QRect(int(box.left()), int(std::max(box.top(), clip.top() + 42)),
                                        qMax(0, int(clip.right() - box.left()) + 1), labelImageHeight + 2);
                    for (int r = firstRegion; r < hudRegions.size(); ++r)
                        hudRegions[r] &= clip.toAlignedRect();
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
            m_overlayDetections != m_detectionRevision || hudNow - m_overlayUpdatedMs >= m_hudStatsIntervalMs ||
            (m_overlayExpiresMs > 0 && hudNow > m_overlayExpiresMs);
        if (m_perfEnabled) m_perf.time[tdm::HudRegions].add(regionTimer.nsecsElapsed() / 1e6);
        if (repaintHud) {
        QElapsedTimer rasterTimer; if (m_perfEnabled) {
            rasterTimer.start(); ++m_perf.hudRebuilds;
            if (m_overlaySettings || m_overlaySize != size()) ++m_perf.hudLayout;
            if (m_overlayDetections != m_detectionRevision) ++m_perf.hudRevision;
            if (hudNow - m_overlayUpdatedMs >= m_hudStatsIntervalMs) ++m_perf.hudPeriodic;
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
            const bool hdmi = quad && m_hdmiFull;
            const int nLab = hdmi ? 2 : (quad ? CAM_COUNT : 1);
            const double pw = content.width() / (hdmi ? 2 : (quad ? GRID_COLS : 1));
            const double ph = content.height() / (hdmi ? 1 : (quad ? GRID_ROWS : 1));
            const double ox = content.left(), oy = content.top();
            for (int i = 0; i < nLab; ++i) {
                const int cameraIndex = hdmi ? (i == 0 ? tdm::hdmiLeftCamera : tdm::hdmiRightCamera)
                                             : (quad ? i : pane);
                const int col = hdmi ? (cameraIndex == tdm::hdmiRightCamera ? 1 : 0)
                                     : (quad ? i % GRID_COLS : 0);
                const int row = hdmi ? 0 : (quad ? i / GRID_COLS : 0);
                const QRectF box(ox + col * pw + 6, oy + row * ph + 6,
                                 std::min(360.0, pw - 12), cameraLabelHeight);
                if (box.right() > content.right() || box.bottom() > content.bottom())
                    continue;
                const bool selected = !videoMode && cameraIndex == pane;
                painter.fillRect(box, selected ? QColor(12, 78, 86, 225) : QColor(12, 22, 34, 210));
                painter.drawImage(box.left() + 8, box.top() + 3,
                                  textImage(birdActive ? QString("C1 俯视 %1×%2").arg(m_birdW).arg(m_birdH) : videoMode ? QString("视频 · 采集 %1 fps").arg(
                                                m_metricsPaused || metricNow - m_videoReceivedMs >= 1000 ? 0 : m_dispFps, 0, 'f', 1) :
                                            QString("C%1  %4 采集 %2 · 画面 %3").arg(cameraIndex + 1)
                                                .arg(camFps.value(cameraIndex), 0, 'f', 1)
                                                .arg(m_cameraUploadRates[cameraIndex].rate(metricNow), 0, 'f', 1)
                                                  .arg(QString("%1×%2").arg(m_cameraGeometry[cameraIndex].width).arg(m_cameraGeometry[cameraIndex].height)),
                                            QColor(225, 239, 245), 11));
            }
            if (quad && !paneRect.isEmpty()) {
                painter.setPen(QPen(QColor(62, 213, 199), 2));
                if(m_cam34Shared && !m_hdmiFull && pane==tdm::hdmiInferenceCamera)
                    for(int c:{2,3})painter.drawRect(cam34::tileFor(c,content).adjusted(1,1,-1,-1));
                else painter.drawRect(paneRect.adjusted(1,1,-1,-1));
            }
        }
        /* 检测框/车道掩码：矩形用 QPainter 画（便宜），标签文字走缓存位图 */
        {
            painter.save();
            painter.setClipRect(paneRect, Qt::IntersectClip);
            const double sx = paneRect.width() / (double)MODEL_W;
            const double sy = paneRect.height() / (double)(m_hdmiFull ? tdm::hdmiAnalyticsHeight : IMG_H);
            const double baseX = paneRect.left();
            const double baseY = paneRect.top() - (m_hdmiFull ? tdm::hdmiModelPad : 80) * sy;
            if (!laneMask.isNull()) {
                // C3/C4 shared inference receives a 640x480 network canvas,
                // but its active wire image occupies x=0..640, y=200..440.
                // The two 320x240 halves belong to C3 and C4 respectively.
                // Drawing the whole mask over `content` leaks points into C5/C6
                // (for example a point at network x=500 becomes a C6 marker).
                if (m_cam34Shared && !m_hdmiFull && paneMask == 0x3F &&
                    pane == tdm::hdmiInferenceCamera) {
                    const QRectF left = cam34::tileFor(2, content);
                    const QRectF right = cam34::tileFor(3, content);
                    painter.drawImage(left, laneMask, QRectF(0, 200, 320, 240));
                    painter.drawImage(right, laneMask, QRectF(320, 200, 320, 240));
                } else {
                    painter.drawImage(QRectF(baseX, baseY, MODEL_W * sx, MODEL_H * sy), laneMask);
                }
            }
            for (const Detection &d : dets) {
                if (d.validUntilMs > 0 && monotonicMs() > d.validUntilMs) continue;
                auto expireAt = [&](qint64 deadline) {
                    if (deadline > 0 && deadline >= hudNow && (m_overlayExpiresMs == 0 || deadline < m_overlayExpiresMs))
                        m_overlayExpiresMs = deadline;
                };
                expireAt(d.validUntilMs);
                const auto mapped=placeDetection(d);
                const QRectF r=mapped.box,clip=mapped.tile;
                painter.save();painter.setClipRect(clip,Qt::IntersectClip);
                const QColor color = d.cls == 0 ? QColor(0, 255, 0)
                                    : (d.cls == 1 ? QColor(255, 60, 60) : QColor(255, 220, 0));
                painter.setPen(QPen(color, 3));
                painter.drawRect(r);
                QString label =
                    QString("%1 %2")
                        .arg(d.cls >= 0 && d.cls < classes.size() ? displayClassName(classes[d.cls])
                                                                  : QString::number(d.cls))
                         .arg(d.score, 0, 'f', 2);
                if (d.trackId)
                    label += QString(" #%1 %2").arg(d.trackId).arg(d.predicted ? "预测" : "追踪");
                const qint64 depthAge = monotonicMs() - d.depthCapturedMs;
                if (std::isfinite(d.depthMeters) && d.depthCapturedMs > 0 && depthAge >= 0 && depthAge <= 300)
                    label += QString(" %1Z=%2m (%3ms)").arg(d.depthTrial ? "试用 " : "")
                        .arg(d.depthMeters, 0, 'f', 2).arg(depthAge);
                else if (!d.depthStatus.isEmpty()) label += " · " + d.depthStatus;
                if (std::isfinite(d.depthMeters) && d.depthCapturedMs > 0) expireAt(d.depthCapturedMs + 300);
                QImage tag = textImage(label, color, 11);
                painter.drawImage(r.left(), std::max(r.top(), clip.top() + 42), tag);
                painter.restore();
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

    // Leave touch events unaccepted: Qt synthesizes exactly one mouse stream.
    // Activate on release in the same target; drags and cancelled taps do nothing.
    void mousePressEvent(QMouseEvent *e) override {
        if (e->button() != Qt::LeftButton) return;
        m_touchStart = e->pos(); m_touchTarget = touchTarget(e->pos());
        m_touchDragged = false; e->accept();
    }
    void mouseMoveEvent(QMouseEvent *e) override {
        if ((e->pos() - m_touchStart).manhattanLength() > 24) m_touchDragged = true;
    }
    void mouseReleaseEvent(QMouseEvent *e) override {
        if (e->button() != Qt::LeftButton) return;
        const int target = m_touchTarget; m_touchTarget = -1;
        if (m_touchDragged || target < 0 || touchTarget(e->pos()) != target ||
            (e->pos() - m_touchStart).manhattanLength() > 24) return;
        const auto buttons = touchButtons();
        if (target < buttons.size()) {
            const auto b = buttons[target];
            if (b.row >= 0) { m_settingRow = b.row; ++m_settingsRevision; }
            fprintf(stderr, "[touch-ui] key=%d row=%d\n", b.key, b.row);
            // One tap = one action. In a single-pane view this button means
            // "back to the six-camera overview"; it must not also toggle HDMI.
            if (b.key==Qt::Key_F && !m_videoMode && m_paneMask!=0x3F && m_keyHook) {
                QKeyEvent overview(QEvent::KeyPress,Qt::Key_G,Qt::NoModifier);
                m_keyHook(&overview);
            } else {
                QKeyEvent key(QEvent::KeyPress, b.key, Qt::NoModifier);
                if (m_keyHook) m_keyHook(&key);
            }
        } else if (target >= 200) {
            m_settingRow = target - 200; ++m_settingsRevision;
        } else if (target >= 100 && m_cameraHook) {
            fprintf(stderr, "[touch-ui] camera=%d\n", target - 100 + 1);
            m_cameraHook(target - 100);
        }
        m_overlayUpdatedMs = 0; update(); e->accept();
    }

private:
    struct TouchButton { QRect rect; QString label; int key; int row = -1; };
    int touchBarHeight() const { return width() < 840 ? 144 : 80; }
    QVector<TouchButton> touchButtons() const {
        QVector<TouchButton> out;
        if (m_settingsVisible) {
            if (width()<840) {
                out.push_back({QRect(width()-200,16,184,60),"返回监看",Qt::Key_Tab,-1});
                for(int row=0;row<8;++row) {
                    out.push_back({QRect(width()-176,104+row*66,72,56),"−",Qt::Key_Left,row});
                    out.push_back({QRect(width()-96,104+row*66,72,56),"+",Qt::Key_Right,row});
                }
                const int pairWidth=(width()-48)/3;
                for(int i=0;i<3;++i)
                    out.push_back({QRect(16+i*(pairWidth+8),height()-72,pairWidth,56),
                        i==0?"C3/4 A":i==1?"C3/4 B 480P":"C3/4 C 720P",Qt::Key_F7+i,-1});
                return out;
            }
            const double s = std::min(width() / 1280.0, height() / 720.0);
            const QPointF origin((width() - 1280*s)/2, (height() - 720*s)/2);
            auto add = [&](QRect r, QString text, int key, int row = -1) {
                out.push_back({QRectF(origin + QPointF(r.x()*s,r.y()*s), QSizeF(r.width()*s,r.height()*s)).toAlignedRect(), text, key, row});
            };
            add(QRect(990,20,250,60), "返回监看", Qt::Key_Tab);
            for (int row=0; row<8; ++row) {
                add(QRect(446,162+row*46,76,42), "−", Qt::Key_Left,row);
                add(QRect(530,162+row*46,76,42), "+", Qt::Key_Right,row);
            }
            add(QRect(650,610,180,56),"C3/4 A",Qt::Key_F7);
            add(QRect(840,610,180,56),"B 480P",Qt::Key_F8);
            add(QRect(1030,610,180,56),"C 720P",Qt::Key_F9);
            return out;
        }
        const QStringList labels = {"HDMI / 六路", "切换相机", "总览", m_metricsPaused ? "继续" : "暂停", "截屏", "帮助", "设置", "720p模式", "俯视"};
        const int keys[] = {Qt::Key_F,Qt::Key_V,Qt::Key_G,Qt::Key_P,Qt::Key_S,Qt::Key_H,Qt::Key_Tab,Qt::Key_F12,Qt::Key_B};
        /* 9 个按钮：窄屏 5 列两行（144px 高正好放满），宽屏 9 列一行。 */
        const int columns = width()<840 ? 5 : 9;
        const int w = width()/columns;
        for (int i=0;i<9;++i)
            out.push_back({QRect((i%columns)*w+6,height()-touchBarHeight()+8+(i/columns)*68,w-12,60),labels[i],keys[i],-1});
        return out;
    }
    int touchTarget(QPoint pos) const {
        const auto buttons=touchButtons();
        for (int i=0;i<buttons.size();++i) if(buttons[i].rect.contains(pos)) return i;
        if (m_settingsVisible) {
            if(width()<840) {
                for(int row=0;row<8;++row) if(QRect(16,100+row*66,width()-200,62).contains(pos)) return 200+row;
                return -1;
            }
            const double s=std::min(width()/1280.0,height()/720.0);
            const QPointF p=(QPointF(pos)-QPointF((width()-1280*s)/2,(height()-720*s)/2))/s;
            for(int row=0;row<8;++row) if(QRectF(48,162+row*46,390,42).contains(p)) return 200+row;
        }
        if (!m_settingsVisible && !m_videoMode && !m_hdmiFull && m_paneMask==0x3F) {
            const int top=std::min(56,height()/8), h=height()-top-touchBarHeight();
            const double aspect=double(GRID_COLS*IMG_W)/(GRID_ROWS*IMG_H);
            const double w=std::min(double(width()),h*aspect), ch=w/aspect;
            const QRectF content((width()-w)/2,top+(h-ch)/2,w,ch);
            if (content.contains(pos))
                return 100 + std::min(2,int((pos.x()-content.x())*3/w)) + 3*std::min(1,int((pos.y()-content.y())*2/ch));
        }
        return -1;
    }
    void paintTouchButtons(QPainter& painter) {
        painter.save(); painter.resetTransform();
        QFont font; font.setPixelSize(width()<840 ? 16 : 21); font.setBold(true); painter.setFont(font);
        for (const auto& b : touchButtons()) {
            const bool act = b.key == Qt::Key_B && m_birdActive;
            painter.setPen(act ? QColor(255,220,0) : QColor(62,213,199));
            painter.setBrush(act ? QColor(66,51,12) : QColor(22,51,66));
            painter.drawRoundedRect(b.rect,8,8);
            painter.drawText(b.rect.adjusted(4,0,-4,0),Qt::AlignCenter,b.label);
        }
        painter.restore();
    }
    std::function<void(int)> m_cameraHook;
    QPoint m_touchStart;
    int m_touchTarget = -1;
    bool m_touchDragged = false;
    /* C1 的 RGB565（640x480，m_cameraPixels[0]）经 LUT 重映射成俯视图。
       保留 RGB565，只在 C1 的序号或几何代数变化时重映射。 */
    QImage& buildBirdFrame() {
        const auto generation = m_cameraGeometry[0].generation;
        if (m_birdBuilt && m_birdBuiltSequence == m_sequences[0] &&
            m_birdBuiltGeneration == generation) return m_birdImage;
        const int bw = m_birdW, bh = m_birdH;
        if (m_birdImage.width() != bw || m_birdImage.height() != bh ||
            m_birdImage.format() != QImage::Format_RGB16)
            m_birdImage = QImage(bw, bh, QImage::Format_RGB16);
        const QByteArray& src = m_cameraPixels[0];
        // 源图可以是 C1 480P（640x480）或 720P（1280x720）；LUT 与之配套。
        const bool hd = src.size() == 1280 * 720 * 2;
        const int srcW = hd ? 1280 : IMG_W;
        const int srcH = hd ? 720 : IMG_H;
        const qint16* lut = (hd && m_birdLutHd.size() == m_birdLut.size())
                                ? m_birdLutHd.data() : m_birdLut.data();
        const uchar* sp = reinterpret_cast<const uchar*>(src.constData());
        uchar* base = m_birdImage.bits();
        const int stride = m_birdImage.bytesPerLine();
        for (int y = 0; y < bh; ++y) {
            quint16* dp = reinterpret_cast<quint16*>(base + y * stride);
            for (int x = 0; x < bw; ++x, ++dp) {
                const int i = y * bw + x;
                const int sx = lut[i * 2 + 0];
                const int sy = lut[i * 2 + 1];
                if (sx < 0 || sy < 0 || sx >= srcW || sy >= srcH) { *dp = 0; continue; }
                const uchar* p = sp + (size_t(sy) * srcW + size_t(sx)) * 2;
                const quint16 v = quint16(p[0]) | (quint16(p[1]) << 8);
                *dp = v;
            }
        }
        m_birdBuilt = true;
        m_birdBuiltSequence = m_sequences[0];
        m_birdBuiltGeneration = generation;
        return m_birdImage;
    }
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
                const int rowBytes = r.width() * 4;
                const uchar* pixels = image.constScanLine(r.y()) + r.x() * 4;
                // Single rows and complete tightly packed rows are already
                // valid GLES2 upload buffers; only strided subrectangles need packing.
                if (r.height() != 1 && !(r.x() == 0 && rowBytes == image.bytesPerLine())) {
                    QElapsedTimer pack; if (m_perfEnabled) pack.start();
                    const int tileBytes = rowBytes * r.height();
                    if (m_uploadTile.size() < tileBytes) m_uploadTile.resize(tileBytes);
                    for (int row = 0; row < r.height(); ++row)
                        memcpy(m_uploadTile.data() + row * rowBytes,
                               image.constScanLine(r.y() + row) + r.x() * 4, rowBytes);
                    pixels = reinterpret_cast<const uchar*>(m_uploadTile.constData());
                    if (m_perfEnabled) packMs += pack.nsecsElapsed() / 1e6;
                }
                if (m_perfEnabled) {
                    ++m_perf.hudUploadRects; m_perf.hudUploadBytes += uint64_t(r.width()) * r.height() * 4;
                }
                glTexSubImage2D(GL_TEXTURE_2D, 0, r.x(), r.y(), r.width(), r.height(),
                                 GL_RGBA, GL_UNSIGNED_BYTE, pixels);
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
        const int bottom = touchBarHeight();
        const QColor ink(223, 234, 244), muted(144, 166, 187), accent(62, 213, 199);
        painter.fillRect(QRect(0, 0, width(), top), QColor(15, 25, 38));
        painter.fillRect(QRect(0, height() - bottom, width(), bottom), QColor(15, 25, 38));
        const QString title = m_videoMode ? "视频监看" : "摄像头监看";
        painter.drawImage(16, std::max(0, (top - 30) / 2), textImage(title, accent, 13));
        const QString summary = m_captureState != CaptureState::Ready ?
            (m_captureState == CaptureState::Error ? QString("Capture error: ") : QString("Capture switching: ")) + m_captureReason :
            !m_calibrationLine.isEmpty() ?
            (m_calibrationExpiresMs > 0 && monotonicMs() > m_calibrationExpiresMs ?
                QString("单车辆试用 · 旧距离已过期，等待新测量") : m_calibrationLine) : QString("%1 · %2 · 新画面 %3 fps")
            .arg(m_metricsPaused ? "已暂停" : "运行中")
            .arg(m_monitorSummary).arg(newFrameRate(), 0, 'f', 0);
        QFont summaryFont; summaryFont.setPointSize(11);
        const QFontMetrics metrics(summaryFont);
        const QString concise = metrics.elidedText(summary, Qt::ElideRight, qMax(0, width() - 470));
        const QColor summaryColor = m_captureState == CaptureState::Error ? QColor(255, 110, 110) :
            m_captureState == CaptureState::Switching ? QColor(255, 205, 100) : ink;
        painter.drawImage(180, std::max(0, (top - 30) / 2), textImage(concise, summaryColor, 11));
        painter.drawImage(qMax(180, width() - 250), std::max(0, (top - 30) / 2),
                          textImage("Tab  设置  /  监看", accent, 11));
        QString keys = m_help ?
            "Tab 设置   V 切换单路/六路   P 暂停   S 截屏   F 全屏   Q 退出  ·  模型与参数请到设置页" :
            "V 切换相机     F 共享识别     G 六路总览     P 暂停     S 截屏     H 帮助     Tab 设置";
        if (!m_calibrationLine.isEmpty()) keys = "S 保存左右原图并检查棋盘   D 距离标签   V 切相机（C5为第二组）   G 六路   Tab 设置";
        if (qEnvironmentVariableIsSet("DETVIEW_STEREO_TRIAL_METERS"))
            keys = "试用草稿 · 中央ROI光轴深度Z · 请用静止、有纹理目标 · V 切相机   G 六路   Tab 设置   Q 退出";
        if (m_captureState == CaptureState::Error)
            keys = "设备异常 · " + m_captureReason + " · Tab 查看设置";
        keys = metrics.elidedText(keys, Qt::ElideRight, qMax(1, width() - 32));
        if (m_help) painter.drawImage(180, 12, textImage(keys, muted, 11));
        paintTouchButtons(painter);
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
        if (width()<840) {
            painter.fillRect(QRect(QPoint(),size()),QColor(10,18,29));
            const QStringList labels={"模型","画面","置信度阈值","模型轮换","框坐标格式","运行状态","分辨率相机","分辨率"};
            QFont f; f.setPixelSize(22); painter.setFont(f); painter.setPen(QColor(229,237,245));
            painter.drawText(QRect(20,16,width()-230,60),Qt::AlignVCenter,"设置 · 即时生效");
            for(int row=0;row<8;++row) {
                const QRect r(16,100+row*66,width()-32,62);
                painter.fillRect(r,row==m_settingRow ? QColor(22,62,70) : QColor(17,29,44));
                painter.drawText(QRect(28,r.y()+4,width()-224,30),Qt::AlignVCenter,labels[row]);
                painter.drawText(QRect(28,r.y()+30,width()-224,30),Qt::AlignVCenter,
                    QFontMetrics(f).elidedText(m_settingValues.value(row),Qt::ElideRight,width()-224));
            }
            painter.drawText(QRect(24,634,width()-48,60),Qt::TextWordWrap,m_statusLine);
            paintTouchButtons(painter); return;
        }
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
        text(QRect(32, 62, 890, 30), "点按 − / + 调整或切换 · 修改即时生效 · 键盘仍可使用", muted, 16);
        card(QRect(32, 110, 594, 422), "识别与显示");
        const QStringList labels = {"模型", "画面", "置信度阈值", "模型轮换", "框坐标格式", "运行状态", "分辨率相机", "分辨率"};
        const QStringList hints = {"← → 切换模型", "← → C1–C6 / 六路", "← → 每次 5%", "Enter 开关", "Enter 切换", "Enter 暂停 / 继续", "← → C1 / C3 / C4", "− VGA / + 720P"};
        for (int row = 0; row < labels.size(); ++row) {
            const QRect rect(48, 162 + row * 46, 562, 42);
            if (row == m_settingRow) {
                painter.setPen(QColor(62, 213, 199)); painter.setBrush(QColor(22, 62, 70));
                painter.drawRoundedRect(rect, 8, 8);
            }
            text(QRect(62, rect.y() + 7, 154, 30), labels[row], row == m_settingRow ? accent : muted, 17);
            text(QRect(226, rect.y() + 2, 208, 26), m_settingValues.value(row), ink, 18, true);
            const QString hint = row == 2 && m_settingValues.value(row).startsWith("R1") ?
                "固定: P35 V45 Z25 TL35 TS40% · NMS .7 · ± 不调整" :
                row == 4 && m_settingValues.value(row) == "按各模型配置" ?
                "轮换时使用各模型的坐标格式" : hints[row];
            text(QRect(226, rect.y() + 28, 208, 20), hint, muted, 12);
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
        paintTouchButtons(painter);
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
    int m_hudStatsIntervalMs = 1000; // Metrics are one-second rolling rates.
    qint64 m_overlayExpiresMs = 0;
    int m_overlayRow = -1;
    GLuint m_cameraTextures[CAM_COUNT][kTextureRing] = {};
    std::array<int, CAM_COUNT> m_cameraTextureSlot{};
    bool m_cameraTextureAllocated[CAM_COUNT][kTextureRing] = {};
    uint64_t m_cameraTextureGeneration[CAM_COUNT][kTextureRing] = {};
    std::array<runtime_camera::Geometry,CAM_COUNT> m_cameraGeometry{};
    bool m_cam1Hd = false;
    bool m_texAlloc = false;
    bool m_dirty = false;
    bool m_videoMode = false;
    bool m_help = false;
    bool m_settingsVisible = false;
    int m_settingRow = 0, m_settingModelIndex = 0;
    QStringList m_settingValues, m_settingModels;
    QString m_pipelineSummary, m_throughputSummary, m_monitorSummary;
    QString m_calibrationLine;
    qint64 m_calibrationExpiresMs = 0;
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
    /* C1 俯视图（CPU remap LUT，语义与 camview 的 /userdata/c1_bird_lut_i16.bin 一致） */
    QImage m_birdImage;
    bool m_birdBuilt = false, m_birdTextureValid = false;
    quint64 m_birdBuiltSequence = 0, m_birdTextureSequence = 0;
    quint64 m_birdBuiltGeneration = 0, m_birdTextureGeneration = 0;
    bool m_videoTextureAllocated = false;
    GLenum m_videoTextureType = GL_UNSIGNED_BYTE;
    bool m_birdActive = false;
    bool m_birdReady = false;
    int m_birdW = 0, m_birdH = 0;
    std::vector<qint16> m_birdLut;
    std::vector<qint16> m_birdLutHd;   // 720P 版本，加载时由 m_birdLut 换算
    QImage m_stereoPreview;
    QByteArray m_uploadTile;
    QString m_stereoStatus, m_visionLine;

    QHash<QString, QImage> m_textCache;
    QVector<Detection> m_dets;
    QStringList m_classes;
    int m_paneMask = 0x3F, m_pane = 0;
    bool m_cam34Shared = false;
    bool m_hdmiFull = false;   // HDMI 满屏视图（C5+C6 拼合 1280x480 铺满内容区）
    double m_dispFps = 0;
    QVector<double> m_camFps = QVector<double>(CAM_COUNT, 0.0);
    std::array<uint64_t, CAM_COUNT> m_sequences{}, m_uploadedSequences{};
    std::array<qint64, CAM_COUNT> m_capturedMs{};
    std::array<tdm::FrameRate, CAM_COUNT> m_cameraUploadRates;
    quint64 m_videoSequence = 0, m_uploadedVideoSequence = 0;
    qint64 m_videoReceivedMs = 0;
    bool m_metricsPaused = false;
    tdm::FrameRate m_takeRate, m_uploadRate, m_newPaintRate, m_paintRate;
    CaptureState m_captureState = CaptureState::Ready;
    QString m_captureReason;
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
    const QString file = QFileInfo(path).fileName().toLower();
    if(file == "mvp_rk3568_int8.rknn") return "MVP";
    if(file == "mvp_accuracy_round1_rk3568_int8.rknn") return "MVP-R1";
    if(file == "mvp_r2_rk3568_int8.rknn") return "MVP-R2";
    if(file == "spatial_lane_rk3568_int8.rknn") return "MVP-R2+ lane";
    if(file == "mvp_plus_shared_rk3568_fp16.rknn") return "MVP+ UFLD";
    if(file == "lane_ufldv2_480x640_rk3568_fp16.rknn") return "UFLDv2";
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
        m_temporalEnabled = !QCoreApplication::arguments().contains("--no-temporal-filter");
        m_boxFilterDebug = QCoreApplication::arguments().contains("--box-filter-debug");
        m_calibrationMode = qEnvironmentVariableIsSet("DETVIEW_CALIBRATION_CAPTURE");
        m_gl = new DetView();
        m_gl->setGeometry(QGuiApplication::primaryScreen()->geometry());
        m_gl->setKeyHook([this](QKeyEvent *e) { handleKey(e); });
        m_gl->setCameraHook([this](int camera) { if (!m_videoMode) onCamChanged(camera); });
        m_gl->show();

        m_camera = new CameraThread();
        m_camera->enableRawCapture(m_calibrationMode ||
            !qEnvironmentVariable("DETVIEW_NATIVE_720_CAPTURE_DIR").isEmpty());
        if (m_calibrationMode) {
            m_capture = new CalibrationCaptureWorker(this);
            connect(m_capture, &CalibrationCaptureWorker::saved, this,
                [this](int generation, QString path, QString message, bool usable) {
                    fprintf(stderr, "[calibration-capture] generation=%d usable=%d path=%s message=%s\n",
                            generation, int(usable), qPrintable(path), qPrintable(message));
                    if (generation == m_sourceGeneration) m_gl->setCalibrationLine(message);
                });
            m_capture->start();
            m_gl->setCalibrationLine("标定采图 · 6×9内角点 / 28.60mm · 摆好并静止后按 S");
        }
        m_videoMode = !videoSource.isEmpty();
        if (m_videoMode)
            m_camera->setVideoSource(videoSource);
        m_camera->setVideoLoop(QCoreApplication::arguments().contains("--video-loop"));
        m_infer = new InferenceThread();
        m_vision = new VisionPipeline(visionOptions);
        std::function<void(const VisionFrame&)> analysisSink;
        if (!m_calibrationMode) analysisSink = [this](const VisionFrame& frame) { m_vision->submitFrame(frame); };
        m_camera->setVisionSink(visionOptions, std::move(analysisSink));
        connect(m_camera, &CameraThread::displayAvailable, this, [this]() {
            const auto frame = m_camera->takeDisplay();
            if(m_resolutionSwitching || m_resolutionError) return;
            if (frame.generation != m_sourceGeneration || (frame.video && frame.image.isNull())) return;
            m_gl->observeFrame(frame);
            if (frame.video) onImage(frame.image, frame.fps);
            else {
                m_camFps = frame.fps;
                m_lastFrameMs = QDateTime::currentMSecsSinceEpoch();
                m_gl->submitCameras(frame);
                if (m_lastHdmiFull != frame.hdmiFull) {
                    m_lastHdmiFull = frame.hdmiFull;
                    m_gl->setStatusLine(frame.hdmiFull ?
                         "C5 + C6 · HDMI 输入全屏（F 返回六路）" : "已恢复 6 路监视");
                    updateHudLines();
                }
                if (m_labelTimer.elapsed() >= 300) {
                    m_labelTimer.restart();
                    updateHudLines();
                }
            }
        });
        connect(m_camera, &CameraThread::statusMsg, this, [this](QString s) {
            m_gl->setStatusLine(s);
            if (s.startsWith("FATAL:")) QCoreApplication::exit(kRestartExitCode);
        });
        connect(m_infer, &InferenceThread::detectionsReady, this, &DetViewController::onDets);
        connect(m_infer, &InferenceThread::laneMaskReady, this, &DetViewController::onLaneMask);
        connect(m_infer, &InferenceThread::mvpResultReady, this,
                [this](QString path,QImage mask,int generation,quint64 frameId,QVector<Detection> dets,
                       int pointCount,double fps,double ms) {
            if(generation != m_sourceGeneration || m_currentIndex < 0 ||
                m_models[m_currentIndex].path != path) return;
            m_lastLaneMs = monotonicMs();
            m_lastLanePoints = pointCount;
            m_gl->setLaneMask(mask);
            if(m_currentIndex >= 0 && m_models[m_currentIndex].independentUfld) {
                if (m_guiInference) m_vision->inferenceFailed(generation,frameId); // Release GUI scheduler slot.
                m_lastMs = ms;
                m_lastDets = 0;
                m_gl->setDetections({},m_classes);
                updateHudLines();
            } else {
                onDets(path,generation,frameId,dets,fps,ms);
            }
        });
        connect(m_camera,&CameraThread::overviewReady,this,[this](quint64 ticket,unsigned mask){
            if(!RuntimeOverviewBarrier::matches(m_overviewTicket,ticket,mask) || m_resolutionError) return;
            m_overviewTicket=0; m_resolutionSwitching=false;
            m_gl->setCaptureState(DetView::CaptureState::Ready);
            auto action=std::move(m_afterOverviewReady);m_afterOverviewReady={};
            if(action) action();
        });
        connect(m_camera, &CameraThread::resolutionChanged, this, [this](int camera,bool hd,bool ok,QString message) {
            fprintf(stderr,"[resolutionChanged] camera=%d hd=%d ok=%d reason=%s\n",camera+1,int(hd),int(ok),qPrintable(message));
            if(!ok) { m_overviewTicket=0; m_afterOverviewReady={}; }
            m_resolutionSwitching=m_overviewTicket!=0; setResolutionError(!ok &&
                (message.startsWith("FATAL startup sensor") || !message.contains("unavailable")));
            /* F1: a fatal startup sensor failure can never recover in-process
               (the capture thread has already returned). Keep the error page
               up for the grace period, then hand the process back to systemd
               instead of freezing the UI while the unit stays "active". */
            if(!ok && message.startsWith("FATAL startup sensor"))
                QTimer::singleShot(kResolutionErrorGraceMs,this,[this]{
                    if(!m_resolutionError) return;   // a later switch recovered
                    fprintf(stderr,"[recover] fatal startup sensor error not cleared after %d ms -> exit(%d)\n",
                            kResolutionErrorGraceMs,kRestartExitCode);
                    fflush(stderr);
                    QCoreApplication::exit(kRestartExitCode);
                });
            if(runtime_camera::supportsHd(camera)) m_cameraHd[camera]=hd;
            if(m_resolutionError) m_gl->clearResolutionFrame();
            resetVision();
            m_gl->setCaptureState(ok ? DetView::CaptureState::Ready : DetView::CaptureState::Error, message);
            updateHudLines();
            finishQueuedResolution(camera,ok);
        });
        connect(m_camera,&CameraThread::pairModeChanged,this,[this](int mode,bool ok,QString message){
            fprintf(stderr,"[pairModeChanged] mode=%d ok=%d reason=%s\n",mode,int(ok),qPrintable(message));
            m_resolutionSwitching=false;
            m_cameraHd[2]=m_camera->cameraHd(2);m_cameraHd[3]=m_camera->cameraHd(3);
            if(ok)resetVision();
            // Recovered/held-safe pair completions must stop the sequence.
            if(!ok && m_camera->resolutionHeldSafe()) setResolutionError(true);
            if(m_resolutionError) m_gl->clearResolutionFrame();
            finishQueuedResolution(mode>=16?(mode-16)/4:-1,ok);
            m_gl->setCaptureState(ok ? DetView::CaptureState::Ready : DetView::CaptureState::Error,message);updateHudLines();
        });
        connect(m_camera,&CameraThread::resolutionAcceptanceStarted,this,[this](int camera) {
            m_resolutionSwitching=true;
            m_gl->setCaptureState(DetView::CaptureState::Switching,QString("C%1 waiting for fresh frames").arg(camera+1));
            updateHudLines();
        });
        connect(m_infer, &InferenceThread::modelLoaded, this, &DetViewController::onModelLoaded);
        m_guiInference = qEnvironmentVariableIsSet("DETVIEW_GUI_INFERENCE");
        auto submitFrame = [infer=m_infer, vision=m_vision](const VisionFrame& frame) {
            const tdm::InferAge age{frame.frameId, frame.sourceGeneration, frame.camera, frame.tag, frame.capturedMs};
            VisionEvidence::instance().event("inference_request", age);
            if (frame.image.size() != QSize(IMG_W, IMG_H) || frame.image.format() != QImage::Format_RGB888) {
                if (frame.fpgaInput) frame.fpgaInput->complete();
                vision->inferenceFailed(frame.sourceGeneration, frame.frameId);
                return;
            }
            if (frame.fpgaInput) {
                if (frame.fpgaInput->camera != frame.camera || frame.fpgaInput->tag != frame.tag ||
                    frame.fpgaInput->sourceGeneration != frame.sourceGeneration)
                    scheme2Quarantine("RAW/RGB packet identity mismatch");
                tdm::inferAgeEvent("direct_submit", age);
                infer->submit(frame.image, frame.sourceGeneration, frame.frameId, frame.fpgaInput, age);
                return;
            }
            QImage input(MODEL_W, MODEL_H, QImage::Format_RGB888);
            input.fill(QColor(114, 114, 114));
            for (int y = 0; y < IMG_H; ++y)
                memcpy(input.scanLine(y + 80), frame.image.constScanLine(y), IMG_W * 3);
            tdm::inferAgeEvent("direct_submit", age);
            infer->submit(input, frame.sourceGeneration, frame.frameId, {}, age);
        };
        if (m_guiInference) {
            connect(m_vision, &VisionPipeline::inferenceRequested, this, [this, submitFrame](VisionFrame frame) {
                if (frame.sourceGeneration != m_sourceGeneration || m_paused || m_calibrationMode ||
                    (frame.fpgaInput && (monotonicMs() < frame.capturedMs || monotonicMs() - frame.capturedMs > 1000))) {
                    if (frame.fpgaInput) frame.fpgaInput->complete();
                    m_vision->inferenceFailed(frame.sourceGeneration, frame.frameId);
                    return;
                }
                submitFrame(frame);
                if (!scheme2::verify()) m_requestRate.add(monotonicMs());
            });
        } else {
            connect(m_vision, &VisionPipeline::inferenceRequested, m_infer, submitFrame,
                    Qt::DirectConnection);
            connect(m_vision, &VisionPipeline::inferenceRequested, this, [this](VisionFrame frame) {
                if (frame.sourceGeneration == m_sourceGeneration && !scheme2::verify())
                    m_requestRate.add(monotonicMs());
            });
            connect(m_infer, &InferenceThread::observationReady, m_vision,
                    [vision=m_vision](QString model, int generation, quint64 frame,
                                      QVector<Detection> boxes, double ms, bool laneOnly) {
                if (laneOnly) vision->inferenceFailed(generation, frame);
                else vision->submitDetections(model, generation, frame, std::move(boxes), ms);
            }, Qt::DirectConnection);
        }
        connect(m_infer, &InferenceThread::inferenceFailed, m_vision,
            [vision=m_vision](int generation, quint64 frameId) {
                vision->inferenceFailed(generation, frameId);
            }, Qt::DirectConnection);
        connect(m_vision, &VisionPipeline::acceptedDetectorResult, this,
                [this](QString model, int generation, quint64 frameId, QVector<Detection> dets, qint64 acceptedMs) {
            if (generation != m_sourceGeneration || !selectedDetectionModel(model)) return;
            observeBoxes(model, frameId, dets, acceptedMs);
        });
        connect(m_vision, &VisionPipeline::tracksReady, this,
                [this](QString model, int generation, quint64 frameId, QVector<Detection> dets, double ms) {
            if (generation != m_sourceGeneration || !selectedDetectionModel(model)) return;
            if (QCoreApplication::arguments().contains("--tracker-debug") &&
                monotonicMs() - m_trackerDebugMs >= 250) {
                m_trackerDebugMs = monotonicMs();
                QJsonArray boxes;
                int tracked = 0, predicted = 0, raw = 0;
                for (const auto& d : dets) {
                    if (d.trackId) { ++tracked; if (d.predicted) ++predicted; }
                    else ++raw;
                    boxes.append(QJsonObject{{"class", d.cls}, {"id", QString::number(d.trackId)},
                        {"score", double(d.score)}, {"ncc", double(d.matchScore)}, {"predicted", d.predicted},
                        {"x", double(d.x1)}, {"y", double(d.y1 - 80)},
                        {"w", double(d.x2 - d.x1)}, {"h", double(d.y2 - d.y1)},
                        {"ttl_ms", double(d.validUntilMs - m_trackerDebugMs)}});
                }
                const QJsonObject record{{"captured_at_host_ms", double(m_trackerDebugMs)},
                    {"model", QFileInfo(model).fileName()}, {"generation", generation},
                    {"source_frame", QString::number(frameId)}, {"tracked_vehicles", tracked},
                    {"predicted_vehicles", predicted}, {"raw_detections", raw},
                    {"update_ms", ms}, {"boxes", boxes}};
                fprintf(stderr, "[tracker-debug] %s\n", QJsonDocument(record).toJson(QJsonDocument::Compact).constData());
            }
            dets = presentationBoxes(model, dets, monotonicMs());
            if (m_rotationEnabled) {
                m_lastTrackMs = monotonicMs();
                m_results[model] = dets;
                m_resultTime[model] = monotonicMs();
                updateRotationOverlay();
            } else if (m_currentIndex >= 0 && m_models[m_currentIndex].path == model) {
                m_lastTrackMs = monotonicMs();
                m_lastDets = dets.size();
                m_gl->setDetections(dets, m_classes);
            }
            m_trackingMs = ms;
            if (m_visionOptions.stereoVehicleTrial) {
                QString text = "单车辆试用 · 未识别到车辆";
                qint64 expiresMs = 0;
                for (const auto& d : dets) {
                    if (d.depthStatus.isEmpty()) continue;
                    const qint64 age = monotonicMs() - d.depthCapturedMs;
                    if (std::isfinite(d.depthMeters) && d.depthCapturedMs > 0 && age >= 0 && age <= 300) {
                        text = QString("单车辆试用 Z=%1 米 · 检测框ROI · 同步未确认 · 请保持静止")
                            .arg(d.depthMeters, 0, 'f', 2);
                        expiresMs = d.depthCapturedMs + 300;
                        fprintf(stderr, "[vehicle-range] frame=%llu meters=%.4f captured_ms=%lld age_ms=%lld trial=%d cls=%d score=%.3f box=%.1f,%.1f,%.1f,%.1f\n",
                            (unsigned long long)frameId, d.depthMeters, (long long)d.depthCapturedMs, (long long)age,
                            int(d.depthTrial), d.cls, d.score, d.x1, d.y1, d.x2, d.y2);
                    } else text = "单车辆试用 · " + d.depthStatus;
                    break;
                }
                m_gl->setCalibrationLine(text, expiresMs);
            }
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
            if (m_lastLaneMs > 0 && monotonicMs() - m_lastLaneMs > 2000) {
                m_gl->setLaneMask({});
                m_lastLaneMs = 0;
                m_lastLanePoints = 0;
            }
            updateHudLines();
            if (!scheme2::verify() && m_statsTimer.elapsed() >= 5000) {
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
            /* F1: bound the life of a latched resolution error. While
               m_resolutionError is set, displayAvailable() drops every frame
               and watchdogAction() returns Wait, so nothing else can clear it;
               the latch age is therefore also the "no verified frame" age.
               The deliberate operator hold is exempt (m_runtimeHold). */
            if(m_resolutionError && !m_runtimeHold && m_errorSinceMs>0 &&
               QDateTime::currentMSecsSinceEpoch()-m_errorSinceMs>=kResolutionErrorGraceMs) {
                fprintf(stderr,"[recover] resolution error held %d ms without verified frames -> exit(%d)\n",
                        kResolutionErrorGraceMs,kRestartExitCode);
                fflush(stderr);
                QCoreApplication::exit(kRestartExitCode);
                return;
            }
            if (m_lastFrameMs == 0)
                return;
            const qint64 silent = QDateTime::currentMSecsSinceEpoch() - m_lastFrameMs;
            const auto action=cam1::watchdogAction(m_paused,m_resolutionSwitching,m_resolutionError,
                m_camera->cam1Hd(),silent,m_noFrameTimeoutMs);
            if(action==cam1::WatchdogAction::Wait) return;
            if(action==cam1::WatchdogAction::HoldRuntime) {
                // F4/F1: this is the deliberate operator hold (720P no-frame,
                // "automatic restart inhibited"); it must never be expired by
                // the bounded-error timer below.
                m_runtimeHold=true;
                setResolutionError(true);
                resetVision(); m_gl->clearResolutionFrame();
                m_gl->setCaptureState(DetView::CaptureState::Error,"720P no-frame timeout · stopping capture · automatic restart inhibited");
                m_camera->requestRuntimeHold(); updateHudLines(); return;
            }
            fprintf(stderr, "[recover] no new frame for %lld ms -> exit(%d) for supervisor restart\n",
                    (long long)silent,kRestartExitCode);
            fflush(stderr);
            ::_exit(kRestartExitCode);
        });
        watchdog->start(5000);
        if (!m_models.isEmpty())
            onModelChanged(0);
    }
    ~DetViewController() override {
        if (m_capture) { m_capture->stop(); m_capture->wait(); }
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
        if (on) {
            // The window's first showFullScreen() is dropped when it runs before
            // the window is mapped and the WM (xfwm4) has taken it over: the
            // request is lost, QWindow still reports isFullScreen()==true, so a
            // plain repeat is a no-op, and the window keeps its frame at +5+56.
            // Re-assert by toggling state (forces a fresh WM hint), then verify.
            forceFullscreen();
            QTimer::singleShot(0, m_gl, [this] { forceFullscreen(); });
            QTimer::singleShot(400, m_gl, [this] { forceFullscreen(); });
            QTimer::singleShot(1200, m_gl, [this] { forceFullscreen(); });
        } else {
            if (m_gl) m_gl->showNormal();
        }
    }
    // showFullScreen() alone is not re-sent while Qt already believes the window
    // is fullscreen, so drop to normal first. Harmless when already correct.
    void forceFullscreen() {
        if (!m_gl || !m_full) return;
        m_gl->showNormal();
        m_gl->showFullScreen();
    }
    /* 0..5 = C1..C6 单路，CAM_COUNT = 6 路 3x2 */
    void setCameraMode(int mode) {
        if (mode >= 0 && mode <= CAM_COUNT+1)
            onCamChanged(mode);
    }
    /* --prefer-hdmifull：0=off 1=on 2=auto，转发给采集线程 */
    void setHdmiPrefer(int mode) {
        m_hdmiManual = mode == 1;
        m_camera->setHdmiPrefer(mode);
        resetVision();
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
    void setCam1Resolution(bool hd) { m_resolutionCamera=0; if(hd!=m_cameraHd[0]) switchResolution(hd); }
    void setCameraResolution(int camera,bool hd) {
        if(!runtime_camera::supportsHd(camera)) return;
        m_resolutionCamera=camera;
        if(hd!=m_cameraHd[camera]) switchResolution(hd);
    }
    void setCameraResolutions(const QVector<std::pair<int,bool>>& requests) {
        if(m_resolutionSwitching || m_resolutionError || m_720pPending || m_videoMode) return;
        if(m_720pMode) onCamChanged(CAM_COUNT);
        m_resolutionQueue.clear();
        for(const auto& request:requests) m_resolutionQueue.requests.push_back(request);
        applyNextResolution();
    }

private:
    void handleKey(QKeyEvent *e) {
        int k = e->key();
        if(k==Qt::Key_F12) {
            if(!e->isAutoRepeat() && !m_videoMode) onCamChanged(CAM_COUNT+1);
            return;
        }
        if(m_720pPending || !m_resolutionQueue.idle()) {
            if(k!=Qt::Key_Escape && k!=Qt::Key_Q && k!=Qt::Key_Tab && k!=Qt::Key_Backtab) return;
        }
        if(k==Qt::Key_F5 || k==Qt::Key_F6 || k==Qt::Key_F7 || k==Qt::Key_F8 || k==Qt::Key_F9 || k==Qt::Key_F10 || k==Qt::Key_F11) {
            if(m_resolutionSwitching || m_resolutionError || m_videoMode || e->isAutoRepeat())return;
            waitForOverviewReady([this,k]{startPairMode(k);});
            return;
        }
        if((m_resolutionSwitching || m_resolutionError) && k!=Qt::Key_Escape && k!=Qt::Key_Q &&
           k!=Qt::Key_Tab && k!=Qt::Key_Backtab && k!=Qt::Key_S) return;
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
                    if (!m_videoMode) onCamChanged(((m_720pMode?CAM_COUNT+1:m_camMode) + direction + CAM_COUNT + 2) % (CAM_COUNT + 2));
                    return;
                case 2: onConfChanged(m_confPct + direction * 5); return;
                case 3: k = Qt::Key_R; break;
                case 4: k = Qt::Key_C; break;
                case 5: k = Qt::Key_P; break;
                case 6: {
                    const int targets[]={0,2,3,4};
                    const int count=m_camera->c5Supported()?4:3;
                    int index=m_resolutionCamera==0?0:m_resolutionCamera==2?1:m_resolutionCamera==3?2:3;
                    m_resolutionCamera=targets[(index+direction+count)%count];
                    updateHudLines(); return;
                }
                case 7: switchResolution(k==Qt::Key_Return || k==Qt::Key_Enter ? !m_cameraHd[m_resolutionCamera] : direction>0); return;
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
            // 与全屏共用 F：Shift+F 全屏，单按 F 在 HDMI 满屏/6 路间切换
            if (e->modifiers() & Qt::ShiftModifier) {
                setFullscreen(!m_full);
            } else if (!m_videoMode && m_camMode == CAM_COUNT) {
                if (e->isAutoRepeat() || m_calibrationMode) break;
                if (!m_hdmiManual && !m_camera->opticalStreaming()) {
                    m_gl->setStatusLine("C5/C6 no signal: optical link has no fresh frames; HDMI view refused");
                    updateHudLines();
                    break;
                }
                if(m_720pMode) onCamChanged(CAM_COUNT);
                m_hdmiManual = !m_hdmiManual;
                m_camera->setHdmiOverride(m_hdmiManual ? 1 : 0);
                resetVision();
                m_gl->setStatusLine(m_hdmiManual
                    ? "C5 + C6 · HDMI（F 返回六路）"
                    : "6 路监视（F 键 HDMI 满屏）");
                updateHudLines();
            }
            break;
        case Qt::Key_S:
            if (e->isAutoRepeat()) break;
            onScreenshot();
            break;
        case Qt::Key_D:
            if (m_calibrationMode && !e->isAutoRepeat()) {
                m_captureDistance = (m_captureDistance + 1) % 5;
                const double distances[] = {0, .5, 1, 2, 4};
                m_gl->setCalibrationLine(m_captureDistance ? QString("标定采图 · 距离标签 %1m · 静止后按 S").arg(distances[m_captureDistance]) :
                    QString("标定采图 · 距离未指定 · 换位置/倾角，静止后按 S"));
            }
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
            if (!m_videoMode) onCamChanged(((m_720pMode?CAM_COUNT+1:m_camMode) + 1) % (CAM_COUNT + 2));
            break;
        case Qt::Key_G:
            if (!m_videoMode) onCamChanged(CAM_COUNT);
            m_gl->setSettingsVisible(false);
            break;
        case Qt::Key_B:
            if (e->isAutoRepeat()) break;
            onBirdToggle();
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
        if (m_visionOptions.stereoVehicleTrial)
            m_gl->setCalibrationLine("单车辆试用 · 等待新车辆与同帧测距");
        ++m_sourceGeneration;
        m_boxFilters.clear();
        m_boxPresentationAssociations.clear();
        m_boxObservationCounts.clear();
        m_boxSourceFrames.clear();
        m_infer->resetMetrics(m_sourceGeneration);
        m_requestRate.reset(monotonicMs());
        m_gl->resetRates();
        m_resultMs.clear(); m_resultFps.clear();
        m_rotInferFps = m_lastMs = 0;
        m_lastDets = 0;
        QStringList paths;
        QHash<QString, QVector<int>> vehicleClasses;
        bool lane = false;
        if (m_rotationEnabled) {
            for (const auto& model : m_rotation) {
                paths.append(model.path);
                vehicleClasses.insert(model.path, vehicleTrackingClasses(model));
            }
        } else if (m_currentIndex >= 0) {
            paths.append(m_models[m_currentIndex].path);
            lane = m_models[m_currentIndex].lane || m_models[m_currentIndex].independentUfld;
            vehicleClasses.insert(m_models[m_currentIndex].path, vehicleTrackingClasses(m_models[m_currentIndex]));
        }
        const int selected = m_videoMode ? 0 : (m_hdmiManual && m_camMode == CAM_COUNT ?
            tdm::hdmiInferenceCamera : (m_camMode == CAM_COUNT ?
            (m_visionOptions.stereoEnabled() ? m_visionOptions.primaryStereoLeft() : 0) : m_camMode));
        m_vision->configure(m_sourceGeneration, selected, lane, paths, vehicleClasses);
        for (const auto& path : paths) {
            QStringList ids;
            for (int c : vehicleClasses.value(path)) ids << QString::number(c);
            fprintf(stderr, "[tracking-policy] model=%s vehicle_classes=%s interval_ms=%d template_side=%d\n",
                qPrintable(QFileInfo(path).fileName()), qPrintable(ids.isEmpty() ? "none" : ids.join(',')),
                m_visionOptions.trackingIntervalMs, m_visionOptions.maxTemplateSide);
        }
        m_camera->setSourceGeneration(m_sourceGeneration);
        m_results.clear();
        m_resultTime.clear();
        m_gl->setDetections({}, m_classes);
        m_gl->setLaneMask({});
        m_lastStereoMs = m_lastTrackMs = m_lastLaneMs = 0;
        m_lastLanePoints = 0;
        m_gl->setStereoPreview({}, m_visionOptions.stereoEnabled() ? "双目：等待配对帧" : QString());
    }
    /* F1: m_resolutionError is a latch. Watch when it is taken so the watchdog
       can bound its life, and release it as soon as a switch verifies healthy
       again (a successful resolutionChanged calls this with false). */
    void setResolutionError(bool error) {
        if(error && !m_resolutionError) m_errorSinceMs=QDateTime::currentMSecsSinceEpoch();
        if(!error) { m_errorSinceMs=0; m_runtimeHold=false; }
        m_resolutionError=error;
    }
    /* F5: the overview ticket deadline. Reports through the same failure path
       the capture thread would use (CaptureState::Error + HUD) but does not
       latch m_resolutionError: a missing acknowledgement is transient and must
       not freeze the keyboard. */
    void reportOverviewTimeout(quint64 ticket) {
        static const QString reason=QStringLiteral("overview timeout (5 s)");
        m_overviewTicket=0; m_afterOverviewReady={};
        m_resolutionSwitching=false;
        resetVision();
        m_gl->clearResolutionFrame();
        m_gl->setCaptureState(DetView::CaptureState::Error,reason);
        fprintf(stderr,"[overview] ticket=%llu result=failed reason=%s\n",
                (unsigned long long)ticket,qPrintable(reason));
        updateHudLines();
    }
    void waitForOverviewReady(std::function<void()> action) {
        // Do not enqueue a pair operation until the native mask transaction has
        // acknowledged this exact request and restarted all six readers.
        m_720pMode=false; m_camMode=CAM_COUNT; m_hdmiManual=false;
        m_camera->setHdmiOverride(0);m_camera->setMode(CAM_COUNT);
        m_gl->setCameraLayout(CAM_COUNT,m_visionOptions.stereoEnabled()?m_visionOptions.primaryStereoLeft():0);
        m_resolutionSwitching=true;
        m_afterOverviewReady=std::move(action);
        m_overviewTicket=++m_overviewSerial;
        const quint64 ticket=m_overviewTicket;
        m_camera->requestOverviewReady(m_overviewTicket);
        /* F5: if the capture thread is dead or wedged nothing ever acknowledges
           this ticket, m_resolutionSwitching stays true and every key is
           swallowed forever. Bound the wait. */
        QTimer::singleShot(kOverviewTicketTimeoutMs,this,[this,ticket]{
            if(m_overviewTicket!=ticket) return;   // acknowledged meanwhile
            reportOverviewTimeout(ticket);
        });
        m_gl->setCaptureState(DetView::CaptureState::Switching,"Waiting for verified six-camera capture and readers");
        updateHudLines();
    }
    void startPairMode(int k) {
        if(m_resolutionError) return;
        const auto mode=(k==Qt::Key_F5 || k==Qt::Key_F6 || k==Qt::Key_F7)?runtime_camera::Mode::Default:
            k==Qt::Key_F9?runtime_camera::Mode::Hd720:runtime_camera::Mode::FullVga;
        m_resolutionSwitching=true;
        m_gl->setCaptureState(DetView::CaptureState::Switching,"C3/C4 switching; waiting for both banks");
        const bool independent=k==Qt::Key_F5 || k==Qt::Key_F6 || k==Qt::Key_F10 || k==Qt::Key_F11;
        const bool requested=independent?
            m_camera->requestCam34Mode((k==Qt::Key_F5 || k==Qt::Key_F10)?2:3,mode):m_camera->requestCam34Mode(mode);
        if(!requested) {
            m_resolutionSwitching=false;m_gl->setCaptureState(DetView::CaptureState::Error,"C3/C4 mode request unavailable");
        }
    }
    void switchResolution(bool hd) {
        if(m_videoMode || m_resolutionSwitching || m_resolutionError) return;
        if(hd==m_cameraHd[m_resolutionCamera]) return;
        if(m_resolutionCamera==2 || m_resolutionCamera==3 || m_720pMode) {
            const int camera=m_resolutionCamera;
            waitForOverviewReady([this,camera,hd]{m_resolutionCamera=camera;submitResolution(hd);});
            return;
        }
        submitResolution(hd);
    }
    void submitResolution(bool hd) {
        if(m_resolutionError) return;
        m_resolutionSwitching=true;
        m_camera->setPaused(false); m_paused=false; m_gl->setMetricsPaused(false);
        if(!m_camera->requestResolution(m_resolutionCamera,hd)) {
            m_resolutionSwitching=false;
            finishQueuedResolution(m_resolutionCamera,false);
            m_gl->setCaptureState(DetView::CaptureState::Error,"Resolution request unavailable");
            return;
        }
        resetVision();
        m_gl->clearResolutionFrame();
        m_gl->setCaptureState(DetView::CaptureState::Switching,QString("C%1 resolution switching").arg(m_resolutionCamera+1));
        updateHudLines();
    }
    void finishQueuedResolution(int camera,bool ok) {
        const bool advance=m_resolutionQueue.complete(camera,ok);
        if(!ok) { m_720pPending=false; updateHudLines(); }
        if(advance) QTimer::singleShot(0,this,[this]{applyNextResolution();});
    }
    void applyNextResolution() {
        if(m_resolutionSwitching || m_resolutionError || m_resolutionQueue.failed) return;
        const int camera=m_resolutionQueue.next(m_cameraHd);
        if(camera>=0) {
            // next() selected a target different from the committed state.
            setCameraResolution(camera,!m_cameraHd[camera]);
            return;
        }
        if(m_720pPending && m_resolutionQueue.idle()) {
            // Pair admission requires six-camera capture. Keep that gate intact:
            // apply the restricted mask only after every native HD commit.
            if(!m_cameraHd[0] || !m_cameraHd[2] || !m_cameraHd[3]) return;
            m_720pPending=false; m_720pMode=true;
            m_camera->setMode(CAM_COUNT+1);
            resetVision(); m_gl->clearResolutionFrame();
            m_gl->setStatusLine("720p模式 · C1/C3/C4 · C2/C5/C6 停采");
            updateHudLines();
        }
    }

    bool selectedDetectionModel(const QString& path) const {
        if (m_rotationEnabled) {
            for (const auto& model : m_rotation)
                if (model.path == path) return !model.independentUfld;
            return false;
        }
        return m_currentIndex >= 0 && m_currentIndex < m_models.size() &&
            m_models[m_currentIndex].path == path && !m_models[m_currentIndex].independentUfld;
    }

    void observeBoxes(const QString& model, quint64 frameId,
                      const QVector<Detection>& raw, qint64 acceptedMs) {
        // Only distinct accepted detector frames count toward confirmation.
        const auto previous = m_boxSourceFrames.constFind(model);
        if (previous != m_boxSourceFrames.constEnd() && frameId <= previous.value()) return;
        m_boxSourceFrames[model] = frameId;
        const quint64 observations = ++m_boxObservationCounts[model];
        std::vector<Detection> visible(raw.begin(), raw.end());
        if (m_temporalEnabled) {
            // Tracking intentionally samples the detector at a lower cadence.
            // Its visibility must bridge that cadence rather than blink every
            // time the 250ms scheduler interval exceeds the 180ms video grace.
            const qint64 modelCount = m_rotationEnabled ? std::max(1, m_rotation.size()) : 1;
            bool trackingCadence = m_visionOptions.tracking;
            for (const auto& info : m_models)
                if (info.path == model && (info.lane || info.independentUfld)) trackingCadence = false;
            const qint64 holdMs = trackingCadence ?
                std::max<qint64>(180, std::min<qint64>(1500,
                    qint64(m_visionOptions.detectionIntervalMs) * modelCount + 80)) : 180;
            auto filter = m_boxFilters.find(model);
            if (filter == m_boxFilters.end()) {
                tdm::TemporalDetectionFilter<Detection>::Config config;
                config.retentionMs = holdMs;
                config.maximumObservationGapMs = std::max<qint64>(600, holdMs + 180);
                filter = m_boxFilters.emplace(model,
                    tdm::TemporalDetectionFilter<Detection>(config)).first;
            }
            // Give the renderer an expiry even if the camera stops and no
            // subsequent tracksReady callback asks visible() to prune it.
            for (auto& d : visible)
                d.validUntilMs = d.validUntilMs > 0 ?
                    std::min(d.validUntilMs, acceptedMs + holdMs) : acceptedMs + holdMs;
            // Queued worker timestamps can precede the last GUI paint. Use
            // GUI monotonic time for state progression, retaining the worker
            // deadline above so a queued old reply cannot gain extra lifetime.
            visible = filter->second.process(visible, frameId, monotonicMs());
        }
        const int hidden = std::max(0, raw.size() - int(visible.size()));
        if (m_boxFilterDebug) {
            auto boxes = [](const auto& detections) {
                QJsonArray result;
                for (const auto& d : detections)
                    result.append(QJsonObject{{"class", d.cls}, {"score", double(d.score)},
                        {"x1", double(d.x1)}, {"y1", double(d.y1)},
                        {"x2", double(d.x2)}, {"y2", double(d.y2)},
                        {"valid_until_ms", double(d.validUntilMs)}});
                return result;
            };
            const QJsonObject record{{"model", QFileInfo(model).fileName()},
                {"generation", m_sourceGeneration}, {"source_frame", QString::number(frameId)},
                {"accepted_ms", double(acceptedMs)}, {"enabled", m_temporalEnabled},
                {"observed", double(observations)}, {"raw", raw.size()},
                {"visible", int(visible.size())}, {"hidden", hidden},
                {"raw_boxes", boxes(raw)}, {"filtered_boxes", boxes(visible)}};
            fprintf(stderr, "[box-filter] %s\n", QJsonDocument(record).toJson(QJsonDocument::Compact).constData());
        } else if (observations <= 3 || observations % 20 == 0) {
            fprintf(stderr, "[box-filter] model=%s observed=%llu raw=%d visible=%d hidden=%d enabled=%d\n",
                qPrintable(QFileInfo(model).fileName()), (unsigned long long)observations,
                raw.size(), int(visible.size()), hidden, int(m_temporalEnabled));
        }
    }

    static double presentationIou(const Detection& a, const Detection& b) {
        const double w = std::max(0.0, double(std::min(a.x2, b.x2) - std::max(a.x1, b.x1)));
        const double h = std::max(0.0, double(std::min(a.y2, b.y2) - std::max(a.y1, b.y1)));
        const double areaA = std::max(0.0, double(a.x2 - a.x1)) * std::max(0.0, double(a.y2 - a.y1));
        const double areaB = std::max(0.0, double(b.x2 - b.x1)) * std::max(0.0, double(b.y2 - b.y1));
        const double total = areaA + areaB - w * h;
        return total > 0 ? w * h / total : 0;
    }

    QVector<Detection> presentationBoxes(const QString& model,
                                        const QVector<Detection>& candidates, qint64 now) {
        if (!m_temporalEnabled) return candidates;
        const auto filter = m_boxFilters.find(model);
        if (filter == m_boxFilters.end()) return {};
        const auto stable = filter->second.visible(now);
        const auto previous = m_boxPresentationAssociations[model];
        QVector<BoxPresentationAssociation> associations;
        std::vector<bool> previousUsed(size_t(previous.size()), false);
        QVector<Detection> result;
        std::vector<bool> used(size_t(candidates.size()), false);
        for (const auto& observed : stable) {
            if (observed.validUntilMs > 0 && now > observed.validUntilMs) continue;
            int best = -1;
            double bestOverlap = 0.25;
            int binding = -1;
            double bindingOverlap = 0.25;
            for (int i = 0; i < previous.size(); ++i) {
                if (previousUsed[size_t(i)] || previous[i].observed.cls != observed.cls) continue;
                const double overlap = std::max(presentationIou(observed, previous[i].observed),
                                                presentationIou(observed, previous[i].displayed));
                if (overlap >= bindingOverlap) { binding = i; bindingOverlap = overlap; }
            }
            const uint64_t boundTrack = binding >= 0 ? previous[binding].displayed.trackId : 0;
            for (int i = 0; i < candidates.size(); ++i) {
                const auto& candidate = candidates[i];
                if (used[size_t(i)] || candidate.cls != observed.cls ||
                    (candidate.validUntilMs > 0 && now > candidate.validUntilMs)) continue;
                if (boundTrack && candidate.trackId == boundTrack) { best = i; break; }
                const double overlap = presentationIou(observed, candidate);
                if (overlap >= bestOverlap) { best = i; bestOverlap = overlap; }
            }
            Detection display = observed;
            if (best >= 0) {
                used[size_t(best)] = true;
                // Keep live tracker geometry, prediction and depth metadata;
                // neither tracking nor redraws can renew detector visibility.
                display = candidates[best];
                if (observed.validUntilMs > 0)
                    display.validUntilMs = display.validUntilMs > 0 ?
                        std::min(display.validUntilMs, observed.validUntilMs) : observed.validUntilMs;
            }
            result.append(display);
            if (binding >= 0) previousUsed[size_t(binding)] = true;
            associations.append({observed, display});
        }
        m_boxPresentationAssociations[model] = std::move(associations);
        return result;
    }

    void onCamChanged(int index) {
        if(m_resolutionSwitching || m_resolutionError || m_720pPending || !m_resolutionQueue.idle()) return;
        if (index < 0 || index > CAM_COUNT+1 || m_videoMode)
            return;
        const bool native720=index==CAM_COUNT+1;
        m_720pMode=false;
        m_720pPending=native720;
        m_resolutionQueue.clear();
        if(native720) index=CAM_COUNT;
        m_camMode = index;
        m_hdmiManual = false;
        m_camera->setHdmiOverride(0);
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
        if(native720) {
            m_resolutionQueue.requests={{0,true},{2,true},{3,true}};
            waitForOverviewReady([this]{applyNextResolution();});
        }
        updateHudLines();
    }

    /* C1 俯视图开关（工具栏"俯视"按钮 / B 键）。显示层覆盖，不改相机模式。 */
    void onBirdToggle() {
        const bool on = !m_gl->birdActive();
        m_gl->setBirdActive(on);
        if (on && !m_gl->birdActive())
            m_gl->setStatusLine("俯视不可用：需要 C1 为 480P/720P 且 /userdata/c1_bird_lut_i16.bin 存在");
        updateHudLines();
    }

    void onDets(QString modelPath, int sourceGeneration, quint64 frameId,
                QVector<Detection> dets, double fps, double ms) {
        if (sourceGeneration != m_sourceGeneration)
            return;
        if (QCoreApplication::arguments().contains("--tracker-debug")) {
            QJsonArray boxes;
            for (const auto& d : dets) boxes.append(QJsonObject{{"class", d.cls}, {"score", double(d.score)},
                {"x", double(d.x1)}, {"y", double(d.y1 - 80)},
                {"w", double(d.x2 - d.x1)}, {"h", double(d.y2 - d.y1)}});
            const QJsonObject record{{"received_at_host_ms", double(monotonicMs())},
                {"source_frame", QString::number(frameId)}, {"generation", sourceGeneration},
                {"model", QFileInfo(modelPath).fileName()}, {"inference_ms", ms}, {"boxes", boxes}};
            fprintf(stderr, "[detector-debug] %s\n", QJsonDocument(record).toJson(QJsonDocument::Compact).constData());
        }
        if (m_hdmiManual && m_camMode == CAM_COUNT && qEnvironmentVariableIsSet("DETVIEW_CAM34_DETECTION_LOG")) {
            QJsonArray mapped;
            for(const auto& d:dets) {
                const bool right=(d.x1+d.x2)*0.5f>=320.0f;
                const float origin=right?320.0f:0.0f;
                mapped.append(QJsonObject{{"camera",right?4:3},{"class",d.cls},{"score",double(d.score)},
                    {"source_x1",double(std::clamp((d.x1-origin)*2.0f,0.0f,640.0f))},
                    {"source_x2",double(std::clamp((d.x2-origin)*2.0f,0.0f,640.0f))},
                    {"source_y1",double(std::clamp((d.y1-200.0f)*2.0f,0.0f,480.0f))},
                    {"source_y2",double(std::clamp((d.y2-200.0f)*2.0f,0.0f,480.0f))},
                    {"crosses_seam",d.x1<320.0f&&d.x2>320.0f}});
            }
            const QJsonObject row{{"frame",QString::number(frameId)},{"generation",sourceGeneration},{"model",QFileInfo(modelPath).fileName()},{"inference_ms",ms},{"boxes",mapped}};
            fprintf(stderr,"[cam34-detections] %s\n",QJsonDocument(row).toJson(QJsonDocument::Compact).constData());
        }
        if (m_guiInference)
            m_vision->submitDetections(modelPath, sourceGeneration, frameId, dets, ms);
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
        if (m_guiInference) m_vision->inferenceFailed(generation, frameId);
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

    bool round1Selected() const {
        if (m_rotationEnabled) {
            for (const auto& model : m_rotation) if (model.round1Policy.enabled) return true;
            return false;
        }
        return m_currentIndex >= 0 && m_currentIndex < m_models.size() &&
            m_models[m_currentIndex].round1Policy.enabled;
    }

    void onConfChanged(int pct) {
        if (round1Selected()) {
            m_gl->setStatusLine("MVP-R1 类阈值固定: P35 V45 Z25 TL35 TS40%; NMS 0.7 (± 不调整)");
            return;
        }
        m_confPct = std::min(95, std::max(5, pct));
        m_infer->setConf(m_confPct / 100.0f);
        resetVision();
        updateHudLines();
    }

    void onScreenshot() {
        if(m_resolutionSwitching) { QTimer::singleShot(500,this,[this]{onScreenshot();}); return; }
        if(!qEnvironmentVariable("DETVIEW_NATIVE_720_CAPTURE_DIR").isEmpty()) {
            captureNative720(); return;
        }
        if(m_resolutionError || (std::any_of(m_cameraHd.begin(),m_cameraHd.end(),[](bool hd){return hd;}) && m_calibrationMode)) {
            m_gl->setStatusLine("Calibration unavailable while switching or in 720P"); return;
        }
        if (m_calibrationMode) { captureCalibration(); return; }
        const QPixmap pm = QPixmap::fromImage(m_gl->grabFrame());
        if (pm.isNull()) {
            m_gl->setStatusLine("截屏失败: 无画面");
            return;
        }
        const QString dir = "/userdata/detview_shots";
        QDir().mkpath(dir);
        // F6: keep the directory bounded. One slot is reserved for the file
        // about to be written, so at most kShotKeep shots ever remain.
        pruneShots(dir, kShotKeep - 1);
        const QString model = (m_currentIndex >= 0 && m_currentIndex < m_models.size())
                                  ? QFileInfo(m_models[m_currentIndex].path).completeBaseName()
                                  : QString("model");
        // F6: millisecond granularity - two shots within the same second used
        // to collide and overwrite each other.
        const QString ts = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss_zzz");
        QString path = QString("%1/shot_%2_%3.png").arg(dir).arg(model).arg(ts);
        if (!saveShotAtomic(pm, path, "PNG")) {
            path = QString("%1/shot_%2_%3.jpg").arg(dir).arg(model).arg(ts);
            if (!saveShotAtomic(pm, path, "JPG")) {
                m_gl->setStatusLine("截屏保存失败");
                return;
            }
        }
        m_gl->setStatusLine(QString("已保存: %1  (%2x%3)").arg(path).arg(pm.width()).arg(pm.height()));
    }
    void captureNative720() {
        if(m_videoMode || m_paused || m_resolutionError || m_resolutionSwitching ||
           m_720pPending || !m_resolutionQueue.idle()) {
            m_gl->setStatusLine("720P采图失败：等待切换完成并恢复实时采集");return;
        }
        // This owning mailbox contains source pixels, before display/analytics
        // transforms. Copying it retains both buffers throughout file encoding.
        const auto frame=m_camera->rawSnapshot();
        const qint64 now=monotonicMs();
        const int partner=qEnvironmentVariableIntValue("DETVIEW_NATIVE_720_PARTNER")==4?3:2;
        for(int c:{0,partner}) {
            const auto& g=frame.geometries[c];
            if(frame.generation!=m_sourceGeneration || frame.cameraGenerations[c]!=m_sourceGeneration ||
               !g.valid() || g.camera!=c || g.mode!=runtime_camera::Mode::Hd720 ||
               g.width!=1280 || g.height!=720 || g.stride!=2560 ||
               uint32_t(frame.cameraPixels[c].size())!=g.pixelBytes || !frame.cameraSequences[c] ||
               frame.rawCapturedMs[c]<=0 || now<frame.rawCapturedMs[c] || now-frame.rawCapturedMs[c]>500) {
                m_gl->setStatusLine(QString("720P采图失败：等待 C%1 的1280×720原始新帧").arg(c+1));
                fprintf(stderr,"[native720-capture] result=waiting camera=%d\n",c+1);return;
            }
        }
        const qint64 skew=qAbs(frame.rawCapturedMs[0]-frame.rawCapturedMs[partner]);
        if(skew>100) {
            m_gl->setStatusLine(QString("720P采图失败：C1/C%1帧时间差超过100ms，请重试").arg(partner+1));return;
        }
        const QString root=qEnvironmentVariable("DETVIEW_NATIVE_720_CAPTURE_DIR");
        QDir().mkpath(root);
        const QString name="capture_"+QDateTime::currentDateTimeUtc().toString("yyyyMMddTHHmmsszzzZ");
        QDir dir(root);
        if(!dir.mkdir(name)) {m_gl->setStatusLine("720P采图目录创建失败");return;}
        const QString path=dir.filePath(name);
        QJsonArray cameras;
        for(int c:{0,partner}) {
            const auto& g=frame.geometries[c];
            const QString stem=QString("C%1_1280x720").arg(c+1);
            const QImage image(reinterpret_cast<const uchar*>(frame.cameraPixels[c].constData()),
                               1280,720,2560,QImage::Format_RGB16);
            QFile raw(path+"/"+stem+".rgb565");
            if(!raw.open(QIODevice::WriteOnly) || raw.write(frame.cameraPixels[c])!=frame.cameraPixels[c].size() ||
               !raw.flush() || !image.save(path+"/"+stem+".png","PNG")) {
                m_gl->setStatusLine("720P原图写入失败：该组数据不完整");return;
            }
            cameras.append(QJsonObject{{"camera",c+1},{"width",1280},{"height",720},{"stride",2560},
                {"format","RGB565 little-endian"},{"png",stem+".png"},{"raw",stem+".rgb565"},
                {"sequence",QString::number(frame.cameraSequences[c])},{"tag",QString::number(frame.tags[c])},
                {"geometry_generation",QString::number(g.generation)},
                {"raw_captured_ms",double(frame.rawCapturedMs[c])},
                {"raw_sha256",QString::fromLatin1(QCryptographicHash::hash(frame.cameraPixels[c],QCryptographicHash::Sha256).toHex())}});
        }
        QFile manifest(path+"/capture.json");
        const QJsonObject metadata{{"source_generation",m_sourceGeneration},{"requested_ms",double(now)},
            {"host_timestamp_skew_ms",double(skew)},{"hardware_synchronized",false},
            {"note","Native source pixels, no overlays/remap/resize. Host timestamps do not prove simultaneous exposure; keep checkerboard stationary."},
            {"cameras",cameras}};
        const QByteArray data=QJsonDocument(metadata).toJson();
        if(!manifest.open(QIODevice::WriteOnly) || manifest.write(data)!=data.size() || !manifest.flush()) {
            m_gl->setStatusLine("720P采图元数据保存失败：该组数据不可用");return;
        }
        fprintf(stderr,"[native720-capture] result=saved path=%s skew_ms=%lld\n",qPrintable(path),(long long)skew);
        m_gl->setStatusLine(QString("已保存 C1/C%1 720P原图：%2").arg(partner+1).arg(path));
    }
    void captureCalibration() {
        if (m_videoMode || m_paused || !m_capture) {
            m_gl->setCalibrationLine("采图失败：请恢复实时相机画面"); return;
        }
        const int selected = m_camMode == CAM_COUNT ? m_visionOptions.primaryStereoLeft() : m_camMode;
        const auto pairs = m_visionOptions.stereoPairs();
        auto pair = std::find_if(pairs.begin(), pairs.end(), [selected](const StereoPairOptions& p) {
            return p.left == selected || p.right == selected;
        });
        if (pair == pairs.end()) { m_gl->setCalibrationLine("请选择 C1/C2 或 C5/C6 后采图"); return; }
        const auto snapshot = m_camera->rawSnapshot();
        const qint64 now = monotonicMs();
        for (int camera : {pair->left, pair->right}) {
            if (snapshot.generation != m_sourceGeneration || snapshot.cameraGenerations[camera] != m_sourceGeneration ||
                snapshot.cameraPixels[camera].size() != FRAME_BYTES || snapshot.rawCapturedMs[camera] <= 0 ||
                now < snapshot.rawCapturedMs[camera] || now - snapshot.rawCapturedMs[camera] > 500) {
                m_gl->setCalibrationLine("采图失败：等待所选双目两路新帧"); return;
            }
        }
        const std::pair<quint64, quint64> identity{snapshot.cameraSequences[pair->left], snapshot.cameraSequences[pair->right]};
        const int pairKey = pair->left * CAM_COUNT + pair->right;
        if (m_captureSequences.contains(pairKey) && m_captureSequences[pairKey] == identity) {
            m_gl->setCalibrationLine("采图失败：这对帧已保存，请等待新帧"); return;
        }
        auto image = [&](int c) {
            return QImage(reinterpret_cast<const uchar*>(snapshot.cameraPixels[c].constData()), IMG_W, IMG_H,
                          IMG_W * 2, QImage::Format_RGB16).convertToFormat(QImage::Format_RGB888);
        };
        CalibrationCaptureJob job;
        job.left = image(pair->left); job.right = image(pair->right);
        job.leftCamera = pair->left; job.rightCamera = pair->right; job.generation = m_sourceGeneration;
        job.leftSequence = identity.first; job.rightSequence = identity.second;
        job.leftTag = snapshot.tags[pair->left]; job.rightTag = snapshot.tags[pair->right];
        job.leftCapturedMs = snapshot.rawCapturedMs[pair->left]; job.rightCapturedMs = snapshot.rawCapturedMs[pair->right];
        job.requestedMs = now;
        const double distances[] = {0, .5, 1, 2, 4}; job.distanceMeters = distances[m_captureDistance];
        job.outputRoot = qEnvironmentVariable("DETVIEW_CALIBRATION_DIR", "/userdata/detview_calibration");
        job.synchronizationConfirmed = pair->synchronizationConfirmed; job.hasTagOffset = pair->hasTagOffset;
        job.tagOffset = pair->tagOffset;
        if (!m_capture->submit(std::move(job))) { m_gl->setCalibrationLine("正在保存上一对图，请稍候"); return; }
        m_captureSequences[pairKey] = identity;
        m_gl->setCalibrationLine(QString("C%1/C%2 保存原图并检测54个内角点…").arg(pair->left + 1).arg(pair->right + 1));
    }

    QString camModeText() const {
        if(m_720pPending) return QString("720p模式 · 切换中");
        if(m_720pMode) return QString("720p模式 · C1/C3/C4");
        if (m_camMode >= CAM_COUNT)
            return m_hdmiManual ? QString("HDMI · C5/C6") : QString("6 路 3x2");
        return QString("C%1").arg(m_camMode + 1);
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
            modelLine = QString("模型: %1").arg(shortModelName(info.path));
            if (m_lastMs > 0)
                modelLine += QString("   处理 %1 ms  %2").arg(m_lastMs, 0, 'f', 1)
                    .arg(info.independentUfld ? QString("lane points") :
                         (info.lane ? QString("lane mask") : QString("检测 %1").arg(m_lastDets)));
            if(info.sharedUfld || info.independentUfld) modelLine += QString("  车道点 %1").arg(m_lastLanePoints);
        }
        if (m_temporalEnabled && (m_rotationEnabled || (m_currentIndex >= 0 &&
            !m_models[m_currentIndex].independentUfld &&
            (!m_models[m_currentIndex].lane || m_models[m_currentIndex].sharedUfld))))
            modelLine += "  框稳定 3次确认";
        m_gl->setModelLine(modelLine);
        const bool fixedR1 = round1Selected();
        const QString confText = fixedR1 ? QString("R1 person .35 vehicle .45 zebra .25 TL .35 TS .40 / NMS .7") :
            QString("conf %1").arg(m_confPct / 100.0, 0, 'f', 2);
        m_gl->setConfLine(QString("%1 | %2 | %3 | 新画面 %4 fps | NPU 请求 %5 / 完成 %6 fps")
                              .arg(camModeText())
                               .arg(confText)
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
        const QString pipeline = QString("%1\n%2\n%3\n%4")
            .arg(m_visionOptions.tracking ? QString("仅车辆模板追踪 · 检测间隔 %1 ms").arg(m_visionOptions.detectionIntervalMs) :
                                           QString("逐帧 NPU 检测"))
            .arg(m_visionOptions.tracking ? QString("最多 %1 辆 · 有效期 %2 ms · 追踪间隔 %3 ms")
                    .arg(m_visionOptions.maxTracks).arg(m_visionOptions.trackingMaxDetectionAgeMs)
                    .arg(m_visionOptions.trackingIntervalMs) :
                    QString("模板追踪已关闭"))
              .arg(stereoDescriptions.isEmpty() ? QString("双目测距未启用") : stereoDescriptions.join("；"))
              .arg(QString("运动抽帧 %1 · 整帧上限 %2 FPS · 元数据不可用时常规推理")
                  .arg(m_visionOptions.motionEnabled ? "开启" : "关闭")
                  .arg(qEnvironmentVariableIsSet("DETVIEW_CAPTURE_MAX_FPS") ?
                      qBound(0,qEnvironmentVariableIntValue("DETVIEW_CAPTURE_MAX_FPS"),120) : 30));
        const QString throughput = QString("NPU 请求 %1 / 完成 %2 次/秒\n处理 %3 ms · 追踪 %4 ms")
            .arg(m_requestRate.rate(monotonicMs()), 0, 'f', 0).arg(npu.completed, 0, 'f', 0)
            .arg(m_lastMs, 0, 'f', 1).arg(m_trackingMs, 0, 'f', 1);
        m_gl->setSettings({activeModel, m_videoMode ? "视频源" : camModeText(),
                            fixedR1 ? QString("R1 类阈值固定") : QString("%1 %").arg(m_confPct), rotation,
                           m_rotationEnabled ? "按各模型配置" : (m_xyxy ? "xyxy" : "cxcywh"),
                            m_paused ? "已暂停" : "运行中", QString("C%1").arg(m_resolutionCamera+1),
                            m_resolutionSwitching ? "Switching…" : (m_resolutionError ? "Error · capture stopped" :
                                (m_cameraHd[m_resolutionCamera] ? "1280×720 · analytics off" : ((m_resolutionCamera==0 || m_resolutionCamera==4)?"VGA · 640×480":"VGA · 320×240")))},
                          modelNames, m_currentIndex, pipeline, throughput, monitor);
    }

    QVector<ModelInfo> m_models;
    QStringList m_classes;
    QVector<ModelInfo> m_rotation, m_rotationSelection;
    bool m_rotationEnabled = false;
    bool m_resolutionSwitching=false, m_resolutionError=false;
    qint64 m_errorSinceMs=0;   // F1: when the error latch was taken (0 = clear)
    bool m_runtimeHold=false;  // F1/F4: deliberate operator hold must never auto-exit
    std::array<bool,CAM_COUNT> m_cameraHd{};
    int m_resolutionCamera=0;
    RuntimeResolutionQueue m_resolutionQueue;
    quint64 m_overviewTicket=0,m_overviewSerial=0;
    std::function<void()> m_afterOverviewReady;
    bool m_720pMode=false, m_720pPending=false;
    int m_currentIndex = -1;
    QHash<QString, QVector<Detection>> m_results;
    std::map<QString, tdm::TemporalDetectionFilter<Detection>> m_boxFilters;
    struct BoxPresentationAssociation { Detection observed; Detection displayed; };
    QHash<QString, QVector<BoxPresentationAssociation>> m_boxPresentationAssociations;
    QHash<QString, quint64> m_boxObservationCounts, m_boxSourceFrames;
    bool m_temporalEnabled = true, m_boxFilterDebug = false, m_guiInference = false;
    QHash<QString, qint64> m_resultTime;
    QHash<QString, double> m_resultMs;
    QHash<QString, double> m_resultFps;
    int m_visibleDets = 0;
    int m_lastLanePoints = 0;
    double m_rotInferFps = 0;
    tdm::FrameRate m_requestRate;
    int m_sourceGeneration = 0;
    bool m_xyxy = false;
    int m_confPct = 25;      /* 与 InferenceThread 默认 conf 一致 */
    int m_camMode = CAM_COUNT;
    bool m_lastHdmiFull = false;   // 与最近一帧 DisplayFrame.hdmiFull 对齐（HUD 文案用）
    bool m_hdmiManual = false;     // F 键手动 HDMI 满屏（remote XTest 亦可触发）
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
    bool m_calibrationMode = false;
    int m_captureDistance = 0;
    CalibrationCaptureWorker* m_capture = nullptr;
    QHash<int, std::pair<quint64, quint64>> m_captureSequences;
    double m_trackingMs = 0;
    qint64 m_trackerDebugMs = 0;
    qint64 m_lastStereoMs = 0, m_lastTrackMs = 0, m_lastLaneMs = 0;
};

#ifdef DETVIEW_RUNTIME_TEST_ONLY
// Dedicated hardware-free executable: no controller, workers or driver opens.
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);
    return DetView::selfTestTouch() && DetView::selfTestRefresh() &&
        DetView::selfTestResolutionDisplay() && CameraThread::selfTestDisplay() ? 0 : 1;
}
#else
int main(int argc, char **argv) {
    // Run the same fake-board tests as the standalone executable before Qt,
    // environment verification, controller construction or driver access.
    for(int i=1;i<argc;++i)
        if(std::strcmp(argv[i],"--c5-runtime-selftest")==0) return c5_test::run();
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--fpga-infer-verify") == 0) qputenv("DETVIEW_FPGA_INFER_VERIFY", "1");
        if (std::strcmp(argv[i], "--fpga-infer-verify-count") == 0 && i + 1 < argc)
            qputenv("DETVIEW_FPGA_INFER_VERIFY_COUNT", argv[++i]);
    }
    if (scheme2::verify()) {
        if (!scheme2::enabled()) {
            fprintf(stderr, "[scheme2-verify] ERROR requires DETVIEW_FPGA_INFER_RGB=1\n");
            return 2;
        }
        fprintf(stderr, "[scheme2-verify] ENABLED required_count=%u native_exact=1 decoder_want_float=1 performance_sample=0\n", scheme2::verifyCount());
        qunsetenv("DET_BENCH");
    }
    // Avoid Qt's extra deferred-update delay for the live camera display.
    // Keep an explicit environment override for comparison or other displays.
    if (!qEnvironmentVariableIsSet("QT_QPA_UPDATE_IDLE_TIME"))
        qputenv("QT_QPA_UPDATE_IDLE_TIME", "0");
    fprintf(stderr, "[display-config] update_idle_ms=%s texture_ring=%d publish_min_ms=%d hud_stats_ms=%d\n",
            qgetenv("QT_QPA_UPDATE_IDLE_TIME").constData(),
            qEnvironmentVariableIsSet("DETVIEW_TEXTURE_RING") ?
                qBound(1, qEnvironmentVariableIntValue("DETVIEW_TEXTURE_RING"), 3) : 1,
            qEnvironmentVariableIsSet("DETVIEW_MIN_MS") ?
                std::max(0, qEnvironmentVariableIntValue("DETVIEW_MIN_MS")) : 24,
            qEnvironmentVariableIsSet("DETVIEW_HUD_STATS_MS") ?
                qBound(100, qEnvironmentVariableIntValue("DETVIEW_HUD_STATS_MS"), 5000) : 1000);
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
    if (app.arguments().contains("--stereo-vehicle-trial")) {
        qputenv("DETVIEW_STEREO_VEHICLE_TRIAL", "1");
        qputenv("DETVIEW_STEREO_TRIAL_METERS", "1");
    }
    if (app.arguments().contains("--stereo-trial-meters")) qputenv("DETVIEW_STEREO_TRIAL_METERS", "1");
    if (app.arguments().contains("--calibration-capture")) qputenv("DETVIEW_CALIBRATION_CAPTURE", "1");
    qRegisterMetaType<QVector<Detection>>("QVector<Detection>");
    /* frameReady 跨线程带每路采集帧率：不注册这个类型，Qt 会丢掉整个排队信号
       （表现就是“显示 0.0 fps、无每路标签、画面不动”，推理却照常跑） */
    qRegisterMetaType<QVector<double>>("QVector<double>");
    qRegisterMetaType<VisionFrame>("VisionFrame");
    cv::setNumThreads(2);
    if (app.arguments().contains("--temporal-selftest")) return tdm::runDetectionTemporalSelfTest();
    if (app.arguments().contains("--touch-selftest")) return DetView::selfTestTouch() ? 0 : 1;
    if (app.arguments().contains("--calibration-capture-selftest")) return runCalibrationCaptureSelfTest();
    if (app.arguments().contains("--tracker-benchmark")) {
        const auto benchmarkArgs = app.arguments();
        const int capAt = benchmarkArgs.indexOf("--track-template-side");
        bool valid = true;
        const int cap = capAt < 0 ? 48 : capAt + 1 < benchmarkArgs.size() ? benchmarkArgs[capAt + 1].toInt(&valid) : -1;
        if (!valid || (cap != 0 && (cap < 16 || cap > 128))) {
            fprintf(stderr, "--track-template-side requires 0 or 16..128\n"); return 2;
        }
        return tdm::runTrackerBenchmark(cap);
    }
    if (app.arguments().contains("--vision-selftest")) {
        const bool ok = runCalibrationCaptureSelfTest() == 0 && selfTestVehiclePolicy() && CameraThread::selfTestDisplay() && DetView::selfTestRefresh() && tdm::runTrackerSelfTest() == 0 &&
                        tdm::runCameraDmaSelfTest() == 0 && runFrameMetricsSelfTest() == 0 &&
                         tdm::runHdmiViewSelfTest() == 0 &&
                         runMotionPolicySelfTest() == 0 &&
                         VisionPipeline::selfTest();
        fprintf(stderr, ok ? "VISION_SELFTEST_PASS\n" : "VISION_SELFTEST_FAIL\n");
        return ok ? 0 : 2;
    }
    if (app.arguments().contains("--dfl-selftest")) {
        const bool ok = InferenceThread::selfTestDfl() && InferenceThread::selfTestDfl(8, 29);
        fprintf(stderr, ok ? "DFL_SELFTEST_PASS\n" : "DFL_SELFTEST_FAIL\n");
        return ok ? 0 : 2;
    }
    if (app.arguments().contains("--trafficlight-selftest")) {
        const bool geometryOk = tdm::runInferenceGeometrySelfTest() == 0;
        const bool decoderOk = InferenceThread::selfTestTrafficlight();
        fprintf(stderr, geometryOk && decoderOk ? "TRAFFICLIGHT_SELFTEST_PASS\n" : "TRAFFICLIGHT_SELFTEST_FAIL\n");
        return geometryOk && decoderOk ? 0 : 2;
    }
    if(app.arguments().contains("--cam34-six-selftest"))return cam34::runSixDisplaySelfTest();
    if (app.arguments().contains("--camera-dma-selftest")) return tdm::runCameraDmaSelfTest();
    if (app.arguments().contains("--motion-policy-selftest")) return runMotionPolicySelfTest();
    if (app.arguments().contains("--cam1-runtime-selftest")) return runCam1RuntimeSelfTest();
    if (app.arguments().contains("--frame-metrics-selftest")) return runFrameMetricsSelfTest();
    if (app.arguments().contains("--wire-guard-selftest")) return selfTestC34WireGuard() ? 0 : 1;
    if (app.arguments().contains("--hdmi-selftest") || app.arguments().contains("--cam34-selftest")) return tdm::runHdmiViewSelfTest();
    if (app.arguments().contains("--mvp-round1-selftest")) {
        const bool metadata = selfTestRound1Metadata();
        const bool decoder = InferenceThread::selfTestRound1();
        return metadata && decoder ? 0 : 1;
    }
    if (app.arguments().contains("--mvp-selftest")) {
        const int points = mvp::runSelfTest();
        const bool dfl = InferenceThread::selfTestMvp();
        const bool round1 = InferenceThread::selfTestRound1();
        const bool metadata = selfTestRound1Metadata();
        return points == 0 && dfl && round1 && metadata ? 0 : 1;
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
    if (args.contains("--video-loop") && (videoSource.isEmpty() || videoSource.contains("://") ||
                                          videoSource.startsWith("/dev/video"))) {
        fprintf(stderr, "--video-loop requires a local video file\n"); return 2;
    }
    if (!videoSource.isEmpty() && !videoSource.contains("://") && !videoSource.startsWith("/dev/video") &&
        !QFileInfo(videoSource).isFile()) {
        fprintf(stderr, "video source file does not exist: %s\n", qPrintable(videoSource)); return 2;
    }
    int hdmiPrefer = 1;   // --prefer-hdmifull：0=off 1=on 2=auto（默认）
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
        visionOptions.tracking = !args.contains("--no-tracking") && !args.contains("--calibration-capture");
        visionOptions.stereoTrialMeters = args.contains("--stereo-trial-meters");
        visionOptions.stereoVehicleTrial = args.contains("--stereo-vehicle-trial");
        if (visionOptions.stereoVehicleTrial) visionOptions.stereoTrialMeters = true;
        visionOptions.detectionIntervalMs = integerOption("--detect-interval-ms", 250);
        visionOptions.motionEnabled = args.contains("--motion-gating") ||
            (!args.contains("--no-motion-gating") && qgetenv("DETVIEW_MOTION_GATING") != "0");
        visionOptions.motionRefreshIntervalMs = integerOption("--motion-refresh-ms", 250);
        visionOptions.minimumDetectionIntervalMs = integerOption("--detect-min-ms", 100);
        if (visionOptions.motionRefreshIntervalMs < 100 || visionOptions.motionRefreshIntervalMs > 500 ||
            (visionOptions.motionEnabled && (visionOptions.minimumDetectionIntervalMs < 100 ||
                                             visionOptions.minimumDetectionIntervalMs > 250)))
            throw std::invalid_argument("Motion refresh must be 100..500ms; motion detection minimum must be 100..250ms");
        fprintf(stderr, "[motion-policy] enabled=%d refresh_ms=%d tracking=%d default_capture_max_fps=60\n",
            visionOptions.motionEnabled, visionOptions.motionRefreshIntervalMs, visionOptions.tracking);
        visionOptions.maxTracks = integerOption("--max-tracks", 12);
        visionOptions.trackingMaxDetectionAgeMs = integerOption("--track-max-age-ms", 2000);
        visionOptions.trackingIntervalMs = integerOption("--track-interval-ms", 33);
        visionOptions.maxTemplateSide = integerOption("--track-template-side", 48);
        visionOptions.stereoIntervalMs = integerOption("--stereo-interval-ms", 200);
        visionOptions.stereoDisparities = integerOption("--stereo-disparities", 32);
        if (visionOptions.detectionIntervalMs < 50 || visionOptions.detectionIntervalMs > 2000 ||
            visionOptions.minimumDetectionIntervalMs < 50 ||
            visionOptions.minimumDetectionIntervalMs > visionOptions.detectionIntervalMs ||
            visionOptions.maxTracks < 1 || visionOptions.maxTracks > 12 ||
            visionOptions.trackingMaxDetectionAgeMs < 500 || visionOptions.trackingMaxDetectionAgeMs > 10000 ||
            visionOptions.trackingIntervalMs < 0 || visionOptions.trackingIntervalMs > 200 ||
            (visionOptions.maxTemplateSide != 0 && (visionOptions.maxTemplateSide < 16 || visionOptions.maxTemplateSide > 128)) ||
            visionOptions.stereoIntervalMs < 100 || visionOptions.stereoIntervalMs > 5000 ||
            visionOptions.stereoDisparities < 16 || visionOptions.stereoDisparities % 16 ||
            visionOptions.stereoDisparities > 128)
            throw std::invalid_argument("Invalid tracking/stereo timing, track count or disparity range");
        /* --prefer-hdmifull [on|off|auto]：裸参数视为 on。on=6 路布局下强制
           HDMI 视图及完整画面识别；auto=等待 F 明确选择（接收端没有模式信号）；
           off=完全保持原有视图逻辑。 */
        const int hdmiArg = args.indexOf("--prefer-hdmifull");
        if (hdmiArg >= 0) {
            const QString value = hdmiArg + 1 < args.size() && !args[hdmiArg + 1].startsWith("--")
                                      ? args[hdmiArg + 1] : QStringLiteral("on");
            if (value == QLatin1String("on")) hdmiPrefer = 1;
            else if (value == QLatin1String("off")) hdmiPrefer = 0;
            else if (value == QLatin1String("auto")) hdmiPrefer = 2;
            else throw std::invalid_argument("--prefer-hdmifull requires on|off|auto");
        }
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
    const int resolutionArg=args.indexOf("--cam1-resolution");
    if(resolutionArg>=0 && (resolutionArg+1>=args.size() ||
       (args[resolutionArg+1]!="480" && args[resolutionArg+1]!="720") || !videoSource.isEmpty())) {
        fprintf(stderr,"--cam1-resolution requires 480 or 720 and FPGA camera source\n"); return 2;
    }
    QVector<std::pair<int,bool>> resolutionRequests;
    if(resolutionArg>=0) resolutionRequests.append({0,args[resolutionArg+1]=="720"});
    const int multiResolutionArg=args.indexOf("--camera-resolution");
    if(multiResolutionArg>=0) {
        if(multiResolutionArg+1>=args.size() || !videoSource.isEmpty() || resolutionArg>=0) {
            fprintf(stderr,"--camera-resolution requires C1=480,C3=720,C4=720 and FPGA source; cannot combine with --cam1-resolution\n");return 2;
        }
        unsigned targets=0;
        for(const QString& specification:args[multiResolutionArg+1].split(',')) {
            const auto fields=specification.toUpper().split('=');
            const int camera=fields.size()==2?(fields[0]=="C1"?0:fields[0]=="C3"?2:fields[0]=="C4"?3:fields[0]=="C5"?4:-1):-1;
            if(camera<0 || (fields[1]!="480" && fields[1]!="720") || (targets & (1u<<camera))) {
                fprintf(stderr,"--camera-resolution entries must be unique C1/C3/C4/C5=480/720\n");return 2;
            }
            targets|=1u<<camera;resolutionRequests.append({camera,fields[1]=="720"});
        }
    }
    // F2: install before any worker/driver state exists so that
    // `systemctl stop/restart` reaches the normal destructors and the
    // VGA/pair restore teardown runs instead of the process being killed.
    installTermHandlers(&app);
    DetViewController w(models, videoSource, visionOptions);
    w.setHdmiPrefer(hdmiPrefer);
    if(!resolutionRequests.isEmpty()) w.setCameraResolutions(resolutionRequests);
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
#endif

#include "main.moc"
