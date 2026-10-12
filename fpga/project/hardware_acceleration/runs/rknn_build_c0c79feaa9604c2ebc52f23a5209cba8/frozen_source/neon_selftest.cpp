// Real AArch64 NEON arithmetic under local QEMU, never RKNN/NPU execution.
#include "native_adapter.h"
#include <sys/mman.h>
#include <unistd.h>
#include <fstream>
#include <iostream>

static void require(bool ok, const char *why) { if (!ok) throw std::runtime_error(why); }
template<class F> static void rejects(F f, const char *why) {
    bool rejected = false;
    try { f(); } catch (const std::runtime_error &) { rejected = true; }
    require(rejected, why);
}
struct GuardedInput {
    void *mapping; size_t length; uint8_t *data;
    explicit GuardedInput(size_t bytes) {
        const size_t page = size_t(sysconf(_SC_PAGESIZE));
        const size_t rounded = (bytes + page - 1) / page * page;
        length = rounded + 2 * page;
        mapping = mmap(nullptr, length, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        require(mapping != MAP_FAILED, "guarded mapping");
        auto *start = static_cast<uint8_t *>(mapping) + page;
        require(mprotect(start, rounded, PROT_READ | PROT_WRITE) == 0, "guarded buffer access");
        data = start + rounded - bytes; // last allocation byte borders PROT_NONE
    }
    ~GuardedInput() { munmap(mapping, length); }
};
static size_t cases = 0, elements = 0, neonCases = 0;
static rknn_tensor_attr logical(unsigned c, unsigned h, unsigned w, rknn_tensor_type type, int zp, float scale) {
    rknn_tensor_attr a{}; a.n_dims = 4; a.dims[0] = 1; a.dims[1] = c; a.dims[2] = h; a.dims[3] = w;
    a.n_elems = a.size = c * h * w; a.fmt = RKNN_TENSOR_NCHW;
    a.type = type; a.qnt_type = RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC; a.zp = zp; a.scale = scale;
    return a;
}
static void check(unsigned c, unsigned h, unsigned w, unsigned padding, rknn_tensor_type type,
                  int zp, float scale, NativePlan::DequantScale policy, unsigned c2 = 8) {
    const auto l = logical(c, h, w, type, zp, scale);
    auto a = l; const unsigned blocks = (c + c2 - 1) / c2 + (c == 3 ? 1 : 0);
    a.n_dims = 5; a.dims[1] = blocks; a.dims[2] = h; a.dims[3] = w; a.dims[4] = c2;
    a.fmt = RKNN_TENSOR_NC1HWC2; a.n_elems = a.size = blocks * h * w * c2;
    const unsigned ws = w + padding; a.w_stride = padding ? ws : 0;
    a.size_with_stride = blocks * h * ws * c2;
    const auto plan = NativePlan::make(l, a, policy);
    GuardedInput input(plan.bytes);
    std::vector<float> expected(l.n_elems), scalar(l.n_elems);
    // Distinct logical channels/pixels cover every byte value in width256.
    // Entire unused blocks, padded channels and padded width carry sentinels.
    for (unsigned block = 0; block < blocks; ++block)
        for (unsigned y = 0; y < h; ++y)
            for (unsigned x = 0; x < ws; ++x)
                for (unsigned k = 0; k < c2; ++k) {
                    const unsigned channel = block * c2 + k;
                    const size_t offset = ((size_t(block) * h + y) * ws + x) * c2 + k;
                    const uint8_t byte = channel < c && x < w ? uint8_t(channel * 37 + y * 29 + x * 13) : 0xa5;
                    input.data[offset] = byte;
                    if (channel < c && x < w) {
                        const int q = type == RKNN_TENSOR_INT8 && byte >= 128 ? int(byte) - 256 : int(byte);
                        expected[(size_t(channel) * h + y) * w + x] = float(q - zp) * plan.effectiveScale;
                    }
                }
    const std::vector<uint8_t> original(input.data, input.data + plan.bytes);
    // Extra capacity remains initialized to expose writes beyond logical size.
    std::vector<float> actual(l.n_elems + 16, -12345.0f);
    actual.resize(l.n_elems);
    plan.convert(input.data, plan.bytes, actual);
    plan.convertScalar(input.data, plan.bytes, scalar);
    require(std::memcmp(actual.data(), scalar.data(), l.n_elems * sizeof(float)) == 0, "NEON/scalar bitwise parity");
    require(std::memcmp(actual.data(), expected.data(), l.n_elems * sizeof(float)) == 0, "independent logical values");
    const float guard = -12345.0f;
    for (unsigned i = 0; i < 16; ++i)
        require(std::memcmp(reinterpret_cast<const uint8_t *>(actual.data()) + (l.n_elems + i) * sizeof(float),
                            &guard, sizeof(float)) == 0, "destination channel/tail overwrite");
    require(std::memcmp(input.data, original.data(), plan.bytes) == 0, "native input must remain immutable");
    rejects([&] { plan.convert(input.data, plan.bytes - 1, actual); }, "NEON short allocation rejection");
    rejects([&] { plan.convertScalar(input.data, plan.bytes - 1, scalar); }, "scalar short allocation rejection");
    std::vector<float> wrong(l.n_elems - 1);
    rejects([&] { plan.convert(input.data, plan.bytes, wrong); }, "NEON destination size rejection");
    // Changing all padding must not change any logical result.
    for (unsigned block = 0; block < blocks; ++block)
        for (unsigned y = 0; y < h; ++y)
            for (unsigned x = 0; x < ws; ++x)
                for (unsigned k = 0; k < c2; ++k)
                    if (block * c2 + k >= c || x >= w)
                        input.data[((size_t(block) * h + y) * ws + x) * c2 + k] ^= 0xff;
    plan.convert(input.data, plan.bytes, actual);
    require(std::memcmp(actual.data(), expected.data(), l.n_elems * sizeof(float)) == 0, "padding content independence");
#if defined(__aarch64__) && defined(__ARM_NEON)
    require(plan.usesNeon() == (c2 == 8), "actual NEON dispatch with c2 fallback");
#else
    require(!plan.usesNeon(), "portable scalar fallback");
#endif
    ++cases; elements += l.n_elems; neonCases += plan.usesNeon();
}
static void archived(const char *nativePath, const char *baselinePath, unsigned c, unsigned h, unsigned w,
                     int zp, float scale) {
    const auto l = logical(c, h, w, RKNN_TENSOR_INT8, zp, scale);
    std::vector<float> old(l.n_elems), expected(l.n_elems), actual(l.n_elems), scalar(l.n_elems);
    std::ifstream native(nativePath, std::ios::binary), baseline(baselinePath, std::ios::binary);
    require(bool(native.read(reinterpret_cast<char *>(old.data()), old.size() * sizeof(float))) &&
            native.peek() == std::char_traits<char>::eof(), "archived native file size/read");
    require(bool(baseline.read(reinterpret_cast<char *>(expected.data()), expected.size() * sizeof(float))) &&
            baseline.peek() == std::char_traits<char>::eof(), "archived baseline file size/read");
    auto a = l; const unsigned blocks = c == 3 ? 2 : 8;
    a.n_dims = 5; a.dims[1] = blocks; a.dims[2] = h; a.dims[3] = w; a.dims[4] = 8;
    a.fmt = RKNN_TENSOR_NC1HWC2; a.size = a.n_elems = a.size_with_stride = blocks * h * w * 8;
    const auto p = NativePlan::make(l, a, NativePlan::DequantScale::Fp16);
    GuardedInput input(p.bytes); std::memset(input.data, 165, p.bytes);
    for (unsigned channel = 0; channel < c; ++channel)
        for (unsigned y = 0; y < h; ++y)
            for (unsigned x = 0; x < w; ++x) {
                const float value = old[(size_t(channel) * h + y) * w + x];
                const long delta = std::lround(double(value) / scale), q = delta + zp;
                require(q >= -128 && q <= 127 && float(delta) * scale == value, "archive exact integer recovery");
                input.data[(((size_t(channel / 8) * h + y) * w + x) * 8) + channel % 8] = uint8_t(q < 0 ? q + 256 : q);
            }
    p.convert(input.data, p.bytes, actual); p.convertScalar(input.data, p.bytes, scalar);
    require(std::memcmp(actual.data(), scalar.data(), l.n_elems * sizeof(float)) == 0 &&
            std::memcmp(actual.data(), expected.data(), l.n_elems * sizeof(float)) == 0,
            "archived reconstructed NC1HWC2 exact NEON/scalar/baseline floats");
    // Reconstructed blocked bytes exercise ISA arithmetic; they cannot certify
    // actual native layout or the rebuilt binary's hardware parity.
    std::cout << "archive_elements=" << l.n_elems << "; exact_neon_scalar_baseline=true; native_raw_certified=false\n";
}
int main(int argc, char **argv) {
    try {
        for (auto type : {RKNN_TENSOR_INT8, RKNN_TENSOR_UINT8})
            for (int zp : (type == RKNN_TENSOR_INT8 ? std::vector<int>{-128, -7, 0, 83, 127} : std::vector<int>{0, 83, 255}))
                for (auto policy : {NativePlan::DequantScale::Fp32, NativePlan::DequantScale::Fp16})
                    for (float scale : {0.0784313753247261f, 0.04749705642461777f, 0.049998946487903595f, 1e-40f})
                        for (unsigned c : {1u, 3u, 5u, 7u, 8u, 9u, 16u, 64u})
                            for (unsigned w : {1u, 7u, 8u, 9u, 15u, 16u, 40u, 79u, 80u, 256u})
                                for (unsigned padding : {0u, 3u})
                                    check(c, 3, w, padding, type, zp, scale, policy);
        for (unsigned size : {40u, 80u}) {
            check(64, size, size, 0, RKNN_TENSOR_INT8, 0, 0.0784313753247261f, NativePlan::DequantScale::Fp16);
            check(3, size, size, 0, RKNN_TENSOR_INT8, size == 80 ? 83 : 72,
                  size == 80 ? 0.04749705642461777f : 0.049998946487903595f, NativePlan::DequantScale::Fp16);
        }
        check(3, 3, 9, 3, RKNN_TENSOR_INT8, 83, 0.04749705642461777f, NativePlan::DequantScale::Fp16, 4);
        if (argc == 9) {
            for (unsigned i = 0; i < 4; ++i)
                archived(argv[1 + 2 * i], argv[2 + 2 * i], i < 2 ? 64 : 3, i % 2 == 0 ? 80 : 40,
                         i % 2 == 0 ? 80 : 40, i < 2 ? 0 : i == 2 ? 83 : 72,
                         i < 2 ? 0.0784313753247261f : i == 2 ? 0.04749705642461777f : 0.049998946487903595f);
        } else require(argc == 1, "expected zero or eight archived file arguments");
        std::cout << "cases=" << cases << "; logical_elements=" << elements << "; neon_cases=" << neonCases
                  << "; bitwise_parity=true; guarded_tails_padding=true; hardware_executed=false\n";
        return 0;
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 1; }
}
