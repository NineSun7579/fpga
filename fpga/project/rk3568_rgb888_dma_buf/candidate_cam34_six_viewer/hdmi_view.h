#pragma once
#include <QByteArray>
#include <QImage>
#include <cstring>
#include "cam34_six.h"

namespace tdm {
// Isolated C3/C4 composite mode. The existing virtual-camera interface
// owns one combined recognition region. F can return to six-camera view.
constexpr int hdmiLeftCamera = 2;
constexpr int hdmiRightCamera = 3;
constexpr int hdmiInferenceCamera = 6; // virtual, full HDMI image; never a DMA index
constexpr int hdmiAnalyticsWidth = 640;
constexpr int hdmiAnalyticsHeight = 240;
constexpr int hdmiAnalyticsPad = 120; // existing pipeline expects 640x480
constexpr int hdmiModelPad = 80 + hdmiAnalyticsPad;

inline bool hdmiPairReady(qint64 now, qint64 left, qint64 right,
                          int generation, int leftGeneration, int rightGeneration) {
    // Latest-buffer pairing is bounded by time, not claimed to be tag-exact.
    return left > 0 && right > 0 && now >= left && now >= right &&
           now - left <= 100 && now - right <= 100 && qAbs(left - right) <= 40 &&
           leftGeneration == generation && rightGeneration == generation;
}

// One 2:1 horizontal box filter per source. The complete vertical field
// is retained. RAW DMA transfer remains two 640x480 RGB565 frames.
inline QImage hdmiAnalyticsImage(const QByteArray&left,const QByteArray&right){
 if(left.size()!=640*480*2||right.size()!=640*480*2)return {};
 QImage result(640,480,QImage::Format_RGB888);if(result.isNull())return {};
 result.fill(qRgb(114,114,114));
 for(int y=0;y<240;++y)for(int c=0;c<2;++c){
  const auto raw=reinterpret_cast<const unsigned char*>((c?right:left).constData());
  auto out=result.scanLine(y+120)+c*320*3;
  for(int x=0;x<320;++x){const auto top=raw+y*2*1280+x*4;cam34::average2x2(top,top+1280,out+x*3);}
 }
 return result;
}

int runHdmiViewSelfTest();
} // namespace tdm
