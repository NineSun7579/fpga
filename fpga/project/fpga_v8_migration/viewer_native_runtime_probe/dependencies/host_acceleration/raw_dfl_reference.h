#pragma once
#include "raw_dfl_native.h"

namespace raw_dfl {
// This intentionally materializes every element of all six heads, then uses
// scalar exp() on float logits. It is the complete CPU baseline, not a LUT path.
struct FloatHeads {
    std::array<std::vector<float>, 6> values;
    // Source attribute box-head encounter order; needed only by compatibility.
    std::array<int, 3> scale_order{0, 1, 2};
    bool pinned_rknn230_dequantization = false;
};

inline FloatHeads full_dequantize(const std::vector<rknn_output>& outs,
                                  const std::vector<rknn_tensor_attr>& attrs, Config config = {}) {
    detail::validate_config(config);
    const auto heads = detail::validate(outs, attrs);
    detail::validate_profile(heads, config.pinned_rknn230_dequantization);
    FloatHeads result;
    result.pinned_rknn230_dequantization = config.pinned_rknn230_dequantization;
    result.scale_order = detail::production_scale_order(attrs);
    for (int s = 0; s < 6; ++s) {
        const auto& h = heads[s];
        auto& values = result.values[s];
        values.resize(h.elems);
        for (std::size_t i = 0; i < h.elems; ++i)
            values[i] = detail::profiled_dequant(detail::code(h.bytes[i], h.type), h, s,
                                                config.pinned_rknn230_dequantization);
    }
    return result;
}

inline std::vector<Detection> scalar_float_decode(const FloatHeads& heads,
                                                 Config config = {}, DecodeStats* stats = nullptr) {
    detail::validate_config(config);
    for (int s = 0; s < 6; ++s) {
        const std::size_t count = std::size_t(s < 3 ? 64 : 3) * widths[s % 3] * widths[s % 3];
        detail::require(heads.values[s].size() == count, "wrong float reference head size");
    }
    DecodeStats measured;
    const auto order = config.production_compatibility ? heads.scale_order : std::array<int, 3>{0, 1, 2};
    if (config.production_compatibility) {
        auto checked_order = order;
        std::sort(checked_order.begin(), checked_order.end());
        detail::require(checked_order == std::array<int, 3>{0, 1, 2}, "invalid float reference scale order");
        const int first = order[0];
        const int n = std::min(widths[first] * widths[first], 2000);
        float maximum = -1e9f, minimum = 1e9f;
        for (int i = 0; i < n; ++i) {
            maximum = std::max(maximum, heads.values[first + 3][i]);
            minimum = std::min(minimum, heads.values[first + 3][i]);
        }
        measured.used_sigmoid = maximum > 1.5f || minimum < -0.5f;
    }
    std::vector<detail::Candidate> candidates;
    candidates.reserve(8400);
    for (const int s : order) {
        const int plane = widths[s] * widths[s];
        const auto& scores = heads.values[s + 3];
        measured.scanned += plane;
        for (int cell = 0; cell < plane; ++cell) {
            float best = -1;
            int best_class = -1;
            for (int c = 0; c < 3; ++c) {
                const float value = scores[c * plane + cell];
                const float score = measured.used_sigmoid ? detail::sigmoid(value) : value;
                if (score > best) { best = score; best_class = c; }
            }
            if (best >= config.confidence && best_class >= 0)
                candidates.push_back({best, best_class, s, cell});
        }
    }
    measured.qualified = candidates.size();
    detail::select_top(candidates, config.topk, config.production_compatibility);
    std::vector<Detection> boxes;
    boxes.reserve(candidates.size());
    for (const auto& c : candidates) {
        const int plane = widths[c.scale] * widths[c.scale];
        const auto& values = heads.values[c.scale];
        std::array<float, 4> distances{};
        for (int side = 0; side < 4; ++side) {
            const std::size_t base = std::size_t(side * 16) * plane + c.cell;
            float maximum = values[base];
            for (int bin = 1; bin < 16; ++bin) maximum = std::max(maximum, values[base + bin * plane]);
            std::array<float, 16> weights{};
            float sum = 0;
            for (int bin = 0; bin < 16; ++bin) {
                weights[bin] = std::exp(values[base + bin * plane] - maximum);
                sum += weights[bin];
            }
            float distance = 0;
            for (int bin = 0; bin < 16; ++bin) distance += bin * weights[bin] / (sum + 1e-9f);
            distances[side] = distance;
        }
        boxes.push_back(detail::box(c, distances));
    }
    measured.dfl_cells = boxes.size();
    if (config.production_compatibility) detail::production_sort_boxes(boxes);
    auto result = detail::nms(boxes, config.iou);
    measured.kept = result.size();
    if (stats) *stats = measured;
    return result;
}

inline std::vector<Detection> scalar_reference(const std::vector<rknn_output>& outs,
                                              const std::vector<rknn_tensor_attr>& attrs,
                                              Config config = {}, DecodeStats* stats = nullptr) {
    return scalar_float_decode(full_dequantize(outs, attrs, config), config, stats);
}

struct Parity {
    std::size_t native_count = 0, reference_count = 0, unmatched = 0, mismatched = 0;
    float max_score_error = 0, max_box_error = 0;
    bool pass() const { return unmatched == 0 && mismatched == 0; }
};

inline Parity compare_exact(const std::vector<Detection>& native,
                            const std::vector<Detection>& reference,
                            float score_tolerance = 1e-6f, float box_tolerance = 1e-3f) {
    Parity p;
    p.native_count = native.size(); p.reference_count = reference.size();
    p.unmatched = native.size() > reference.size() ? native.size() - reference.size() : reference.size() - native.size();
    for (std::size_t i = 0; i < std::min(native.size(), reference.size()); ++i) {
        const auto& a = native[i]; const auto& b = reference[i];
        const float se = std::abs(a.score - b.score);
        const float be = std::max({std::abs(a.x1 - b.x1), std::abs(a.y1 - b.y1),
                                   std::abs(a.x2 - b.x2), std::abs(a.y2 - b.y2)});
        p.max_score_error = std::max(p.max_score_error, se);
        p.max_box_error = std::max(p.max_box_error, be);
        if (a.cls != b.cls || a.anchor != b.anchor || se > score_tolerance || be > box_tolerance) ++p.mismatched;
    }
    return p;
}
} // namespace raw_dfl
