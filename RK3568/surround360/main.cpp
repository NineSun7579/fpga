#include "capture_source.h"
#include "surround_engine.h"
#include "calibration_panel.h"
#include "panorama_renderer.h"
#include "stereo_selection.h"
#include <QApplication>
#include <QOpenGLWindow>
#include <QOpenGLFunctions>
#include <QOpenGLShaderProgram>
#include <QOpenGLFramebufferObject>
#include <QPainter>
#include <QMouseEvent>
#include <QWheelEvent>
#include <QKeyEvent>
#include <QTimer>
#include <QMutex>
#include <QMutexLocker>
#include <QDateTime>
#include <QDir>
#include <QFileInfo>
#include <QGuiApplication>
#include <QScreen>
#include <QSurfaceFormat>
#include <QSaveFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <atomic>
#include <algorithm>
#include <memory>
#include <cmath>
#include <ctime>
#include <opencv2/core.hpp>

using namespace surround;
static qint64 nowMs(){timespec t{};clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1000LL+t.tv_nsec/1000000;}

struct ComposedFrame {
    ProcessResult image;
    CaptureSnapshot capture;
    ViewMode mode=ViewMode::Panorama;
    double processingMs=0;
    quint64 revision=0;
};

// Rendering consumes a single latest-result mailbox. Heavy OpenCV work never
// runs on the event/drag thread; completed old frames are replaced, not queued.
class Composer : public QThread {
public:
    Composer(CaptureSource* capture,Configuration config):m_capture(capture),m_config(config){}
    ~Composer() override {stop();}
    void stop(){m_stop=true;wait();}
    void setMode(ViewMode mode){QMutexLocker lock(&m_mutex);m_mode=mode;}
    void setConfiguration(const Configuration& config){QMutexLocker lock(&m_mutex);m_config=config;++m_configRevision;}
    ComposedFrame latest(){QMutexLocker lock(&m_mutex);return m_latest;}
protected:
    void run() override {
        try {
            Engine engine(m_config);
            quint64 configRevision=0,frameRevision=0;
            qint64 reportAt=nowMs(),sumUs=0;int processed=0;
            while(!m_stop) {
                const qint64 started=nowMs();
                Configuration config;ViewMode mode;quint64 wanted;
                {QMutexLocker lock(&m_mutex);config=m_config;mode=m_mode;wanted=m_configRevision;}
                if(wanted!=configRevision){QString error;if(!engine.setConfig(config,&error))fprintf(stderr,"[configuration] rejected: %s\n",qPrintable(error));configRevision=wanted;}
                const CaptureSnapshot snapshot=m_capture->snapshot();
                FrameInput frames;frames.images=snapshot.images;frames.capturedMs=snapshot.capturedMs;frames.sequence=snapshot.sequences;
                ComposedFrame result;result.capture=snapshot;result.mode=mode;
                if(mode==ViewMode::Birdseye)result.image=engine.render(frames,mode,nowMs());
                else {
                    // Panorama rays are sampled directly from six GPU textures.
                    // Keep only metadata here; no CPU full-panorama allocation.
                    result.image.ageMs.fill(-1);result.image.approximateGeometry=false;
                    QStringList missing;int active=0;std::array<double,CameraCount>freshness{};
                    for(int i=0;i<CameraCount;++i){
                        const auto&camera=config.cameras[i];
                        result.image.approximateGeometry|=!camera.intrinsicCalibrated||!camera.yawCalibrated;
                        const qint64 age=nowMs()-snapshot.capturedMs[i];
                        if(!snapshot.images[i].isNull()&&age>=0&&age<config.staleMs){result.image.active[i]=true;result.image.ageMs[i]=age;++active;freshness[i]=age<=config.freshMs?1.0:double(config.staleMs-age)/double(config.staleMs-config.freshMs);}
                        else missing<<QString("C%1").arg(i+1);
                    }
                    const auto selected=selectStereoEyes(freshness);
                    result.image.status=QString("GPU四方位 · %1/6路实时 · 前C%2 / 后C%3").arg(active).arg(selected[0]?1:2).arg(selected[4]?5:6);
                    if(!missing.isEmpty())result.image.status+=" · 缺少 "+missing.join('/');
                }
                if(mode==ViewMode::Birdseye&&!result.image.output.isNull()){
                    QPainter car(&result.image.output);car.setRenderHint(QPainter::Antialiasing);
                    const QPointF center(result.image.output.width()*.5,result.image.output.height()*.5);
                    const double scale=result.image.output.width()/512.;
                    car.translate(center);car.scale(scale,scale);car.setPen(QPen(QColor(100,160,185),2));car.setBrush(QColor(26,53,69));car.drawRoundedRect(QRectF(-25,-46,50,92),9,9);
                    car.setBrush(QColor(66,135,157));car.drawRoundedRect(QRectF(-19,-28,38,31),5,5);
                    car.setPen(QPen(QColor(91,220,200),3));car.drawLine(QPointF(0,-53),QPointF(0,-65));car.drawLine(QPointF(0,-65),QPointF(-5,-59));car.drawLine(QPointF(0,-65),QPointF(5,-59));car.end();
                }
                result.processingMs=double(nowMs()-started);result.revision=++frameRevision;
                {QMutexLocker lock(&m_mutex);m_latest=std::move(result);}
                ++processed;sumUs+=(nowMs()-started)*1000;
                if(nowMs()-reportAt>=5000){fprintf(stderr,"[compose] mode=%s fps=%.2f mean_ms=%.2f frames=%d\n",mode==ViewMode::Panorama?"panorama":"bird",processed*1000.0/(nowMs()-reportAt),sumUs/1000.0/processed,processed);reportAt=nowMs();sumUs=0;processed=0;}
                const qint64 elapsed=nowMs()-started;if(elapsed<50)msleep(unsigned(50-elapsed));
            }
        } catch(const std::exception& e){fprintf(stderr,"[compose] failure: %s\n",e.what());}
    }
private:
    CaptureSource* m_capture;Configuration m_config;ViewMode m_mode=ViewMode::Panorama;
    QMutex m_mutex;ComposedFrame m_latest;std::atomic<bool>m_stop{false};quint64 m_configRevision=0;
};

class SurroundWindow : public QOpenGLWindow,protected QOpenGLFunctions {
public:
    SurroundWindow(bool synthetic,Configuration config,QString configPath):m_configuration(config),m_configPath(configPath),m_synthetic(synthetic){
        setTitle("Surround360 · 六路环视");resize(1280,800);
        m_capture=std::make_unique<CaptureSource>(synthetic);
        m_composer=std::make_unique<Composer>(m_capture.get(),config);
        m_capture->start();m_composer->start();
        QObject::connect(&m_refresh,&QTimer::timeout,this,[this]{m_latest=m_composer->latest();update();});m_refresh.start(33);
        m_reportAt=nowMs();
    }
    ~SurroundWindow() override {m_refresh.stop();m_composer->stop();m_capture->stop();if(context()){makeCurrent();m_panorama.release();m_panoramaFbo.reset();glDeleteTextures(1,&m_sceneTexture);glDeleteTextures(1,&m_hudTexture);doneCurrent();}}
    bool compositionReady() const {
        return m_latest.revision>0&&m_latest.mode==m_mode&&
            std::any_of(m_latest.image.active.begin(),m_latest.image.active.end(),[](bool active){return active;})&&
            (m_mode==ViewMode::Panorama||!m_latest.image.output.isNull());
    }
    void setMode(ViewMode mode){m_mode=mode;m_composer->setMode(mode);m_hudDirty=true;update();}
    void screenshot(){
        const QString dir=QFileInfo(m_configPath).absolutePath()+"/screenshots";QDir().mkpath(dir);
        const QString file=dir+"/surround_"+(m_mode==ViewMode::Panorama?"panorama_":"bird_")+QDateTime::currentDateTimeUtc().toString("yyyyMMdd_HHmmss_zzz")+".png";
        const QImage pixels=grabFramebuffer();QSaveFile output(file);
        const bool saved=!pixels.isNull()&&output.open(QIODevice::WriteOnly)&&pixels.save(&output,"PNG")&&output.commit();
        fprintf(stderr,"[screenshot] %s %s\n",saved?"PASS":"FAIL",qPrintable(file));
    }
    void rotateYaw(double delta){m_yaw=std::remainder(m_yaw+delta,360.0);update();}
    bool testDragAndSwitch(){
        const double original=m_yaw;
        QMouseEvent press(QEvent::MouseButtonPress,QPointF(300,220),Qt::LeftButton,Qt::LeftButton,Qt::NoModifier);
        QMouseEvent move(QEvent::MouseMove,QPointF(540,220),Qt::NoButton,Qt::LeftButton,Qt::NoModifier);
        QMouseEvent release(QEvent::MouseButtonRelease,QPointF(540,220),Qt::LeftButton,Qt::NoButton,Qt::NoModifier);
        QApplication::sendEvent(this,&press);QApplication::sendEvent(this,&move);QApplication::sendEvent(this,&release);
        QKeyEvent bird(QEvent::KeyPress,Qt::Key_2,Qt::NoModifier);QApplication::sendEvent(this,&bird);
        const bool valid=m_yaw!=original&&m_mode==ViewMode::Birdseye;
        fprintf(stderr,"[interaction] mouse_drag_and_mode_switch=%s yaw_delta=%.1f\n",valid?"PASS":"FAIL",m_yaw-original);
        return valid;
    }
    void testCalibrationPanel(){
        auto* panel=new CalibrationPanel(m_configuration,m_capture->snapshot(),m_configPath);
        panel->setAttribute(Qt::WA_DeleteOnClose);panel->show();
        QTimer::singleShot(700,panel,[this,panel]{
            const QString file=QFileInfo(m_configPath).absolutePath()+"/calibration_panel.png";
            const bool saved=panel->grab().save(file);
            fprintf(stderr,"[interaction] calibration_panel=%s path=%s\n",saved?"PASS":"FAIL",qPrintable(file));panel->close();
        });
    }
protected:
    void initializeGL() override {
        initializeOpenGLFunctions();
        const char* vertex="attribute vec2 position;attribute vec2 texcoord;varying vec2 uv;void main(){uv=texcoord;gl_Position=vec4(position,0.,1.);}";
        const char* fragment=R"(
            #ifdef GL_ES
            precision mediump float;
            #endif
            varying vec2 uv;uniform sampler2D image;uniform float mode;uniform float yaw;uniform float pitch;uniform float hfov;uniform float verticalFov;uniform float viewportAspect;uniform float sourceAspect;
            void main(){vec2 p=uv;
              if(mode>0.5 && mode<1.5){
                vec2 q=vec2((uv.x-.5)*2.,(.5-uv.y)*2.);float sx=q.x*tan(hfov*.5);float sy=q.y*tan(hfov*.5)/viewportAspect;
                float ry=cos(pitch)*sy+sin(pitch);float rz=cos(pitch)-sin(pitch)*sy;
                float theta=atan(sx,rz)+yaw;float elevation=atan(ry,sqrt(sx*sx+rz*rz));
                p.x=fract(theta/6.283185307+.5);p.y=.5-elevation/verticalFov;
                if(p.y<0.||p.y>1.){gl_FragColor=vec4(.025,.035,.05,1.);return;}
              }else if(mode>1.5){
                if(viewportAspect>sourceAspect)p.x=(uv.x-.5)*viewportAspect/sourceAspect+.5;
                else p.y=(uv.y-.5)*sourceAspect/viewportAspect+.5;
                if(p.x<0.||p.x>1.||p.y<0.||p.y>1.){gl_FragColor=vec4(.025,.035,.05,1.);return;}
              }
              gl_FragColor=texture2D(image,p);
            })";
        if(!m_shader.addShaderFromSourceCode(QOpenGLShader::Vertex,vertex)||!m_shader.addShaderFromSourceCode(QOpenGLShader::Fragment,fragment)||!m_shader.link()){
            fprintf(stderr,"[gl] shader error: %s\n",qPrintable(m_shader.log()));QCoreApplication::exit(2);return;
        }
        glGenTextures(1,&m_sceneTexture);glGenTextures(1,&m_hudTexture);
        QString error;if(!m_panorama.initialize(&error)){fprintf(stderr,"[gl] panorama shader error: %s\n",qPrintable(error));QCoreApplication::exit(2);return;}
        m_panoramaFbo=std::make_unique<QOpenGLFramebufferObject>(QSize(640,480));
        if(!m_panoramaFbo->isValid()){fprintf(stderr,"[gl] panorama framebuffer error\n");QCoreApplication::exit(2);return;}
        fprintf(stderr,"[gl] renderer=%s\n",reinterpret_cast<const char*>(glGetString(GL_RENDERER)));
    }
    void resizeGL(int,int) override {m_hudDirty=true;}
    void paintGL() override {
        const qint64 started=nowMs();
        glBindFramebuffer(GL_FRAMEBUFFER,defaultFramebufferObject());
        glDisable(GL_SCISSOR_TEST);glDisable(GL_DEPTH_TEST);glDisable(GL_CULL_FACE);
        glViewport(0,0,int(width()*devicePixelRatio()),int(height()*devicePixelRatio()));
        glClearColor(.025f,.035f,.05f,1);glClear(GL_COLOR_BUFFER_BIT);
        if(m_latest.mode==ViewMode::Birdseye&&m_latest.revision!=m_uploadedRevision && !m_latest.image.output.isNull()){
            upload(m_sceneTexture,m_latest.image.output);m_uploadedRevision=m_latest.revision;++m_freshPaints;
        }
        const int top=104,bottom=86;const int viewHeight=std::max(1,height()-top-bottom);
        if(m_latest.mode==ViewMode::Panorama&&m_latest.revision){
            // Six-camera projection is performed at the requested 480p,
            // then a single inexpensive texture scales it to the monitor.
            m_panoramaFbo->bind();glViewport(0,0,640,480);
            QString error;
            if(!m_panorama.draw(m_latest.capture,m_configuration,m_yaw,m_pitch,m_hfov,float(width())/viewHeight,nowMs(),&error)){
                fprintf(stderr,"[gl] panorama draw error: %s\n",qPrintable(error));QCoreApplication::exit(2);
            }
            if(m_panorama.uploadBytes()>0)++m_freshPaints;
            m_panoramaFbo->release();glBindFramebuffer(GL_FRAMEBUFFER,defaultFramebufferObject());
            glViewport(0,int(bottom*devicePixelRatio()),int(width()*devicePixelRatio()),int(viewHeight*devicePixelRatio()));
            draw(m_panoramaFbo->texture(),0.f,1,1,1.f,0.f);
        }else if(m_uploadedRevision){
            glViewport(0,int(bottom*devicePixelRatio()),int(width()*devicePixelRatio()),int(viewHeight*devicePixelRatio()));
            draw(m_sceneTexture,m_latest.mode==ViewMode::Panorama?1.f:2.f,float(width())/viewHeight,float(m_latest.image.output.width())/m_latest.image.output.height());
        }
        if(m_hudDirty||nowMs()-m_hudAt>500){rebuildHud();m_hudDirty=false;m_hudAt=nowMs();}
        glDisable(GL_SCISSOR_TEST);glEnable(GL_BLEND);glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);
        glViewport(0,int((height()-top)*devicePixelRatio()),int(width()*devicePixelRatio()),int(top*devicePixelRatio()));draw(m_hudTexture,0.f,1,1,0.f,.5f);
        glViewport(0,0,int(width()*devicePixelRatio()),int(bottom*devicePixelRatio()));draw(m_hudTexture,0.f,1,1,.5f,1.f);
        glDisable(GL_BLEND);++m_paints;m_paintSum+=nowMs()-started;m_paintMax=std::max(m_paintMax,nowMs()-started);
        if(nowMs()-m_reportAt>=5000){const double seconds=(nowMs()-m_reportAt)/1000.;fprintf(stderr,"[display] paints_fps=%.2f new_frames_fps=%.2f paint_mean_ms=%.2f paint_max_ms=%lld yaw=%.1f fov=%.1f mode=%s size=%dx%d dpr=%.2f\n",m_paints/seconds,m_freshPaints/seconds,m_paintSum/double(m_paints),(long long)m_paintMax,m_yaw,m_hfov,m_mode==ViewMode::Panorama?"panorama":"bird",width(),height(),devicePixelRatio());m_reportAt=nowMs();m_paints=m_freshPaints=0;m_paintSum=m_paintMax=0;}
    }
    void mousePressEvent(QMouseEvent* event) override {
        if(event->button()!=Qt::LeftButton)return;
        if(event->pos().y()<54){const int x=event->pos().x();if(x<180)setMode(ViewMode::Panorama);else if(x<360)setMode(ViewMode::Birdseye);else if(x<500)calibrate();else if(x<640)screenshot();return;}
        m_dragging=true;m_lastMouse=event->pos();
    }
    void mouseMoveEvent(QMouseEvent* event) override {if(m_dragging&&m_mode==ViewMode::Panorama){rotateYaw(-(event->pos().x()-m_lastMouse.x())*.22);m_pitch=std::clamp(m_pitch+(event->pos().y()-m_lastMouse.y())*.12,-25.,25.);m_lastMouse=event->pos();}}
    void mouseReleaseEvent(QMouseEvent*) override {m_dragging=false;}
    void wheelEvent(QWheelEvent*event)override {m_hfov=std::clamp(m_hfov-event->angleDelta().y()/120.*5.,45.,120.);m_hudDirty=true;update();}
    void keyPressEvent(QKeyEvent*event)override {
        switch(event->key()){
        case Qt::Key_1:setMode(ViewMode::Panorama);break;case Qt::Key_2:setMode(ViewMode::Birdseye);break;
        case Qt::Key_Tab:setMode(m_mode==ViewMode::Panorama?ViewMode::Birdseye:ViewMode::Panorama);break;
        case Qt::Key_Left:rotateYaw(-15);break;case Qt::Key_Right:rotateYaw(15);break;
        case Qt::Key_C:calibrate();break;case Qt::Key_S:screenshot();break;
        case Qt::Key_F:if(windowState()==Qt::WindowFullScreen)showNormal();else showFullScreen();break;
        case Qt::Key_Q:case Qt::Key_Escape:close();break;default:QOpenGLWindow::keyPressEvent(event);
        }
    }
private:
    void calibrate(){
        auto*panel=new CalibrationPanel(m_configuration,m_capture->snapshot(),m_configPath);
        panel->setAttribute(Qt::WA_DeleteOnClose);QObject::connect(panel,&CalibrationPanel::applied,panel,[this](const Configuration&config){m_configuration=config;m_composer->setConfiguration(config);m_hudDirty=true;});panel->show();panel->raise();
    }
    void upload(GLuint texture,const QImage& image){
        const QImage pixels=image.convertToFormat(QImage::Format_RGBA8888);glBindTexture(GL_TEXTURE_2D,texture);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
        // Panorama wrap is calculated explicitly; clamp prevents GLES2 NPOT
        // repeat restrictions from invalidating the 1536x480 texture.
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
        glPixelStorei(GL_UNPACK_ALIGNMENT,4);glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,pixels.width(),pixels.height(),0,GL_RGBA,GL_UNSIGNED_BYTE,pixels.constBits());
    }
    void draw(GLuint texture,float mode,float aspect,float sourceAspect,float v0=0,float v1=1){
        const GLfloat positions[]={-1,-1,1,-1,-1,1,1,1};const GLfloat tex[]={0,v1,1,v1,0,v0,1,v0};
        m_shader.bind();m_shader.setUniformValue("image",0);m_shader.setUniformValue("mode",mode);m_shader.setUniformValue("yaw",float(m_yaw*M_PI/180));m_shader.setUniformValue("pitch",float(m_pitch*M_PI/180));m_shader.setUniformValue("hfov",float(m_hfov*M_PI/180));m_shader.setUniformValue("verticalFov",float(m_configuration.verticalFovDeg*M_PI/180));m_shader.setUniformValue("viewportAspect",aspect);m_shader.setUniformValue("sourceAspect",sourceAspect);
        glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,texture);m_shader.enableAttributeArray("position");m_shader.enableAttributeArray("texcoord");m_shader.setAttributeArray("position",GL_FLOAT,positions,2);m_shader.setAttributeArray("texcoord",GL_FLOAT,tex,2);glDrawArrays(GL_TRIANGLE_STRIP,0,4);m_shader.disableAttributeArray("position");m_shader.disableAttributeArray("texcoord");m_shader.release();
    }
    void rebuildHud(){
        QImage image(std::max(640,width()),208,QImage::Format_RGBA8888);image.fill(Qt::transparent);QPainter p(&image);p.fillRect(image.rect(),QColor(12,22,34,245));p.setRenderHint(QPainter::Antialiasing);p.setFont(QFont("Noto Sans CJK SC",13));
        const QStringList titles={"1  环绕视图","2  360俯视图","C  标定","S  截图"};const int xs[]={8,188,368,508};const int widths[]={164,164,124,124};
        for(int i=0;i<4;++i){p.setPen(Qt::NoPen);p.setBrush((i==0&&m_mode==ViewMode::Panorama)||(i==1&&m_mode==ViewMode::Birdseye)?QColor(20,110,135):QColor(34,50,68));p.drawRoundedRect(QRect(xs[i],8,widths[i],40),7,7);p.setPen(Qt::white);p.drawText(QRect(xs[i],8,widths[i],40),Qt::AlignCenter,titles[i]);}
        p.setPen(m_latest.image.approximateGeometry?QColor(255,194,75):QColor(76,214,158));
        p.drawText(QRect(14,58,image.width()-20,34),Qt::AlignVCenter,(m_synthetic?"演示画面 · ":"")+QString(m_latest.image.approximateGeometry?"未标定预览 · 接缝与俯视几何待校正":"已载入标定")+" · "+m_latest.image.status);
        if(!m_latest.capture.error.isEmpty()){p.setPen(QColor(255,120,100));p.drawText(QRect(650,8,std::max(1,image.width()-660),44),Qt::AlignVCenter|Qt::TextWordWrap,m_latest.capture.error);}
        p.setFont(QFont("Noto Sans CJK SC",10));const QStringList roles={"前双目1","前双目2","左","右","后双目1","后双目2"};const int cardWidth=image.width()/6;
        for(int i=0;i<6;++i){const qint64 age=m_latest.capture.images[i].isNull()?-1:nowMs()-m_latest.capture.capturedMs[i];p.setPen(age>=0&&age<1000?QColor(99,213,170):QColor(255,159,97));p.drawText(QRect(i*cardWidth+8,112,cardWidth-12,40),Qt::AlignVCenter,QString("C%1 %2  %3 fps\n%4").arg(i+1).arg(roles[i]).arg(m_latest.capture.fps[i],0,'f',1).arg(age<0?"无画面":age>1000?"输入停止":"实时"));}
        p.setPen(QColor(150,180,200));p.drawText(QRect(14,166,image.width()-20,32),Qt::AlignVCenter,QString("鼠标拖动转向 · 滚轮缩放 · Tab切换 · F全屏 · Q退出   |   480p六路 · 图像处理 %1ms").arg(m_latest.processingMs,0,'f',1));p.end();upload(m_hudTexture,image);
    }
    std::unique_ptr<CaptureSource>m_capture;std::unique_ptr<Composer>m_composer;Configuration m_configuration;QString m_configPath;
    QTimer m_refresh;ComposedFrame m_latest;QOpenGLShaderProgram m_shader;PanoramaRenderer m_panorama;GLuint m_sceneTexture=0,m_hudTexture=0;quint64 m_uploadedRevision=0;
    std::unique_ptr<QOpenGLFramebufferObject>m_panoramaFbo;
    ViewMode m_mode=ViewMode::Panorama;double m_yaw=0,m_pitch=0,m_hfov=85;bool m_synthetic=false,m_dragging=false,m_hudDirty=true;QPoint m_lastMouse;
    qint64 m_hudAt=0,m_reportAt=0,m_paintSum=0,m_paintMax=0;int m_paints=0,m_freshPaints=0;
};

int main(int argc,char**argv){
    qputenv("QT_SCALE_FACTOR","1");qputenv("QT_AUTO_SCREEN_SCALE_FACTOR","0");
    QSurfaceFormat format;format.setRenderableType(QSurfaceFormat::OpenGLES);format.setVersion(2,0);format.setSwapInterval(1);QSurfaceFormat::setDefaultFormat(format);
    QApplication app(argc,argv);app.setApplicationName("surround360");cv::setNumThreads(2);const auto args=app.arguments();
    if(args.contains("--selftest")){const int capture=runCaptureSelfTest();const int engine=runEngineSelfTest();return capture||engine?1:0;}
    QString configPath="/userdata/surround360/calibration.json";const int configOption=args.indexOf("--config");if(configOption>=0&&configOption+1<args.size())configPath=args[configOption+1];
    QDir().mkpath(QFileInfo(configPath).absolutePath());Configuration config;
    if(QFileInfo::exists(configPath)){QString error;if(!Configuration::load(configPath,config,&error)){fprintf(stderr,"[configuration] %s\n",qPrintable(error));return 2;}}
    else {QString error;if(!config.save(configPath,&error))fprintf(stderr,"[configuration] unable to save preview defaults: %s\n",qPrintable(error));}
    SurroundWindow window(args.contains("--synthetic"),config,configPath);
    if(args.contains("--bird"))window.setMode(ViewMode::Birdseye);
    if(args.contains("--fullscreen"))window.showFullScreen();else window.show();
    auto seconds=[&](QString option){const int index=args.indexOf(option);return index>=0&&index+1<args.size()?args[index+1].toInt():0;};
    if(seconds("--duration")>0)QTimer::singleShot(seconds("--duration")*1000,&app,&QCoreApplication::quit);
    if(seconds("--shot")>0)QTimer::singleShot(seconds("--shot")*1000,&window,[&]{window.screenshot();});
    if(args.contains("--demo-tour")){
        auto*tour=new QTimer(&window);QObject::connect(tour,&QTimer::timeout,&window,[&]{window.rotateYaw(2);});tour->start(50);
        QTimer::singleShot(12000,&window,[&]{window.setMode(ViewMode::Birdseye);});
        QTimer::singleShot(24000,&window,[&]{window.setMode(ViewMode::Panorama);});
    }
    if(args.contains("--interaction-test")){
        QTimer::singleShot(7000,&window,[&]{window.setMode(ViewMode::Panorama);window.screenshot();if(!window.testDragAndSwitch())QCoreApplication::exit(2);});
        QTimer::singleShot(17000,&window,[&]{window.screenshot();window.setMode(ViewMode::Panorama);});
    }
    if(args.contains("--calibration-test"))QTimer::singleShot(11000,&window,[&]{window.testCalibrationPanel();});
    QTimer::singleShot(10000,&window,[&]{if(!window.compositionReady()){fprintf(stderr,"[startup] no composed image\n");QCoreApplication::exit(2);}});
    return app.exec();
}
