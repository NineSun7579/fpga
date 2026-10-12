#pragma once
// Pure checked CPU copy. No allocation, RKNN calls, preprocessing or caching.
#include "prepared/sdk/rknn_api.h"
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>

namespace SingleCopyInput {
constexpr size_t Width = 640, Height = 640, Channels = 3;
constexpr size_t RowBytes = Width * Channels, Bytes = RowBytes * Height;

inline void validate(void *destination, size_t destinationBytes, const void *source, size_t sourceBytes,
                     const rknn_tensor_attr &binding, size_t inputRowBytes) {
    if (!destination || !source || destinationBytes != Bytes || sourceBytes != Bytes ||
        inputRowBytes != RowBytes || binding.index != 0 || binding.n_dims != 4 ||
        binding.dims[0] != 1 || binding.dims[1] != Height || binding.dims[2] != Width || binding.dims[3] != Channels ||
        binding.fmt != RKNN_TENSOR_NHWC || binding.type != RKNN_TENSOR_UINT8 || binding.pass_through != 0 ||
        binding.n_elems != Bytes || binding.size != Bytes || binding.size_with_stride != Bytes ||
        binding.w_stride != Width || binding.h_stride != Height)
        throw std::runtime_error("native_io_single_copy requires exact UINT8 NHWC 1x640x640x3, pass_through0, "
                                 "row1920, width/height stride640 and two full1228800-byte buffers");
    const uintptr_t dst = reinterpret_cast<uintptr_t>(destination), src = reinterpret_cast<uintptr_t>(source);
    if (dst > std::numeric_limits<uintptr_t>::max() - Bytes || src > std::numeric_limits<uintptr_t>::max() - Bytes ||
        (dst < src + Bytes && src < dst + Bytes))
        throw std::runtime_error("native_io_single_copy pointer range overflow or overlapping buffers");
}

inline void copy(void *destination, size_t destinationBytes, const void *source, size_t sourceBytes,
                 const rknn_tensor_attr &binding, size_t inputRowBytes) {
    validate(destination, destinationBytes, source, sourceBytes, binding, inputRowBytes);
    std::memcpy(destination, source, Bytes);
}
} // namespace SingleCopyInput
