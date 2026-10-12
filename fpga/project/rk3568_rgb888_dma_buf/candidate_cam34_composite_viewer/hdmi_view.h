#pragma once
#include <QByteArray>
#include <QImage>
#include <cstring>

namespace tdm {
// Isolated C3/C4 composite mode. The existing virtual-camera interface
// owns one combined recognition region. F can return to six-camera view.
constexpr int hdmiLeftCamera = 2;
constexpr int hdmiRightCamera = 3;
constexpr int hdmiInferenceCamera = 6; // virtual, full HDMI image; never a DMA index
constexpr int hdmiAnalyticsWidth = 640;
constexpr int hdmiAnalyticsHeight = 480;
constexpr int hdmiAnalyticsPad = 0; // existing pipeline expects 640x480
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
inline QImage hdmiAnalyticsImage(const QByteArray &left, const QByteArray &right) {
    constexpr int sourceWidth=640, height=480, rowBytes=sourceWidth*2;
    if(left.size()!=rowBytes*height || right.size()!=rowBytes*height) return {};
    QImage result(640,480,QImage::Format_RGB888);
    if(result.isNull()) return {};
    for(int y=0;y<height;++y) {
        auto out=result.scanLine(y);
        for(int camera=0;camera<2;++camera) {
            const auto src=reinterpret_cast<const unsigned char*>((camera?right:left).constData())+y*rowBytes;
            for(int x=0;x<320;++x) {
                const unsigned a=unsigned(src[x*4]) | (unsigned(src[x*4+1])<<8);
                const unsigned b=unsigned(src[x*4+2]) | (unsigned(src[x*4+3])<<8);
                const unsigned ar=(a>>11)&31, ag=(a>>5)&63, ab=a&31;
                const unsigned br=(b>>11)&31, bg=(b>>5)&63, bb=b&31;
                auto pixel=out+(camera*320+x)*3;
                pixel[0]=(((ar<<3)|(ar>>2))+((br<<3)|(br>>2))+1)/2;
                pixel[1]=(((ag<<2)|(ag>>4))+((bg<<2)|(bg>>4))+1)/2;
                pixel[2]=(((ab<<3)|(ab>>2))+((bb<<3)|(bb>>2))+1)/2;
            }
        }
    }
    return result;
}

int runHdmiViewSelfTest();
} // namespace tdm
