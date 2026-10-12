#pragma once

// Software reference for the isolated RGB565 -> RGB888 FPGA input path.
// The caller owns a stable RAW copy; this function does not establish a lease.
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace fpga_v8_raw {
inline constexpr std::size_t width = 640, height = 480, model_height = 640;
inline constexpr std::size_t raw_bytes = width * height * 2;
inline constexpr std::size_t input_bytes = width * model_height * 3;
inline constexpr std::size_t pad_top = 80;
inline constexpr std::uint8_t padding = 114;

inline std::vector<std::uint8_t> prepare(const std::uint8_t* raw, std::size_t size) {
    if (!raw || size != raw_bytes)
        throw std::invalid_argument("requires a complete 640x480 little-endian RGB565 RAW copy");
    std::vector<std::uint8_t> rgb(input_bytes, padding);
    auto* destination = rgb.data() + pad_top * width * 3;
    for (std::size_t i = 0; i < width * height; ++i) {
        const auto pixel = std::uint16_t(raw[i * 2]) | (std::uint16_t(raw[i * 2 + 1]) << 8);
        const auto red = (pixel >> 11) & 31, green = (pixel >> 5) & 63, blue = pixel & 31;
        destination[i * 3] = std::uint8_t((red << 3) | (red >> 2));
        destination[i * 3 + 1] = std::uint8_t((green << 2) | (green >> 4));
        destination[i * 3 + 2] = std::uint8_t((blue << 3) | (blue >> 2));
    }
    return rgb;
}
} // namespace fpga_v8_raw
