// Host CPU copy checks: repeated complete frames, source immutability, canaries,
// and rejection before any write. Does not load a runtime or execute inference.
#include "single_copy_input.h"
#include <algorithm>
#include <iostream>
#include <vector>

static void require(bool ok, const char *why) { if (!ok) throw std::runtime_error(why); }
static rknn_tensor_attr binding() {
    rknn_tensor_attr a{}; a.n_dims = 4; a.dims[0] = 1; a.dims[1] = 640; a.dims[2] = 640; a.dims[3] = 3;
    a.fmt = RKNN_TENSOR_NHWC; a.type = RKNN_TENSOR_UINT8; a.pass_through = 0;
    a.n_elems = a.size = a.size_with_stride = uint32_t(SingleCopyInput::Bytes);
    a.w_stride = a.h_stride = 640; return a;
}
int main() {
    try {
        constexpr size_t Guard = 32, Bytes = SingleCopyInput::Bytes;
        std::vector<uint8_t> source(Bytes + 2 * Guard, 0xb6), destination(Bytes + 2 * Guard, 0xa5);
        auto *src = source.data() + Guard, *dst = destination.data() + Guard;
        const auto valid = binding();
        size_t frames = 0, rejections = 0;
        for (unsigned frame = 0; frame < 7; ++frame) {
            // Preserve letterbox pads; change every content row between frames.
            // Refill/corrupt destination first so stale prior input cannot pass.
            std::fill(src, src + Bytes, 114);
            for (size_t y = 80; y < 560; ++y)
                for (size_t x = 0; x < SingleCopyInput::RowBytes; ++x)
                    src[y * SingleCopyInput::RowBytes + x] = uint8_t(y * 29 + x * 13 + frame * 47);
            std::fill(dst, dst + Bytes, uint8_t(frame + 1));
            const auto before = source;
            SingleCopyInput::copy(dst, Bytes, src, Bytes, valid, SingleCopyInput::RowBytes);
            require(std::equal(src, src + Bytes, dst), "full frame copy including gray114 pads");
            require(source == before, "source/guards immutable");
            require(std::all_of(destination.begin(), destination.begin() + Guard, [](uint8_t b) { return b == 0xa5; }) &&
                    std::all_of(destination.end() - Guard, destination.end(), [](uint8_t b) { return b == 0xa5; }),
                    "destination canaries");
            ++frames;
        }
        auto reject = [&](void *d, size_t ds, const void *s, size_t ss, const rknn_tensor_attr &a, size_t row) {
            const auto dstBefore = destination, srcBefore = source;
            bool failed = false;
            try { SingleCopyInput::copy(d, ds, s, ss, a, row); } catch (const std::runtime_error &) { failed = true; }
            require(failed, "invalid copy accepted");
            require(destination == dstBefore && source == srcBefore, "rejected copy must change no bytes");
            ++rejections;
        };
        for (size_t size : {size_t(0), Bytes - 1, Bytes + 1, Bytes + 4096}) {
            reject(dst, size, src, Bytes, valid, 1920);
            reject(dst, Bytes, src, size, valid, 1920);
        }
        reject(nullptr, Bytes, src, Bytes, valid, 1920);
        reject(dst, Bytes, nullptr, Bytes, valid, 1920);
        reject(dst, Bytes, dst, Bytes, valid, 1920);
        reject(dst, Bytes, dst + 1, Bytes, valid, 1920);
        reject(dst + 1, Bytes, dst, Bytes, valid, 1920);
        const auto overflow = reinterpret_cast<void *>(std::numeric_limits<uintptr_t>::max() - 10);
        reject(overflow, Bytes, src, Bytes, valid, 1920);
        reject(dst, Bytes, overflow, Bytes, valid, 1920);
        for (size_t stride : {size_t(0), size_t(1919), size_t(1923)}) reject(dst, Bytes, src, Bytes, valid, stride);
        for (unsigned i = 0; i < 16; ++i) {
            auto a = valid;
            switch (i) {
            case 0: a.index = 1; break;
            case 1: a.n_dims = 3; break;
            case 2: a.dims[0] = 2; break;
            case 3: a.dims[1] = 641; break;
            case 4: a.dims[2] = 641; break;
            case 5: a.dims[3] = 4; break;
            case 6: a.fmt = RKNN_TENSOR_NCHW; break;
            case 7: a.type = RKNN_TENSOR_INT8; break;
            case 8: a.pass_through = 1; break;
            case 9: --a.n_elems; break;
            case 10: --a.size; break;
            case 11: ++a.size_with_stride; break;
            case 12: a.w_stride = 641; break;
            case 13: a.h_stride = 641; break;
            case 14: a.w_stride = 0; break;
            case 15: a.h_stride = 0; break;
            }
            reject(dst, Bytes, src, Bytes, a, 1920);
        }
        std::cout << "full_frame_copies=" << frames << "; unchanged_on_rejection=" << rejections
                  << "; canaries_and_padding_passed=true; hardware_executed=false\n";
        return 0;
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 1; }
}
