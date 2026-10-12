#pragma once
#include "viewer_native_guard.hpp"

namespace viewer_native {
// Only the existing pinned profile; current trafficlight/rectangular models
// must retain their production float decoder even with identical head shapes.
inline bool current_geometry_gate(bool trafficlight, int width, int height, int channels) noexcept {
    return !trafficlight && width == 640 && height == 640 && channels == 3;
}
inline Decision check_current_profile(bool requested, const Identity& id,
                                     const rknn_tensor_attr& input,
                                     const std::vector<rknn_tensor_attr>& attrs,
                                     bool trafficlight, int width, int height, int channels) {
    if (!current_geometry_gate(trafficlight, width, height, channels))
        return {false, "current native requires non-trafficlight 640x640 RGB3"};
    return check_profile(requested, id, input, attrs);
}
} // namespace viewer_native
