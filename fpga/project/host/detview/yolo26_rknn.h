// yolo26_rknn.h -- YOLO26n RKNN inference for RK3568 NPU.
// Model contract (Desktop/yolo26_rk3568/README.md):
//   input : 640x640 RGB uint8 NHWC, normalization inside the model (mean0/std255)
//   e2e   : output [1,300,6] = x1,y1,x2,y2,score,class_id -- NMS-free, sorted
//   std   : output [1,4+nc,8400] cx,cy,w,h + class scores -- needs NMS here
#ifndef DETVIEW_YOLO26_RKNN_H
#define DETVIEW_YOLO26_RKNN_H

#include <string>
#include <vector>
#include <cstdint>

struct Det {
    float x1 = 0, y1 = 0, x2 = 0, y2 = 0, score = 0;
    int cls = 0;
};

class Yolo26Rknn {
public:
    ~Yolo26Rknn();
    // Load model; on failure returns false and fills err.
    bool load(const std::string &path, std::string &err);
    // e2e models don't encode the class count in the output shape; the caller
    // must supply it (labels list size) after load().
    void setNumClasses(int nc) { if (e2e_) nc_ = nc; }
    void unload();
    bool loaded() const { return ctx_ != 0; }

    // Header flavour actually found in the model file
    bool e2e() const { return e2e_; }
    bool split() const { return split_; }   // YOLO11 split head: boxes + scores
    int  numClasses() const { return nc_; }
    int  modelW() const { return mw_; }
    int  modelH() const { return mh_; }

    // input: NHWC RGB888 buffer of modelW*modelH*3 (letterboxed frame).
    // Returns boxes in MODEL coordinates; caller maps back to camera space.
    std::vector<Det> infer(const uint8_t *nhwc, float confThresh, float nmsThresh);

    double lastInferMs() const { return lastMs_; }
    // highest class score seen in the last infer (before thresholding) -- lets
    // the UI show how confident the model actually was even with 0 boxes.
    float lastScoreMax() const { return lastScoreMax_; }

private:
    void *ctx_ = nullptr;                 // rknn_context
    bool  e2e_ = false;
    bool  split_ = false;                 // [SPLIT] YOLO11 head: 2 outputs
    bool  posFirst_ = false;
    bool  generic_ = false;
    int   n_out_ = 1;                     // number of model outputs (1 or 2)
    int   boxOut_ = -1, clsOut_ = -1;     // split: which output is boxes/scores
    int   out_elems_ = 0;              // std head laid out as [1,8400,4+nc]
    int   nc_ = 0;
    int   mw_ = 640, mh_ = 640;
    double lastMs_ = 0;
    float  lastScoreMax_ = 0;
    int32_t out_zp_ = 0; float out_scale_ = 1.0f;
    int32_t in_zp_ = 0; float in_scale_ = 1.0f;
    std::vector<int8_t> qbuf_;
    std::vector<float> outBuf_;           // float outputs storage
};

// class-aware NMS, boxes in xyxy
std::vector<Det> nmsClassAware(std::vector<Det> dets, float iouThresh);

#endif // DETVIEW_YOLO26_RKNN_H
