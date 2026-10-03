# -*- coding: utf-8 -*-
"""patch_camview6b.py -- camview 六宫格 part2: View 签名/成员/HUD key/pane/connect"""
import io

P = r'C:\Users\NineSun\Desktop\ov56401\project\host\camview\main.cpp'
s = io.open(P, encoding='utf-8', newline='').read()

def sub1(old, new):
    global s
    n = s.count(old)
    assert n == 1, 'count=%d: %r' % (n, old[:70])
    s = s.replace(old, new)

# 1) submitFrame signature + body
sub1("""    void submitFrame(const QByteArray &rgb565, int w, int h, double fps,
                     double fps1, double fps2, double fps3, double fps4, const QString &status) {
        frame_ = rgb565;          // QByteArray 隐式共享, 只是引用计数 +1
        fw_ = w; fh_ = h; fps_ = fps; status_ = status;
        fps1_ = fps1; fps2_ = fps2; fps3_ = fps3; fps4_ = fps4;""",
"""    void submitFrame(const QByteArray &rgb565, int w, int h, double fps,
                     double fps1, double fps2, double fps3, double fps4,
                     double fps5, double fps6, const QString &status) {
        frame_ = rgb565;          // QByteArray 隐式共享, 只是引用计数 +1
        fw_ = w; fh_ = h; fps_ = fps; status_ = status;
        fps1_ = fps1; fps2_ = fps2; fps3_ = fps3; fps4_ = fps4;
        fps5_ = fps5; fps6_ = fps6;""")

# 2) members
sub1("    double fps1_ = 0, fps2_ = 0, fps3_ = 0, fps4_ = 0;   // [FPS3] per-camera capture rates",
     "    double fps1_ = 0, fps2_ = 0, fps3_ = 0, fps4_ = 0, fps5_ = 0, fps6_ = 0;   // [FPS3+SFP] per-camera capture rates")

# 3) HUD cache key
sub1("""    const QString key = QString("%1|%2|%3|%4|%5|%6x%7|%8|%9|%10|%11")
                            .arg(fps_, 0, 'f', 0).arg(status_).arg(help_).arg(statusOnly_)
                            .arg(dprW).arg(fw_).arg(fh_)
                            .arg(fps1_, 0, 'f', 0).arg(fps2_, 0, 'f', 0).arg(fps3_, 0, 'f', 0)
                            .arg(fps4_, 0, 'f', 0);""",
"""    const QString key = QString("%1|%2|%3|%4|%5|%6x%7|%8|%9|%10|%11|%12|%13")
                            .arg(fps_, 0, 'f', 0).arg(status_).arg(help_).arg(statusOnly_)
                            .arg(dprW).arg(fw_).arg(fh_)
                            .arg(fps1_, 0, 'f', 0).arg(fps2_, 0, 'f', 0).arg(fps3_, 0, 'f', 0)
                            .arg(fps4_, 0, 'f', 0).arg(fps5_, 0, 'f', 0).arg(fps6_, 0, 'f', 0);""")

# 4) pane labels 2x2 -> 3x2
sub1("""    // [FPS3 2026-09-27] Per-pane frame-rate label in the top-left corner of
    // each of the four camera images. The panes are the four quadrants of the
    // letterboxed 2x2 composite (fw_ x fh_ is 2*640 x 2*480).""",
"""    // [FPS3+SFP] Per-pane frame-rate label in the top-left corner of each of
    // the six camera images. Panes are the 3x2 grid of the composite
    // (fw_ x fh_ is 3*640 x 2*480).""")
sub1("""        const float pw = dw / 2.0f;
        const float ph = dh / 2.0f;
        const double cf[4] = { fps1_, fps2_, fps3_, fps4_ };
        f.setPointSize(12);
        p.setFont(f);
        for (int i = 0; i < 4; ++i) {
            const QRect box((int)(dx + (i % 2) * pw) + 6, (int)(dy + (i / 2) * ph) + 6, 150, 32);
            p.fillRect(box, QColor(0, 0, 0, 170));
            p.setPen(QColor(0, 255, 120));
            p.drawText(box.adjusted(8, 0, -6, 0), Qt::AlignLeft | Qt::AlignVCenter,
                       QString("C%1  %2 fps").arg(i + 1).arg(cf[i], 0, 'f', 1));
        }""",
"""        const float pw = dw / 3.0f;
        const float ph = dh / 2.0f;
        const double cf[6] = { fps1_, fps2_, fps3_, fps4_, fps5_, fps6_ };
        f.setPointSize(12);
        p.setFont(f);
        for (int i = 0; i < 6; ++i) {
            const QRect box((int)(dx + (i % 3) * pw) + 6, (int)(dy + (i / 3) * ph) + 6, 150, 32);
            p.fillRect(box, QColor(0, 0, 0, 170));
            p.setPen(QColor(0, 255, 120));
            p.drawText(box.adjusted(8, 0, -6, 0), Qt::AlignLeft | Qt::AlignVCenter,
                       QString("C%1  %2 fps").arg(i + 1).arg(cf[i], 0, 'f', 1));
        }""")

# 5) main() connect lambda
sub1("""    QObject::connect(grabber, &Grabber::frameReady, view,
        [view](const QByteArray &rgb565, int w, int h, double fps,
               double fps1, double fps2, double fps3, double fps4, const QString &status) {
            view->submitFrame(rgb565, w, h, fps, fps1, fps2, fps3, fps4, status);
        });""",
"""    QObject::connect(grabber, &Grabber::frameReady, view,
        [view](const QByteArray &rgb565, int w, int h, double fps,
               double fps1, double fps2, double fps3, double fps4,
               double fps5, double fps6, const QString &status) {
            view->submitFrame(rgb565, w, h, fps, fps1, fps2, fps3, fps4, fps5, fps6, status);
        });""")

io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('camview6 part2 OK (5 subs)')
