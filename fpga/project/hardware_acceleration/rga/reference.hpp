#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#if defined(__aarch64__)
#include <arm_neon.h>
#endif

namespace rga_probe {
constexpr int W = 640, H = 480, MH = 640, PAD_Y = 80;
constexpr size_t RAW_BYTES = size_t(W) * H * 2;
constexpr size_t RGB_BYTES = size_t(W) * H * 3;
constexpr size_t MODEL_BYTES = size_t(W) * MH * 3;
using Bytes = std::vector<uint8_t>;

inline uint16_t word_le(const uint8_t* p) {
    return uint16_t(p[0]) | (uint16_t(p[1]) << 8);
}
inline std::array<uint8_t, 3> golden_pixel(uint16_t v) {
    const unsigned r = v >> 11, g = (v >> 5) & 63, b = v & 31;
    return {{uint8_t((r << 3) | (r >> 2)), uint8_t((g << 2) | (g >> 4)),
             uint8_t((b << 3) | (b >> 2))}};
}
// Explicit little-endian input: R5 is in bits 15:11, no implicit RGB swap.
// NEON matches the existing viewer conversion on little-endian AArch64.
inline void convert(const uint8_t* src, uint8_t* dst, size_t pixels) {
#if defined(__aarch64__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    while (pixels >= 8) {
        const uint16x8_t v = vreinterpretq_u16_u8(vld1q_u8(src));
        const uint16x8_t r = vshrq_n_u16(v, 11);
        const uint16x8_t g = vandq_u16(vshrq_n_u16(v, 5), vdupq_n_u16(63));
        const uint16x8_t b = vandq_u16(v, vdupq_n_u16(31));
        uint8x8x3_t rgb;
        rgb.val[0] = vmovn_u16(vorrq_u16(vshlq_n_u16(r, 3), vshrq_n_u16(r, 2)));
        rgb.val[1] = vmovn_u16(vorrq_u16(vshlq_n_u16(g, 2), vshrq_n_u16(g, 4)));
        rgb.val[2] = vmovn_u16(vorrq_u16(vshlq_n_u16(b, 3), vshrq_n_u16(b, 2)));
        vst3_u8(dst, rgb);
        src += 16; dst += 24; pixels -= 8;
    }
#endif
    for (size_t i = 0; i < pixels; ++i) {
        const auto p = golden_pixel(word_le(src + 2 * i));
        std::memcpy(dst + 3 * i, p.data(), 3);
    }
}
inline Bytes tiled_colors() {
    Bytes raw(RAW_BYTES);
    for (size_t i = 0; i < raw.size() / 2; ++i) {
        raw[2 * i] = uint8_t(i); raw[2 * i + 1] = uint8_t(i >> 8);
    }
    return raw;
}
inline Bytes golden(const Bytes& raw, bool model) {
    if (raw.size() != RAW_BYTES) throw std::runtime_error("fixture is not 640x480 RGB565");
    Bytes out(model ? MODEL_BYTES : RGB_BYTES, 114);
    convert(raw.data(), out.data() + (model ? size_t(PAD_Y) * W * 3 : 0), size_t(W) * H);
    return out;
}
inline std::string fnv1a(const uint8_t* p, size_t size) {
    uint64_t h = UINT64_C(14695981039346656037);
    for (size_t i = 0; i < size; ++i) { h ^= p[i]; h *= UINT64_C(1099511628211); }
    std::ostringstream s; s << std::hex << std::setfill('0') << std::setw(16) << h;
    return s.str();
}
inline std::string fnv1a(const Bytes& b) { return fnv1a(b.data(), b.size()); }

struct Difference {
    std::array<uint64_t, 3> bytes{{0, 0, 0}};
    std::array<unsigned, 3> max{{0, 0, 0}};
    uint64_t pixels = 0;
    bool exact() const { return pixels == 0; }
};
inline Difference compare(const uint8_t* actual, const uint8_t* expected, size_t pixels) {
    Difference d;
    for (size_t i = 0; i < pixels; ++i) {
        bool changed = false;
        for (int c = 0; c < 3; ++c) {
            const unsigned delta = unsigned(std::abs(int(actual[3*i+c]) - int(expected[3*i+c])));
            if (delta) { ++d.bytes[c]; changed = true; }
            d.max[c] = std::max(d.max[c], delta);
        }
        d.pixels += changed;
    }
    return d;
}
inline bool padding_ok(const uint8_t* p) {
    for (int y = 0; y < MH; ++y) if (y < PAD_Y || y >= PAD_Y + H)
        for (int x = 0; x < W * 3; ++x) if (p[size_t(y)*W*3+x] != 114) return false;
    return true;
}

enum class Correction { exact, replicate_or, lut, rejected };
inline const char* name(Correction c) {
    switch (c) {
    case Correction::exact: return "exact";
    case Correction::replicate_or: return "bit_replication_or";
    case Correction::lut: return "verified_channel_lut";
    default: return "rejected";
    }
}
struct Calibration {
    Correction correction = Correction::rejected;
    Difference diff;
    std::array<std::array<int, 256>, 3> lut;
    std::string reason;
    Calibration() { for (auto& channel : lut) channel.fill(-1); }
};
// This gate requires all 65536 words and checks repeated spatial samples too.
// A LUT is allowed only within 5/6-bit expansion bounds and only if each raw
// channel value maps to exactly one reference value; no channel permutation.
inline Calibration calibrate(const Bytes& raw, const uint8_t* actual) {
    Calibration out;
    std::array<bool, 65536> seen{};
    std::array<std::array<int, 64>, 3> forward;
    for (auto& channel : forward) channel.fill(-1);
    bool exact = true, shifted = true, bounded = true, consistent = true;
    Bytes ref = golden(raw, false);
    out.diff = compare(actual, ref.data(), size_t(W) * H);
    for (size_t i = 0; i < raw.size()/2; ++i) {
        const uint16_t v = word_le(raw.data()+2*i);
        seen[v] = true;
        const std::array<int, 3> q{{int(v >> 11), int((v >> 5) & 63), int(v & 31)}};
        const auto gold = golden_pixel(v);
        for (int c = 0; c < 3; ++c) {
            const int a = actual[3*i+c], e = gold[c], bits = c == 1 ? 2 : 3;
            exact &= a == e;
            shifted &= a == (q[c] << bits);
            // Both truncation and rounding are considered, but only injective
            // mappings with a maximum deviation of 7/3 are repairable.
            bounded &= std::abs(a-e) <= (c == 1 ? 3 : 7);
            if (out.lut[c][a] != -1 && out.lut[c][a] != e) consistent = false;
            out.lut[c][a] = e;
            if (forward[c][q[c]] != -1 && forward[c][q[c]] != a) consistent = false;
            forward[c][q[c]] = a;
        }
    }
    if (!std::all_of(seen.begin(), seen.end(), [](bool b) { return b; }))
        out.reason = "missing RGB565 words";
    else if (exact) out.correction = Correction::exact;
    else if (shifted) out.correction = Correction::replicate_or;
    else if (bounded && consistent) out.correction = Correction::lut;
    else out.reason = "not an injective channel-local expansion within quantization bounds";
    return out;
}
inline void correct(uint8_t* dst, size_t pixels, const Calibration& cal) {
    if (cal.correction == Correction::rejected) throw std::runtime_error("correction was not validated");
    if (cal.correction == Correction::exact) return;
    if (cal.correction == Correction::replicate_or) {
#if defined(__aarch64__)
        while (pixels >= 16) {
            uint8x16x3_t rgb = vld3q_u8(dst);
            rgb.val[0] = vorrq_u8(rgb.val[0], vshrq_n_u8(rgb.val[0], 5));
            rgb.val[1] = vorrq_u8(rgb.val[1], vshrq_n_u8(rgb.val[1], 6));
            rgb.val[2] = vorrq_u8(rgb.val[2], vshrq_n_u8(rgb.val[2], 5));
            vst3q_u8(dst, rgb); dst += 48; pixels -= 16;
        }
#endif
        for (size_t i = 0; i < pixels; ++i) {
            dst[3*i] |= dst[3*i] >> 5;
            dst[3*i+1] |= dst[3*i+1] >> 6;
            dst[3*i+2] |= dst[3*i+2] >> 5;
        }
    } else {
#if defined(__aarch64__)
        // AArch64 byte-table lookup, validated separately from the fast OR path.
        // Keep a validity table so an unseen driver byte cannot become zero.
        std::array<std::array<uint8_t, 256>, 3> mapping{}, valid{};
        for (int c = 0; c < 3; ++c) for (int a = 0; a < 256; ++a) {
            mapping[c][a] = uint8_t(std::max(cal.lut[c][a], 0));
            valid[c][a] = cal.lut[c][a] >= 0 ? 255 : 0;
        }
        auto lookup = [](const uint8_t* table, uint8x16_t indices) {
            uint8x16_t result = vdupq_n_u8(0);
            for (int group = 0; group < 4; ++group) {
                uint8x16x4_t block;
                for (int part = 0; part < 4; ++part)
                    block.val[part] = vld1q_u8(table + group*64 + part*16);
                const uint8x16_t adjusted = vsubq_u8(indices, vdupq_n_u8(uint8_t(group*64)));
                result = vorrq_u8(result, vqtbl4q_u8(block, adjusted));
            }
            return result;
        };
        while (pixels >= 16) {
            uint8x16x3_t rgb = vld3q_u8(dst);
            for (int c = 0; c < 3; ++c) {
                if (vminvq_u8(lookup(valid[c].data(), rgb.val[c])) != 255)
                    throw std::runtime_error("value absent from exhaustive calibration");
                rgb.val[c] = lookup(mapping[c].data(), rgb.val[c]);
            }
            vst3q_u8(dst, rgb); dst += 48; pixels -= 16;
        }
#endif
        for (size_t i = 0; i < pixels; ++i) for (int c = 0; c < 3; ++c) {
            const int value = cal.lut[c][dst[3*i+c]];
            if (value < 0) throw std::runtime_error("value absent from exhaustive calibration");
            dst[3*i+c] = uint8_t(value);
        }
    }
}
} // namespace rga_probe
