#include <QByteArray>
#include <QMutex>
#include <QMutexLocker>
#include <QImage>
#include <QVector>
#include <QCoreApplication>
#include <array>
#include <atomic>
#include <memory>
#include <cstdio>
#include "vision_types.h"
#include "hdmi_view.h"
#include "thumbnail_delivery.h"
constexpr int CAM_COUNT = 6, FRAME_BYTES = 640 * 480 * 2;
static qint64 monotonicMs() { return 1000; }
struct LatestFrames {
    QMutex mutex;
    QByteArray c[CAM_COUNT];
    std::array<thumbnail::Geometry, CAM_COUNT> geometry{};
    bool have[CAM_COUNT] = {};
    uint64_t errors[CAM_COUNT] = {};
    double fps[CAM_COUNT] = {};
    qint64 lastCapturedMs[CAM_COUNT] = {};
    qint64 rawCapturedMs[CAM_COUNT] = {};
    qint64 dmaReturnedNs[CAM_COUNT] = {};
    quint32 tags[CAM_COUNT] = {};
    int sourceGenerations[CAM_COUNT] = {};
    uint64_t gen = 0;                // 存下任意一帧就自增（显示侧据此推进）
    uint64_t camGen[CAM_COUNT] = {}; // 每路自己的帧计数（只转换变化的那一路）
};
class CameraThread {
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
        bool hdmiFull = false;   // HDMI 满屏视图（仅 6 路 3x2 布局下由显示端采用）
        std::array<qint64, CAM_COUNT> dmaReturnedNs{};
        std::array<thumbnail::Geometry, CAM_COUNT> geometry{};
    };
    int refreshDisplay(DisplayFrame& frame) {
        QMutexLocker config(&m_configMutex);
        const bool hdmi = m_mode.load() == CAM_COUNT && m_hdmiActive.load();
        const int mask = m_mode.load() == CAM_COUNT ? 0x3F : (1 << m_selectedCamera.load());
        if (!m_liveFrames || m_stop || m_paused || frame.video ||
            frame.generation != m_sourceGeneration.load() || frame.paneMask != mask ||
            frame.hdmiFull != hdmi || (!hdmi && frame.pane != m_selectedCamera.load())) return 0;
        QMutexLocker latest(&m_liveFrames->mutex);
        int refreshed = 0;
        for (int c = 0; c < CAM_COUNT; ++c) {
            if (!(mask & (1 << c)) || (hdmi && c < tdm::hdmiLeftCamera) ||
                !m_liveFrames->have[c] || !m_liveFrames->geometry[c].valid(size_t(m_liveFrames->c[c].size())) ||
                (hdmi && !m_liveFrames->geometry[c].raw()) ||
                m_liveFrames->sourceGenerations[c] != frame.generation ||
                m_liveFrames->camGen[c] <= frame.cameraSequences[c]) continue;
            frame.cameraPixels[c] = m_liveFrames->c[c]; // Owned implicit-sharing reference.
            frame.geometry[c] = m_liveFrames->geometry[c];
            frame.cameraSequences[c] = m_liveFrames->camGen[c];
            frame.capturedMs[c] = m_liveFrames->lastCapturedMs[c];
            frame.rawCapturedMs[c] = m_liveFrames->rawCapturedMs[c];
            frame.dmaReturnedNs[c] = m_liveFrames->dmaReturnedNs[c];
            frame.tags[c] = m_liveFrames->tags[c];
            frame.cameraGenerations[c] = m_liveFrames->sourceGenerations[c];
            if (c < frame.camFps.size()) frame.camFps[c] = m_liveFrames->fps[c];
            refreshed |= 1 << c;
        }
        frame.changedMask |= refreshed;
        return refreshed;
    }
    DisplayFrame takeDisplay() {
        QMutexLocker lock(&m_displayMutex);
        DisplayFrame frame = m_latestDisplay;
        m_latestDisplay = {};
        m_displayPending = false;
        return frame;
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
            if (m_rawCaptureEnabled && !frame.video) m_rawSnapshot = frame;
            m_latestDisplay = std::move(frame);
            notify = !m_displayPending;
            m_displayPending = true;
        }
        if (notify) emit displayAvailable();
    }
    void setSourceGeneration(int generation) {
        QMutexLocker lock(&m_configMutex);
        m_sourceGeneration = generation;
    }
    void setMode(int mode) {
        QMutexLocker lock(&m_configMutex);
        m_selectedCamera = mode == CAM_COUNT ? (m_options.stereoEnabled() ? m_options.primaryStereoLeft() : 0) : mode;
        m_mode = mode;
        updateHdmiActive();
    }
    void setPaused(bool paused) {
        QMutexLocker lock(&m_configMutex);
        m_paused = paused;
    }
    void setHdmiOverride(int mode) { m_hdmiOverride.store(mode); updateHdmiActive(); }
    void updateHdmiActive() {
        const int overrideMode = m_hdmiOverride.load();
        m_hdmiActive = m_mode.load() == CAM_COUNT &&
                       (overrideMode >= 0 ? overrideMode == 1 : m_hdmiPrefer.load() == 1);
    }
    static bool selfTestLateLatch() {
        CameraThread source;
        source.setSourceGeneration(7);
        source.setMode(0);
        source.m_liveFrames = std::make_shared<LatestFrames>();
        auto& latest = *source.m_liveFrames;
        latest.have[0] = true;
        latest.c[0] = QByteArray(FRAME_BYTES, char(0x22));
        latest.camGen[0] = 2; latest.sourceGenerations[0] = 7;
        latest.tags[0] = 123; latest.rawCapturedMs[0] = 100;
        latest.lastCapturedMs[0] = 101; latest.dmaReturnedNs[0] = 100123456;
        DisplayFrame frame;
        frame.generation = 7; frame.paneMask = 1; frame.pane = 0;
        frame.cameraSequences[0] = 1;
        frame.cameraPixels[0] = QByteArray(FRAME_BYTES, char(0x11));
        frame.camFps = QVector<double>(CAM_COUNT, 0);
        source.publishDisplay(frame);
        const auto taken = source.takeDisplay();
        if (source.refreshDisplay(frame) != 1 || frame.cameraSequences[0] != 2 ||
            frame.cameraPixels[0][0] != char(0x22) || frame.tags[0] != 123 ||
            frame.cameraGenerations[0] != 7 || frame.rawCapturedMs[0] != 100 ||
            frame.capturedMs[0] != 101 || frame.dmaReturnedNs[0] != 100123456 ||
            source.m_displayPending || frame.replacedBeforeTake != taken.replacedBeforeTake) return false;
        latest.c[0].fill(char(0x33)); // Writer detaches; GUI snapshot stays intact.
        if (frame.cameraPixels[0][0] != char(0x22) || source.refreshDisplay(frame) != 0) return false;
        latest.camGen[0] = 3;
        source.setPaused(true);
        if (source.refreshDisplay(frame) != 0) return false;
        source.setPaused(false);
        latest.sourceGenerations[0] = 6;
        if (source.refreshDisplay(frame) != 0) return false;
        latest.sourceGenerations[0] = 7;
        source.setSourceGeneration(8);
        if (source.refreshDisplay(frame) != 0) return false;
        source.setSourceGeneration(7);
        source.setMode(1);
        if (source.refreshDisplay(frame) != 0) return false;
        source.setMode(0);
        frame.video = true;
        if (source.refreshDisplay(frame) != 0) return false;
        frame.video = false;
        if (source.refreshDisplay(frame) != 1 || frame.cameraPixels[0][0] != char(0x33)) return false;
        source.setMode(CAM_COUNT); source.setHdmiOverride(1);
        frame.paneMask = 0x3F; frame.hdmiFull = false;
        if (source.refreshDisplay(frame) != 0) return false;
        frame.hdmiFull = true;
        latest.camGen[0] = 4;
        latest.have[4] = true; latest.camGen[4] = 1; latest.sourceGenerations[4] = 7;
        latest.c[4] = QByteArray(FRAME_BYTES, char(0x44));
        if (source.refreshDisplay(frame) != (1 << 4) || frame.cameraSequences[0] != 3) return false;
        source.setHdmiOverride(0);
        frame.hdmiFull = false;
        latest.camGen[4] = 2;
        latest.geometry[4] = {320, 240};
        latest.c[4] = QByteArray(thumbnail::Bytes, char(0x55));
        if (source.refreshDisplay(frame) != ((1 << 0) | (1 << 4)) ||
            frame.geometry[4].raw() || frame.geometry[4].width != 320 ||
            frame.cameraPixels[4].size() != thumbnail::Bytes) return false;
        const auto thumbnailOwned = frame.cameraPixels[4];
        latest.camGen[4] = 3;
        latest.geometry[4] = {};
        latest.c[4] = QByteArray(FRAME_BYTES, char(0x66));
        if (source.refreshDisplay(frame) != (1 << 4) || !frame.geometry[4].raw() ||
            frame.cameraPixels[4].size() != FRAME_BYTES || thumbnailOwned[0] != char(0x55)) return false;
        // Malformed sizes and stale generations cannot replace accepted RAW.
        latest.camGen[4] = 4;
        latest.c[4].resize(thumbnail::Bytes);
        if (source.refreshDisplay(frame) != 0) return false;
        source.m_liveFrames.reset();
        if (source.refreshDisplay(frame) != 0 || frame.cameraPixels[4][0] != char(0x66)) return false;
        fprintf(stderr, "DISPLAY_LATE_LATCH_SELFTEST_PASS\n");
        return true;
    }
    QMutex m_configMutex, m_displayMutex;
    std::shared_ptr<LatestFrames> m_liveFrames;
    std::atomic<bool> m_stop{false}, m_paused{false}, m_hdmiActive{false}, m_rawCaptureEnabled{false};
    std::atomic<int> m_mode{CAM_COUNT}, m_selectedCamera{0}, m_sourceGeneration{0};
    std::atomic<int> m_hdmiOverride{-1}, m_hdmiPrefer{2};
    VisionOptions m_options;
    DisplayFrame m_latestDisplay, m_rawSnapshot;
    bool m_displayPending = false;
    int m_lastDisplayGeneration = -1;
    int notifications = 0;
    void displayAvailable() { ++notifications; }
};
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    return CameraThread::selfTestLateLatch() ? 0 : 2;
}
