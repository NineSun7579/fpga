# -*- coding: utf-8 -*-
"""patch_camview6.py -- camview 4 路 2x2 -> 6 路 3x2 (SFP fiber cam5/cam6)"""
import io

P = r'C:\Users\NineSun\Desktop\ov56401\project\host\camview\main.cpp'
s = io.open(P, encoding='utf-8', newline='').read()

def sub1(old, new):
    global s
    n = s.count(old)
    assert n == 1, 'count=%d: %r' % (n, old[:70])
    s = s.replace(old, new)

# 1) defines
sub1("""#define TAG4_ADDR_1 (CAM4_ADDR_1 + FRAME_BYTES)
#define TAG4_ADDR_2 (CAM4_ADDR_2 + FRAME_BYTES)""",
"""#define TAG4_ADDR_1 (CAM4_ADDR_1 + FRAME_BYTES)
#define TAG4_ADDR_2 (CAM4_ADDR_2 + FRAME_BYTES)
// [SFP 2026-09-29] fiber channels cam5/cam6 (QR3 HSST CH2 from PGL50H)
#define CAM5_ADDR_1 0x01800000u
#define CAM5_ADDR_2 0x01A00000u
#define TAG5_ADDR_1 (CAM5_ADDR_1 + FRAME_BYTES)
#define TAG5_ADDR_2 (CAM5_ADDR_2 + FRAME_BYTES)
#define CAM6_ADDR_1 0x01C00000u
#define CAM6_ADDR_2 0x01E00000u
#define TAG6_ADDR_1 (CAM6_ADDR_1 + FRAME_BYTES)
#define TAG6_ADDR_2 (CAM6_ADDR_2 + FRAME_BYTES)""")

# 2) LatestFrames
sub1("""    QMutex mutex;
    QByteArray c1, c2, c3, c4;
    bool have1 = false, have2 = false, have3 = false, have4 = false;
    uint64_t errors1 = 0, errors2 = 0, errors3 = 0, errors4 = 0;
    qint64 last1 = 0, last2 = 0, last3 = 0, last4 = 0;""",
"""    QMutex mutex;
    QByteArray c1, c2, c3, c4, c5, c6;
    bool have1 = false, have2 = false, have3 = false, have4 = false, have5 = false, have6 = false;
    uint64_t errors1 = 0, errors2 = 0, errors3 = 0, errors4 = 0, errors5 = 0, errors6 = 0;
    qint64 last1 = 0, last2 = 0, last3 = 0, last4 = 0, last5 = 0, last6 = 0;""")
sub1("    double fps1 = 0, fps2 = 0, fps3 = 0, fps4 = 0;",
     "    double fps1 = 0, fps2 = 0, fps3 = 0, fps4 = 0, fps5 = 0, fps6 = 0;")

# 3) CameraWorker address ternaries
sub1("""        const uint32_t ta = camera_ == 1 ? TAG_ADDR_1 : camera_ == 2 ? TAG2_ADDR_1 : camera_ == 3 ? TAG3_ADDR_1 : TAG4_ADDR_1;
        const uint32_t tb = camera_ == 1 ? TAG_ADDR_2 : camera_ == 2 ? TAG2_ADDR_2 : camera_ == 3 ? TAG3_ADDR_2 : TAG4_ADDR_2;
        const uint32_t ba = camera_ == 1 ? CAM_ADDR_1 : camera_ == 2 ? CAM2_ADDR_1 : camera_ == 3 ? CAM3_ADDR_1 : CAM4_ADDR_1;
        const uint32_t bb = camera_ == 1 ? CAM_ADDR_2 : camera_ == 2 ? CAM2_ADDR_2 : camera_ == 3 ? CAM3_ADDR_2 : CAM4_ADDR_2;""",
"""        const uint32_t ta = camera_ == 1 ? TAG_ADDR_1 : camera_ == 2 ? TAG2_ADDR_1 : camera_ == 3 ? TAG3_ADDR_1 :
                            camera_ == 4 ? TAG4_ADDR_1 : camera_ == 5 ? TAG5_ADDR_1 : TAG6_ADDR_1;
        const uint32_t tb = camera_ == 1 ? TAG_ADDR_2 : camera_ == 2 ? TAG2_ADDR_2 : camera_ == 3 ? TAG3_ADDR_2 :
                            camera_ == 4 ? TAG4_ADDR_2 : camera_ == 5 ? TAG5_ADDR_2 : TAG6_ADDR_2;
        const uint32_t ba = camera_ == 1 ? CAM_ADDR_1 : camera_ == 2 ? CAM2_ADDR_1 : camera_ == 3 ? CAM3_ADDR_1 :
                            camera_ == 4 ? CAM4_ADDR_1 : camera_ == 5 ? CAM5_ADDR_1 : CAM6_ADDR_1;
        const uint32_t bb = camera_ == 1 ? CAM_ADDR_2 : camera_ == 2 ? CAM2_ADDR_2 : camera_ == 3 ? CAM3_ADDR_2 :
                            camera_ == 4 ? CAM4_ADDR_2 : camera_ == 5 ? CAM5_ADDR_2 : CAM6_ADDR_2;""")

# 4) worker error/store/fps branches
sub1("""                if (camera_ == 1) ++frames_->errors1;
                else if (camera_ == 2) ++frames_->errors2;
                else if (camera_ == 3) ++frames_->errors3;
                else ++frames_->errors4;""",
"""                if (camera_ == 1) ++frames_->errors1;
                else if (camera_ == 2) ++frames_->errors2;
                else if (camera_ == 3) ++frames_->errors3;
                else if (camera_ == 4) ++frames_->errors4;
                else if (camera_ == 5) ++frames_->errors5;
                else ++frames_->errors6;""")
sub1("""            if (camera_ == 1) { frames_->c1 = frame; frames_->have1 = true; frames_->last1 = QDateTime::currentMSecsSinceEpoch(); }
            else if (camera_ == 2) { frames_->c2 = frame; frames_->have2 = true; frames_->last2 = QDateTime::currentMSecsSinceEpoch(); }
            else if (camera_ == 3) { frames_->c3 = frame; frames_->have3 = true; frames_->last3 = QDateTime::currentMSecsSinceEpoch(); }
            else { frames_->c4 = frame; frames_->have4 = true; frames_->last4 = QDateTime::currentMSecsSinceEpoch(); }""",
"""            if (camera_ == 1) { frames_->c1 = frame; frames_->have1 = true; frames_->last1 = QDateTime::currentMSecsSinceEpoch(); }
            else if (camera_ == 2) { frames_->c2 = frame; frames_->have2 = true; frames_->last2 = QDateTime::currentMSecsSinceEpoch(); }
            else if (camera_ == 3) { frames_->c3 = frame; frames_->have3 = true; frames_->last3 = QDateTime::currentMSecsSinceEpoch(); }
            else if (camera_ == 4) { frames_->c4 = frame; frames_->have4 = true; frames_->last4 = QDateTime::currentMSecsSinceEpoch(); }
            else if (camera_ == 5) { frames_->c5 = frame; frames_->have5 = true; frames_->last5 = QDateTime::currentMSecsSinceEpoch(); }
            else { frames_->c6 = frame; frames_->have6 = true; frames_->last6 = QDateTime::currentMSecsSinceEpoch(); }""")
sub1("""                if (camera_ == 1) frames_->fps1 = f;
                else if (camera_ == 2) frames_->fps2 = f;
                else if (camera_ == 3) frames_->fps3 = f;
                else frames_->fps4 = f;""",
"""                if (camera_ == 1) frames_->fps1 = f;
                else if (camera_ == 2) frames_->fps2 = f;
                else if (camera_ == 3) frames_->fps3 = f;
                else if (camera_ == 4) frames_->fps4 = f;
                else if (camera_ == 5) frames_->fps5 = f;
                else frames_->fps6 = f;""")

# 5) signal signature
sub1("""    void frameReady(const QByteArray &rgb565, int w, int h, double fps,
                    double fps1, double fps2, double fps3, double fps4, const QString &status);""",
"""    void frameReady(const QByteArray &rgb565, int w, int h, double fps,
                    double fps1, double fps2, double fps3, double fps4,
                    double fps5, double fps6, const QString &status);""")

# 6) workers + buffers
sub1("        CameraWorker w1(dev_, &latest, 1), w2(dev_, &latest, 2), w3(dev_, &latest, 3), w4(dev_, &latest, 4);\n        w1.start(); w2.start(); w3.start(); w4.start();",
     "        CameraWorker w1(dev_, &latest, 1), w2(dev_, &latest, 2), w3(dev_, &latest, 3), w4(dev_, &latest, 4),\n                     w5(dev_, &latest, 5), w6(dev_, &latest, 6);\n        w1.start(); w2.start(); w3.start(); w4.start(); w5.start(); w6.start();")
sub1("QByteArray c1(FRAME_BYTES, 0), c2(FRAME_BYTES, 0), c3(FRAME_BYTES, 0), c4(FRAME_BYTES, 0),\n                   comp(4 * FRAME_BYTES, 0);",
     "QByteArray c1(FRAME_BYTES, 0), c2(FRAME_BYTES, 0), c3(FRAME_BYTES, 0), c4(FRAME_BYTES, 0),\n                   c5(FRAME_BYTES, 0), c6(FRAME_BYTES, 0), comp(6 * FRAME_BYTES, 0);")

# 7) snapshot block
sub1("""        bool ready; qint64 last1, last2, last3, last4; uint64_t err1, err2, err3, err4, gen;
        double cf1, cf2, cf3, cf4;
            { QMutexLocker lock(&latest.mutex);
              ready = latest.have1 || latest.have2 || latest.have3 || latest.have4;
              gen = latest.gen;
              if (latest.have1) c1 = latest.c1;
              if (latest.have2) c2 = latest.c2;
              if (latest.have3) c3 = latest.c3;
              if (latest.have4) c4 = latest.c4;
              last1 = latest.last1; last2 = latest.last2; last3 = latest.last3; last4 = latest.last4;
              err1 = latest.errors1; err2 = latest.errors2; err3 = latest.errors3; err4 = latest.errors4;
              cf1 = latest.fps1; cf2 = latest.fps2; cf3 = latest.fps3; cf4 = latest.fps4; }""",
"""        bool ready; qint64 last1, last2, last3, last4, last5, last6; uint64_t err1, err2, err3, err4, err5, err6, gen;
        double cf1, cf2, cf3, cf4, cf5, cf6;
            { QMutexLocker lock(&latest.mutex);
              ready = latest.have1 || latest.have2 || latest.have3 || latest.have4 || latest.have5 || latest.have6;
              gen = latest.gen;
              if (latest.have1) c1 = latest.c1;
              if (latest.have2) c2 = latest.c2;
              if (latest.have3) c3 = latest.c3;
              if (latest.have4) c4 = latest.c4;
              if (latest.have5) c5 = latest.c5;
              if (latest.have6) c6 = latest.c6;
              last1 = latest.last1; last2 = latest.last2; last3 = latest.last3; last4 = latest.last4;
              last5 = latest.last5; last6 = latest.last6;
              err1 = latest.errors1; err2 = latest.errors2; err3 = latest.errors3; err4 = latest.errors4;
              err5 = latest.errors5; err6 = latest.errors6;
              cf1 = latest.fps1; cf2 = latest.fps2; cf3 = latest.fps3; cf4 = latest.fps4;
              cf5 = latest.fps5; cf6 = latest.fps6; }""")

# 8) composite 2x2 -> 3x2
sub1("""            for (int y = 0; y < IMG_H; ++y) {
                // [QUAD 2026-09-27] 2x2 grid: top C1|C2, bottom C3|C4.
                memcpy(comp.data() + (size_t)y * 2 * rowb,                  c1.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)y * 2 * rowb + rowb,           c2.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)(y + IMG_H) * 2 * rowb,        c3.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)(y + IMG_H) * 2 * rowb + rowb, c4.constData() + (size_t)y * rowb, rowb);
            }""",
"""            for (int y = 0; y < IMG_H; ++y) {
                // [SFP 2026-09-29] 3x2 grid: top C1|C2|C3, bottom C4|C5|C6.
                memcpy(comp.data() + (size_t)y * 3 * rowb,                  c1.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)y * 3 * rowb + rowb,           c2.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)y * 3 * rowb + 2 * rowb,       c3.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)(y + IMG_H) * 3 * rowb,        c4.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)(y + IMG_H) * 3 * rowb + rowb, c5.constData() + (size_t)y * rowb, rowb);
                memcpy(comp.data() + (size_t)(y + IMG_H) * 3 * rowb + 2 * rowb, c6.constData() + (size_t)y * rowb, rowb);
            }""")

# 9) byteswap loop size
sub1("                for (int i = 0; i < 4 * FRAME_BYTES; i += 2) {",
     "                for (int i = 0; i < 6 * FRAME_BYTES; i += 2) {")

# 10) status + emit
sub1("""            const QString status = QString("D:%1  C1:%2 C2:%3 C3:%4 C4:%5  E1:%6 E2:%7 E3:%8 E4:%9")
                                       .arg(fps, 0, 'f', 1)
                                       .arg(now - last1 < 500 ? "OK" : "WAIT")
                                       .arg(now - last2 < 500 ? "OK" : "WAIT")
                                       .arg(now - last3 < 500 ? "OK" : "WAIT")
                                       .arg(now - last4 < 500 ? "OK" : "WAIT")
                                       .arg(err1).arg(err2).arg(err3).arg(err4);
            emit frameReady(comp, 2 * IMG_W, 2 * IMG_H, fps, cf1, cf2, cf3, cf4, status);""",
"""            const QString status = QString("D:%1  C1:%2 C2:%3 C3:%4 C4:%5 C5:%6 C6:%7  E1:%8 E2:%9 E3:%10 E4:%11 E5:%12 E6:%13")
                                       .arg(fps, 0, 'f', 1)
                                       .arg(now - last1 < 500 ? "OK" : "WAIT")
                                       .arg(now - last2 < 500 ? "OK" : "WAIT")
                                       .arg(now - last3 < 500 ? "OK" : "WAIT")
                                       .arg(now - last4 < 500 ? "OK" : "WAIT")
                                       .arg(now - last5 < 500 ? "OK" : "WAIT")
                                       .arg(now - last6 < 500 ? "OK" : "WAIT")
                                       .arg(err1).arg(err2).arg(err3).arg(err4).arg(err5).arg(err6);
            emit frameReady(comp, 3 * IMG_W, 2 * IMG_H, fps, cf1, cf2, cf3, cf4, cf5, cf6, status);""")

# 11) worker shutdown
sub1("""        w1.stop(); w2.stop(); w3.stop(); w4.stop();
        w1.wait(3000); w2.wait(3000); w3.wait(3000); w4.wait(3000);""",
"""        w1.stop(); w2.stop(); w3.stop(); w4.stop(); w5.stop(); w6.stop();
        w1.wait(3000); w2.wait(3000); w3.wait(3000); w4.wait(3000); w5.wait(3000); w6.wait(3000);""")

# 12) View::submitFrame + members
sub1("""    void submitFrame(const QByteArray &rgb565, int w, int h, double fps,""",
     """    void submitFrame(const QByteArray &rgb565, int w, int h, double fps,""")
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('camview6 patched part1 OK')
