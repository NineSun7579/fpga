// preprocess.h -- color/geometry conversion between the camera wire format
// (RGB565, 640x480) and the YOLO26 model input (RGB888 uint8, 640x640 NHWC).
#ifndef DETVIEW_PREPROCESS_H
#define DETVIEW_PREPROCESS_H

#include <cstdint>
#include <cstring>

namespace prep {

// Camera frame geometry (must match ov5640_top.v H_CMOS_DISP/V_CMOS_DISP)
constexpr int CAM_W = 640;
constexpr int CAM_H = 480;
constexpr int FRAME_BYTES = CAM_W * CAM_H * 2;   // 614400

// DDR tag slots written by the [FRTAG] bitstream: frame counter of each
// ping-pong buffer, 32-bit little-endian in bytes 0..3 of a 16B AXI beat
// placed right after the frame in DDR.
constexpr uint32_t TAG_ADDR_1 = 0x00800000u + FRAME_BYTES; // 0x00896000
constexpr uint32_t TAG_ADDR_2 = 0x00A00000u + FRAME_BYTES; // 0x00A96000

// RGB565 -> RGB888 with bit replication (no precision invented, none lost).
// byteSwap: fix wire byte order (camview B key). rbSwap: swap R/B channels (C key).
inline void rgb565ToRgb888(const uint8_t *src, int w, int h, uint8_t *dst,
                           bool byteSwap, bool rbSwap) {
    for (int i = 0; i < w * h; ++i) {
        uint16_t px = (uint16_t)(src[2 * i] | (src[2 * i + 1] << 8));
        if (byteSwap) px = (uint16_t)((px >> 8) | (px << 8));
        int r5 = (px >> 11) & 0x1F;
        int g6 = (px >> 5) & 0x3F;
        int b5 = px & 0x1F;
        int r8 = (r5 << 3) | (r5 >> 2);
        int g8 = (g6 << 2) | (g6 >> 4);
        int b8 = (b5 << 3) | (b5 >> 2);
        if (rbSwap) { int t = r8; r8 = b8; b8 = t; }
        dst[3 * i + 0] = (uint8_t)r8;
        dst[3 * i + 1] = (uint8_t)g8;
        dst[3 * i + 2] = (uint8_t)b8;
    }
}

// 640x480 -> 640x640 letterbox: scale 1.0, x_pad 0, 80 black rows top and bottom.
// Returns y_pad (rows added on top) so callers can map boxes back:
//   y_src = y_model - yPad;  x_src = x_model.
inline int letterboxCamToModel(const uint8_t *src, uint8_t *dst, int modelW, int modelH) {
    const int padTop = (modelH - CAM_H) / 2;   // 80 for 640x640
    memset(dst, 0, (size_t)padTop * modelW * 3);
    for (int y = 0; y < CAM_H; ++y)
        memcpy(dst + (size_t)(padTop + y) * modelW * 3, src + (size_t)y * CAM_W * 3,
               (size_t)CAM_W * 3);
    memset(dst + (size_t)(padTop + CAM_H) * modelW * 3, 0,
           (size_t)(modelH - padTop - CAM_H) * modelW * 3);
    return padTop;
}

} // namespace prep
#endif // DETVIEW_PREPROCESS_H
