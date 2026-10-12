#include "hdmi_view.h"
#include <cstdio>
int tdm::runHdmiViewSelfTest(){
 int failures=0;auto expect=[&](bool ok,const char*n){fprintf(stderr,"%s %s\n",ok?"[ok]":"[FAIL]",n);failures+=!ok;};
 QImage left(320,240,QImage::Format_RGB16),right(320,240,QImage::Format_RGB16);left.fill(Qt::red);right.fill(Qt::blue);
 auto bytes=[](const QImage&i){return QByteArray(reinterpret_cast<const char*>(i.constBits()),i.sizeInBytes());};
 auto image=hdmiAnalyticsImage(bytes(left),bytes(right));
 expect(image.size()==QSize(640,480)&&image.format()==QImage::Format_RGB888,"network input stays 640x480 RGB888");
 expect(image.pixelColor(0,119)==QColor(114,114,114)&&image.pixelColor(639,360)==QColor(114,114,114),"exact 120 gray rows above and below");
 expect(image.pixelColor(0,120).red()>240&&image.pixelColor(319,359).red()>240&&image.pixelColor(320,120).blue()>240&&image.pixelColor(639,359).blue()>240,"compressed C3/C4 bytes placed once without a second resize");
 left.fill(Qt::black);reinterpret_cast<quint16*>(left.scanLine(239))[319]=0xffff;
 auto edge=hdmiAnalyticsImage(bytes(left),bytes(right));
 expect(edge.pixelColor(319,359)==QColor(255,255,255)&&edge.pixelColor(318,359)==QColor(0,0,0),"wire bottom-right pixel survives");
 expect(hdmiAnalyticsImage(bytes(left),{}).isNull(),"missing frame rejected");
 expect(hdmiAnalyticsImage(QByteArray(640*480*2,0),bytes(right)).isNull(),"640x480 RAW input rejected rather than silently compressed by CPU");
 expect(hdmiPairReady(1000,980,990,3,3,3),"fresh pair accepted");
 expect(!hdmiPairReady(1000,800,990,3,3,3),"stale frame rejected");
 expect(!hdmiPairReady(1000,940,990,3,3,3),"excessive skew rejected");
 expect(!hdmiPairReady(1000,980,990,3,2,3),"generation mismatch rejected");
 fprintf(stderr,failures?"CAM34_WIRE_SELFTEST_FAIL\n":"CAM34_WIRE_SELFTEST_PASS\n");return failures?2:0;
}
