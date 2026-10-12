// Host IEEE arithmetic checks against the compiler's independent _Float16
// implementation. No runtime library, NPU execution or hardware certification.
#include "native_adapter.h"
#include <iostream>

static_assert(__FLT16_MANT_DIG__ == 11 && sizeof(_Float16) == 2, "independent IEEE binary16 compiler oracle required");
static void require(bool ok, const char *why) { if (!ok) throw std::runtime_error(why); }
static uint16_t oracleBits(float f) {
    const _Float16 h = static_cast<_Float16>(f);
    uint16_t bits; std::memcpy(&bits, &h, sizeof(bits)); return bits;
}
static float oracleHalf(float f) { return static_cast<float>(static_cast<_Float16>(f)); }
static void check(float f) {
    const uint16_t actual = NativePlan::halfBits(f), expected = oracleBits(f);
    if (std::isnan(f)) require((actual & 0x7c00) == 0x7c00 && (actual & 1023), "NaN preserved");
    else require(actual == expected, "binary16 nearest ties-even oracle mismatch");
}
int main() {
    try {
        size_t checked = 0;
        for (unsigned bits = 0; bits < 0x7c00; ++bits) {
            // Decode through the independent compiler oracle, then check all
            // representable finite halves, their negative values, and every
            // finite adjacent midpoint with both binary32 neighbors.
            const uint16_t hb = uint16_t(bits); _Float16 h;
            std::memcpy(&h, &hb, sizeof(h)); const float f = static_cast<float>(h);
            check(f); check(-f); checked += 2;
            if (bits + 1 < 0x7c00) {
                const uint16_t nextBits = uint16_t(bits + 1); _Float16 next;
                std::memcpy(&next, &nextBits, sizeof(next));
                const float midpoint = (f + static_cast<float>(next)) * 0.5f;
                for (float v : {midpoint, std::nextafter(midpoint, 0.0f),
                                std::nextafter(midpoint, std::numeric_limits<float>::infinity())}) {
                    check(v); check(-v); checked += 2;
                }
            }
        }
        uint32_t state = 0x6f764940;
        for (unsigned i = 0; i < 200000; ++i) {
            state ^= state << 13; state ^= state >> 17; state ^= state << 5;
            float f; std::memcpy(&f, &state, sizeof(f)); check(f); ++checked;
        }
        for (float f : {65519.0f, 65520.0f, 65521.0f, -65520.0f,
                        std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity(),
                        std::numeric_limits<float>::quiet_NaN()}) { check(f); ++checked; }
        const std::vector<float> scales{0.0784313753247261f, 0.04749705642461777f, 0.049998946487903595f,
                                        0.1f, 1.0f, std::ldexp(1.0f, -14), std::ldexp(1.0f, -24),
                                        std::ldexp(1.0f, -25), 1e-10f, 65504.0f, 65519.0f};
        size_t lutChecks = 0;
        for (auto type : {RKNN_TENSOR_INT8, RKNN_TENSOR_UINT8})
            for (int zp : (type == RKNN_TENSOR_INT8 ? std::vector<int>{-128, -7, 0, 83, 127} : std::vector<int>{0, 83, 255}))
                for (float scale : scales) {
                    rknn_tensor_attr a{};
                    a.n_dims = 4; a.dims[0] = 1; a.dims[1] = 1; a.dims[2] = 1; a.dims[3] = 256;
                    a.n_elems = 256; a.size = 256; a.size_with_stride = 256; a.fmt = RKNN_TENSOR_NCHW;
                    a.type = type; a.qnt_type = RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC; a.zp = zp; a.scale = scale;
                    std::vector<uint8_t> bytes(256); for (unsigned i = 0; i < 256; ++i) bytes[i] = uint8_t(i);
                    std::vector<float> actual(256), defaultActual(256);
                    const auto plan = NativePlan::make(a, a, NativePlan::DequantScale::Fp16);
                    const auto defaultPlan = NativePlan::make(a, a);
                    plan.convert(bytes.data(), bytes.size(), actual);
                    defaultPlan.convert(bytes.data(), bytes.size(), defaultActual);
                    require(plan.effectiveScale == oracleHalf(scale), "round scale once");
                    for (unsigned i = 0; i < 256; ++i) {
                        const int q = type == RKNN_TENSOR_INT8 && i >= 128 ? int(i) - 256 : int(i);
                        const float expected = float(q - zp) * oracleHalf(scale);
                        require(actual[i] == expected, "all raw bytes use signedness/zp and half-scale binary32 product");
                        require(defaultActual[i] == float(q - zp) * scale, "default fp32 policy unchanged");
                        ++lutChecks;
                    }
                }
        const float product = 127.0f * oracleHalf(scales[0]);
        require(product == 9.96063232421875f && product != oracleHalf(product), "scale rounding differs from result rounding");
        rknn_tensor_attr a{};
        a.n_dims = 4; a.dims[0] = a.dims[1] = a.dims[2] = a.dims[3] = 1;
        a.n_elems = a.size = 1; a.fmt = RKNN_TENSOR_NCHW; a.type = RKNN_TENSOR_INT8;
        a.qnt_type = RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC; a.scale = 65520.0f;
        bool rejected = false;
        try { NativePlan::make(a, a, NativePlan::DequantScale::Fp16); } catch (const std::runtime_error &) { rejected = true; }
        require(rejected, "nonfinite rounded scale declined");
        std::cout << "IEEE binary16 oracle checks=" << checked << "; all-byte LUT checks=" << lutChecks
                  << "; scale-only policy; hardware untested\n";
        return 0;
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 1; }
}
