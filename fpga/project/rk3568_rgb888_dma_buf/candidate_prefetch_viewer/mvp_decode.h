#pragma once
#include <array>
#include <cmath>
#include <vector>
#include "rknn_api.h"

namespace mvp {
// Exact anchors from pipeline.json and dataset_summary.json in the delivery.
struct LaneContract {
    std::array<float, 24> rows{{201.17999267578125f,212.2178192138672f,223.25564575195312f,234.29347229003906f,245.331298828125f,256.369140625f,267.4069519042969f,278.4447937011719f,289.48260498046875f,300.5204162597656f,311.5582580566406f,322.5960693359375f,333.6339111328125f,344.6717224121094f,355.7095642089844f,366.7474060058594f,377.78521728515625f,388.82305908203125f,399.8608703613281f,410.8987121582031f,421.9365234375f,432.9743347167969f,444.0121765136719f,455.04998779296875f}};
    std::array<float, 32> cols{{12.779999732971191f,32.56838607788086f,52.356773376464844f,72.14515686035156f,91.93354797363281f,111.72193145751953f,131.51031494140625f,151.2987060546875f,171.0871124267578f,190.87548828125f,210.66387939453125f,230.4522705078125f,250.24066162109375f,270.029052734375f,289.81744384765625f,309.6058044433594f,329.3941955566406f,349.1825866699219f,368.970947265625f,388.7593688964844f,408.5477294921875f,428.3361511230469f,448.12451171875f,467.91290283203125f,487.7012939453125f,507.48968505859375f,527.278076171875f,547.0664672851562f,566.8548583984375f,586.6432495117188f,606.4315795898438f,626.2200317382812f}};
};
enum class Kind { Detection, Shared, Independent };
inline bool shape(const rknn_tensor_attr& a, unsigned c, unsigned h, unsigned w) {
    return a.n_dims == 4 && a.fmt == RKNN_TENSOR_NCHW && a.dims[0] == 1 &&
           a.dims[1] == c && a.dims[2] == h && a.dims[3] == w && a.n_elems == c*h*w;
}
inline bool validOutputs(const std::vector<rknn_tensor_attr>& attrs, Kind kind) {
    const unsigned offset = kind == Kind::Independent ? 0 : 6;
    const unsigned total = kind == Kind::Detection ? 6 : offset + 4;
    if (attrs.size() != total) return false;
    // INT8 board runtime groups boxes first, then classes; shared is interleaved.
    // Validate the six-head set by exact shape, independent of compiler ordering.
    if (offset) {
        int seen[3][2] = {};
        for (unsigned i=0;i<6;++i) {
            bool found=false;
            for(unsigned s=0;s<3;++s) for(unsigned head=0;head<2;++head)
                if(shape(attrs[i],head==0?64:5,60>>s,80>>s)) {
                    if(++seen[s][head]!=1) return false;
                    found=true;
                }
            if(!found) return false;
        }
        for(const auto& s:seen) if(s[0]!=1||s[1]!=1) return false;
    }
    return kind == Kind::Detection ||
        (shape(attrs[offset],64,24,8) && shape(attrs[offset+1],48,32,8) &&
         shape(attrs[offset+2],2,24,8) && shape(attrs[offset+3],2,32,8));
}
struct Point { float x, y; int lane; bool row; }; // canonical 640-square
inline bool decodePoints(const std::array<const float*,4>& tensors, const LaneContract& anchors,
                         std::vector<Point>& points) {
    points.clear();
    for (const float* p : tensors) if (!p) return false;
    for (int axis = 0; axis < 2; ++axis) {
        const int count = axis == 0 ? 24 : 32, grid = axis == 0 ? 64 : 48;
        const float* loc = tensors[axis]; const float* exist = tensors[axis+2];
        for (int a = 0; a < count; ++a) for (int lane = 0; lane < 8; ++lane) {
            const int index = a*8+lane, plane = count*8;
            if (!std::isfinite(exist[index]) || !std::isfinite(exist[plane+index])) return false;
            // NumPy/PyTorch argmax choose the first index on ties (absent).
            if (exist[plane+index] <= exist[index]) continue;
            int best = 0; float value = loc[index];
            if (!std::isfinite(value)) return false;
            for (int g = 1; g < grid; ++g) {
                const float candidate = loc[g*plane+index];
                if (!std::isfinite(candidate)) return false;
                if (candidate > value) { value = candidate; best = g; }
            }
            // Both delivered executable references use endpoints, no half-cell.
            const float coordinate = float(best) / float(grid-1) * (axis == 0 ? 639.f : 479.f);
            points.push_back(axis == 0 ? Point{coordinate, anchors.rows[a]+80.f,lane,true}
                                      : Point{anchors.cols[a],coordinate+80.f,lane,false});
        }
    }
    return true;
}
int runSelfTest();
} // namespace mvp
