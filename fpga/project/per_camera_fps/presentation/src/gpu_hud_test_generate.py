"""Generate a Qt-only integration harness from the actual production renderer.

Usage: python gpu_hud_test_generate.py BUILD_DIRECTORY
Then qmake gpu_hud_test.pro and build in that directory. No RKNN/RGA/OpenCV needed.
"""
from pathlib import Path
import sys

src = Path(__file__).resolve().parent
text = (src / "main.cpp").read_text(encoding="utf-8")
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
method = text[text.index("    struct GpuImage"):text.index("    void setVertices(")]
glyph = text[text.index("    QImage textImage("):text.index("    QOpenGLShaderProgram m_prog")]
shaders = text[text.index('        static const char *vsrc ='):text.index('        glGenTextures(1, &m_tex);')]
fields = text[text.index('    bool m_gpuHud ='):text.index('    QSize m_overlaySize;')]
header = r'''
#include <QGuiApplication>
#include <QOpenGLWindow>
#include <QOpenGLFunctions>
#include <QOpenGLShaderProgram>
#include <QPainter>
#include <QFontMetrics>
#include <QElapsedTimer>
#include <QThread>
#include <QHash>
#include <functional>
#include <cmath>
#include <cstdio>
#include <vector>
#include "vision_types.h"
#include "display_perf.h"
#include "frame_metrics.h"
constexpr int CAM_COUNT=6, GRID_COLS=3, GRID_ROWS=2, MODEL_W=640, MODEL_H=640, IMG_H=480;
static qint64 fakeNow=1000;
static qint64 monotonicMs() { return fakeNow; }
class Harness : public QOpenGLWindow, protected QOpenGLFunctions {
public:
    QOpenGLShaderProgram m_prog, m_gpuProg;
    tdm::DisplayPerfWindow m_perf;
    bool m_perfEnabled=true, m_overlaySettings=false, m_metricsPaused=false, m_help=false;
    QString m_monitorSummary="test", m_statusLine;
    qint64 m_videoReceivedMs=1000;
    qint64 m_overlayUpdatedMs=0;
    double m_dispFps=40;
    quint64 m_detectionRevision=1;
    QHash<QString,QImage> m_textCache;
    std::array<tdm::FrameRate,6> m_cameraUploadRates;
    QImage m_stereoPreview;
    QVector<Detection> detections;
    int pane=0, mask=0x3f;
    bool video=false, expireDuringDraw=false;
    QImage lane;
    double newFrameRate() { return 40; }
'''
tail = r'''
    void initializeGL() override {
        initializeOpenGLFunctions();
        m_gpuHud=true;
SHADERS
        glGenTextures(1,&m_previewTexture);
        glBindTexture(GL_TEXTURE_2D,m_previewTexture);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
        glGenBuffers(1,&m_gpuVertexBuffer);
        fprintf(stderr,"gpu_hud_test_renderer=%s\n",glGetString(GL_RENDERER));
    }
    void paintGL() override {
        if (!m_gpuHud) qFatal("GPU shader initialization failed");
        glDisable(GL_BLEND); glDisable(GL_SCISSOR_TEST);
        glClearColor(0,0,1,1);
        paintGpuMonitor(QRectF(0,56,1280,640),video,mask,pane,QVector<double>(6,40),detections,
                        QStringList{"object","red"},lane,fakeNow,[&] {
            if (expireDuringDraw) fakeNow=1201;
        });
    }
    QImage frame() {
        QGuiApplication::processEvents(); makeCurrent(); paintGL(); glFinish();
        QImage image(width(),height(),QImage::Format_RGBA8888);
        glReadPixels(0,0,width(),height(),GL_RGBA,GL_UNSIGNED_BYTE,image.bits());
        image=image.mirrored();
        if (glGetError()!=GL_NO_ERROR) qFatal("GL error during pixel test");
        doneCurrent(); return image;
    }
    bool pixel(const QImage& image, int x,int y,const QColor& expected) {
        const QColor actual=image.pixelColor(x,y);
        if (std::abs(actual.red()-expected.red())>2 || std::abs(actual.green()-expected.green())>2 ||
            std::abs(actual.blue()-expected.blue())>2) {
            fprintf(stderr,"pixel(%d,%d) actual=%d,%d,%d expected=%d,%d,%d\n",x,y,
                    actual.red(),actual.green(),actual.blue(),expected.red(),expected.green(),expected.blue());
            return false;
        }
        return true;
    }
};
int main(int argc,char** argv) {
    qputenv("QT_SCALE_FACTOR","1"); qputenv("QT_AUTO_SCREEN_SCALE_FACTOR","0");
    QGuiApplication app(argc,argv); Harness h; h.resize(1280,720); h.show();
    for (int i=0;i<10;++i) { app.processEvents(); QThread::msleep(10); }
    Detection d; d.cls=0; d.score=.9f; d.x1=160; d.x2=320; d.y1=240; d.y2=400; d.validUntilMs=1200;
    h.detections={d}; ++h.m_detectionRevision;
    auto image=h.frame(); bool ok=true;
    ok &= h.pixel(image,106,180,QColor(0,255,0)); // left detection border
    ok &= h.pixel(image,180,140,QColor(0,0,255)); // box interior preserves camera
    ok &= h.pixel(image,800,10,QColor(15,25,38)); // chrome
    ok &= h.pixel(image,425,200,QColor(62,213,199)); // selected pane border
    for (int camera=0;camera<6;++camera) {
        const QColor bg=camera==0 ? QColor(12,78,86,225) : QColor(12,22,34,210);
        const double alpha=bg.alphaF();
        ok &= h.pixel(image,int(camera%3*1280.0/3)+7,56+camera/3*320+7,
            QColor(qRound(bg.red()*alpha),qRound(bg.green()*alpha),qRound(bg.blue()*alpha+255*(1-alpha))));
    }
    // Compare actual uploaded cached glyph bytes to independent CPU blending.
    for (const auto& cmd : h.m_gpuCommands) {
        if (cmd.image.isNull() || cmd.rect.top()>50) continue;
        QImage reference(image.size(),QImage::Format_ARGB32_Premultiplied); reference.fill(QColor(15,25,38));
        QPainter p(&reference); p.drawImage(cmd.rect.topLeft(),cmd.image); p.end();
        const QRect r=cmd.rect.toAlignedRect().intersected(image.rect());
        for (int y=r.top();y<=r.bottom();++y) for (int x=r.left();x<=r.right();++x)
            if (!h.pixel(image,x,y,reference.pixelColor(x,y))) { ok=false; goto glyphDone; }
glyphDone: break;
    }
    const auto rebuilds=h.m_perf.hudRebuilds;
    h.m_stereoPreview=QImage(32,16,QImage::Format_RGB888); h.m_stereoPreview.fill(Qt::red);
    image=h.frame(); ok &= h.m_perf.hudRebuilds==rebuilds;
    ok &= h.pixel(image,1200,650,QColor(255,0,0)); // independent preview orientation/placement
    h.m_stereoPreview.fill(Qt::green); image=h.frame();
    ok &= h.m_perf.hudRebuilds==rebuilds;
    ok &= h.pixel(image,1200,650,QColor(0,255,0));
    { QPainter p(&h.m_stereoPreview); p.fillRect(QRect(0,0,32,8),Qt::red); }
    image=h.frame();
    ok &= h.pixel(image,1200,610,QColor(255,0,0));
    ok &= h.pixel(image,1200,680,QColor(0,255,0));
    h.m_stereoPreview=QImage(); image=h.frame(); ok &= h.pixel(image,1200,650,QColor(0,0,255));
    h.expireDuringDraw=true; image=h.frame(); ok &= h.pixel(image,106,180,QColor(0,0,255));
    h.expireDuringDraw=false; fakeNow=1300; image=h.frame();
    ok &= h.pixel(image,106,180,QColor(0,0,255)); // expired commands removed
    d.validUntilMs=0; d.depthMeters=1.23; d.depthCapturedMs=1200;
    h.detections={d}; ++h.m_detectionRevision; image=h.frame();
    ok &= h.m_gpuExpires==1500;
    fakeNow=1501; image=h.frame();
    ok &= h.m_gpuExpires==0;
    ok &= h.pixel(image,106,180,QColor(0,255,0)); // depth expiration preserves detection
    const QImage plain=h.textImage("object 0.90",Qt::green,11);
    bool plainLabel=false;
    for (const auto& cmd : h.m_gpuCommands) if (cmd.image.cacheKey()==plain.cacheKey()) plainLabel=true;
    ok &= plainLabel;
    d.x2=800; h.detections={d}; ++h.m_detectionRevision; image=h.frame();
    ok &= h.pixel(image,450,163,QColor(0,0,255)); // oversize detection clipped to selected pane
    h.detections.clear(); ++h.m_detectionRevision; h.pane=1; image=h.frame();
    ok &= h.pixel(image,425,200,QColor(0,0,255)); // previous selection removed
    ok &= h.pixel(image,427,200,QColor(62,213,199)); // new selected left border
    h.video=true; h.mask=1; image=h.frame(); ok &= h.m_gpuVideo;
    h.m_overlaySettings=true; image=h.frame(); ok &= !h.m_overlaySettings;
    h.lane=QImage(16,16,QImage::Format_ARGB32_Premultiplied); h.lane.fill(QColor(255,0,0,128));
    ++h.m_detectionRevision; image=h.frame(); ok &= h.pixel(image,600,300,QColor(128,0,127));
    fprintf(stderr,ok ? "GPU_HUD_TEST_PASS\n" : "GPU_HUD_TEST_FAIL\n");
    return ok ? 0 : 1;
}
'''.replace("SHADERS", shaders)
(out / "gpu_hud_test.cpp").write_text(header + method + glyph + fields + tail, encoding="utf-8")
(out / "gpu_hud_test.pro").write_text(
    'QT += core gui\nCONFIG += c++17 console\nCONFIG -= app_bundle\n'
    'TARGET = gpu_hud_test\nSOURCES += gpu_hud_test.cpp\nwin32-msvc:QMAKE_CXXFLAGS += /utf-8\n'
    f'INCLUDEPATH += "{src.as_posix()}"\n', encoding="utf-8")
print(out)
