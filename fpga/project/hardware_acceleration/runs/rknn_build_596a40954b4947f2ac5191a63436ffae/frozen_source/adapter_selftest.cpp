// Host-only arithmetic/bounds checks. Does not load RKNN or claim NPU parity.
#include "native_adapter.h"
#include <iostream>

static void require(bool ok, const char *why) { if (!ok) throw std::runtime_error(why); }
template<class F> static void rejects(F f, const char *why) {
    bool rejected = false;
    try { f(); } catch (const std::runtime_error &) { rejected = true; }
    require(rejected, why);
}

// Dimensions, quantization and capacities below are from the parent's actual
// RKNN2.3.0/driver0.9.8 probe.stdout for SHA21451a51...: box_p3/p4 are C64,
// cls_p3/p4 are logical C3 but native9 capacity16 and native11 capacity8.
// This tests metadata/mapping arithmetic; hardware float-array and exact tuple
// certification is still mandatory and is not implied by these fixtures.
static void checkReportedLayout(unsigned channels, unsigned height, unsigned width,
                                unsigned index, rknn_tensor_format fmt, unsigned widthStride = 0) {
    const unsigned plane = height * width;
    rknn_tensor_attr l{}, a{};
    l.index = index; l.n_dims = 4; l.dims[0] = 1; l.dims[1] = channels;
    l.dims[2] = height; l.dims[3] = width; l.n_elems = channels * plane;
    l.size = l.n_elems; l.size_with_stride = (channels == 3 ? 8 : channels) * plane;
    l.fmt = RKNN_TENSOR_NCHW; l.type = RKNN_TENSOR_INT8;
    l.qnt_type = RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC;
    l.zp = channels == 64 ? 0 : height == 80 ? 83 : 72;
    l.scale = channels == 64 ? 0.0784313753247261f :
                              height == 80 ? 0.04749705642461777f : 0.049998946487903595f;
    a = l; a.fmt = fmt; a.w_stride = widthStride;
    const unsigned storageChannels = channels == 64 ? 64 : fmt == RKNN_TENSOR_NC1HWC2 ? 16 : 8;
    if (fmt == RKNN_TENSOR_NC1HWC2) {
        a.n_dims = 5; a.dims[1] = storageChannels / 8; a.dims[2] = height;
        a.dims[3] = width; a.dims[4] = 8;
    } else {
        a.n_dims = 4; a.dims[1] = height; a.dims[2] = width; a.dims[3] = storageChannels;
    }
    const unsigned ws = widthStride ? widthStride : width;
    a.n_elems = storageChannels * plane; a.size = a.n_elems;
    a.size_with_stride = storageChannels * height * ws;
    const NativePlan p = NativePlan::make(l, a);
    require(p.storageChannels == storageChannels, "must retain queried native channel capacity");
    require(p.bytes == a.size_with_stride && p.elements == l.n_elems, "native/logical storage sizes");
    std::vector<int8_t> input(a.size_with_stride, -128);
    std::vector<float> expected(l.n_elems), output(l.n_elems, 999.0f);
    // Fill every reported storage position: all extra channels and width pads
    // contain a different sentinel from the logical prefix. Classifier block2
    // is entirely padding for native9, rather than assumed to carry classes.
    for (unsigned c = 0; c < storageChannels; ++c)
        for (unsigned y = 0; y < height; ++y)
            for (unsigned x = 0; x < ws; ++x) {
                const size_t off = fmt == RKNN_TENSOR_NC1HWC2 ?
                    (((c / 8) * height + y) * ws + x) * 8 + c % 8 :
                    (y * ws + x) * storageChannels + c;
                if (c >= channels || x >= width) {
                    input[off] = c < 8 ? 127 : -128;
                    continue;
                }
                const int q = int((c * 43 + y * 7 + x * 11) % 100) - 30;
                input[off] = int8_t(q);
                expected[(c * height + y) * width + x] = float(q - l.zp) * l.scale;
            }
    p.convert(input.data(), input.size(), output);
    require(output == expected, "runtime-reported native prefix mapping/stride");
    rejects([&] { p.convert(input.data(), input.size() - 1, output); }, "short full padded allocation");
    if (p.bytes > l.n_elems)
        rejects([&] { p.convert(input.data(), l.n_elems, output); }, "logical bytes cannot replace padded allocation");
    // Mutate only padding. Prefix output must not depend on any extra channel
    // content or the second native9 classifier block.
    for (unsigned c = 0; c < storageChannels; ++c)
        for (unsigned y = 0; y < height; ++y)
            for (unsigned x = 0; x < ws; ++x) if (c >= channels || x >= width) {
                const size_t off = fmt == RKNN_TENSOR_NC1HWC2 ?
                    (((c / 8) * height + y) * ws + x) * 8 + c % 8 :
                    (y * ws + x) * storageChannels + c;
                input[off] = 53;
            }
    p.convert(input.data(), input.size(), output);
    require(output == expected, "padding content must not affect logical prefix");
    auto bad = a; --bad.n_elems;
    rejects([&] { NativePlan::make(l, bad); }, "padded dimension element mismatch");
    bad = a; --bad.size;
    rejects([&] { NativePlan::make(l, bad); }, "padded dimension byte mismatch");
    bad = a; --bad.size_with_stride;
    rejects([&] { NativePlan::make(l, bad); }, "padded stride allocation too short");
    bad = a; ++bad.size_with_stride;
    rejects([&] { NativePlan::make(l, bad); }, "unexplained extra bytes still rejected");
    bad = a; bad.w_stride = width - 1;
    rejects([&] { NativePlan::make(l, bad); }, "width stride smaller than queried width");
    bad = a; bad.h_stride = height + 1;
    rejects([&] { NativePlan::make(l, bad); }, "height stride still rejected");
    if (channels == 3) {
        bad = a;
        if (fmt == RKNN_TENSOR_NC1HWC2) { bad.dims[1] = 1; bad.dims[4] = 2; }
        else bad.dims[3] = 2;
        bad.n_elems = 2 * plane; bad.size = bad.n_elems; bad.size_with_stride = 2 * height * ws;
        rejects([&] { NativePlan::make(l, bad); }, "undersized reported channel capacity");
    }
}
int main() {
    try {
        rknn_tensor_attr l{}, a{};
        l.n_dims = 4; l.dims[0] = 1; l.dims[1] = 3; l.dims[2] = 2; l.dims[3] = 3;
        l.n_elems = 18; l.size = 18; l.fmt = RKNN_TENSOR_NCHW;
        l.type = RKNN_TENSOR_INT8; l.qnt_type = RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC; l.zp = -7; l.scale = 0.25f;
        a = l; a.n_dims = 5; a.dims[1] = 2; a.dims[2] = 2; a.dims[3] = 3; a.dims[4] = 2;
        a.fmt = RKNN_TENSOR_NC1HWC2; a.n_elems = 24; a.size = 24;
        a.w_stride = 4; a.size_with_stride = 32;
        NativePlan p = NativePlan::make(l, a);
        std::vector<int8_t> blocked(32, 127);
        std::vector<float> actual(18), expected(18);
        for (size_t c = 0; c < 3; ++c)
            for (size_t y = 0; y < 2; ++y)
                for (size_t x = 0; x < 3; ++x) {
                    const size_t i = (c * 2 + y) * 3 + x;
                    const int q = int(i) - 12;
                    blocked[(((c / 2) * 2 + y) * 4 + x) * 2 + c % 2] = int8_t(q);
                    expected[i] = float(q + 7) * 0.25f;
                }
        p.convert(blocked.data(), blocked.size(), actual);
        require(actual == expected, "NC1HWC2 channel/width padding or signed affine conversion");
        rejects([&] { p.convert(blocked.data(), 31, actual); }, "short buffer must be rejected");
        rejects([&] { std::vector<float> shortOut(17); p.convert(blocked.data(), 32, shortOut); }, "short FP32 destination");
        rejects([&] { p.convert(nullptr, 32, actual); }, "null native buffer");
        auto bad = a; bad.h_stride = 3;
        rejects([&] { NativePlan::make(l, bad); }, "unknown height stride");
        bad = a; bad.size_with_stride = 33;
        rejects([&] { NativePlan::make(l, bad); }, "hidden padding must be declined");
        bad = a; bad.dims[1] = 1; bad.n_elems = 12; bad.size = 12;
        rejects([&] { NativePlan::make(l, bad); }, "insufficient C1 channels");
        bad = a; bad.qnt_type = RKNN_TENSOR_QNT_DFP;
        rejects([&] { NativePlan::make(l, bad); }, "DFP not implemented");
        bad = a; bad.scale = 0;
        rejects([&] { NativePlan::make(l, bad); }, "invalid affine scale");
        bad = a; bad.zp = 1000;
        rejects([&] { NativePlan::make(l, bad); }, "invalid zero point");
        bad = a; bad.fmt = RKNN_TENSOR_UNDEFINED;
        rejects([&] { NativePlan::make(l, bad); }, "unknown layout");
        a = l; a.fmt = RKNN_TENSOR_NHWC; a.dims[1] = 2; a.dims[2] = 3; a.dims[3] = 3;
        a.type = RKNN_TENSOR_UINT8; a.zp = 128; a.w_stride = 4; a.size_with_stride = 24;
        p = NativePlan::make(l, a);
        std::vector<uint8_t> interleaved(24, 255);
        for (size_t c = 0; c < 3; ++c)
            for (size_t y = 0; y < 2; ++y)
                for (size_t x = 0; x < 3; ++x) {
                    const size_t i = (c * 2 + y) * 3 + x;
                    interleaved[(y * 4 + x) * 3 + c] = uint8_t(128 + i);
                    expected[i] = float(i) * 0.25f;
                }
        p.convert(interleaved.data(), 24, actual);
        require(actual == expected, "NHWC width stride and UINT8 zero point");
        for (auto fmt : {RKNN_TENSOR_NC1HWC2, RKNN_TENSOR_NHWC}) {
            checkReportedLayout(64, 80, 80, 0, fmt);
            checkReportedLayout(64, 40, 40, 1, fmt);
            checkReportedLayout(3, 80, 80, 2, fmt);
            checkReportedLayout(3, 40, 40, 3, fmt);
            checkReportedLayout(3, 2, 3, 2, fmt, 4);
        }
        require(NativePlan::half(0x0001) == std::ldexp(1.0f, -24), "FP16 subnormal");
        require(NativePlan::half(0x3c00) == 1.0f && NativePlan::half(0xc000) == -2.0f, "FP16 normal signs");
        require(std::isinf(NativePlan::half(0x7c00)) && std::isnan(NativePlan::half(0x7e00)), "FP16 special values");
        std::cout << "adapter arithmetic and rejection checks completed; hardware untested\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n'; return 2;
    }
}
