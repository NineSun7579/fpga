#include "src/current_native_gate.hpp"
#include <atomic>
#include <optional>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>

// Container adapter only: production decoder body is imported byteexact.
template<class T> class QVector : public std::vector<T> {
public:
    void append(const T& value) { this->push_back(value); }
    int size() const { return static_cast<int>(std::vector<T>::size()); }
};
using Detection = raw_dfl::Detection;
struct CurrentProductionOracle {
    static constexpr float IOU_THRESH = 0.45f;
    int m_nc = 3;
    bool m_trafficlight = false, m_xyxy = false;
    struct { int width = 640; } m_geometry;
    std::atomic<float> m_conf{0.32f};
    // Existing production int/float conversions are intentionally retained.
#pragma warning(push)
#pragma warning(disable: 4244)
#include "current_retained_decoder.inc"
#pragma warning(pop)
};

namespace {
using namespace viewer_native;
unsigned checks = 0, cases = 0, release_calls = 0, released_buffers = 0;
int release_status = 0;
void check(bool value, const char* expression, int line) {
    ++checks;
    if (!value) throw std::runtime_error(std::to_string(line) + ": " + expression);
}
#define CHECK(x) check(bool(x), #x, __LINE__)
struct Fixture { Identity identity; rknn_tensor_attr input{}; std::vector<rknn_tensor_attr> heads; };

rknn_tensor_attr read_attr(std::istream& file) {
    rknn_tensor_attr a{};
    std::string name;
    unsigned format = 0, type = 0, quant = 0;
    std::uint32_t bits = 0;
    file >> a.index >> name >> a.n_dims >> a.dims[0] >> a.dims[1] >> a.dims[2] >> a.dims[3]
         >> format >> type >> quant >> a.n_elems >> a.size >> a.w_stride >> a.size_with_stride >> a.zp >> bits;
    CHECK(file.good() && name.size() < sizeof(a.name));
    std::memcpy(a.name, name.c_str(), name.size() + 1);
    a.fmt = static_cast<rknn_tensor_format>(format);
    a.type = static_cast<rknn_tensor_type>(type);
    a.qnt_type = static_cast<rknn_tensor_qnt_type>(quant);
    a.scale = raw_dfl::detail::float_from_bits(bits);
    return a;
}
Fixture load(const char* filename) {
    std::ifstream file(filename);
    CHECK(file.good());
    Fixture f;
    file >> f.identity.model_sha >> f.identity.runtime_sha >> std::quoted(f.identity.api) >> f.identity.driver;
    f.identity.one_canonical_mapped_runtime = true;
    f.identity.inputs = 1; f.identity.outputs = 6; f.identity.classes = 3;
    f.input = read_attr(file);
    for (unsigned i = 0; i != 6; ++i) f.heads.push_back(read_attr(file));
    return f;
}
Decision gate(const Fixture& f, bool requested = true) {
    return check_current_profile(requested, f.identity, f.input, f.heads, false, 640, 640, 3);
}
void test(const std::string& name, const std::function<void()>& body) {
    body(); ++cases; std::cout << "PASS " << name << '\n';
}
int fake_release(rknn_context context, std::uint32_t count, rknn_output* outputs) {
    CHECK(context == 123 && count == 6);
    ++release_calls;
    for (std::uint32_t i = 0; i < count; ++i) {
        CHECK(outputs[i].buf != nullptr);
        ++released_buffers;
    }
    return release_status;
}

void tests(const Fixture& recorded) {
    test("current geometry and trafficlight exclude otherwise exact dangerous profile", [&] {
        CHECK(check_current_profile(true, recorded.identity, recorded.input, recorded.heads, false, 640, 640, 3).enabled);
        for (const auto trafficlight : {false, true}) {
            CHECK(!check_current_profile(true, recorded.identity, recorded.input, recorded.heads, trafficlight, 640, 480, 3).enabled);
        }
        CHECK(!check_current_profile(true, recorded.identity, recorded.input, recorded.heads, true, 640, 640, 3).enabled);
        CHECK(!check_current_profile(true, recorded.identity, recorded.input, recorded.heads, false, 640, 640, 1).enabled);
        CHECK(!check_current_profile(true, recorded.identity, recorded.input, recorded.heads, false, 480, 640, 3).enabled);
        auto shapeOnly = recorded;
        shapeOnly.identity.model_sha = "21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31";
        CHECK(!gate(shapeOnly).enabled);
        // Reindex/rename permuted class heads: dimensions alone are insufficient.
        auto permuted = recorded;
        std::swap(permuted.heads[3].scale, permuted.heads[4].scale);
        std::swap(permuted.heads[3].zp, permuted.heads[4].zp);
        CHECK(!gate(permuted).enabled);
    });
    test("current production oracle parity on pinned signed heads all scales and thresholds", [&] {
        std::array<std::vector<std::uint8_t>, 6> storage;
        std::vector<rknn_output> outputs(6), floatOutputs(6);
        std::array<std::vector<float>, 6> floats;
        for (unsigned i = 0; i != 6; ++i) {
            storage[i].resize(recorded.heads[i].n_elems, static_cast<std::uint8_t>(i < 3 ? 0 : 128));
            outputs[i].index = i; outputs[i].buf = storage[i].data();
            outputs[i].size = recorded.heads[i].n_elems;
        }
        for (unsigned scale = 0; scale != 3; ++scale) {
            const unsigned w = recorded.heads[scale].dims[3];
            const unsigned cell = (w - 1) * w + w - 1; // unclipped bottom-right box
            const unsigned plane = w * w;
            storage[scale + 3][scale * plane + cell] = static_cast<std::uint8_t>(127 - scale * 10);
            for (unsigned side = 0; side != 4; ++side)
                storage[scale][(side * 16 + 2) * plane + cell] = 120;
        }
        const auto heads = raw_dfl::detail::validate(outputs, recorded.heads);
        for (unsigned i = 0; i != 6; ++i) {
            floats[i].resize(storage[i].size());
            for (std::size_t j = 0; j != storage[i].size(); ++j)
                floats[i][j] = raw_dfl::detail::profiled_dequant(raw_dfl::detail::code(storage[i][j], RKNN_TENSOR_INT8), heads[i], static_cast<int>(i), true);
            floatOutputs[i].index = i; floatOutputs[i].want_float = 1;
            floatOutputs[i].buf = floats[i].data();
            floatOutputs[i].size = recorded.heads[i].n_elems * 4;
        }
        CurrentProductionOracle oracle;
        for (const float confidence : {0.05f, 0.32f, 0.5f, 0.95f}) {
            oracle.m_conf = confidence;
            raw_dfl::NativeDecoder decoder(decoder_config(confidence));
            const auto native = decoder.decode(outputs, recorded.heads);
            const auto current = oracle.decode(floatOutputs, recorded.heads);
            CHECK(native.size() == static_cast<std::size_t>(current.size()));
            if (confidence == 0.32f) CHECK(native.size() == 3);
            for (std::size_t i = 0; i != native.size(); ++i) {
                CHECK(native[i].cls == current[i].cls);
                CHECK(std::fabs(native[i].score - current[i].score) <= 1e-6f);
                CHECK(std::fabs(native[i].x1 - current[i].x1) <= 1e-3f);
                CHECK(std::fabs(native[i].y1 - current[i].y1) <= 1e-3f);
                CHECK(std::fabs(native[i].x2 - current[i].x2) <= 1e-3f);
                CHECK(std::fabs(native[i].y2 - current[i].y2) <= 1e-3f);
            }
        }
    });
    test("native float native transitions retain context decoder state after completed cache growth", [&] {
        struct Context { Decision mode; std::optional<raw_dfl::NativeDecoder> decoder; };
        std::vector<Context> cache;
        cache.push_back({gate(recorded), {}});
        auto v4 = recorded; v4.identity.model_sha = "different-same-shape-3cls";
        cache.push_back({gate(v4), {}});
        cache.push_back({check_current_profile(true, recorded.identity, recorded.input, recorded.heads, true, 640, 480, 3), {}});
        cache.push_back({gate(recorded), {}});
        cache[0].decoder.emplace(decoder_config(0.32f));
        cache[3].decoder.emplace(decoder_config(0.95f));
        const auto* saved = &*cache[0].decoder;
        std::array<std::vector<std::uint8_t>, 6> storage;
        std::vector<rknn_output> outputs(6);
        for (unsigned i = 0; i != 6; ++i) {
            storage[i].resize(recorded.heads[i].n_elems, static_cast<std::uint8_t>(i < 3 ? 0 : 128));
            outputs[i].index = i; outputs[i].buf = storage[i].data();
            outputs[i].size = recorded.heads[i].n_elems;
        }
        storage[3][0] = 127;
        Context* selected = nullptr;
        for (unsigned index : {0u, 1u, 3u, 2u, 0u, 3u, 2u, 1u, 0u}) {
            selected = &cache[index];
            CHECK(selected->mode.enabled == (index == 0 || index == 3));
            if (selected->mode.enabled) {
                const auto detections = selected->decoder->decode(outputs, recorded.heads);
                CHECK(detections.size() == (index == 0 ? 1u : 0u));
                if (index == 0) CHECK(&*selected->decoder == saved);
            }
            else CHECK(!selected->decoder);
        }
        CHECK(cache[0].decoder->class_table_count() > 0);
        CHECK(cache[3].decoder->class_table_count() > 0);
        selected = nullptr;
        cache.clear();
        CHECK(selected == nullptr && cache.empty());
        cache.push_back({gate(v4), {}}); CHECK(!cache[0].mode.enabled);
    });
    test("recorded board native profile accepted with packed outputs and device padding", [&] {
        const auto d = gate(recorded); CHECK(d.enabled && !d.reason.empty());
        CHECK(recorded.heads[2].size == 25600 && recorded.heads[2].size_with_stride == 30720);
        CHECK(recorded.heads[3].size == 19200 && recorded.heads[3].size_with_stride == 51200);
    });
    test("explicit opt-in string truth; false and unset stay on original float path", [&] {
        CHECK(opt_in("1"));
        for (const auto value : {"", "0", "true", "yes", "01", " 1", "1 "}) {
            CHECK(!opt_in(value)); CHECK(!gate(recorded, opt_in(value)).enabled);
        }
    });
    const std::vector<std::pair<const char*, std::function<void(Identity&)>>> identities{
        {"default v4 model rejected", [](auto& i) { i.model_sha = "21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31"; }},
        {"one-bit model hash change", [](auto& i) { i.model_sha[0] = '0'; }},
        {"different runtime library", [](auto& i) { i.runtime_sha[0] = '0'; }},
        {"runtime mapping ambiguous", [](auto& i) { i.one_canonical_mapped_runtime = false; }},
        {"API short alias insufficient", [](auto& i) { i.api = "2.3.0"; }},
        {"API different build", [](auto& i) { i.api += "x"; }},
        {"driver mismatch", [](auto& i) { i.driver = "0.9.9"; }},
        {"wrong input count", [](auto& i) { i.inputs = 2; }},
        {"wrong output count", [](auto& i) { i.outputs = 1; }},
        {"wrong configured class count", [](auto& i) { i.classes = 29; }},
        {"lane model excluded", [](auto& i) { i.lane = true; }},
        {"INT8 input override excluded", [](auto& i) { i.int8_input_override = true; }}
    };
    for (const auto& mutation : identities) test(mutation.first, [&] {
        auto changed = recorded; mutation.second(changed.identity);
        const auto d = gate(changed); CHECK(!d.enabled && !d.reason.empty());
    });
    const std::vector<std::pair<const char*, std::function<void(rknn_tensor_attr&)>>> head_changes{
        {"name", [](auto& a) { a.name[0] = 'x'; }},
        {"unterminated name", [](auto& a) { std::memset(a.name, 'x', sizeof(a.name)); }},
        {"index", [](auto& a) { a.index = 6; }},
        {"shape rank", [](auto& a) { a.n_dims = 3; }},
        {"batch", [](auto& a) { a.dims[0] = 2; }},
        {"channel count", [](auto& a) { ++a.dims[1]; }},
        {"height", [](auto& a) { ++a.dims[2]; }},
        {"width", [](auto& a) { ++a.dims[3]; }},
        {"NHWC layout", [](auto& a) { a.fmt = RKNN_TENSOR_NHWC; }},
        {"unsigned outputs", [](auto& a) { a.type = RKNN_TENSOR_UINT8; }},
        {"float outputs", [](auto& a) { a.type = RKNN_TENSOR_FLOAT32; }},
        {"quantization", [](auto& a) { a.qnt_type = RKNN_TENSOR_QNT_NONE; }},
        {"zero point", [](auto& a) { ++a.zp; }},
        {"one-bit scale", [](auto& a) { a.scale = raw_dfl::detail::float_from_bits(raw_dfl::detail::float_bits(a.scale) ^ 1); }},
        {"zero scale", [](auto& a) { a.scale = 0; }},
        {"nonfinite scale", [](auto& a) { a.scale = std::numeric_limits<float>::quiet_NaN(); }},
        {"element count", [](auto& a) { --a.n_elems; }},
        {"logical byte size", [](auto& a) { ++a.size; }},
        {"width stride", [](auto& a) { a.w_stride = 128; }},
        {"allocation bytes", [](auto& a) { ++a.size_with_stride; }}
    };
    for (unsigned index = 0; index != 6; ++index) {
        for (const auto& mutation : head_changes) {
            test("head " + std::to_string(index) + " rejects " + mutation.first, [&] {
                auto changed = recorded; mutation.second(changed.heads[index]);
                const auto d = gate(changed); CHECK(!d.enabled && !d.reason.empty());
            });
        }
    }
    test("duplicate/missing/reordered heads rejected", [&] {
        auto f = recorded; f.heads.pop_back(); CHECK(!gate(f).enabled);
        f = recorded; f.heads[1] = f.heads[0]; CHECK(!gate(f).enabled);
        f = recorded; std::swap(f.heads[0], f.heads[1]); CHECK(!gate(f).enabled);
    });
    for (const auto& mutation : head_changes) test(std::string("input rejects ") + mutation.first, [&] {
        auto changed = recorded; mutation.second(changed.input);
        // Input is already NHWC: switch it to NCHW for this layout mutation.
        if (std::string(mutation.first) == "NHWC layout") changed.input.fmt = RKNN_TENSOR_NCHW;
        CHECK(!gate(changed).enabled);
    });
    test("confidence slider uses production compatibility, pinned dequant, top300, IOU .45", [] {
        for (const float confidence : {0.05f, 0.25f, 0.32f, 0.95f}) {
            const auto c = decoder_config(confidence);
            CHECK(c.confidence == confidence && c.iou == 0.45f && c.topk == 300);
            CHECK(c.production_compatibility && c.pinned_rknn230_dequantization);
        }
        for (const float value : {-0.01f, 1.01f, std::numeric_limits<float>::quiet_NaN()}) {
            bool rejected = false;
            try { decoder_config(value); } catch (const std::invalid_argument&) { rejected = true; }
            CHECK(rejected);
        }
    });
    test("mapped library discovery handles segments, symlinks, deleted/ambiguous/absent paths", [] {
        const auto p = mapped_runtime_paths(
            "1000-2000 r-xp 00000000 08:01 100 /usr/lib/librknnrt.so\n"
            "2000-3000 rw-p 00001000 08:01 100 /usr/lib/librknnrt.so\n"
            "3000-4000 r-xp 00000000 08:01 101 /opt/vendor/librknnrt.so.2\n"
            "4000-5000 r-xp 00000000 08:01 102 /usr/lib/notlibrknnrt.so\n");
        CHECK(p.error.empty() && p.paths.size() == 2);
        CHECK(p.paths[0] == "/usr/lib/librknnrt.so" && p.paths[1] == "/opt/vendor/librknnrt.so.2");
        CHECK(!mapped_runtime_paths("1000-2000 r-xp 0 08:01 100 /usr/lib/librknnrt.so (deleted)\n").error.empty());
        CHECK(!mapped_runtime_paths("1000-2000 r-xp 0 08:01 100 /usr/lib/librknnrt.so.2 (deleted)\n").error.empty());
        CHECK(!mapped_runtime_paths("1000-2000 r-xp 0 08:01 100 /x\\040y/librknnrt.so\n").error.empty());
        CHECK(!mapped_runtime_paths("1000-2000 r-xp 0 08:01 100 /usr/lib/libother.so\n").error.empty());
    });
    test("successful signed native decode returns independent detection values and releases once", [&] {
        std::array<std::vector<std::uint8_t>, 6> storage;
        std::vector<rknn_output> outputs(6);
        for (unsigned i = 0; i != 6; ++i) {
            storage[i].resize(recorded.heads[i].n_elems, static_cast<std::uint8_t>(i < 3 ? 0 : 128));
            outputs[i].index = i; outputs[i].buf = storage[i].data();
            outputs[i].size = static_cast<std::uint32_t>(storage[i].size());
        }
        storage[3][0] = 127; // One qualifying p3 anchor; no other class/anchor qualifies.
        const auto initial_releases = release_calls;
        std::vector<raw_dfl::Detection> owned;
        {
            OutputLease lease(123, outputs, fake_release);
            raw_dfl::NativeDecoder decoder(decoder_config(0.32f));
            owned = decoder.decode(outputs, recorded.heads);
            CHECK(owned.size() == 1 && owned[0].cls == 0 && owned[0].score > 0.8f);
            CHECK(lease.finish() == 0 && lease.finish() == 0);
        }
        CHECK(release_calls == initial_releases + 1);
        const auto saved = owned[0];
        for (auto& head : storage) std::fill(head.begin(), head.end(), static_cast<std::uint8_t>(0));
        CHECK(owned[0].score == saved.score && owned[0].x1 == saved.x1 && owned[0].x2 == saved.x2);
    });
    test("native buffer validation exception releases all outputs, no successful completion", [&] {
        std::uint8_t placeholder = 0;
        std::vector<rknn_output> outputs(6);
        for (unsigned i = 0; i != 6; ++i) {
            outputs[i].index = i; outputs[i].buf = &placeholder; outputs[i].size = recorded.heads[i].n_elems;
        }
        for (unsigned mode = 0; mode != 4; ++mode) {
            auto broken = outputs;
            if (mode == 0) --broken[0].size;
            if (mode == 1) broken[0].want_float = 1;
            if (mode == 2) broken[0].index = 5;
            if (mode == 3) broken[0].size = recorded.heads[0].n_elems * 4;
            const auto initial_releases = release_calls;
            bool completed = false, rejected = false;
            try {
                OutputLease lease(123, broken, fake_release);
                raw_dfl::NativeDecoder decoder(decoder_config(0.32f));
                decoder.decode(broken, recorded.heads);
                completed = true;
            } catch (const std::invalid_argument&) { rejected = true; }
            CHECK(rejected && !completed && release_calls == initial_releases + 1);
        }
    });
    test("release failure remains failure and destructor does not make a second release attempt", [] {
        std::uint8_t placeholder = 0;
        std::vector<rknn_output> outputs(6);
        for (auto& o : outputs) o.buf = &placeholder;
        const auto initial_releases = release_calls;
        release_status = -7;
        {
            OutputLease lease(123, outputs, fake_release);
            CHECK(lease.finish() == -7 && lease.finish() == -7);
        }
        CHECK(release_calls == initial_releases + 1);
        release_status = 0;
    });
    test("throwing release is contained and attempted exactly once", [] {
        std::vector<rknn_output> outputs(6);
        const auto initial_releases = release_calls;
        auto throwing = +[](rknn_context, std::uint32_t, rknn_output*) -> int {
            ++release_calls;
            throw std::runtime_error("injected release failure");
        };
        {
            OutputLease lease(123, outputs, throwing);
            CHECK(lease.finish() == -1 && lease.finish() == -1);
        }
        CHECK(release_calls == initial_releases + 1);
    });
}
} // namespace
int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::invalid_argument("usage: native_guard_selftest recorded_profile.txt");
        tests(load(argv[1]));
        std::cout << "NATIVE_GUARD_PASS cases=" << cases << " checks=" << checks
                  << " releases=" << release_calls << " released_buffers=" << released_buffers << '\n';
        return 0;
    } catch (const std::exception& e) { std::cerr << "NATIVE_GUARD_FAIL " << e.what() << '\n'; return 1; }
}
