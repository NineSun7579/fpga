#pragma once
#include "raw_dfl_reference.h"
#include <atomic>
#include <QVector>

namespace raw_dfl_legacy {
constexpr int MODEL_W = 640;
constexpr float IOU_THRESH = 0.45f;
struct Detection { float x1=0, y1=0, x2=0, y2=0, score=0; int cls=0; };

class ProductionDecoder {
public:
    int m_nc = 3;
    bool m_xyxy = false;
    bool m_trafficlight = false;
    tdm::InferenceGeometry m_geometry;
    std::atomic<float> m_conf{0.25f};
    // Read-only import of the real production implementation, not a copy.
#include "../board/current_retained_decoder.inc"
};

inline QVector<Detection> decode(ProductionDecoder& decoder, raw_dfl::FloatHeads& heads,
                                 const std::vector<rknn_tensor_attr>& attrs) {
    std::vector<rknn_output> float_outputs(attrs.size());
    for (std::size_t i = 0; i < attrs.size(); ++i) {
        int slot = -1;
        for (int s = 0; s < 6; ++s) if (std::strcmp(attrs[i].name, raw_dfl::names[s]) == 0) slot = s;
        raw_dfl::detail::require(slot >= 0, "legacy adapter unknown head");
        auto& output = float_outputs[i];
        output.index = attrs[i].index;
        output.want_float = 1;
        output.buf = heads.values[slot].data();
        output.size = std::uint32_t(heads.values[slot].size() * sizeof(float));
    }
    return decoder.decode(float_outputs, attrs);
}

// Precisely report the production raw-DFL heuristic: class 0, first paired box
// scale in attrs order, first min(H*W,2000) cells; strict >1.5 or <-0.5.
inline bool uses_sigmoid(const raw_dfl::FloatHeads& heads,
                          const std::vector<rknn_tensor_attr>& attrs) {
    for (const auto& a : attrs) {
        for (int s = 0; s < 3; ++s) if (std::strcmp(a.name, raw_dfl::names[s]) == 0) {
            float lo = -0.0f, hi = 0.0f;
            const auto& values = heads.values[s + 3];
            lo = hi = values[0];
            const int n = std::min(raw_dfl::widths[s] * raw_dfl::widths[s], 2000);
            for (int i = 1; i < n; ++i) { lo = std::min(lo, values[i]); hi = std::max(hi, values[i]); }
            return hi > 1.5f || lo < -0.5f;
        }
    }
    throw std::invalid_argument("legacy heuristic has no paired scale");
}

struct Comparison {
    std::size_t native_count = 0, legacy_count = 0, matched = 0;
    std::size_t native_unmatched = 0, legacy_unmatched = 0, score_mismatches = 0;
    float max_box_error = 0, max_score_error = 0;
};

// Match boxes by class and <=1e-3 pixel distance without depending on legacy
// std::sort tie order. Counts and unmatched boxes expose top-300/NMS differences.
inline Comparison compare(const std::vector<raw_dfl::Detection>& native,
                           const QVector<Detection>& legacy) {
    Comparison p;
    p.native_count = native.size(); p.legacy_count = std::size_t(legacy.size());
    std::vector<bool> used(std::size_t(legacy.size()), false);
    for (const auto& a : native) {
        int best = -1;
        float best_error = INFINITY;
        for (int j = 0; j < legacy.size(); ++j) {
            const auto& b = legacy[j];
            if (used[j] || a.cls != b.cls) continue;
            const float error = std::max({std::abs(a.x1-b.x1), std::abs(a.y1-b.y1),
                                          std::abs(a.x2-b.x2), std::abs(a.y2-b.y2)});
            if (error < best_error) { best_error = error; best = j; }
        }
        if (best < 0 || best_error > 1e-3f) { ++p.native_unmatched; continue; }
        used[best] = true; ++p.matched;
        p.max_box_error = std::max(p.max_box_error, best_error);
        const float score_error = std::abs(a.score - legacy[best].score);
        p.max_score_error = std::max(p.max_score_error, score_error);
        if (score_error > 1e-6f) ++p.score_mismatches;
    }
    p.legacy_unmatched = p.legacy_count - p.matched;
    return p;
}
} // namespace raw_dfl_legacy
