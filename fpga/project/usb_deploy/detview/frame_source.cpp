#include "frame_source.h"

volatile sig_atomic_t PangoDev::timeoutHit_ = 0;

bool FrameSource::initCamera(QString &err) {
    dev_ = new PangoDev;
    if (!dev_->open()) { err = QString("FATAL: ") + dev_->lastErr(); return false; }
    dev_->regWrite(R_CAM_EN, 0);
    msleep(60);
    dev_->regWrite(R_ADDR1, CAM_ADDR_1);
    err = "TAG-ACK ";
    dev_->regWrite(R_ADDR2, CAM_ADDR_2);
    dev_->regWrite(R_ACK, 3);
    bool ok1 = false, ok2 = false;
    last1_ = readTag(prep::TAG_ADDR_1, ok1);
    last2_ = readTag(prep::TAG_ADDR_2, ok2);
    if (!ok1) last1_ = 0;
    if (!ok2) last2_ = 0;
    expectedBuf_ = last1_ == last2_ ? 0 :
                   ((int32_t)(last1_ - last2_) > 0 ? 1 : 0);
    dev_->regWrite(R_CAM_EN, 1);
    return true;
}

uint32_t FrameSource::readTag(uint32_t addr, bool &ok) {
    uint8_t tmp[16] = {0};
    ok = dev_->ddrRead(addr, 16, tmp);
    if (!ok) return 0;
    uint32_t v;
    memcpy(&v, tmp, 4);                      // little-endian bytes 0..3
    return v;
}

bool FrameSource::readFrame(int bufIdx, std::vector<uint8_t> &dst) {
    dst.resize(prep::FRAME_BYTES);
    return dev_->ddrRead(bufIdx == 0 ? CAM_ADDR_1 : CAM_ADDR_2, prep::FRAME_BYTES, dst.data());
}

void FrameSource::tickFps() {
    ++fpsCount_;
    if (!fpsT_.isValid()) { fpsT_.start(); return; }
    double el = fpsT_.elapsed() / 1000.0;
    if (el >= 0.5) { fps_ = fpsCount_ / el; fpsCount_ = 0; fpsT_.restart(); }
}

// One poll/grab iteration of the mode machine. Returns true when a fresh frame
// was captured (img is a detached RGB888 copy with the byte/RB swap flags applied).
bool FrameSource::cycle(QImage &img, quint32 &fid) {
    bool ok1 = true, ok2 = true;
    uint32_t c1 = last1_, c2 = last2_;
    if (mode_ == Mode::TAG) {
        uint32_t tagAddr = expectedBuf_ == 0 ? prep::TAG_ADDR_1 : prep::TAG_ADDR_2;
        uint32_t c = readTag(tagAddr, ok1);
        if (expectedBuf_ == 0) c1 = c; else c2 = c;
        if (!ok1) { msleep(20); return false; }
    } else {
        c1 = readTag(prep::TAG_ADDR_1, ok1);
        c2 = readTag(prep::TAG_ADDR_2, ok2);
        if (!ok1 || !ok2) { msleep(20); return false; }
    }

    if (mode_ == Mode::PROBE) {
        if (c1 != last1_ || c2 != last2_) {
            mode_ = Mode::TAG;
            QMutexLocker l(&m_); syncMode_ = "TAG-SYNC";
            emit statusMsg("TAG-SYNC (frame counters alive)");
        } else if (++probeCycles_ > 25) {
            mode_ = Mode::STBL;
            QMutexLocker l(&m_); syncMode_ = "STBL-FALLBACK";
            emit statusMsg("STBL-FALLBACK (no counters: old bitstream)");
        } else {
            msleep(10);
            return false;
        }
    }

    if (mode_ == Mode::TAG) {
        if (c1 == last1_ && c2 == last2_) { msleep(4); return false; }  // no new frame
        int buf = expectedBuf_;
        if ((buf == 0 ? c1 : c2) == (buf == 0 ? last1_ : last2_)) {
            msleep(10);
            return false;
        }
        if (!readFrame(buf, rawA_)) { msleep(10); return false; }
        last1_ = c1; last2_ = c2;
        fid = (buf == 0) ? c1 : c2;
        dev_->regWrite(R_ACK, 1u << buf);   // release for flow-controlled bitstreams
        expectedBuf_ ^= 1;
    } else { // STBL
        bool got = false;
        for (int attempt = 0; attempt < 2 && !got; ++attempt) {
            int buf = (stblBuf_ + attempt) % 2;
            if (!readFrame(buf, rawA_)) continue;
            if (!readFrame(buf, rawB_)) continue;
            if (memcmp(rawA_.data(), rawB_.data(), prep::FRAME_BYTES) == 0) {
                stblBuf_ = buf ^ 1;          // next cycle start from the other buffer
                dev_->regWrite(R_ACK, 1u << buf);
                fid = 0;
                got = true;
            }
        }
        if (!got) { msleep(5); return false; } // both buffers in flux, brief wait
    }

    bool sb, sc;
    { QMutexLocker l(&m_); sb = swapB_; sc = swapC_; }
    std::vector<uint8_t> rgb(prep::CAM_W * prep::CAM_H * 3);
    prep::rgb565ToRgb888(rawA_.data(), prep::CAM_W, prep::CAM_H, rgb.data(), sb, sc);
    img = QImage(rgb.data(), prep::CAM_W, prep::CAM_H, prep::CAM_W * 3,
                 QImage::Format_RGB888).copy();
    tickFps();
    lastId_.store(fid);
    return true;
}

void FrameSource::run() {
    QString err;
    if (!initCamera(err)) { emit statusMsg(err); return; }
    emit statusMsg(err);

    while (run_) {
        if (paused_) { msleep(20); continue; }
        QImage img;
        quint32 fid = 0;
        if (cycle(img, fid))
            emit frameReady(img, fps_, fid);
        else
            msleep(1);
    }
}

bool FrameSource::grabOnce(QImage &out, double &fps, quint32 &frameId) {
    if (!dev_) {
        QString err;
        if (!initCamera(err)) { emit statusMsg(err); return false; }
    }
    QImage img;
    quint32 fid = 0;
    if (!cycle(img, fid)) return false;
    out = img;
    fps = fps_;
    frameId = fid;
    return true;
}
