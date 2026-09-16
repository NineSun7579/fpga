// frame_source.h -- camera grabber with tear-free buffer selection.
//
// [FRTAG] bitstream: the FPGA writes a 32-bit frame counter right after each
// frame in DDR (prep::TAG_ADDR_1/2), then holds that buffer until host ACK.
// A changed tag therefore identifies a complete frame with exclusive ownership.
//
// Old bitstream fallback ("STBL"): counters stay 0 -> double-read stability
// check: a frame is shown only if two consecutive full reads are identical
// (if the engine were rewriting it they would differ; identical content
// rewritten is visually identical anyway).
#ifndef DETVIEW_FRAME_SOURCE_H
#define DETVIEW_FRAME_SOURCE_H

#include <QImage>
#include <QThread>
#include <QMutex>
#include <QElapsedTimer>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <vector>
#include "pango_dev.h"
#include "preprocess.h"

// Camera register window (M01) -- write-only usage, never read (M01 reads
// wedge the PCIe read channel, see DOC/交付说明 §8-§10)
#define REG_BASE   0x20000000u
#define R_ACK      (REG_BASE + 0x00)
#define R_CAM_EN   (REG_BASE + 0x40)
#define R_ADDR1    (REG_BASE + 0x80)
#define R_ADDR2    (REG_BASE + 0xC0)
#define CAM_ADDR_1 0x00800000u
#define CAM_ADDR_2 0x00A00000u

class FrameSource : public QThread {
    Q_OBJECT
public:
    explicit FrameSource(QObject *parent = nullptr) : QThread(parent) {}
    ~FrameSource() override { stop(); }

    void stop() { run_ = false; wait(3000); }
    void setPaused(bool on) { paused_ = on; }
    void setByteSwap(bool on) { QMutexLocker l(&m_); swapB_ = on; }
    void setRBSwap(bool on)   { QMutexLocker l(&m_); swapC_ = on; }

    // Sync mode reported for the HUD: "TAG-SYNC" (frame counters) or
    // "STBL-FALLBACK" (double-read stability, old bitstream)
    QString syncMode() const { QMutexLocker l(&m_); return syncMode_; }
    quint64 lastFrameId() const { return lastId_.load(); }

    // Synchronous single-frame grab (used by --selftest; the GUI mode runs run())
    bool grabOnce(QImage &out, double &fps, quint32 &frameId);

signals:
    void frameReady(const QImage &img, double fps, quint32 frameId);
    void statusMsg(const QString &s);

protected:
    void run() override;

private:
    enum class Mode { PROBE, TAG, STBL };
    bool initCamera(QString &err);
    uint32_t readTag(uint32_t addr, bool &ok);
    bool readFrame(int bufIdx, std::vector<uint8_t> &dst);
    bool cycle(QImage &img, quint32 &fid);

    PangoDev *dev_ = nullptr;
    std::atomic_bool run_{true};
    std::atomic_bool paused_{false};
    bool swapB_ = false, swapC_ = false;
    mutable QMutex m_;
    QString syncMode_ = "PROBE";
    std::atomic<quint64> lastId_{0};

    Mode mode_ = Mode::PROBE;
    uint32_t last1_ = 0, last2_ = 0;
    int expectedBuf_ = 0;
    int probeCycles_ = 0;
    int stblBuf_ = 0;

    std::vector<uint8_t> rawA_, rawB_;   // frame scratch / double-read pair
    QElapsedTimer fpsT_;
    int fpsCount_ = 0;
    double fps_ = 0;
    void tickFps();
};

#endif // DETVIEW_FRAME_SOURCE_H
