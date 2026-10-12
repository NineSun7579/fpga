#pragma once

// Experimental, header-only decoder. No RKNN calls, Qt, OpenCV, or float heads.
// Consume packed RKNN_QUERY_OUTPUT_ATTR + rknn_outputs_get(want_float=0).
#include "rknn_api.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cfenv>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace raw_dfl {

inline constexpr std::array<const char*, 6> names{
    "box_p3", "box_p4", "box_p5", "cls_p3", "cls_p4", "cls_p5"};
inline constexpr std::array<int, 3> widths{80, 40, 20};
inline constexpr std::array<int, 3> strides{8, 16, 32};
inline constexpr std::array<int, 3> anchor_bases{0, 6400, 8000};

struct Config {
    float confidence = 0.25f;
    float iou = 0.45f;
    std::size_t topk = 300;
    // Opt in to the frozen production heuristic and both score-only sorts.
    // Default remains always-sigmoid with canonical deterministic score ties.
    bool production_compatibility = false;
    // Only the pinned wb_v8 model + audited RKNN 2.3.0 library. Caller must
    // bind model/API/library identities; exact output attrs are checked here.
    bool pinned_rknn230_dequantization = false;
};

struct Detection {
    float x1 = 0, y1 = 0, x2 = 0, y2 = 0, score = 0;
    int cls = 0;
    // Canonical p3/p4/p5, row-major cell; used for deterministic score ties.
    int anchor = 0;
};

struct DecodeStats {
    std::size_t scanned = 0, qualified = 0, dfl_cells = 0, kept = 0;
    bool used_sigmoid = true;
};

namespace detail {
inline void require(bool ok, const std::string& message) {
    if (!ok) throw std::invalid_argument("raw DFL: " + message);
}

inline void validate_config(const Config& c) {
    require(std::isfinite(c.confidence) && c.confidence >= 0 && c.confidence <= 1,
            "confidence must be finite in [0,1]");
    require(std::isfinite(c.iou) && c.iou >= 0 && c.iou <= 1,
            "IoU must be finite in [0,1]");
    require(c.topk > 0 && c.topk <= 8400, "topk must be in [1,8400]");
}

struct Head {
    const std::uint8_t* bytes = nullptr;
    rknn_tensor_type type = RKNN_TENSOR_INT8;
    int zp = 0;
    float scale = 0;
    std::size_t elems = 0;
    std::uint32_t index = 0;
};

inline int code(std::uint8_t byte, rknn_tensor_type type) {
    return type == RKNN_TENSOR_INT8 && byte >= 128 ? int(byte) - 256 : int(byte);
}

inline float dequant(int q, const Head& h) {
    return float(q - h.zp) * h.scale;
}

inline std::uint32_t float_bits(float value) {
    static_assert(sizeof(float) == sizeof(std::uint32_t) && std::numeric_limits<float>::is_iec559,
                  "raw DFL requires IEEE binary32 floats");
    std::uint32_t bits;
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}

inline float float_from_bits(std::uint32_t bits) {
    float value;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

// Source: runtime_dequant_probe/pipeline_metadata.json and runtime_bits in
// pipeline_mapping.csv. These are model/runtime-specific, not RKNN rules.
inline constexpr std::array<int, 6> pinned_zps{0, -2, -35, 83, 69, 71};
inline constexpr std::array<std::uint32_t, 6> pinned_scale_bits{
    0x3da0a0a1u, 0x3d9e27dau, 0x3d7c33afu, 0x3d425e3cu, 0x3d50337bu, 0x3d4d63f2u};
// Binary32 representations of binary16 round-to-nearest-even coefficients.
inline constexpr std::array<std::uint32_t, 6> pinned_half_scale_bits{
    0x3da0a000u, 0x3d9e2000u, 0x3d7c4000u, 0x3d426000u, 0x3d504000u, 0x3d4d6000u};

inline float profiled_dequant(int q, const Head& h, int slot, bool pinned) {
    if (!pinned) return dequant(q, h);
    if (slot % 3 != 2)
        return float(q - h.zp) * float_from_bits(pinned_half_scale_bits[slot]);
    // The offset product is rounded to float BEFORE the fused multiply-add.
    // Volatile enforces that boundary even under compiler FP contraction.
    const volatile float offset = -float(h.zp) * h.scale;
    return std::fma(float(q), h.scale, offset);
}

inline float sigmoid(float x) {
    // Deliberately the same float expression as ProductionDecoder::sigmoidf.
    return 1.0f / (1.0f + std::exp(-x));
}

inline std::array<Head, 6> validate(const std::vector<rknn_output>& outs,
                                    const std::vector<rknn_tensor_attr>& attrs) {
    require(outs.size() == 6 && attrs.size() == 6, "requires exactly six outputs");
    std::array<Head, 6> heads{};
    std::array<bool, 6> seen_names{}, seen_attrs{}, seen_outs{};
    std::array<const rknn_output*, 6> by_index{};
    for (const auto& o : outs) {
        require(o.index < 6 && !seen_outs[o.index], "duplicate/invalid output index");
        seen_outs[o.index] = true;
        by_index[o.index] = &o;
    }
    for (const auto& a : attrs) {
        require(a.index < 6 && !seen_attrs[a.index], "duplicate/invalid attribute index");
        seen_attrs[a.index] = true;
        require(std::memchr(a.name, '\0', sizeof(a.name)) != nullptr, "unterminated head name");
        int slot = -1;
        for (int j = 0; j < 6; ++j) if (std::strcmp(a.name, names[j]) == 0) slot = j;
        require(slot >= 0, "unsupported head name");
        require(!seen_names[slot], "duplicate head name");
        seen_names[slot] = true;
        const int width = widths[slot % 3], ch = slot < 3 ? 64 : 3;
        const std::size_t elems = std::size_t(ch) * width * width;
        const auto& o = *by_index[a.index];
        const std::string label = names[slot];
        require(a.n_dims == 4 && a.dims[0] == 1 && a.dims[1] == unsigned(ch) &&
                a.dims[2] == unsigned(width) && a.dims[3] == unsigned(width),
                label + " requires exact [1,C,H,W] shape");
        require(a.fmt == RKNN_TENSOR_NCHW, label + " requires NCHW");
        require(a.type == RKNN_TENSOR_INT8 || a.type == RKNN_TENSOR_UINT8,
                label + " requires S8 or U8");
        require(a.qnt_type == RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC,
                label + " requires affine quantization");
        const int lo = a.type == RKNN_TENSOR_INT8 ? -128 : 0;
        const int hi = a.type == RKNN_TENSOR_INT8 ? 127 : 255;
        require(a.zp >= lo && a.zp <= hi, label + " zero point outside code range");
        require(std::isfinite(a.scale) && a.scale > 0 && std::isfinite(255.0f * a.scale),
                label + " scale must be finite, positive, with finite code range");
        require(a.n_elems == elems && a.size == elems, label + " wrong attribute byte/element size");
        require(a.w_stride == 0 || a.w_stride == unsigned(width), label + " padded width unsupported");
        // size_with_stride describes device allocation, not outputs_get's packed data.
        require(o.size == elems, label + " requires exact packed output byte size");
        require(o.want_float == 0, label + " requires want_float=0");
        require(o.buf != nullptr, label + " null output buffer");
        heads[slot] = {static_cast<const std::uint8_t*>(o.buf), a.type, a.zp,
                       a.scale, elems, a.index};
    }
    return heads;
}

inline void validate_profile(const std::array<Head, 6>& heads, bool pinned) {
    if (!pinned) return;
#if defined(__FAST_MATH__) || defined(_M_FP_FAST)
    require(false, "pinned runtime profile requires compilation without fast-math");
#endif
    require(std::fegetround() == FE_TONEAREST, "pinned runtime profile requires round-to-nearest FP mode");
    for (int s = 0; s < 6; ++s) {
        const auto& h = heads[s];
        require(h.index == unsigned(s) && h.type == RKNN_TENSOR_INT8 && h.zp == pinned_zps[s] &&
                float_bits(h.scale) == pinned_scale_bits[s],
                std::string(names[s]) + " does not match pinned RKNN 2.3.0 index/type/zp/scale bits");
    }
}

// Call after validate(): the frozen decoder builds scales by box-head encounter
// order in attrs, then scans each scale row-major, independently of RKNN index.
inline std::array<int, 3> production_scale_order(const std::vector<rknn_tensor_attr>& attrs) {
    std::array<int, 3> order{};
    int count = 0;
    for (const auto& a : attrs)
        for (int s = 0; s < 3; ++s)
            if (std::strcmp(a.name, names[s]) == 0) order[count++] = s;
    require(count == 3, "production compatibility requires all three box heads");
    return order;
}

struct Candidate {
    float score;
    int cls, scale, cell;
    int anchor() const { return anchor_bases[scale] + cell; }
};

inline bool higher(const Candidate& a, const Candidate& b) {
    if (a.score != b.score) return a.score > b.score;
    if (a.anchor() != b.anchor()) return a.anchor() < b.anchor();
    return a.cls < b.cls;
}

inline void select_top(std::vector<Candidate>& c, std::size_t k, bool production_compatibility = false) {
    if (production_compatibility) {
        // Full score-only sort is required: partial_sort/stable_sort or an
        // anchor tiebreaker would select different tied production candidates.
        std::sort(c.begin(), c.end(), [](const Candidate& a, const Candidate& b) { return a.score > b.score; });
        if (c.size() > k) c.resize(k);
    } else if (c.size() > k) {
        std::partial_sort(c.begin(), c.begin() + k, c.end(), higher);
        c.resize(k);
    } else std::sort(c.begin(), c.end(), higher);
}

inline void production_sort_boxes(std::vector<Detection>& boxes) {
    // Production nmsAppend performs this SECOND score-only std::sort even
    // though the candidates were sorted already. Equal scores reorder again.
    std::sort(boxes.begin(), boxes.end(), [](const Detection& a, const Detection& b) { return a.score > b.score; });
}

// Input is sorted by the selected mode's score/tie policy. Deliberately
// class-agnostic, unclipped coordinates, strict IoU > threshold, production eps.
inline std::vector<Detection> nms(const std::vector<Detection>& boxes, float threshold) {
    std::vector<Detection> result;
    result.reserve(boxes.size());
    std::vector<bool> removed(boxes.size(), false);
    for (std::size_t i = 0; i < boxes.size(); ++i) {
        if (removed[i]) continue;
        const auto& a = boxes[i];
        result.push_back(a);
        for (std::size_t j = i + 1; j < boxes.size(); ++j) {
            if (removed[j]) continue;
            const auto& b = boxes[j];
            const float w = std::max(0.0f, std::min(a.x2, b.x2) - std::max(a.x1, b.x1));
            const float h = std::max(0.0f, std::min(a.y2, b.y2) - std::max(a.y1, b.y1));
            const float inter = w * h;
            const float ai = (a.x2 - a.x1) * (a.y2 - a.y1);
            const float bj = (b.x2 - b.x1) * (b.y2 - b.y1);
            if (inter / (ai + bj - inter + 1e-6f) > threshold) removed[j] = true;
        }
    }
    return result;
}

inline Detection box(const Candidate& c, const std::array<float, 4>& d) {
    const int width = widths[c.scale], stride = strides[c.scale];
    const float cx = (c.cell % width + 0.5f) * stride;
    const float cy = (c.cell / width + 0.5f) * stride;
    return {cx - d[0] * stride, cy - d[1] * stride,
            cx + d[2] * stride, cy + d[3] * stride, c.score, c.cls, c.anchor()};
}
} // namespace detail

class NativeDecoder {
public:
    explicit NativeDecoder(Config config = {}) : config_(config) { detail::validate_config(config_); }

    // Caches 256-entry tables across calls, shared when affine attrs are identical.
    // One instance per decoding thread; output buffers need only live for this call.
    std::vector<Detection> decode(const std::vector<rknn_output>& outs,
                                  const std::vector<rknn_tensor_attr>& attrs,
                                  DecodeStats* stats = nullptr) {
        const auto heads = detail::validate(outs, attrs);
        detail::validate_profile(heads, config_.pinned_rknn230_dequantization);
        std::array<const ClassTable*, 3> cls{};
        std::array<const ExpTable*, 3> exp{};
        // Obtain indices first: vector growth must not invalidate table pointers.
        std::array<std::size_t, 3> ci{}, ei{};
        for (int s = 0; s < 3; ++s) {
            ci[s] = class_table(heads[s + 3], s + 3);
            const float scale = config_.pinned_rknn230_dequantization && s < 2
                ? detail::float_from_bits(detail::pinned_half_scale_bits[s]) : heads[s].scale;
            ei[s] = exp_table(scale);
        }
        for (int s = 0; s < 3; ++s) { cls[s] = &classes_[ci[s]]; exp[s] = &exps_[ei[s]]; }
        if (config_.pinned_rknn230_dequantization && !p5_box_ready_) {
            for (int byte = 0; byte < 256; ++byte)
                p5_box_logits_[byte] = detail::profiled_dequant(detail::code(std::uint8_t(byte), heads[2].type), heads[2], 2, true);
            p5_box_ready_ = true;
        }
        DecodeStats measured;
        const auto order = config_.production_compatibility ? detail::production_scale_order(attrs)
                                                            : std::array<int, 3>{0, 1, 2};
        if (config_.production_compatibility) {
            const int first = order[0];
            const int n = std::min(widths[first] * widths[first], 2000);
            const auto* bytes = heads[first + 3].bytes;
            float maximum = -1e9f, minimum = 1e9f;
            for (int i = 0; i < n; ++i) {
                const float value = cls[first]->raw[bytes[i]];
                maximum = std::max(maximum, value);
                minimum = std::min(minimum, value);
            }
            measured.used_sigmoid = maximum > 1.5f || minimum < -0.5f;
        }
        std::vector<detail::Candidate> candidates;
        candidates.reserve(8400);
        for (const int s : order) {
            const auto* bytes = heads[s + 3].bytes;
            const auto& table = measured.used_sigmoid ? cls[s]->score : cls[s]->raw;
            const int plane = widths[s] * widths[s];
            measured.scanned += plane;
            for (int cell = 0; cell < plane; ++cell) {
                const float a = table[bytes[cell]], b = table[bytes[plane + cell]],
                            c = table[bytes[2 * plane + cell]];
                const float maximum = std::max(a, std::max(b, c));
                if (maximum < config_.confidence) continue; // No box loads/DFL here.
                int best_class = 0;
                float best = a;
                if (b > best) { best = b; best_class = 1; }
                if (c > best) { best = c; best_class = 2; }
                candidates.push_back({best, best_class, s, cell});
            }
        }
        measured.qualified = candidates.size();
        detail::select_top(candidates, config_.topk, config_.production_compatibility);
        std::vector<Detection> boxes;
        boxes.reserve(candidates.size());
        for (const auto& c : candidates) {
            const auto& head = heads[c.scale];
            const int plane = widths[c.scale] * widths[c.scale];
            std::array<float, 4> distances{};
            for (int side = 0; side < 4; ++side) {
                std::array<int, 16> codes{};
                int maximum = -128;
                for (int bin = 0; bin < 16; ++bin) {
                    codes[bin] = detail::code(head.bytes[(side * 16 + bin) * plane + c.cell], head.type);
                    maximum = std::max(maximum, codes[bin]);
                }
                std::array<float, 16> weights{};
                float sum = 0;
                const bool runtime_p5 = config_.pinned_rknn230_dequantization && c.scale == 2;
                std::array<float, 16> logits{};
                float max_logit = -INFINITY;
                if (runtime_p5) {
                    for (int bin = 0; bin < 16; ++bin) {
                        logits[bin] = p5_box_logits_[std::uint8_t(codes[bin])];
                        max_logit = std::max(max_logit, logits[bin]);
                    }
                }
                for (int bin = 0; bin < 16; ++bin) {
                    // (q-zp)*scale - (maxq-zp)*scale = (q-maxq)*scale.
                    // Positive affine scale makes the actual largest code the max.
                    // Pinned p5 FMA logits need actual rounded float subtraction;
                    // a code-difference LUT cannot reproduce their rounding.
                    weights[bin] = runtime_p5 ? std::exp(logits[bin] - max_logit)
                                             : exp[c.scale]->weight[maximum - codes[bin]];
                    sum += weights[bin];
                }
                float distance = 0;
                for (int bin = 0; bin < 16; ++bin)
                    distance += bin * weights[bin] / (sum + 1e-9f);
                distances[side] = distance;
            }
            boxes.push_back(detail::box(c, distances));
        }
        measured.dfl_cells = boxes.size();
        if (config_.production_compatibility) detail::production_sort_boxes(boxes);
        auto result = detail::nms(boxes, config_.iou);
        measured.kept = result.size();
        if (stats) *stats = measured;
        return result;
    }

    std::size_t class_table_count() const { return classes_.size(); }
    std::size_t exp_table_count() const { return exps_.size(); }

private:
    struct ClassTable {
        rknn_tensor_type type;
        int zp;
        float scale;
        std::array<float, 256> score{};
        std::array<float, 256> raw{};
    };
    struct ExpTable { float scale; std::array<float, 256> weight{}; };
    Config config_;
    std::vector<ClassTable> classes_;
    std::vector<ExpTable> exps_;
    std::array<float, 256> p5_box_logits_{};
    bool p5_box_ready_ = false;

    std::size_t class_table(const detail::Head& h, int slot) {
        for (std::size_t i = 0; i < classes_.size(); ++i)
            if (classes_[i].type == h.type && classes_[i].zp == h.zp && classes_[i].scale == h.scale) return i;
        ClassTable table{h.type, h.zp, h.scale, {}, {}};
        for (int byte = 0; byte < 256; ++byte) {
            table.raw[byte] = detail::profiled_dequant(detail::code(std::uint8_t(byte), h.type), h,
                                                      slot, config_.pinned_rknn230_dequantization);
            table.score[byte] = detail::sigmoid(table.raw[byte]);
        }
        classes_.push_back(table);
        return classes_.size() - 1;
    }
    std::size_t exp_table(float scale) {
        for (std::size_t i = 0; i < exps_.size(); ++i) if (exps_[i].scale == scale) return i;
        ExpTable table{scale, {}};
        for (int difference = 0; difference < 256; ++difference)
            table.weight[difference] = std::exp(-float(difference) * scale);
        exps_.push_back(table);
        return exps_.size() - 1;
    }
};

// Convenience entry point; keep NativeDecoder alive for repeated decode timings.
inline std::vector<Detection> decode(const std::vector<rknn_output>& outs,
                                     const std::vector<rknn_tensor_attr>& attrs,
                                     Config config = {}, DecodeStats* stats = nullptr) {
    NativeDecoder decoder(config);
    return decoder.decode(outs, attrs, stats);
}
} // namespace raw_dfl
