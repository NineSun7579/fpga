#include "raw_dfl_reference.h"
#ifdef RAW_DFL_WITH_LEGACY
#include "legacy_production_adapter.h"
#endif
#include <iostream>
#include <fstream>
#include <limits>
#include <random>
#include <sstream>

namespace {
void expect(bool ok, const std::string& message) {
    if (!ok) throw std::runtime_error(message);
}

struct Fixture {
    std::array<std::vector<std::uint8_t>, 6> bytes;
    std::vector<rknn_tensor_attr> attrs{6};
    std::vector<rknn_output> outs{6};
    explicit Fixture(bool u8 = false) {
        for (int s = 0; s < 6; ++s) {
            auto& a = attrs[s];
            a.index = s;
            std::memcpy(a.name, raw_dfl::names[s], std::strlen(raw_dfl::names[s]) + 1);
            a.n_dims = 4; a.dims[0] = 1; a.dims[1] = s < 3 ? 64 : 3;
            a.dims[2] = a.dims[3] = raw_dfl::widths[s % 3];
            a.n_elems = a.size = a.dims[1] * a.dims[2] * a.dims[3];
            a.fmt = RKNN_TENSOR_NCHW;
            a.type = u8 ? RKNN_TENSOR_UINT8 : RKNN_TENSOR_INT8;
            a.qnt_type = RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC;
            a.zp = u8 ? 128 : 0; a.scale = s < 3 ? 0.25f : 0.1f;
            bytes[s].assign(a.n_elems, std::uint8_t(u8 ? 0 : -128));
            outs[s].index = s; outs[s].size = a.size; outs[s].buf = bytes[s].data();
        }
    }
    // q is relative to zp, so the same fixture can exercise S8 and U8.
    void put(int s, int channel, int cell, int q) {
        const int plane = raw_dfl::widths[s % 3] * raw_dfl::widths[s % 3];
        bytes[s][channel * plane + cell] = std::uint8_t(q + attrs[s].zp);
    }
    void peak(int scale, int cell, int bin = 2) {
        for (int side = 0; side < 4; ++side) put(scale, side * 16 + bin, cell, 127);
    }
};

float largest_error = 0;
float largest_legacy_error = 0;
std::size_t compatibility_fixtures = 0;
std::vector<raw_dfl::Detection> parity(Fixture& fixture, raw_dfl::Config config = {}) {
    raw_dfl::NativeDecoder native(config);
    auto a = native.decode(fixture.outs, fixture.attrs);
    auto b = raw_dfl::scalar_reference(fixture.outs, fixture.attrs, config);
    const auto p = raw_dfl::compare_exact(a, b);
    largest_error = std::max(largest_error, p.max_box_error);
    expect(p.pass(), "native/scalar parity: mismatched=" + std::to_string(p.mismatched) +
                     " unmatched=" + std::to_string(p.unmatched) + " max_box=" + std::to_string(p.max_box_error));
    return a;
}

std::vector<raw_dfl::Detection> production_parity(Fixture& fixture, bool expected_sigmoid, bool pinned_profile = false) {
    raw_dfl::Config config;
    config.production_compatibility = true;
    config.pinned_rknn230_dequantization = pinned_profile;
    raw_dfl::NativeDecoder native(config);
    raw_dfl::DecodeStats stats, reference_stats;
    auto result = native.decode(fixture.outs, fixture.attrs, &stats);
    auto heads = raw_dfl::full_dequantize(fixture.outs, fixture.attrs, config);
    auto reference = raw_dfl::scalar_float_decode(heads, config, &reference_stats);
    const auto exact = raw_dfl::compare_exact(result, reference);
    largest_error = std::max(largest_error, exact.max_box_error);
    expect(exact.pass(), "production-compatible native/scalar ordered parity");
    expect(stats.used_sigmoid == expected_sigmoid && reference_stats.used_sigmoid == expected_sigmoid,
           "production heuristic decision must match expected sample semantics");
#ifdef RAW_DFL_WITH_LEGACY
    raw_dfl_legacy::ProductionDecoder legacy;
    expect(raw_dfl_legacy::uses_sigmoid(heads, fixture.attrs) == expected_sigmoid, "actual production heuristic decision");
    const auto old = raw_dfl_legacy::decode(legacy, heads, fixture.attrs);
    const auto p = raw_dfl_legacy::compare(result, old);
    expect(p.native_unmatched == 0 && p.legacy_unmatched == 0 && p.score_mismatches == 0,
           "production-compatible counts/boxes/scores against real include");
    expect(result.size() == std::size_t(old.size()), "production-compatible ordered count");
    // Ordered comparison catches both score-only sorts, not just a matching set.
    for (std::size_t i = 0; i < result.size(); ++i) {
        const auto& a = result[i]; const auto& b = old[int(i)];
        const float error = std::max({std::abs(a.x1-b.x1), std::abs(a.y1-b.y1),
                                      std::abs(a.x2-b.x2), std::abs(a.y2-b.y2)});
        largest_legacy_error = std::max(largest_legacy_error, error);
        expect(a.cls == b.cls && std::abs(a.score - b.score) <= 1e-6f && error <= 1e-3f,
               "production-compatible output order against real include");
    }
#endif
    ++compatibility_fixtures;
    return result;
}

void three_scales(bool u8) {
    Fixture f(u8);
    const std::array<int, 3> cells{0, 10 * 40 + 10, 19 * 20 + 19};
    for (int s = 0; s < 3; ++s) { f.peak(s, cells[s]); f.put(s + 3, s, cells[s], 50 - s); }
    raw_dfl::NativeDecoder native;
    raw_dfl::DecodeStats stats;
    const auto d = native.decode(f.outs, f.attrs, &stats);
    expect(stats.scanned == 8400 && stats.qualified == 3 && stats.dfl_cells == 3 && d.size() == 3,
           "early confidence filter must avoid all background DFL");
    expect(d[0].cls == 0 && d[1].cls == 1 && d[2].cls == 2, "all three classes/scales");
    expect(std::abs(d[0].x1 + 12) < 1e-4f && std::abs(d[0].y1 + 12) < 1e-4f,
           "negative coordinates remain unclipped");
    expect(std::abs(d[1].x1 - 136) < 1e-4f && std::abs(d[1].x2 - 200) < 1e-4f, "stride16");
    expect(std::abs(d[2].x2 - 688) < 1e-4f, "padding/outside input box remains unclipped");
    expect(native.class_table_count() == 1 && native.exp_table_count() == 1, "identical head attrs share LUTs");
    native.decode(f.outs, f.attrs);
    expect(native.class_table_count() == 1 && native.exp_table_count() == 1, "LUTs reused across calls");
    auto expected = parity(f);
    production_parity(f, true);
#ifdef RAW_DFL_WITH_LEGACY
    auto heads = raw_dfl::full_dequantize(f.outs, f.attrs);
    raw_dfl_legacy::ProductionDecoder legacy;
    expect(raw_dfl_legacy::uses_sigmoid(heads, f.attrs), "legacy normal logits sample uses sigmoid");
    const auto old = raw_dfl_legacy::decode(legacy, heads, f.attrs);
    const auto compatibility = raw_dfl_legacy::compare(expected, old);
    expect(compatibility.native_unmatched == 0 && compatibility.legacy_unmatched == 0 && compatibility.score_mismatches == 0,
           "normal distinct-score fixture agrees with actual production decoder");
#endif
    std::swap(f.attrs[0], f.attrs[4]);
    std::swap(f.attrs[1], f.attrs[5]);
    std::swap(f.outs[0], f.outs[2]);
    std::swap(f.outs[1], f.outs[4]);
    auto permuted = parity(f);
    expect(raw_dfl::compare_exact(permuted, expected).pass(), "independently permuted outputs and attrs");
    production_parity(f, true);
}

void confidence_and_nms() {
    Fixture f;
    f.peak(0, 0); f.put(3, 0, 0, 0); f.put(3, 1, 0, 0);
    raw_dfl::Config c; c.confidence = 0.5f;
    auto d = parity(f, c);
    expect(d.size() == 1 && d[0].cls == 0 && d[0].score == 0.5f, "inclusive confidence and lowest-class tie, one label");
    c.confidence = std::nextafter(0.5f, 1.0f);
    expect(parity(f, c).empty(), "score immediately below threshold rejected");
    c.confidence = std::nextafter(0.5f, 0.0f);
    expect(parity(f, c).size() == 1, "score immediately above threshold kept");
    f.put(3, 0, 0, 50); f.put(3, 1, 0, 45);
    f.peak(0, 1); f.put(3, 2, 1, 40);
    d = parity(f);
    expect(d.size() == 1 && d[0].anchor == 0, "class-agnostic NMS suppresses overlapping other class");
    c = {}; c.iou = 1;
    expect(parity(f, c).size() == 2, "strict IoU comparison");
    c.iou = 0;
    expect(parity(f, c).size() == 1, "IoU zero suppresses positive overlap");
}

void topk_and_all_probability_range_logits() {
    Fixture f(true);
    // ALL class logits are [0,1]. Legacy's sample heuristic chooses probabilities.
    for (int s = 3; s < 6; ++s) {
        f.attrs[s].scale = 0.01f; f.attrs[s].zp = 0;
        std::fill(f.bytes[s].begin(), f.bytes[s].end(), std::uint8_t(0));
    }
    for (int s = 0; s < 3; ++s) {
        // Peaked bin0 gives near-zero-area boxes, so NMS cannot hide topk ordering.
        const int plane = raw_dfl::widths[s] * raw_dfl::widths[s];
        for (int cell = 0; cell < plane; ++cell) f.peak(s, cell, 0);
    }
    f.put(3, 2, 700, 100);
    auto d = parity(f);
    expect(d.size() == 300 && d[0].anchor == 700 && d[0].cls == 2, "top300 before DFL/NMS");
    expect(std::abs(d[0].score - raw_dfl::detail::sigmoid(1.0f)) < 1e-7f,
           "[0,1] logits must still use sigmoid");
    expect(d[1].anchor == 0 && d.back().anchor == 298 && d[1].score == 0.5f,
           "deterministic canonical tie order and sigmoid(0)");
    raw_dfl::Config c; c.topk = 1;
    expect(parity(f, c).size() == 1, "configurable topk");
    c.topk = 300; c.confidence = 0.6f;
    expect(parity(f, c).size() == 1, "all-zero logits below 0.6, one sigmoid(1) qualifies");
    const auto compatible = production_parity(f, false);
    expect(compatible.size() == 1 && compatible[0].score == 1,
           "compatibility mode matches legacy [0,1] fixture while default retains 300");
#ifdef RAW_DFL_WITH_LEGACY
    auto heads = raw_dfl::full_dequantize(f.outs, f.attrs);
    raw_dfl_legacy::ProductionDecoder legacy;
    expect(!raw_dfl_legacy::uses_sigmoid(heads, f.attrs), "real legacy heuristic chooses probabilities");
    const auto old = raw_dfl_legacy::decode(legacy, heads, f.attrs);
    const auto p = raw_dfl_legacy::compare(d, old);
    expect(old.size() == 1 && std::abs(old[0].score - 1.0f) < 1e-7f && p.native_unmatched == 299 && p.score_mismatches == 1,
           "report actual legacy [0,1] heuristic discrepancy");
    std::cout << "legacy [0,1] discrepancy: native_count=" << d.size() << " legacy_count=" << old.size()
              << " native_score=" << d[0].score << " legacy_score=" << old[0].score << '\n';
#endif
}

void production_ties_and_order() {
    for (bool u8 : {false, true}) {
        for (int bin : {0, 2}) {
            for (bool sigmoid : {false, true}) {
                Fixture f(u8);
                // 8400 equal-score qualified cells exercise full sort, truncation,
                // the second score sort, class ties, and optionally heavy NMS.
                for (int s = 3; s < 6; ++s) {
                    for (auto& byte : f.bytes[s]) byte = std::uint8_t(f.attrs[s].zp + (sigmoid ? 20 : 5));
                }
                for (int s = 0; s < 3; ++s) {
                    const int plane = raw_dfl::widths[s] * raw_dfl::widths[s];
                    for (int cell = 0; cell < plane; ++cell) f.peak(s, cell, bin);
                }
                const auto normal = production_parity(f, sigmoid);
                expect(!normal.empty() && (bin != 0 || normal.size() == 300), "dense tied production fixture nonempty/top300");
                // Preserve each box/cls pair and permute encounter order to p5,
                // p3,p4. Buffer permutation is independent; adapter aligns pairs.
                const std::array<int, 6> permutation{2, 5, 0, 3, 1, 4};
                auto attrs = f.attrs;
                auto outs = f.outs;
                for (int i = 0; i < 6; ++i) f.attrs[i] = attrs[permutation[i]];
                std::reverse(f.outs.begin(), f.outs.end());
                const auto reordered = production_parity(f, sigmoid);
                expect(!reordered.empty(), "reordered tied production fixture");
                if (bin == 0)
                    expect(!raw_dfl::compare_exact(normal, reordered).pass(),
                           "compatibility ties must depend on production scale encounter order");
                // Default canonical contract remains independent of attrs order.
                const auto canonical_reordered = parity(f);
                f.attrs = std::move(attrs); f.outs = std::move(outs);
                const auto canonical = parity(f);
                expect(raw_dfl::compare_exact(canonical, canonical_reordered).pass(), "default unchanged for dense reordered ties");
            }
        }
    }
}

void production_heuristic_boundaries() {
    Fixture f;
    for (int s = 3; s < 6; ++s) {
        f.attrs[s].scale = 0.125f;
        std::fill(f.bytes[s].begin(), f.bytes[s].end(), std::uint8_t(0));
    }
    f.put(3, 0, 0, 12);   // Exactly 1.5 does not trigger sigmoid.
    f.put(3, 0, 1, -4);   // Exactly -0.5 does not trigger sigmoid.
    f.put(3, 0, 2000, -5); // First excluded sample cannot trigger.
    f.put(3, 1, 20, 16);  // Class1 logit 2 cannot trigger class0 sampling.
    f.put(4, 0, 0, -5);   // A different first paired scale WOULD trigger.
    production_parity(f, false);
    f.put(3, 0, 1999, 13); // Last included sample >1.5 triggers.
    production_parity(f, true);
    f.put(3, 0, 1999, -5); // Last included sample <-0.5 also triggers.
    production_parity(f, true);
    f.put(3, 0, 1999, 0);
    auto attrs = f.attrs;
    const std::array<int, 6> permutation{1, 4, 2, 5, 0, 3};
    for (int i = 0; i < 6; ++i) f.attrs[i] = attrs[permutation[i]];
    production_parity(f, true); // p4 now supplies the sample, not p3.
}

void random_affine() {
    std::mt19937 rng(3568);
    for (int trial = 0; trial < 8; ++trial) {
        Fixture f;
        for (int s = 0; s < 6; ++s) {
            auto& a = f.attrs[s];
            const bool u8 = (s + trial) % 2;
            a.type = u8 ? RKNN_TENSOR_UINT8 : RKNN_TENSOR_INT8;
            // Includes endpoints of zero-point ranges, distinct scale per head,
            // realistic pinned scales, and uniform/saturated box distributions.
            a.zp = u8 ? (trial % 3 == 0 ? 0 : trial % 3 == 1 ? 255 : 128)
                      : (trial % 3 == 0 ? -128 : trial % 3 == 1 ? 127 : 0);
            a.scale = trial == 6 ? 1e-6f : trial == 7 ? 10.0f : 0.0474532f + 0.009f * s;
            for (auto& byte : f.bytes[s]) byte = std::uint8_t(rng() & 255);
        }
        auto d = parity(f);
        expect(!d.empty(), "random fixture must exercise nonempty topk/NMS");
        // Determine the expected heuristic from dequantized class0 only.
        auto floats = raw_dfl::full_dequantize(f.outs, f.attrs);
        float maximum = -1e9f, minimum = 1e9f;
        for (int i = 0; i < 2000; ++i) {
            maximum = std::max(maximum, floats.values[3][i]);
            minimum = std::min(minimum, floats.values[3][i]);
        }
        production_parity(f, maximum > 1.5f || minimum < -0.5f);
    }
    // Full difference range 255, stable max-subtract, and extreme sigmoid values.
    Fixture f;
    for (int s = 0; s < 6; ++s) f.attrs[s].scale = 10;
    f.peak(0, 0, 15); f.put(3, 2, 0, 127);
    auto d = parity(f);
    expect(d.size() == 1 && d[0].score == 1 && std::abs(d[0].x1 + 116) < 1e-4f, "range255 and softmax underflow stable");
}

template<class Mutate> void rejects(const char* name, Mutate mutate) {
    Fixture f;
    mutate(f);
    for (bool compatibility : {false, true}) {
        raw_dfl::Config config;
        config.production_compatibility = compatibility;
        bool threw = false;
        try { raw_dfl::decode(f.outs, f.attrs, config); } catch (const std::invalid_argument&) { threw = true; }
        expect(threw, std::string("must reject ") + name + " in both modes");
    }
}

void validation() {
    rejects("missing head", [](Fixture& f){ f.outs.pop_back(); });
    rejects("wrong name", [](Fixture& f){ std::memcpy(f.attrs[0].name, "box_p2", 7); });
    rejects("unterminated name", [](Fixture& f){ std::memset(f.attrs[0].name, 'x', sizeof(f.attrs[0].name)); });
    rejects("duplicate name", [](Fixture& f){ std::memcpy(f.attrs[1].name, "box_p3", 7); });
    rejects("wrong dimensions", [](Fixture& f){ f.attrs[0].dims[3] = 79; });
    rejects("wrong bins", [](Fixture& f){ f.attrs[0].dims[1] = 32; });
    rejects("wrong classes", [](Fixture& f){ f.attrs[3].dims[1] = 4; });
    rejects("NHWC", [](Fixture& f){ f.attrs[0].fmt = RKNN_TENSOR_NHWC; });
    rejects("float type", [](Fixture& f){ f.attrs[0].type = RKNN_TENSOR_FLOAT32; });
    rejects("DFP", [](Fixture& f){ f.attrs[0].qnt_type = RKNN_TENSOR_QNT_DFP; });
    rejects("short attr", [](Fixture& f){ --f.attrs[0].size; });
    rejects("short element count", [](Fixture& f){ --f.attrs[0].n_elems; });
    rejects("short output", [](Fixture& f){ --f.outs[0].size; });
    rejects("padded output", [](Fixture& f){ ++f.outs[0].size; });
    rejects("padded width", [](Fixture& f){ f.attrs[0].w_stride = 96; });
    rejects("want_float", [](Fixture& f){ f.outs[0].want_float = 1; });
    rejects("null buffer", [](Fixture& f){ f.outs[0].buf = nullptr; });
    rejects("duplicate output index", [](Fixture& f){ f.outs[1].index = 0; });
    rejects("duplicate attr index", [](Fixture& f){ f.attrs[1].index = 0; });
    rejects("bad output index", [](Fixture& f){ f.outs[0].index = 6; });
    rejects("bad zero point", [](Fixture& f){ f.attrs[0].zp = 128; });
    rejects("zero scale", [](Fixture& f){ f.attrs[0].scale = 0; });
    rejects("negative scale", [](Fixture& f){ f.attrs[0].scale = -0.1f; });
    rejects("NaN scale", [](Fixture& f){ f.attrs[0].scale = std::numeric_limits<float>::quiet_NaN(); });
    rejects("infinite scale", [](Fixture& f){ f.attrs[0].scale = INFINITY; });
    rejects("overflowing scale range", [](Fixture& f){ f.attrs[0].scale = std::numeric_limits<float>::max(); });
    for (int which = 0; which < 4; ++which) {
        bool threw = false;
        raw_dfl::Config c;
        if (which == 0) c.confidence = NAN;
        if (which == 1) c.iou = -0.1f;
        if (which == 2) c.topk = 0;
        if (which == 3) c.topk = 8401;
        try { raw_dfl::NativeDecoder decoder(c); } catch (const std::invalid_argument&) { threw = true; }
        expect(threw, "invalid config rejected");
    }
}

// Independent fixture constants copied from the probe metadata, rather than
// using the decoder's guard constants to construct its own passing inputs.
constexpr std::array<int, 6> fixture_zps{0, -2, -35, 83, 69, 71};
constexpr std::array<std::uint32_t, 6> fixture_scales{
    0x3da0a0a1u, 0x3d9e27dau, 0x3d7c33afu, 0x3d425e3cu, 0x3d50337bu, 0x3d4d63f2u};
std::uint32_t test_bits(float value) {
    std::uint32_t bits;
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}
float test_float(std::uint32_t bits) {
    float value;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}
void set_pinned_attrs(Fixture& fixture) {
    for (int s = 0; s < 6; ++s) {
        fixture.attrs[s].zp = fixture_zps[s];
        fixture.attrs[s].scale = test_float(fixture_scales[s]);
    }
}

void pinned_profile_basics() {
    // Independently computed binary32 expectations: Python struct binary16 RNE
    // for p3/p4; exact rational q*scale + rounded binary32 offset, then one
    // binary32 rounding for p5. Includes unobserved extrema: these are synthetic
    // formula expectations, not claims of board observation.
    constexpr std::array<std::array<std::uint32_t, 4>, 6> expected{{
        {0x00000000u, 0x411f5ec0u, 0xc120a000u, 0xbda0a000u},
        {0x3e1e2000u, 0x411f5c40u, 0xc11ba780u, 0x3d9e2000u},
        {0x4009ec44u, 0x411f98b5u, 0xc0b73d8du, 0x4005fb75u},
        {0xc07c1480u, 0x4005a200u, 0xc1203520u, 0xc07f1e00u},
        {0xc0608500u, 0x403cba00u, 0xc1204140u, 0xc063c600u},
        {0xc063dae0u, 0x4033b774u, 0xc11fa8b1u, 0xc0671070u}
    }};
    constexpr std::array<int, 4> bytes{0, 127, 128, 255};
    Fixture f;
    set_pinned_attrs(f);
    for (int s = 0; s < 6; ++s)
        for (std::size_t i = 0; i < f.bytes[s].size(); ++i) f.bytes[s][i] = std::uint8_t(bytes[i % 4]);
    raw_dfl::Config config;
    config.pinned_rknn230_dequantization = true;
    const auto heads = raw_dfl::detail::validate(f.outs, f.attrs);
    auto floats = raw_dfl::full_dequantize(f.outs, f.attrs, config);
    auto mathematical = raw_dfl::full_dequantize(f.outs, f.attrs);
    expect(floats.pinned_rknn230_dequantization && !mathematical.pinned_rknn230_dequantization,
           "float reference records explicit conversion profile");
    for (int s = 0; s < 6; ++s) {
        for (int i = 0; i < 4; ++i) {
            const int q = bytes[i] < 128 ? bytes[i] : bytes[i] - 256;
            expect(test_bits(floats.values[s][i]) == expected[s][i], "24 independent endpoint runtime float bits");
            expect(test_bits(raw_dfl::detail::profiled_dequant(q, heads[s], s, true)) == expected[s][i],
                   "native runtime conversion endpoint bits");
            expect(test_bits(mathematical.values[s][i]) == test_bits(float(q-fixture_zps[s]) * f.attrs[s].scale),
                   "same pinned inputs retain mathematical default");
        }
    }
    expect(test_bits(raw_dfl::detail::profiled_dequant(-35, heads[2], 2, true)) == 0x33980000u,
           "p5 box q==zp FMA residual is not zero");
    expect(test_bits(raw_dfl::detail::profiled_dequant(71, heads[5], 5, true)) == 0x33f00000u,
           "p5 class q==zp synthetic FMA residual is not zero");
    parity(f, config);
    production_parity(f, true, true);
    // Force only p5 candidates so selected p5 scalar exp cannot be untested.
    std::fill(f.bytes[3].begin(), f.bytes[3].end(), std::uint8_t(128));
    std::fill(f.bytes[4].begin(), f.bytes[4].end(), std::uint8_t(128));
    const auto p5 = parity(f, config);
    expect(!p5.empty() && std::all_of(p5.begin(), p5.end(), [](const raw_dfl::Detection& d) { return d.anchor >= 8000; }),
           "pinned p5 DFL uses runtime-rounded logits on selected cells");
    production_parity(f, true, true);
    std::swap(f.attrs[0], f.attrs[2]); std::reverse(f.outs.begin(), f.outs.end());
    parity(f, config); production_parity(f, true, true);

    for (int s = 0; s < 6; ++s) {
        for (int mutation = 0; mutation < 4; ++mutation) {
            Fixture bad; set_pinned_attrs(bad);
            if (mutation == 0) bad.attrs[s].scale = std::nextafter(bad.attrs[s].scale, INFINITY);
            if (mutation == 1) ++bad.attrs[s].zp;
            if (mutation == 2) { bad.attrs[s].type = RKNN_TENSOR_UINT8; bad.attrs[s].zp = 0; }
            if (mutation == 3) {
                const int other = (s + 1) % 6;
                std::swap(bad.attrs[s].index, bad.attrs[other].index);
                std::swap(bad.outs[s].index, bad.outs[other].index);
            }
            bool native_threw = false, reference_threw = false;
            try { raw_dfl::decode(bad.outs, bad.attrs, config); } catch (const std::invalid_argument&) { native_threw = true; }
            try { raw_dfl::full_dequantize(bad.outs, bad.attrs, config); } catch (const std::invalid_argument&) { reference_threw = true; }
            expect(native_threw && reference_threw, "both runtime paths reject altered pinned scale/zp/type/index");
            raw_dfl::decode(bad.outs, bad.attrs); // These remain legal generic attrs.
        }
    }
    std::cout << "PINNED PROFILE PASS: 24 independent endpoint bits, 2 FMA residuals, selected p5 DFL, 24 pin mutations\n";
}

void probe_mapping(const std::string& path) {
    std::ifstream stream(path);
    expect(bool(stream), "open runtime mapping CSV " + path);
    std::string line;
    std::getline(stream, line);
    if (!line.empty() && line.back() == '\r') line.pop_back();
    expect(line == "head,index,type,zp,scale,byte,code,runtime_float,runtime_bits,count,affine_float,affine_bits",
           "runtime mapping CSV header");
    Fixture fixture;
    set_pinned_attrs(fixture);
    const auto heads = raw_dfl::detail::validate(fixture.outs, fixture.attrs);
    std::array<std::array<bool, 256>, 6> seen{};
    std::array<std::array<std::uint32_t, 256>, 6> observed_bits{};
    std::array<std::vector<std::uint8_t>, 6> observed_codes;
    std::size_t rows = 0, differs_from_mathematical = 0;
    std::uint64_t elements = 0;
    while (std::getline(stream, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        std::vector<std::string> fields;
        std::istringstream row(line);
        std::string field;
        while (std::getline(row, field, ',')) fields.push_back(field);
        expect(fields.size() == 12, "runtime mapping row fields");
        const int slot = std::stoi(fields[1]), byte = std::stoi(fields[5]), q = std::stoi(fields[6]);
        expect(slot >= 0 && slot < 6 && byte >= 0 && byte <= 255, "runtime mapping valid slot/byte");
        expect(fields[0] == raw_dfl::names[slot] && std::stoi(fields[2]) == int(RKNN_TENSOR_INT8) &&
               std::stoi(fields[3]) == fixture_zps[slot] && test_bits(std::stof(fields[4])) == fixture_scales[slot],
               "runtime mapping pinned metadata");
        expect(q == (byte < 128 ? byte : byte - 256) && !seen[slot][byte], "runtime mapping signed code and no duplicate/ambiguous floats");
        const auto bits = std::uint32_t(std::stoul(fields[8])); // Never parse runtime_float decimal.
        expect(test_bits(raw_dfl::detail::profiled_dequant(q, heads[slot], slot, true)) == bits,
               "BIT MISMATCH authoritative mapping: " + fields[0] + " byte=" + fields[5]);
        if (test_bits(raw_dfl::detail::dequant(q, heads[slot])) != bits) ++differs_from_mathematical;
        const auto count = std::stoull(fields[9]);
        expect(count > 0, "mapped code must be observed");
        elements += count;
        seen[slot][byte] = true; observed_bits[slot][byte] = bits;
        observed_codes[slot].push_back(std::uint8_t(byte)); ++rows;
    }
    expect(rows == 1214 && elements == 16884000, "complete pinned probe pair/element counts");
    raw_dfl::FloatHeads observed;
    observed.pinned_rknn230_dequantization = true;
    for (int s = 0; s < 6; ++s) {
        expect(!observed_codes[s].empty(), "probe includes all six heads");
        observed.values[s].resize(fixture.bytes[s].size());
        for (std::size_t i = 0; i < fixture.bytes[s].size(); ++i) {
            const auto byte = observed_codes[s][i % observed_codes[s].size()];
            fixture.bytes[s][i] = byte;
            observed.values[s][i] = test_float(observed_bits[s][byte]);
        }
    }
    raw_dfl::Config config;
    config.pinned_rknn230_dequantization = true;
    auto converted = raw_dfl::full_dequantize(fixture.outs, fixture.attrs, config);
    for (int s = 0; s < 6; ++s)
        for (std::size_t i = 0; i < converted.values[s].size(); ++i)
            expect(test_bits(converted.values[s][i]) == test_bits(observed.values[s][i]), "full reference mapping bits");
    for (bool compatibility : {false, true}) {
        config.production_compatibility = compatibility;
        const auto native = raw_dfl::decode(fixture.outs, fixture.attrs, config);
        const auto independent = raw_dfl::scalar_float_decode(observed, config);
        const auto p = raw_dfl::compare_exact(native, independent);
        expect(p.pass(), "both contracts compare to independently observed runtime floats");
        largest_error = std::max(largest_error, p.max_box_error);
    }
    production_parity(fixture, true, true);
    std::cout << "RUNTIME MAPPING BITEXACT PASS: pairs=" << rows << " observed_elements=" << elements
              << " different_from_mathematical=" << differs_from_mathematical
              << " per_head=";
    for (int s = 0; s < 6; ++s) std::cout << (s ? "," : "") << observed_codes[s].size();
    std::cout << "; independent observed-float decoder parity PASS in both contracts\n";
}
} // namespace

int main(int argc, char** argv) {
    try {
        expect(argc <= 2, "usage: selftest [pipeline_mapping.csv]");
        three_scales(false); three_scales(true);
        confidence_and_nms(); topk_and_all_probability_range_logits();
        production_ties_and_order(); production_heuristic_boundaries();
        random_affine(); validation();
        pinned_profile_basics();
        if (argc == 2) probe_mapping(argv[1]);
        std::cout << "SELFTEST PASS: S8/U8, 3 scales/classes, permutations, exact sigmoid, top300/ties, "
                     "class-agnostic NMS, confidence boundaries, affine extremes, contract rejection; max_box_error="
                  << largest_error << " px\n";
#ifdef RAW_DFL_WITH_LEGACY
        std::cout << "PRODUCTION COMPATIBILITY PASS against frozen include: fixtures=" << compatibility_fixtures
                  << " heuristic boundaries, dense ties, both score sorts, attrs order; max_legacy_box_error="
                  << largest_legacy_error << " px\n";
#else
        std::cout << "PRODUCTION COMPATIBILITY native/scalar PASS: fixtures=" << compatibility_fixtures << '\n';
        std::cout << "Real production comparison requires -DRAW_DFL_WITH_LEGACY and Qt5Core.\n";
#endif
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "SELFTEST FAIL: " << e.what() << '\n'; return 1;
    }
}
