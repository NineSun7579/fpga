"""Extract candidate methods into a host Qt test (no DMA, RKNN, RGA or GL)."""
from pathlib import Path

root = Path(__file__).resolve().parent
text = (root / "src/main.cpp").read_text(encoding="utf-8")

def extract(start):
    begin = text.index(start)
    brace = text.index("{", begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[begin:end]

methods = ["    int refreshDisplay(DisplayFrame& frame)",
           "    DisplayFrame takeDisplay()", "    void publishDisplay(DisplayFrame frame)",
           "    void setSourceGeneration(int generation)", "    void setMode(int mode)",
           "    void setPaused(bool paused)", "    void setHdmiOverride(int mode)",
           "    void updateHdmiActive()", "    static bool selfTestLateLatch()"]
prefix = '''#include <QByteArray>
#include <QMutex>
#include <QMutexLocker>
#include <QImage>
#include <QVector>
#include <QCoreApplication>
#include <array>
#include <atomic>
#include <memory>
#include <cstdio>
#include "src/vision_types.h"
#include "src/hdmi_view.h"
constexpr int CAM_COUNT = 6, FRAME_BYTES = 640 * 480 * 2;
static qint64 monotonicMs() { return 1000; } // Publisher bookkeeping only.
'''
members = '''
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
'''
generated = prefix + extract("struct LatestFrames") + ";\nclass CameraThread {\npublic:\n"
generated += extract("    struct DisplayFrame") + ";\n"
generated += "\n".join(extract(method) for method in methods)
generated += members
(root / "latch_host_test.cpp").write_text(generated, encoding="utf-8")
print("Generated latch_host_test.cpp from exact candidate methods; uses actual Qt ownership/mutex types")
