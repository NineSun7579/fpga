#ifndef VIEWER_NATIVE_CANDIDATE_GUARD_HPP
#define VIEWER_NATIVE_CANDIDATE_GUARD_HPP

// Pure C++17 profile gate. RKNN struct definitions only, no Qt or RKNN calls.
#include "raw_dfl_native.h"
#include <sstream>

namespace viewer_native {
inline constexpr const char* kModelSha = "be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9";
inline constexpr const char* kRuntimeSha = "73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885";
inline constexpr const char* kApi = "2.3.0 (c949ad889d@2024-11-07T11:35:33)";
inline constexpr const char* kDriver = "0.9.8";
inline constexpr std::array<std::uint32_t, 6> kAllocationBytes{{409600, 102400, 30720, 51200, 12800, 3840}};
inline constexpr std::array<std::uint32_t, 6> kScaleBits{{
    0x3da0a0a1, 0x3d9e27da, 0x3d7c33af, 0x3d425e3c, 0x3d50337b, 0x3d4d63f2}};
inline constexpr std::array<int, 6> kZeroPoints{{0, -2, -35, 83, 69, 71}};

struct Decision {
    bool enabled = false;
    std::string reason;
};
inline bool opt_in(const std::string& value) noexcept { return value == "1"; }
inline bool terminated(const char* text, std::size_t length) noexcept {
    return std::memchr(text, '\0', length) != nullptr;
}

struct Identity {
    std::string model_sha, runtime_sha, api, driver;
    bool one_canonical_mapped_runtime = false;
    unsigned inputs = 0, outputs = 0;
    int classes = 0;
    bool lane = false, int8_input_override = false;
};

// The caller canonicalizes these paths and rejects ambiguous loaded libraries.
// No environment variable or link-time library path stands in for actual mappings.
struct MappedPaths { std::vector<std::string> paths; std::string error; };
inline MappedPaths mapped_runtime_paths(const std::string& maps) {
    MappedPaths result;
    std::istringstream lines(maps);
    std::string line;
    while (std::getline(lines, line)) {
        std::istringstream fields(line);
        std::string range, permissions, offset, device, inode, path;
        if (!(fields >> range >> permissions >> offset >> device >> inode)) continue;
        std::getline(fields, path);
        const auto start = path.find_first_not_of(" \t");
        if (start == std::string::npos) continue;
        path.erase(0, start);
        const auto slash = path.find_last_of('/');
        const auto basename = path.substr(slash == std::string::npos ? 0 : slash + 1);
        if (basename != "librknnrt.so" && basename.compare(0, 13, "librknnrt.so.") != 0 &&
            basename != "librknnrt.so (deleted)") continue;
        if (path.empty() || path.front() != '/' || path.find(" (deleted)") != std::string::npos ||
            path.find('\\') != std::string::npos) {
            result.error = "loaded RKNN runtime mapping is deleted, escaped or inaccessible";
            return result;
        }
        if (std::find(result.paths.begin(), result.paths.end(), path) == result.paths.end())
            result.paths.push_back(path);
    }
    if (result.paths.empty()) result.error = "no RKNN runtime found in /proc/self/maps";
    return result;
}

inline Decision check_profile(bool requested, const Identity& id,
                              const rknn_tensor_attr& input,
                              const std::vector<rknn_tensor_attr>& attrs) {
    if (!requested) return {false, "DET_V8_NATIVE must equal 1"};
    if (id.model_sha != kModelSha) return {false, "model SHA256 is outside pinned V8 profile"};
    if (!id.one_canonical_mapped_runtime) return {false, "loaded RKNN runtime path is unverified or ambiguous"};
    if (id.runtime_sha != kRuntimeSha) return {false, "loaded RKNN runtime SHA256 mismatch"};
    if (id.api != kApi) return {false, "RKNN API version mismatch"};
    if (id.driver != kDriver) return {false, "RKNN driver version mismatch"};
    if (id.inputs != 1 || id.outputs != 6 || attrs.size() != 6)
        return {false, "native profile requires one input and six outputs"};
    if (id.classes != 3 || id.lane) return {false, "native profile requires three-class detection"};
    if (id.int8_input_override) return {false, "DET_INT8_IN override requires existing float path"};
    if (!terminated(input.name, sizeof(input.name)) || std::strcmp(input.name, "images") != 0 ||
        input.index != 0 || input.n_dims != 4 || input.dims[0] != 1 || input.dims[1] != 640 ||
        input.dims[2] != 640 || input.dims[3] != 3 || input.fmt != RKNN_TENSOR_NHWC ||
        input.type != RKNN_TENSOR_INT8 || input.qnt_type != RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC ||
        input.zp != -128 || raw_dfl::detail::float_bits(input.scale) != 0x3b808081 ||
        input.n_elems != 1228800 || input.size != 1228800 || input.w_stride != 640 ||
        input.size_with_stride != 1228800)
        return {false, "input attribute differs from recorded RGB640 NHWC profile"};
    try {
        std::uint8_t placeholder = 0;
        std::vector<rknn_output> outputs(6);
        for (unsigned i = 0; i != 6; ++i) {
            const auto& a = attrs[i];
            if (a.index != i || !terminated(a.name, sizeof(a.name)) ||
                std::strcmp(a.name, raw_dfl::names[i]) != 0 || a.type != RKNN_TENSOR_INT8 ||
                a.zp != kZeroPoints[i] || raw_dfl::detail::float_bits(a.scale) != kScaleBits[i] ||
                a.w_stride != 0 || a.size_with_stride != kAllocationBytes[i])
                return {false, "output attribute identity/quantization/stride mismatch at index " + std::to_string(i)};
            outputs[i].index = i;
            outputs[i].buf = &placeholder; // Validation is metadata-only; never decode it.
            outputs[i].size = a.n_elems;
        }
        const auto heads = raw_dfl::detail::validate(outputs, attrs);
        raw_dfl::detail::validate_profile(heads, true);
    } catch (const std::exception& e) { return {false, e.what()}; }
    return {true, "pinned V8 native profile verified"};
}

inline raw_dfl::Config decoder_config(float confidence) {
    raw_dfl::Config c;
    c.confidence = confidence;
    c.iou = 0.45f;
    c.topk = 300;
    c.production_compatibility = true;
    c.pinned_rknn230_dequantization = true;
    raw_dfl::detail::validate_config(c);
    return c;
}

// Exactly one release attempt after successful get, including exceptions. Tests
// supply a fake function; the viewer supplies its actual rknn_outputs_release.
class OutputLease {
public:
    using Release = int (*)(rknn_context, std::uint32_t, rknn_output*);
    OutputLease(rknn_context context, std::vector<rknn_output>& outputs, Release release)
        : context_(context), outputs_(outputs), release_(release) {}
    OutputLease(const OutputLease&) = delete;
    OutputLease& operator=(const OutputLease&) = delete;
    ~OutputLease() noexcept { if (active_) finish(); }
    int finish() noexcept {
        if (!active_) return status_;
        active_ = false;
        try { status_ = release_(context_, static_cast<std::uint32_t>(outputs_.size()), outputs_.data()); }
        catch (...) { status_ = -1; }
        return status_;
    }
private:
    rknn_context context_;
    std::vector<rknn_output>& outputs_;
    Release release_;
    bool active_ = true;
    int status_ = 0;
};
} // namespace viewer_native
#endif
