#include "hdmi_view.h"
#include <cstdio>
int tdm::runHdmiViewSelfTest() {
 int failures=0;
 auto expect=[&](bool ok,const char* name){std::fprintf(stderr,"%s %s\n",ok?"[ok]":"[FAIL]",name);failures+=!ok;};
 QImage left(640,480,QImage::Format_RGB16),right(640,480,QImage::Format_RGB16);
 left.fill(Qt::red);right.fill(Qt::blue);
 QByteArray l(reinterpret_cast<const char*>(left.constBits()),left.sizeInBytes());
 QByteArray r(reinterpret_cast<const char*>(right.constBits()),right.sizeInBytes());
 const QImage image=hdmiAnalyticsImage(l,r);
 expect(image.size()==QSize(640,480)&&image.format()==QImage::Format_RGB888,"one 640x480 RGB888 input");
 expect(image.pixelColor(0,0).red()>240&&image.pixelColor(319,479).red()>240&&
        image.pixelColor(320,0).blue()>240&&image.pixelColor(639,479).blue()>240,
        "C3 occupies all left rows and C4 all right rows without padding");
 for(int y=0;y<480;++y){auto p=reinterpret_cast<quint16*>(left.scanLine(y));for(int x=0;x<640;++x)p[x]=(x&1)?0:0xffff;}
 l=QByteArray(reinterpret_cast<const char*>(left.constBits()),left.sizeInBytes());
 const QImage mean=hdmiAnalyticsImage(l,r);
 expect(mean.pixelColor(25,200)==QColor(128,128,128),"black-white adjacent columns average to 128 rather than nearest-neighbor");
 left.fill(Qt::black);reinterpret_cast<quint16*>(left.scanLine(479))[638]=0xffff;reinterpret_cast<quint16*>(left.scanLine(479))[639]=0xffff;
 l=QByteArray(reinterpret_cast<const char*>(left.constBits()),left.sizeInBytes());
 const QImage edge=hdmiAnalyticsImage(l,r);
 expect(edge.pixelColor(319,479)==QColor(255,255,255)&&edge.pixelColor(318,479)==QColor(0,0,0),"last columns and bottom row preserved");
 expect(hdmiAnalyticsImage(l,{}).isNull()&&hdmiAnalyticsImage(l,r.left(100)).isNull(),"missing and truncated half rejected");
 expect(hdmiPairReady(1000,980,990,3,3,3),"fresh current-generation pair accepted");
 expect(!hdmiPairReady(1000,800,990,3,3,3),"stale half rejected");
 expect(!hdmiPairReady(1000,940,990,3,3,3),"excessive skew rejected");
 expect(!hdmiPairReady(1000,980,990,3,2,3),"old generation rejected");
 expect(!hdmiPairReady(1000,1001,990,3,3,3),"future timestamp rejected");
 std::fprintf(stderr,failures?"CAM34_SELFTEST_FAIL\n":"CAM34_SELFTEST_PASS\n");return failures?2:0;
}
