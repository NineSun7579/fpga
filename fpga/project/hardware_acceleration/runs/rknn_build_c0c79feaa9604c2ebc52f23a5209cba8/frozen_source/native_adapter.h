#pragma once
#include "sdk/rknn_api.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
#if defined(__aarch64__) && defined(__ARM_NEON)
#include <arm_neon.h>
#endif

// Metadata eligibility is necessary; hardware float-array and exact tuple
// parity are still required to certify every output and fixture.
struct NativePlan {
    enum class DequantScale { Fp32, Fp16 };
    rknn_tensor_attr logical{}, native{};
    size_t n = 0, c = 0, h = 0, w = 0, c1 = 0, c2 = 0, ws = 0;
    size_t storageChannels = 0;
    size_t elements = 0, bytes = 0, itemBytes = 0;
    bool flat = false;
    DequantScale dequantScale = DequantScale::Fp32;
    float effectiveScale = 0;
    std::array<float, 256> affineLut{};

    // IEEE binary32 -> binary16, round to nearest, ties to even. Used only for
    // the opt-in scale policy; the dequantized product stays binary32.
    static uint16_t halfBits(float value) {
        static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559,
                      "binary32 IEEE float required");
        uint32_t bits; std::memcpy(&bits, &value, sizeof(bits));
        const uint16_t sign = uint16_t((bits >> 16) & 0x8000);
        const uint32_t exp = (bits >> 23) & 255, frac = bits & 0x7fffff;
        if (exp == 255) return uint16_t(sign | 0x7c00 | (frac ? ((frac >> 13) | 0x200) : 0));
        if (!exp) return sign; // binary32 subnormals are below half a binary16 ULP at zero
        const int he = int(exp) - 112;
        if (he >= 31) return uint16_t(sign | 0x7c00);
        if (he < -10) return sign;
        const unsigned shift = he <= 0 ? unsigned(14 - he) : 13;
        const uint32_t significand = he <= 0 ? frac | 0x800000 : frac;
        uint32_t rounded = significand >> shift;
        const uint32_t remainder = significand & ((uint32_t(1) << shift) - 1);
        const uint32_t halfway = uint32_t(1) << (shift - 1);
        if (remainder > halfway || (remainder == halfway && (rounded & 1))) ++rounded;
        return uint16_t(sign | ((he <= 0 ? 0 : uint32_t(he) << 10) + rounded));
    }

    static size_t mul(size_t a, size_t b) {
        if (b && a > std::numeric_limits<size_t>::max() / b)
            throw std::runtime_error("tensor dimension overflow");
        return a * b;
    }
    static size_t product(const rknn_tensor_attr &a) {
        if (!a.n_dims || a.n_dims > RKNN_MAX_DIMS) throw std::runtime_error("invalid rank");
        size_t result = 1;
        for (uint32_t i = 0; i < a.n_dims; ++i) {
            if (!a.dims[i]) throw std::runtime_error("zero/dynamic dimension unsupported");
            result = mul(result, a.dims[i]);
        }
        return result;
    }
    static bool sameDims(const rknn_tensor_attr &a, const rknn_tensor_attr &b) {
        return a.n_dims == b.n_dims && std::equal(a.dims, a.dims + a.n_dims, b.dims);
    }
    static NativePlan make(const rknn_tensor_attr &l, const rknn_tensor_attr &a,
                           DequantScale policy = DequantScale::Fp32) {
        NativePlan p; p.logical = l; p.native = a; p.dequantScale = policy;
        p.elements = product(l);
        if (p.elements != l.n_elems || product(a) != a.n_elems || a.index != l.index)
            throw std::runtime_error("element count/index does not match queried dimensions");
        if (a.type == RKNN_TENSOR_INT8 || a.type == RKNN_TENSOR_UINT8) {
            p.itemBytes = 1;
            if (a.qnt_type != RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC ||
                !std::isfinite(a.scale) || a.scale <= 0)
                throw std::runtime_error("INT8/UINT8 requires finite positive per-tensor affine scale");
            if ((a.type == RKNN_TENSOR_INT8 && (a.zp < -128 || a.zp > 127)) ||
                (a.type == RKNN_TENSOR_UINT8 && (a.zp < 0 || a.zp > 255)))
                throw std::runtime_error("affine zero point outside storage type range");
            p.effectiveScale = policy == DequantScale::Fp16 ? half(halfBits(a.scale)) : a.scale;
            if (!std::isfinite(p.effectiveScale))
                throw std::runtime_error("selected dequant scale rounds to nonfinite binary16");
            // Index by stored byte, interpreting INT8 as signed. This policy
            // rounds the scale once; it never rounds the resulting float.
            for (size_t byte = 0; byte < p.affineLut.size(); ++byte) {
                const int q = a.type == RKNN_TENSOR_INT8 && byte >= 128 ? int(byte) - 256 : int(byte);
                p.affineLut[byte] = float(q - a.zp) * p.effectiveScale;
            }
        } else if (a.type == RKNN_TENSOR_FLOAT32 || a.type == RKNN_TENSOR_FLOAT16) {
            p.itemBytes = a.type == RKNN_TENSOR_FLOAT32 ? 4 : 2;
            if (a.qnt_type != RKNN_TENSOR_QNT_NONE)
                throw std::runtime_error("float output has unsupported quantization");
        } else throw std::runtime_error("unsupported native tensor type (no DFP/INT4/BF16 guess)");
        size_t storage = 0;
        if (l.n_dims == 3 && a.fmt == l.fmt && sameDims(l, a) &&
            (a.fmt == RKNN_TENSOR_NCHW || a.fmt == RKNN_TENSOR_NHWC)) {
            if ((a.w_stride && a.w_stride != a.dims[2]) || a.h_stride)
                throw std::runtime_error("rank3 stride semantics not certified");
            p.flat = true;
            storage = p.elements;
        } else {
            // The frozen raw-DFL decoder indexes rank4 as NCHW. Do not silently
            // reinterpret logical NHWC attributes to make it seem compatible.
            if (l.n_dims != 4 || l.fmt != RKNN_TENSOR_NCHW || l.dims[0] != 1)
                throw std::runtime_error("logical layout unsupported by frozen rank4 decoder adapter");
            p.n = l.dims[0]; p.c = l.dims[1]; p.h = l.dims[2]; p.w = l.dims[3];
            if (a.fmt == RKNN_TENSOR_NCHW && sameDims(l, a)) {
                p.storageChannels = p.c;
                p.ws = a.w_stride ? a.w_stride : p.w;
                storage = mul(mul(mul(p.n, p.c), p.h), p.ws);
            } else if (a.fmt == RKNN_TENSOR_NHWC && a.n_dims == 4 &&
                       a.dims[0] == p.n && a.dims[1] == p.h &&
                       a.dims[2] == p.w) {
                p.storageChannels = a.dims[3];
                if (p.storageChannels < p.c)
                    throw std::runtime_error("native NHWC channel capacity smaller than logical channels");
                p.ws = a.w_stride ? a.w_stride : p.w;
                storage = mul(mul(mul(p.n, p.h), p.ws), p.storageChannels);
            } else if (a.fmt == RKNN_TENSOR_NC1HWC2 && a.n_dims == 5 &&
                       a.dims[0] == p.n && a.dims[2] == p.h && a.dims[3] == p.w) {
                p.c1 = a.dims[1]; p.c2 = a.dims[4];
                p.storageChannels = mul(p.c1, p.c2);
                if (p.storageChannels < p.c)
                    throw std::runtime_error("native NC1HWC2 channel capacity smaller than logical channels");
                p.ws = a.w_stride ? a.w_stride : p.w;
                storage = mul(mul(mul(mul(p.n, p.c1), p.h), p.ws), p.c2);
            } else throw std::runtime_error("native dimensions/format do not describe supported layout");
            if (p.ws < p.w || (a.h_stride && a.h_stride != p.h))
                throw std::runtime_error("invalid width or unsupported output height stride");
        }
        const size_t packed = mul(product(a), p.itemBytes);
        p.bytes = mul(storage, p.itemBytes);
        if (a.size != packed) throw std::runtime_error("native size differs from dimension/type product");
        const size_t allocation = a.size_with_stride ? a.size_with_stride : a.size;
        if (allocation < p.bytes) throw std::runtime_error("reported allocation too small for strides");
        // Channel capacity comes from native dimensions, never a ceil(C/C2)
        // assumption. The logical channel prefix is a candidate mapping that
        // still requires hardware array/tuple parity; padding contents are not
        // read. Reject any allocation padding not explained by dimensions/ws.
        if (allocation != p.bytes) throw std::runtime_error("unexplained padding/stride in native allocation");
        return p;
    }
    static float half(uint16_t bits) {
        const unsigned sign = bits >> 15, exp = (bits >> 10) & 31, frac = bits & 1023;
        float v;
        if (!exp) v = std::ldexp(float(frac), -24);
        else if (exp == 31) v = frac ? std::numeric_limits<float>::quiet_NaN() : std::numeric_limits<float>::infinity();
        else v = std::ldexp(float(1024 + frac), int(exp) - 25);
        return sign ? -v : v;
    }
private:
    // make() checks full storage multiplication/bytes, and convert() checks
    // available memory. Its indices stay within that storage, so the hot loop
    // can multiply the byte offset without repeating overflow checks per value.
    float value(const void *buf, size_t i) const {
        const unsigned char *b = static_cast<const unsigned char *>(buf) + i * itemBytes;
        if (native.type == RKNN_TENSOR_FLOAT32) { float f; std::memcpy(&f, b, 4); return f; }
        if (native.type == RKNN_TENSOR_FLOAT16) { uint16_t h16; std::memcpy(&h16, b, 2); return half(h16); }
        return affineLut[*b];
    }
    void validateBuffer(const void *buf, size_t available, const std::vector<float> &dst) const {
        if (!buf || available < bytes || dst.size() != elements)
            throw std::runtime_error("native conversion buffer bounds/size violation");
    }
#if defined(__aarch64__) && defined(__ARM_NEON)
    template<bool Signed> static void storeAffine8(uint8x8_t values, int16x8_t zp,
                                                   float32x4_t scale, float *out) {
        const int16x8_t widened = Signed ? vmovl_s8(vreinterpret_s8_u8(values)) :
                                          vreinterpretq_s16_u16(vmovl_u8(values));
        const int16x8_t delta = vsubq_s16(widened, zp);
        // Integers in [-255,255] convert exactly. Multiplication stays FP32;
        // there is no result rounding, accumulation or FMA.
        vst1q_f32(out, vmulq_f32(vcvtq_f32_s32(vmovl_s16(vget_low_s16(delta))), scale));
        vst1q_f32(out + 4, vmulq_f32(vcvtq_f32_s32(vmovl_s16(vget_high_s16(delta))), scale));
    }
    template<bool Signed> void convertBlocked8(const void *buf, std::vector<float> &dst) const {
        const auto *input = static_cast<const uint8_t *>(buf);
        const int16x8_t zp = vdupq_n_s16(int16_t(native.zp));
        const float32x4_t scale = vdupq_n_f32(effectiveScale);
        const size_t plane = h * w, rowBytes = ws * 8, blockBytes = h * rowBytes;
        // Capacity/strides/bytes were validated by make(), and convert() checks
        // full allocation bounds. Extra native blocks are never visited.
        for (size_t channel = 0, block = 0; channel < c; channel += 8, ++block) {
            const size_t active = std::min(size_t(8), c - channel);
            for (size_t y = 0; y < h; ++y) {
                const uint8_t *row = input + block * blockBytes + y * rowBytes;
                float *out = dst.data() + channel * plane + y * w;
                size_t x = 0;
                for (; w - x >= 8; x += 8) {
                    // vld4 gives alternating Ck/C(k+4) from four pixels.
                    // Unzip two four-pixel loads to get eight pixels/channel.
                    const uint8x8x4_t first = vld4_u8(row + x * 8);
                    const uint8x8x4_t second = vld4_u8(row + x * 8 + 32);
                    for (size_t k = 0; k < std::min(size_t(4), active); ++k) {
                        const uint8x8x2_t channels = vuzp_u8(first.val[k], second.val[k]);
                        storeAffine8<Signed>(channels.val[0], zp, scale, out + k * plane + x);
                        if (k + 4 < active)
                            storeAffine8<Signed>(channels.val[1], zp, scale, out + (k + 4) * plane + x);
                    }
                }
                // Never load past logical row width; up to seven pixels use
                // the exact same precomputed values as the scalar reference.
                for (size_t k = 0; k < active; ++k)
                    for (size_t tail = x; tail < w; ++tail)
                        out[k * plane + tail] = affineLut[row[tail * 8 + k]];
            }
        }
    }
#endif
    void convertScalarUnchecked(const void *buf, std::vector<float> &dst) const {
        if (flat) { for (size_t i = 0; i < elements; ++i) dst[i] = value(buf, i); return; }
        const size_t pixelStep = native.fmt == RKNN_TENSOR_NCHW ? 1 :
                                 native.fmt == RKNN_TENSOR_NHWC ? storageChannels : c2;
        const size_t rowStep = ws * pixelStep, blockStep = h * rowStep;
        for (size_t ci = 0; ci < c; ++ci) {
            const size_t channelStart = native.fmt == RKNN_TENSOR_NCHW ? ci * blockStep :
                                        native.fmt == RKNN_TENSOR_NHWC ? ci :
                                        (ci / c2) * blockStep + ci % c2;
            for (size_t y = 0; y < h; ++y) {
                size_t index = channelStart + y * rowStep;
                float *out = dst.data() + (ci * h + y) * w;
                for (size_t x = 0; x < w; ++x, index += pixelStep)
                    out[x] = value(buf, index);
            }
        }
    }
public:
    bool usesNeon() const {
#if defined(__aarch64__) && defined(__ARM_NEON)
        return !flat && n == 1 && native.fmt == RKNN_TENSOR_NC1HWC2 && c2 == 8 &&
               itemBytes == 1 && native.qnt_type == RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC &&
               (native.type == RKNN_TENSOR_INT8 || native.type == RKNN_TENSOR_UINT8);
#else
        return false;
#endif
    }
    const char *conversionKernel() const { return usesNeon() ? "aarch64_neon_nc1hwc2_c2_8" : "scalar_reference"; }
    // Explicit reference for ISA parity tests; same public buffer validation.
    void convertScalar(const void *buf, size_t available, std::vector<float> &dst) const {
        validateBuffer(buf, available, dst);
        convertScalarUnchecked(buf, dst);
    }
    void convert(const void *buf, size_t available, std::vector<float> &dst) const {
        validateBuffer(buf, available, dst);
#if defined(__aarch64__) && defined(__ARM_NEON)
        if (usesNeon()) {
            if (native.type == RKNN_TENSOR_INT8) convertBlocked8<true>(buf, dst);
            else convertBlocked8<false>(buf, dst);
            return;
        }
#endif
        convertScalarUnchecked(buf, dst);
    }
};
