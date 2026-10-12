#include "hdmi_view.h"
#include <cstdio>
int tdm::runHdmiViewSelfTest(){
 int failures=0;auto expect=[&](bool ok,const char*n){std::fprintf(stderr,"%s %s\n",ok?"[ok]":"[FAIL]",n);failures+=!ok;};
 QImage left(640,480,QImage::Format_RGB16),right(640,480,QImage::Format_RGB16);left.fill(Qt::red);right.fill(Qt::blue);
 auto bytes=[](const QImage&i){return QByteArray(reinterpret_cast<const char*>(i.constBits()),i.sizeInBytes());};
 auto image=hdmiAnalyticsImage(bytes(left),bytes(right));
 expect(image.size()==QSize(640,480)&&image.format()==QImage::Format_RGB888,"model input stays 640x480 RGB888");
 expect(image.pixelColor(0,119)==QColor(114,114,114)&&image.pixelColor(639,360)==QColor(114,114,114),"exactly 120 gray rows above and below 640x240 content");
 expect(image.pixelColor(0,120).red()>240&&image.pixelColor(319,359).red()>240&&image.pixelColor(320,120).blue()>240&&image.pixelColor(639,359).blue()>240,"C3/C4 each 320x240 retain original aspect and correct side");
 for(int y=0;y<480;++y){auto p=reinterpret_cast<quint16*>(left.scanLine(y));for(int x=0;x<640;++x)p[x]=(y&1)?0:0xffff;}
 auto mean=hdmiAnalyticsImage(bytes(left),bytes(right));
 expect(mean.pixelColor(25,200)==QColor(128,128,128),"vertical neighbors are averaged, not stretched 320x480");
 left.fill(Qt::black);for(int y:{478,479})for(int x:{638,639})reinterpret_cast<quint16*>(left.scanLine(y))[x]=0xffff;
 auto edge=hdmiAnalyticsImage(bytes(left),bytes(right));
 expect(edge.pixelColor(319,359)==QColor(255,255,255)&&edge.pixelColor(318,359)==QColor(0,0,0),"last source 2x2 block reaches last content pixel");
 expect(hdmiAnalyticsImage(bytes(left),{}).isNull(),"missing source rejected");
 expect(hdmiPairReady(1000,980,990,3,3,3),"fresh pair accepted");
 expect(!hdmiPairReady(1000,800,990,3,3,3),"stale half rejected");
 expect(!hdmiPairReady(1000,940,990,3,3,3),"excessive skew rejected");
 expect(!hdmiPairReady(1000,980,990,3,2,3),"old generation rejected");
 std::fprintf(stderr,failures?"CAM34_320x240_SELFTEST_FAIL\n":"CAM34_320x240_SELFTEST_PASS\n");return failures?2:0;
}
