// Standalone completed-inference experiment. No production/viewer modifications.
#include "raw_dfl_native.h"
#include "legacy_production_adapter.h"
#include <QByteArray>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QString>
#include <opencv2/opencv.hpp>
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <numeric>
#include <utility>
#if defined(__linux__)
#include <dlfcn.h>
#include <time.h>
#endif

namespace {
constexpr const char* pinned_sha = "be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9";
constexpr const char* pinned_name = "det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn";
constexpr const char* pinned_runtime_sha = "73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885";
constexpr const char* pinned_runtime_api = "2.3.0 (c949ad889d@2024-11-07T11:35:33)";
constexpr int frame_count = 30, warm_count = 30, round_count = 4;
constexpr float box_epsilon = 1e-3f, score_epsilon = 1e-6f;
using Clock = std::chrono::steady_clock;
using Detections = std::vector<raw_dfl::Detection>;
volatile double result_sink = 0;
bool cpu_available = false;
unsigned cleanup_errors = 0, context_serial = 0;

void require(bool ok, const std::string& text) {
    if (!ok) throw std::runtime_error(text);
}
void check(int code, const char* operation) {
    if (code != RKNN_SUCC) throw std::runtime_error(std::string(operation) + " ret=" + std::to_string(code));
}
QString qs(const std::string& text) { return QString::fromStdString(text); }
QJsonValue number(double value) { return std::isfinite(value) ? QJsonValue(value) : QJsonValue(QJsonValue::Null); }
std::ofstream output_file(const std::string& path) {
    std::ofstream file(path, std::ios::binary);
    require(bool(file), "cannot write " + path);
    file.exceptions(std::ios::badbit | std::ios::failbit);
    file << std::fixed << std::setprecision(9);
    return file;
}
void csv_number(std::ostream& file, double value) {
    if (std::isfinite(value)) file << value; // An empty CPU field means unavailable.
}
std::string sha256(const void* bytes, std::size_t size) {
    require(size <= std::size_t(std::numeric_limits<int>::max()), "hash input too large");
    return QCryptographicHash::hash(QByteArray::fromRawData(static_cast<const char*>(bytes), int(size)),
                                    QCryptographicHash::Sha256).toHex().toStdString();
}

bool probe_cpu_clock() {
#if defined(__linux__) && defined(CLOCK_THREAD_CPUTIME_ID)
    timespec t{};
    return clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t) == 0;
#else
    return false;
#endif
}
double cpu_ms() {
#if defined(__linux__) && defined(CLOCK_THREAD_CPUTIME_ID)
    if (cpu_available) {
        timespec t{};
        require(clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t) == 0, "thread CPU clock failed");
        return double(t.tv_sec) * 1000.0 + double(t.tv_nsec) / 1e6;
    }
#endif
    return std::numeric_limits<double>::quiet_NaN();
}
struct Stamp {
    Clock::time_point wall;
    double cpu;
    static Stamp now() { return {Clock::now(), cpu_ms()}; }
};
struct Timing { double wall = 0, cpu = std::numeric_limits<double>::quiet_NaN(); };
Timing elapsed(const Stamp& begin, const Stamp& end) {
    return {std::chrono::duration<double, std::milli>(end.wall - begin.wall).count(), end.cpu - begin.cpu};
}
enum Stage { Preprocess, InputSet, Run, Get, Decode, Release, Completed, StageCount };
constexpr std::array<const char*, StageCount> stage_names{
    "preprocess", "inputs_set", "blocking_run", "outputs_get_validate", "decode_copy_owned", "outputs_release", "completed"};
enum class Profile { Baseline, Native };
const char* profile_name(Profile p) { return p == Profile::Baseline ? "baseline_runtime_float_production" : "native_quantized"; }
const char* decoder_contract(const raw_dfl::Config& config) {
    return config.production_compatibility ? "production_compatibility" : "canonical_always_sigmoid";
}
const char* dequant_contract(const raw_dfl::Config& config) {
    return config.pinned_rknn230_dequantization ? "pinned_wb_v8_rknn230_runtime_float" : "queried_affine_float32";
}

// Match the existing benchmark's RGB640 bilinear letterbox, including rounding.
cv::Mat prepare(const cv::Mat& bgr) {
    const double scale = std::min(640.0 / bgr.cols, 640.0 / bgr.rows);
    const int width = std::lround(bgr.cols * scale), height = std::lround(bgr.rows * scale);
    cv::Mat resized, rgb, padded(640, 640, CV_8UC3, cv::Scalar(114, 114, 114));
    cv::resize(bgr, resized, cv::Size(width, height), 0, 0, cv::INTER_LINEAR);
    cv::cvtColor(resized, rgb, cv::COLOR_BGR2RGB);
    rgb.copyTo(padded(cv::Rect((640 - width) / 2, (640 - height) / 2, width, height)));
    return padded;
}
struct Input { cv::Mat bgr; std::string id, input_sha; };
std::vector<Input> load_inputs(const std::string& list_path) {
    std::ifstream list(list_path);
    require(bool(list), "cannot open frame list " + list_path);
    std::vector<Input> inputs;
    inputs.reserve(frame_count);
    std::string line;
    while (int(inputs.size()) < frame_count && std::getline(list, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        auto path = std::filesystem::path(line);
        if (path.is_relative()) path = std::filesystem::path(list_path).parent_path() / path;
        const auto id = std::filesystem::absolute(path).lexically_normal().string();
        auto bgr = cv::imread(id, cv::IMREAD_COLOR);
        require(!bgr.empty() && bgr.cols > 0 && bgr.rows > 0 && bgr.type() == CV_8UC3, "cannot load BGR road image " + id);
        auto rgb = prepare(bgr);
        require(rgb.isContinuous(), "letterbox must be contiguous");
        inputs.push_back({std::move(bgr), id, sha256(rgb.data, 640 * 640 * 3)});
    }
    require(int(inputs.size()) == frame_count, "requires 30 stored road images");
    return inputs;
}
struct Model {
    std::string path, actual_sha;
    std::vector<char> bytes;
    Model(const std::string& file_path, const std::string& supplied_sha) : path(file_path) {
        require(supplied_sha == pinned_sha, "MODEL_SHA must equal the pinned wb_v8 model SHA256");
        require(std::filesystem::path(path).filename().string() == pinned_name, "requires pinned raw-dfl6 model filename");
        std::ifstream file(path, std::ios::binary);
        require(bool(file), "cannot open RKNN model " + path);
        bytes.assign(std::istreambuf_iterator<char>(file), {});
        require(!bytes.empty() && bytes.size() <= std::size_t(std::numeric_limits<int>::max()), "invalid model byte length");
        require(!file.bad(), "model read error");
        actual_sha = sha256(bytes.data(), bytes.size());
        require(actual_sha == pinned_sha, "loaded model bytes fail SHA256 pin");
    }
};

QJsonObject attr_json(const rknn_tensor_attr& a) {
    QJsonArray dims;
    for (unsigned i = 0; i < a.n_dims; ++i) dims.append(int(a.dims[i]));
    return {{"index", int(a.index)}, {"name", QString::fromUtf8(a.name)}, {"dims", dims},
            {"fmt", int(a.fmt)}, {"type", int(a.type)}, {"qnt_type", int(a.qnt_type)},
            {"n_elems", double(a.n_elems)}, {"attr_bytes", double(a.size)}, {"zp", a.zp},
            {"scale", double(a.scale)}, {"w_stride", double(a.w_stride)}, {"size_with_stride", double(a.size_with_stride)}};
}
class Session {
public:
    rknn_context ctx = 0;
    rknn_tensor_attr input{};
    std::vector<rknn_tensor_attr> attrs;
    std::vector<rknn_output> outs;
    rknn_sdk_version version{};
    std::array<std::uint32_t, 6> observed_bytes{};
    bool acquired = false;
    unsigned serial = ++context_serial;

    explicit Session(Model& model) {
        try {
            // No asynchronous or performance-collection flag. outputs_get is for this input.
            check(rknn_init(&ctx, model.bytes.data(), std::uint32_t(model.bytes.size()), 0, nullptr), "rknn_init flags=0");
            rknn_input_output_num io{};
            check(rknn_query(ctx, RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io)), "query IO");
            require(io.n_input == 1 && io.n_output == 6, "requires queried 1 input / 6 outputs");
            check(rknn_query(ctx, RKNN_QUERY_INPUT_ATTR, &input, sizeof(input)), "query input attr");
            require(std::memchr(input.name, '\0', sizeof(input.name)) != nullptr, "unterminated input name");
            require(input.index == 0 && input.n_dims == 4 && input.dims[0] == 1 && input.n_elems == 640 * 640 * 3 &&
                    ((input.fmt == RKNN_TENSOR_NHWC && input.dims[1] == 640 && input.dims[2] == 640 && input.dims[3] == 3) ||
                     (input.fmt == RKNN_TENSOR_NCHW && input.dims[1] == 3 && input.dims[2] == 640 && input.dims[3] == 640)),
                    "requires queried RGB640 input shape");
            attrs.resize(6); outs.resize(6);
            for (unsigned i = 0; i < 6; ++i) {
                attrs[i].index = i;
                check(rknn_query(ctx, RKNN_QUERY_OUTPUT_ATTR, &attrs[i], sizeof(attrs[i])), "query logical output attr");
                require(attrs[i].index == i, "runtime changed queried output index");
            }
            // Attribute-only validation: validate() does not read the placeholder byte.
            // It checks all logical NCHW names/shapes/quantization before either decoder.
            std::uint8_t placeholder = 0;
            auto shape_outputs = outs;
            for (unsigned i = 0; i < 6; ++i) {
                shape_outputs[i].index = i;
                shape_outputs[i].buf = &placeholder;
                shape_outputs[i].size = attrs[i].n_elems;
            }
            raw_dfl::detail::validate(shape_outputs, attrs);
            check(rknn_query(ctx, RKNN_QUERY_SDK_VERSION, &version, sizeof(version)), "query SDK/driver version");
            require(std::memchr(version.api_version, '\0', sizeof(version.api_version)) &&
                    std::memchr(version.drv_version, '\0', sizeof(version.drv_version)), "unterminated runtime version");
        } catch (...) { cleanup(); throw; }
    }
    Session(const Session&) = delete;
    Session& operator=(const Session&) = delete;
    ~Session() noexcept { cleanup(); }

    void set(const cv::Mat& rgb) {
        require(!acquired, "previous outputs were not retired");
        require(rgb.isContinuous() && rgb.type() == CV_8UC3 && rgb.rows == 640 && rgb.cols == 640, "invalid prepared RGB input");
        rknn_input in{};
        in.buf = rgb.data; in.size = 640 * 640 * 3;
        in.type = RKNN_TENSOR_UINT8; in.fmt = RKNN_TENSOR_NHWC; in.pass_through = 0;
        check(rknn_inputs_set(ctx, 1, &in), "rknn_inputs_set");
    }
    void run() { check(rknn_run(ctx, nullptr), "blocking rknn_run"); }
    void get(Profile p) {
        require(!acquired, "outputs already acquired");
        for (unsigned i = 0; i < 6; ++i) {
            outs[i] = {}; outs[i].index = i;
            outs[i].want_float = p == Profile::Baseline ? 1 : 0;
        }
        check(rknn_outputs_get(ctx, 6, outs.data(), nullptr), "rknn_outputs_get");
        acquired = true; // Validation failures still release through RAII.
        for (unsigned i = 0; i < 6; ++i) {
            const std::uint32_t expected = attrs[i].n_elems * (p == Profile::Baseline ? std::uint32_t(sizeof(float)) : 1u);
            require(outs[i].index == attrs[i].index && outs[i].buf && outs[i].size == expected &&
                    outs[i].want_float == (p == Profile::Baseline ? 1 : 0) && !outs[i].is_prealloc,
                    "requires exact packed runtime output buffers in attribute order");
            if (p == Profile::Baseline)
                require(reinterpret_cast<std::uintptr_t>(outs[i].buf) % alignof(float) == 0, "unaligned runtime float output");
            observed_bytes[i] = outs[i].size;
        }
    }
    void release() {
        require(acquired, "release without successful get");
        const int code = rknn_outputs_release(ctx, 6, outs.data());
        acquired = false;
        for (auto& o : outs) o.buf = nullptr;
        // On failure ownership is uncertain: do not risk a second release. Context
        // destruction is still attempted by RAII and this completion is rejected.
        check(code, "rknn_outputs_release");
    }
    void close() {
        require(!acquired, "closing context with acquired outputs");
        const auto old = ctx; ctx = 0;
        if (old) check(rknn_destroy(old), "rknn_destroy");
    }
    QJsonObject metadata(Profile p) const {
        QJsonArray heads;
        for (unsigned i = 0; i < 6; ++i) {
            auto a = attr_json(attrs[i]);
            a.insert("observed_outputs_get_bytes", double(observed_bytes[i]));
            a.insert("want_float", p == Profile::Baseline ? 1 : 0);
            heads.append(a);
        }
        return {{"context_serial", int(serial)}, {"init_flags", 0}, {"input", attr_json(input)}, {"logical_heads", heads},
                {"runtime_api_version", QString::fromUtf8(version.api_version)}, {"driver_version", QString::fromUtf8(version.drv_version)}};
    }
private:
    void cleanup() noexcept {
        if (acquired) {
            const int code = rknn_outputs_release(ctx, 6, outs.data());
            if (code != RKNN_SUCC) { ++cleanup_errors; std::fprintf(stderr, "cleanup outputs_release ret=%d\n", code); }
            acquired = false;
        }
        if (ctx) {
            const int code = rknn_destroy(ctx);
            if (code != RKNN_SUCC) { ++cleanup_errors; std::fprintf(stderr, "cleanup rknn_destroy ret=%d\n", code); }
            ctx = 0;
        }
    }
};
void same_session_contract(const Session& a, const Session& b) {
    require(attr_json(a.input) == attr_json(b.input), "input metadata changed between contexts");
    for (unsigned i = 0; i < 6; ++i)
        require(attr_json(a.attrs[i]) == attr_json(b.attrs[i]), "logical output metadata changed between contexts");
    require(std::strcmp(a.version.api_version, b.version.api_version) == 0 &&
            std::strcmp(a.version.drv_version, b.version.drv_version) == 0, "runtime versions changed between contexts");
}

// Both paths copy the same owned tuple type while the RKNN lease is live.
template<class Container> Detections own(const Container& decoded) {
    Detections result;
    result.reserve(std::size_t(decoded.size()));
    for (const auto& d : decoded) result.push_back({d.x1, d.y1, d.x2, d.y2, d.score, d.cls, -1});
    return result;
}
struct Completion {
    Detections detections;
    std::array<Timing, StageCount> times{};
};
void complete(Session& session, Profile p, raw_dfl::NativeDecoder& native,
              raw_dfl_legacy::ProductionDecoder& production, const Input& input, Completion& result) {
    std::array<Stamp, 7> ticks;
    ticks[0] = Stamp::now();
    auto rgb = prepare(input.bgr);
    ticks[1] = Stamp::now();
    session.set(rgb);
    ticks[2] = Stamp::now();
    session.run();
    ticks[3] = Stamp::now();
    session.get(p);
    ticks[4] = Stamp::now();
    if (p == Profile::Baseline) {
        // attrs retain INT8/UINT8 logical metadata; runtime buffers are actual
        // floats with n_elems*sizeof(float) bytes. Production reads logical NCHW.
        auto decoded = production.decode(session.outs, session.attrs);
        result.detections = own(decoded);
    } else {
        auto decoded = native.decode(session.outs, session.attrs);
        result.detections = own(decoded);
    }
    ticks[5] = Stamp::now();
    session.release();
    rgb = cv::Mat();
    ticks[6] = Stamp::now();
    for (int s = 0; s < Completed; ++s) result.times[s] = elapsed(ticks[s], ticks[s + 1]);
    result.times[Completed] = elapsed(ticks[0], ticks[6]);
}
void consume(const std::vector<Completion>& completions) {
    double value = 0;
    for (const auto& c : completions) {
        value += double(c.detections.size());
        for (const auto& d : c.detections) value += d.cls + d.score + d.x1 + d.y1 + d.x2 + d.y2;
    }
    result_sink = result_sink + value; // Once per block, outside its timing window.
}

bool finite(const raw_dfl::Detection& d) {
    return d.cls >= 0 && d.cls < 3 && std::isfinite(d.score) && std::isfinite(d.x1) &&
           std::isfinite(d.y1) && std::isfinite(d.x2) && std::isfinite(d.y2);
}
float box_error(const raw_dfl::Detection& a, const raw_dfl::Detection& b) {
    return std::max({std::abs(a.x1-b.x1), std::abs(a.y1-b.y1), std::abs(a.x2-b.x2), std::abs(a.y2-b.y2)});
}
// Maximum bipartite matching avoids greedy false failures for overlapping boxes
// or repeated equal detections. No rank/anchor assumption for legacy score ties.
std::vector<int> matching(const Detections& lhs, const Detections& rhs, bool include_score) {
    std::vector<std::vector<int>> edges(lhs.size());
    for (std::size_t i = 0; i < lhs.size(); ++i) {
        if (!finite(lhs[i])) continue;
        for (std::size_t j = 0; j < rhs.size(); ++j)
            if (finite(rhs[j]) && lhs[i].cls == rhs[j].cls && box_error(lhs[i], rhs[j]) <= box_epsilon &&
                (!include_score || std::abs(lhs[i].score-rhs[j].score) <= score_epsilon)) edges[i].push_back(int(j));
    }
    std::vector<int> right(rhs.size(), -1), left(lhs.size(), -1);
    std::vector<bool> visited(rhs.size());
    std::function<bool(int)> augment = [&](int i) {
        for (int j : edges[i]) {
            if (visited[j]) continue;
            visited[j] = true;
            if (right[j] < 0 || augment(right[j])) { right[j] = i; return true; }
        }
        return false;
    };
    for (std::size_t i = 0; i < lhs.size(); ++i) {
        std::fill(visited.begin(), visited.end(), false);
        augment(int(i));
    }
    for (std::size_t j = 0; j < right.size(); ++j) if (right[j] >= 0) left[right[j]] = int(j);
    return left;
}
struct Comparison {
    std::size_t lhs_count = 0, rhs_count = 0, matched = 0, box_matched = 0;
    std::size_t lhs_unmatched = 0, rhs_unmatched = 0, score_mismatches = 0, invalid_lhs = 0, invalid_rhs = 0;
    float max_score_error = 0, max_box_error = 0;
    bool pass() const { return lhs_count == rhs_count && matched == lhs_count && !invalid_lhs && !invalid_rhs; }
    QJsonObject json() const {
        return {{"pass", pass()}, {"lhs_count", double(lhs_count)}, {"rhs_count", double(rhs_count)},
                {"matched", double(matched)}, {"box_matched", double(box_matched)},
                {"lhs_unmatched", double(lhs_unmatched)}, {"rhs_unmatched", double(rhs_unmatched)},
                {"score_mismatches", double(score_mismatches)}, {"invalid_lhs", double(invalid_lhs)}, {"invalid_rhs", double(invalid_rhs)},
                {"max_score_error", double(max_score_error)}, {"max_box_error_px", double(max_box_error)}};
    }
};
Comparison compare(const Detections& lhs, const Detections& rhs) {
    Comparison p;
    p.lhs_count = lhs.size(); p.rhs_count = rhs.size();
    for (const auto& d : lhs) if (!finite(d)) ++p.invalid_lhs;
    for (const auto& d : rhs) if (!finite(d)) ++p.invalid_rhs;
    const auto strict = matching(lhs, rhs, true), boxes = matching(lhs, rhs, false);
    for (int j : strict) if (j >= 0) ++p.matched;
    for (int j : boxes) if (j >= 0) ++p.box_matched;
    p.lhs_unmatched = lhs.size() - p.matched; p.rhs_unmatched = rhs.size() - p.matched;
    p.score_mismatches = p.box_matched - p.matched;
    const auto& diagnostics = p.pass() ? strict : boxes;
    for (std::size_t i = 0; i < diagnostics.size(); ++i) if (diagnostics[i] >= 0) {
        const auto& b = rhs[diagnostics[i]];
        p.max_score_error = std::max(p.max_score_error, std::abs(lhs[i].score-b.score));
        p.max_box_error = std::max(p.max_box_error, box_error(lhs[i], b));
    }
    return p;
}
struct Checks {
    std::size_t checks = 0, failures = 0, lhs_unmatched = 0, rhs_unmatched = 0, score_mismatches = 0;
    void add(const Comparison& p) {
        ++checks; if (!p.pass()) ++failures;
        lhs_unmatched += p.lhs_unmatched; rhs_unmatched += p.rhs_unmatched; score_mismatches += p.score_mismatches;
    }
    QJsonObject json() const {
        return {{"checks", double(checks)}, {"failures", double(failures)}, {"pass", failures == 0},
                {"lhs_unmatched", double(lhs_unmatched)}, {"rhs_unmatched", double(rhs_unmatched)}, {"score_mismatches", double(score_mismatches)}};
    }
};
void parity_row(std::ofstream& file, const char* scope, int round, int cycle, int frame,
                const Input& input, const char* comparison, const Comparison& p) {
    file << pinned_sha << ',' << scope << ',' << round << ',' << cycle << ',' << frame << ',' << input.input_sha << ',' << comparison
         << ',' << p.pass() << ',' << p.lhs_count << ',' << p.rhs_count << ',' << p.matched << ',' << p.box_matched
         << ',' << p.lhs_unmatched << ',' << p.rhs_unmatched << ',' << p.score_mismatches << ',' << p.invalid_lhs << ',' << p.invalid_rhs
         << ',' << p.max_score_error << ',' << p.max_box_error << '\n';
}
void detection_rows(std::ofstream& file, const char* scope, int round, int block, int cycle, int frame,
                    const Input& input, const char* profile, const Detections& detections) {
    for (std::size_t i = 0; i < detections.size(); ++i) {
        const auto& d = detections[i];
        file << pinned_sha << ',' << scope << ',' << round << ',' << block << ',' << cycle << ',' << frame << ',' << input.input_sha
             << ',' << profile << ',' << i << ',' << d.anchor << ',' << d.cls << ',' << d.score
             << ',' << d.x1 << ',' << d.y1 << ',' << d.x2 << ',' << d.y2 << '\n';
    }
}

// Only certification copies full float heads; the timed pipelines never do.
raw_dfl::FloatHeads copy_runtime_floats(const Session& session) {
    raw_dfl::FloatHeads heads;
    for (unsigned i = 0; i < 6; ++i) {
        int slot = -1;
        for (int s = 0; s < 6; ++s) if (std::strcmp(session.attrs[i].name, raw_dfl::names[s]) == 0) slot = s;
        require(slot >= 0, "runtime float head map failed");
        const auto* data = static_cast<const float*>(session.outs[i].buf);
        heads.values[slot].assign(data, data + session.attrs[i].n_elems);
    }
    return heads;
}
QJsonObject float_difference(const raw_dfl::FloatHeads& runtime, const raw_dfl::FloatHeads& dequant) {
    std::size_t count = 0, unequal = 0, nonfinite = 0;
    double maximum = 0, squares = 0;
    QJsonArray heads;
    for (int s = 0; s < 6; ++s) {
        require(runtime.values[s].size() == dequant.values[s].size(), "float diagnostic shape mismatch");
        double head_max = 0;
        std::size_t head_unequal = 0;
        for (std::size_t i = 0; i < runtime.values[s].size(); ++i) {
            ++count;
            const float a = runtime.values[s][i], b = dequant.values[s][i];
            if (!std::isfinite(a) || !std::isfinite(b)) { ++nonfinite; continue; }
            const double error = std::abs(double(a) - b);
            maximum = std::max(maximum, error); head_max = std::max(head_max, error); squares += error * error;
            if (a != b) { ++unequal; ++head_unequal; }
        }
        heads.append(QJsonObject{{"name", raw_dfl::names[s]}, {"max_abs_error", head_max}, {"unequal_elements", double(head_unequal)}});
    }
    return {{"elements", double(count)}, {"unequal_elements", double(unequal)}, {"nonfinite_elements", double(nonfinite)},
            {"max_abs_error", maximum}, {"rmse", std::sqrt(squares / double(count))}, {"heads", heads}};
}
struct Certification {
    Checks exact, compatibility, scalar_vs_production, runtime_vs_dequant_production, native_vs_dequant_production;
    QJsonObject metadata;
};
Certification certify(Model& model, const std::vector<Input>& inputs, std::ofstream& parity, std::ofstream& detections,
                      const raw_dfl::Config& config) {
    Session baseline(model), candidate(model);
    same_session_contract(baseline, candidate);
    if (config.pinned_rknn230_dequantization)
        require(std::strcmp(candidate.version.api_version, pinned_runtime_api) == 0,
                "pinned runtime dequantization requires the measured RKNN API build");
    raw_dfl::NativeDecoder native(config);
    raw_dfl_legacy::ProductionDecoder production;
    Certification cert;
    QJsonArray frames;
    for (int frame = 0; frame < frame_count; ++frame) {
        const auto& input = inputs[frame];
        auto rgb = prepare(input.bgr);
        require(sha256(rgb.data, 640 * 640 * 3) == input.input_sha, "baseline certification input changed");
        baseline.set(rgb); baseline.run(); baseline.get(Profile::Baseline);
        const auto old = own(production.decode(baseline.outs, baseline.attrs));
        auto runtime_heads = copy_runtime_floats(baseline);
        baseline.release();

        rgb = prepare(input.bgr);
        require(sha256(rgb.data, 640 * 640 * 3) == input.input_sha, "native certification input changed");
        candidate.set(rgb); candidate.run(); candidate.get(Profile::Native);
        const auto actual = own(native.decode(candidate.outs, candidate.attrs));
        auto float_heads = raw_dfl::full_dequantize(candidate.outs, candidate.attrs, config);
        candidate.release();
        // Everything below owns its data; there are no borrowed buffers after release.
        const auto scalar = own(raw_dfl::scalar_float_decode(float_heads, config));
        const auto converted_old = own(raw_dfl_legacy::decode(production, float_heads, candidate.attrs));
        const auto exact = compare(actual, scalar), compatibility = compare(actual, old);
        const auto scalar_old = compare(scalar, old), runtime_old = compare(old, converted_old), native_old = compare(actual, converted_old);
        cert.exact.add(exact); cert.compatibility.add(compatibility); cert.scalar_vs_production.add(scalar_old);
        cert.runtime_vs_dequant_production.add(runtime_old); cert.native_vs_dequant_production.add(native_old);
        parity_row(parity, "certification", -1, -1, frame, input, "native_vs_exact_scalar", exact);
        parity_row(parity, "certification", -1, -1, frame, input, "native_vs_runtime_production", compatibility);
        parity_row(parity, "certification", -1, -1, frame, input, "exact_scalar_vs_runtime_production", scalar_old);
        parity_row(parity, "certification", -1, -1, frame, input, "runtime_vs_dequant_production", runtime_old);
        parity_row(parity, "certification", -1, -1, frame, input, "native_vs_dequant_production", native_old);
        detection_rows(detections, "certification", -1, -1, -1, frame, input, profile_name(Profile::Baseline), old);
        detection_rows(detections, "certification", -1, -1, -1, frame, input, profile_name(Profile::Native), actual);
        detection_rows(detections, "certification", -1, -1, -1, frame, input,
                       config.production_compatibility ? "production_compatibility_scalar" : "exact_sigmoid_scalar", scalar);
        detection_rows(detections, "certification", -1, -1, -1, frame, input, "production_from_native_dequant", converted_old);
        frames.append(QJsonObject{{"frame", frame}, {"input_sha256", qs(input.input_sha)}, {"exact", exact.json()},
                      {"compatibility", compatibility.json()}, {"exact_scalar_vs_production", scalar_old.json()},
                      {"runtime_vs_dequant_production", runtime_old.json()}, {"native_vs_dequant_production", native_old.json()},
                      {"legacy_sigmoid_runtime", raw_dfl_legacy::uses_sigmoid(runtime_heads, baseline.attrs)},
                      {"legacy_sigmoid_dequant", raw_dfl_legacy::uses_sigmoid(float_heads, candidate.attrs)},
                      {"runtime_float_vs_native_dequant", float_difference(runtime_heads, float_heads)}});
    }
    cert.metadata = {{"timed", false}, {"production_compatibility", config.production_compatibility},
                     {"scalar_contract", decoder_contract(config)}, {"fresh_completions_per_profile", frame_count}, {"baseline_session", baseline.metadata(Profile::Baseline)},
                     {"native_session", candidate.metadata(Profile::Native)}, {"frames", frames}, {"exact", cert.exact.json()},
                     {"compatibility", cert.compatibility.json()}, {"exact_scalar_vs_production", cert.scalar_vs_production.json()},
                     {"runtime_vs_dequant_production", cert.runtime_vs_dequant_production.json()},
                     {"native_vs_dequant_production", cert.native_vs_dequant_production.json()}};
    baseline.close(); candidate.close();
    return cert;
}

struct Distribution {
    std::size_t n = 0;
    double minimum = 0, mean = 0, p50 = 0, p95 = 0, maximum = 0;
    QJsonObject json() const {
        if (!n) return {{"n", 0}, {"available", false}};
        return {{"n", double(n)}, {"available", true}, {"min_ms", minimum}, {"mean_ms", mean},
                {"p50_ms", p50}, {"p95_ms", p95}, {"max_ms", maximum}};
    }
};
Distribution distribution(std::vector<double> values) {
    if (values.empty()) return {};
    std::sort(values.begin(), values.end());
    const auto percentile = [&](double p) { return values[std::size_t(std::ceil(p * values.size())) - 1]; };
    return {values.size(), values.front(), std::accumulate(values.begin(), values.end(), 0.0) / values.size(),
            percentile(0.5), percentile(0.95), values.back()};
}
struct Block {
    int id = 0, round = 0, position = 0, cycles = 0;
    raw_dfl::Config config;
    Profile profile = Profile::Baseline;
    Timing total;
    std::vector<Completion> completions;
    std::size_t class_tables = 0, exp_tables = 0;
    QJsonObject session_metadata;
    double fps() const { return completions.size() * 1000.0 / total.wall; }
};
Block measure_block(Model& model, const std::vector<Input>& inputs, int round, int position, Profile p, int cycles,
                    const QJsonObject& expected_session, const raw_dfl::Config& config) {
    Session session(model);
    // Re-check contract and versions on each fresh context, outside timing.
    const auto initial = session.metadata(p);
    require(initial.value("input") == expected_session.value("input"), "input metadata changed since certification");
    require(initial.value("runtime_api_version") == expected_session.value("runtime_api_version") &&
            initial.value("driver_version") == expected_session.value("driver_version"), "runtime version changed since certification");
    const auto expected_heads = expected_session.value("logical_heads").toArray();
    for (int i = 0; i < 6; ++i) {
        auto expected = expected_heads[i].toObject();
        expected.remove("observed_outputs_get_bytes"); expected.remove("want_float");
        require(attr_json(session.attrs[i]) == expected, "head metadata changed since certification");
    }
    raw_dfl::NativeDecoder native(config);
    raw_dfl_legacy::ProductionDecoder production;
    std::vector<Completion> warm(warm_count);
    for (int i = 0; i < warm_count; ++i) complete(session, p, native, production, inputs[i], warm[i]);
    consume(warm);
    Block block;
    block.config = config;
    block.id = round * 2 + position; block.round = round; block.position = position; block.cycles = cycles; block.profile = p;
    block.completions.resize(std::size_t(frame_count) * cycles); // No sample-vector growth in the timed loop.
    const double cpu_begin = cpu_ms();
    const auto wall_begin = Clock::now();
    for (std::size_t i = 0; i < block.completions.size(); ++i)
        complete(session, p, native, production, inputs[i % frame_count], block.completions[i]);
    const auto wall_end = Clock::now(); // All results owned, outputs retired, samples stored.
    const double cpu_end = cpu_ms();
    block.total = {std::chrono::duration<double, std::milli>(wall_end - wall_begin).count(), cpu_end - cpu_begin};
    require(block.total.wall > 0, "nonpositive block duration");
    block.class_tables = native.class_table_count(); block.exp_tables = native.exp_table_count();
    block.session_metadata = session.metadata(p);
    consume(block.completions);
    session.close(); // Context destruction outside timing, checked rather than silently ignored.
    return block;
}
QJsonObject write_block(const Block& block, const std::vector<Input>& inputs, std::ofstream& samples,
                       std::ofstream& summary, std::ofstream& detections) {
    for (std::size_t i = 0; i < block.completions.size(); ++i) {
        const int frame = int(i % frame_count), cycle = int(i / frame_count);
        const auto& c = block.completions[i]; const auto& input = inputs[frame];
        samples << pinned_sha << ',' << block.id << ',' << block.round << ',' << block.position << ',' << profile_name(block.profile)
                << ',' << i << ',' << cycle << ',' << frame << ',' << input.input_sha << ',' << c.detections.size();
        for (const auto& t : c.times) { samples << ','; csv_number(samples, t.wall); samples << ','; csv_number(samples, t.cpu); }
        samples << '\n';
        detection_rows(detections, "timed", block.round, block.id, cycle, frame, input, profile_name(block.profile), c.detections);
    }
    QJsonObject stages;
    for (int s = 0; s < StageCount; ++s) {
        std::vector<double> wall, cpu;
        wall.reserve(block.completions.size()); cpu.reserve(block.completions.size());
        for (const auto& c : block.completions) {
            wall.push_back(c.times[s].wall);
            if (std::isfinite(c.times[s].cpu)) cpu.push_back(c.times[s].cpu);
        }
        const auto w = distribution(std::move(wall)), c = distribution(std::move(cpu));
        stages.insert(stage_names[s], QJsonObject{{"wall", w.json()}, {"thread_cpu", c.json()}});
        summary << pinned_sha << ',' << block.id << ',' << block.round << ',' << block.position << ',' << profile_name(block.profile)
                << ',' << stage_names[s] << ',' << w.n << ',' << w.minimum << ',' << w.mean << ',' << w.p50 << ',' << w.p95 << ',' << w.maximum << ',';
        if (c.n) summary << c.minimum << ',' << c.mean << ',' << c.p50 << ',' << c.p95 << ',' << c.maximum;
        else summary << ",,,,";
        summary << ',' << block.total.wall << ','; csv_number(summary, block.total.cpu);
        summary << ',' << block.fps() << ',' << block.class_tables << ',' << block.exp_tables << '\n';
    }
    return {{"block", block.id}, {"round", block.round}, {"position", block.position}, {"profile", profile_name(block.profile)},
            {"production_compatibility", block.config.production_compatibility}, {"candidate_contract", decoder_contract(block.config)},
            {"warm_completions", warm_count}, {"timed_completions", double(block.completions.size())}, {"cycles", block.cycles},
            {"block_wall_ms", block.total.wall}, {"block_thread_cpu_ms", number(block.total.cpu)}, {"completed_fps", block.fps()},
            {"class_luts", double(block.class_tables)}, {"exp_luts", double(block.exp_tables)}, {"session", block.session_metadata}, {"stages", stages}};
}
struct Totals {
    std::size_t completions = 0, blocks = 0;
    double wall = 0, cpu = 0;
    void add(const Block& block) {
        completions += block.completions.size(); ++blocks;
        wall += block.total.wall; cpu += block.total.cpu;
    }
    double fps() const { return completions * 1000.0 / wall; }
    QJsonObject json() const {
        return {{"blocks", double(blocks)}, {"timed_completions", double(completions)}, {"warm_completions", double(blocks * warm_count)},
                {"timed_wall_ms", wall}, {"thread_cpu_ms", number(cpu)}, {"completed_fps", fps()}};
    }
};
QJsonObject runtime_library() {
    QJsonObject info{{"api_symbol", "rknn_init"}};
#if defined(__linux__)
    Dl_info loaded{};
    if (dladdr(reinterpret_cast<void*>(&rknn_init), &loaded) && loaded.dli_fname) {
        info.insert("path", QString::fromUtf8(loaded.dli_fname));
        std::ifstream file(loaded.dli_fname, std::ios::binary);
        if (file) {
            std::vector<char> bytes((std::istreambuf_iterator<char>(file)), {});
            if (!file.bad() && !bytes.empty() && bytes.size() <= std::size_t(std::numeric_limits<int>::max()))
                info.insert("sha256", qs(sha256(bytes.data(), bytes.size())));
        }
    } else info.insert("path", QJsonValue(QJsonValue::Null));
#else
    info.insert("path", QJsonValue(QJsonValue::Null));
    info.insert("note", "library path lookup unavailable on this platform");
#endif
    return info;
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 5 || argc > 8) {
            std::cerr << "usage: pipeline_bench MODEL FRAME_LIST PREFIX MODEL_SHA [cycles=2] [productioncompat=1:0|1] [runtimecompat=1:0|1]\n"
                         "fixed: 30 images, 30 warm completions per block, 4 paired AB/BA/AB/BA rounds\n";
            return 2;
        }
        std::size_t parsed = 0;
        const std::string cycle_text = argc >= 6 ? argv[5] : "2";
        const int cycles = std::stoi(cycle_text, &parsed);
        require(parsed == cycle_text.size() && cycles >= 1 && cycles <= std::numeric_limits<int>::max() / frame_count, "invalid cycles");
        const std::string compatibility_text = argc >= 7 ? argv[6] : "1";
        require(compatibility_text == "0" || compatibility_text == "1", "productioncompat must be exactly 0 or 1");
        raw_dfl::Config config;
        config.production_compatibility = compatibility_text == "1";
        const std::string runtime_compatibility_text = argc == 8 ? argv[7] : "1";
        require(runtime_compatibility_text == "0" || runtime_compatibility_text == "1", "runtimecompat must be exactly 0 or 1");
        config.pinned_rknn230_dequantization = runtime_compatibility_text == "1";
        const std::string model_path = argv[1], frame_list = argv[2], prefix = argv[3], supplied_sha = argv[4];
        cpu_available = probe_cpu_clock();
        cv::setNumThreads(1);
        std::cout << std::fixed << std::setprecision(9);
        Model model(model_path, supplied_sha);
        const auto library = runtime_library();
        if (config.pinned_rknn230_dequantization)
            require(library.value("sha256").toString() == pinned_runtime_sha,
                    "pinned runtime dequantization requires the measured runtime library SHA256");
        const auto inputs = load_inputs(frame_list); // All disk reads and input hashes before any measured window.
        auto samples = output_file(prefix + "_block_samples.csv");
        auto summary = output_file(prefix + "_block_summary.csv");
        auto detections = output_file(prefix + "_detections.csv");
        auto parity = output_file(prefix + "_parity.csv");
        auto totals_file = output_file(prefix + "_totals.csv");
        auto source = output_file(prefix + "_source.json");
        samples << "model_sha256,block,round,position,profile,completion,cycle,frame,input_sha256,detections";
        for (const char* stage : stage_names) samples << ',' << stage << "_wall_ms," << stage << "_cpu_ms";
        samples << '\n';
        summary << "model_sha256,block,round,position,profile,stage,n,wall_min_ms,wall_mean_ms,wall_p50_ms,wall_p95_ms,wall_max_ms,"
                   "cpu_min_ms,cpu_mean_ms,cpu_p50_ms,cpu_p95_ms,cpu_max_ms,block_wall_ms,block_cpu_ms,completed_fps,class_luts,exp_luts\n";
        detections << "model_sha256,scope,round,block,cycle,frame,input_sha256,profile,rank,anchor,class,score,x1,y1,x2,y2\n";
        parity << "model_sha256,scope,round,cycle,frame,input_sha256,comparison,pass,lhs_count,rhs_count,matched,box_matched,"
                  "lhs_unmatched,rhs_unmatched,score_mismatches,invalid_lhs,invalid_rhs,max_score_error,max_box_error_px\n";
        totals_file << "model_sha256,profile,blocks,warm_completions,timed_completions,timed_wall_ms,thread_cpu_ms,completed_fps,"
                       "native_over_baseline_fps_ratio,exact_sigmoid_pass,semantic_compatibility_pass,certification_compatibility_failures,timed_compatibility_failures,production_compatibility,exact_scalar_pass\n";
        QJsonArray frame_metadata;
        for (int i = 0; i < frame_count; ++i)
            frame_metadata.append(QJsonObject{{"frame", i}, {"path", qs(inputs[i].id)}, {"bgr_width", inputs[i].bgr.cols},
                                  {"bgr_height", inputs[i].bgr.rows}, {"preprocessed_rgb_sha256", qs(inputs[i].input_sha)}});
        QJsonObject root{{"schema", "paired_completed_inference_v1"}, {"model", QJsonObject{{"path", qs(model_path)},
                         {"filename_pin", pinned_name}, {"supplied_sha256", qs(supplied_sha)}, {"verified_sha256", qs(model.actual_sha)},
                         {"bytes", double(model.bytes.size())}}}, {"frame_list", qs(frame_list)}, {"frames", frame_metadata},
                          {"runtime_library", library}, {"qt_compile_version", QT_VERSION_STR},
                         {"thread_cpu_clock", cpu_available ? "CLOCK_THREAD_CPUTIME_ID" : "unavailable"},
                         {"settings", QJsonObject{{"rounds", round_count}, {"order", "AB/BA/AB/BA"},
                          {"A", profile_name(Profile::Baseline)}, {"B", profile_name(Profile::Native)}, {"frames", frame_count},
                           {"cycles", cycles}, {"warm_completions_per_block", warm_count}, {"fresh_context_per_block", true},
                            {"production_compatibility", config.production_compatibility}, {"candidate_contract", decoder_contract(config)},
                            {"pinned_rknn230_dequantization", config.pinned_rknn230_dequantization}, {"dequant_contract", dequant_contract(config)},
                           {"scalar_contract", decoder_contract(config)},
                           {"score_contract", config.production_compatibility ? "production first-scale class0 heuristic; raw or sigmoid affine values" : "always sigmoid affine values"},
                           {"sort_contract", config.production_compatibility ? "production scale encounter order and both score-only sorts" : "canonical anchor ties before top300/NMS"},
                          {"init_flags", 0}, {"opencv_threads", 1}, {"confidence", 0.25}, {"iou", 0.45}, {"topk", 300},
                          {"box_tolerance_px", double(box_epsilon)}, {"score_tolerance", double(score_epsilon)}}},
                         {"measurement", QJsonObject{{"preprocess", "cached original BGR -> bilinear rounded RGB640 centered letterbox fill114"},
                          {"completed_window", "preprocess + inputs_set + blocking run + outputs_get/validate + decode/copy owned tuples + release + sample bookkeeping"},
                          {"fps_denominator", "steady_clock first timed completion start through final owned result, release and stored sample"},
                          {"excluded", "disk reads, hashes, initialization, warm completions, comparisons, sink, file/console writes, context destruction"},
                          {"float_snapshot_copy_in_timed_loop", false}, {"npu_exclusive", false},
                          {"contention", "viewer unchanged; concurrent NPU users may contend"}, {"viewer_fps_claim", false},
                           {"cpu_scope", "calling thread only; excludes runtime worker threads and device execution"},
                           {"legacy_exact_sigmoid_fields", "protocol aliases for selected-contract exact scalar parity; consult settings.scalar_contract"},
                          {"cpu_unavailable_representation", "JSON null / empty CSV numeric field"}}}};
#ifdef CV_VERSION
        root.insert("opencv_compile_version", CV_VERSION);
#else
        root.insert("opencv_compile_version", "unavailable (declaration-only local syntax check)");
#endif
        std::cout << "certifying 30 fresh completions per profile before timed blocks; NPU exclusivity is not assumed\n";
        std::cout << "production_compatibility=" << config.production_compatibility << " candidate_contract=" << decoder_contract(config) << '\n';
        std::cout << "runtime_dequantization=" << dequant_contract(config) << '\n';
        const auto cert = certify(model, inputs, parity, detections, config);
        root.insert("certification", cert.metadata);
        std::cout << "certification_exact_sigmoid=" << (cert.exact.failures ? "FAIL" : "PASS")
                  << " certification_exact_scalar=" << (cert.exact.failures ? "FAIL" : "PASS")
                  << " certification_semantic_compatibility=" << (cert.compatibility.failures ? "FAIL" : "PASS") << '\n';
        Checks timed_compatibility;
        Totals baseline_total, native_total;
        QJsonArray blocks, pairs;
        for (int round = 0; round < round_count; ++round) {
            const Profile first = round % 2 == 0 ? Profile::Baseline : Profile::Native;
            const Profile second = first == Profile::Baseline ? Profile::Native : Profile::Baseline;
            const auto expected = [&](Profile p) { return cert.metadata.value(p == Profile::Baseline ? "baseline_session" : "native_session").toObject(); };
            auto a = measure_block(model, inputs, round, 0, first, cycles, expected(first), config);
            blocks.append(write_block(a, inputs, samples, summary, detections));
            std::cout << "block=" << a.id << " profile=" << profile_name(a.profile) << " completed=" << a.completions.size()
                      << " wall_ms=" << a.total.wall << " completed_fps=" << a.fps() << '\n';
            auto b = measure_block(model, inputs, round, 1, second, cycles, expected(second), config);
            blocks.append(write_block(b, inputs, samples, summary, detections));
            std::cout << "block=" << b.id << " profile=" << profile_name(b.profile) << " completed=" << b.completions.size()
                      << " wall_ms=" << b.total.wall << " completed_fps=" << b.fps() << '\n';
            const auto& baseline = a.profile == Profile::Baseline ? a : b;
            const auto& candidate = a.profile == Profile::Native ? a : b;
            baseline_total.add(baseline); native_total.add(candidate);
            Checks pair_checks;
            for (std::size_t i = 0; i < candidate.completions.size(); ++i) {
                const auto p = compare(candidate.completions[i].detections, baseline.completions[i].detections);
                pair_checks.add(p); timed_compatibility.add(p);
                parity_row(parity, "timed", round, int(i / frame_count), int(i % frame_count), inputs[i % frame_count],
                           "native_vs_runtime_production", p);
            }
            pairs.append(QJsonObject{{"round", round}, {"baseline_block", baseline.id}, {"native_block", candidate.id},
                         {"native_over_baseline_fps_ratio", candidate.fps() / baseline.fps()}, {"compatibility", pair_checks.json()}});
        }
        require(baseline_total.completions == native_total.completions &&
                timed_compatibility.checks == native_total.completions, "incomplete paired completion audit");
        const bool exact_pass = cert.exact.failures == 0;
        const bool compatible = cert.compatibility.failures == 0 && timed_compatibility.failures == 0;
        const double ratio = native_total.fps() / baseline_total.fps();
        require(cleanup_errors == 0, "RKNN cleanup errors");
        root.insert("blocks", blocks); root.insert("pairs", pairs);
        root.insert("totals", QJsonObject{{"baseline", baseline_total.json()}, {"native", native_total.json()},
                     {"native_over_baseline_fps_ratio", ratio}, {"exact_sigmoid_pass", exact_pass}, {"semantic_compatibility_pass", compatible},
                     {"exact_scalar_pass", exact_pass}, {"production_compatibility", config.production_compatibility},
                     {"scalar_contract", decoder_contract(config)},
                    {"timed_compatibility", timed_compatibility.json()}, {"certification_compatibility", cert.compatibility.json()},
                    {"benchmark_status", exact_pass && compatible ? "PASS" : "FAIL"}, {"cleanup_errors", int(cleanup_errors)},
                    {"result_sink", number(result_sink)}});
        for (Profile p : {Profile::Baseline, Profile::Native}) {
            const auto& t = p == Profile::Baseline ? baseline_total : native_total;
            totals_file << pinned_sha << ',' << profile_name(p) << ',' << t.blocks << ',' << t.blocks * warm_count << ',' << t.completions
                        << ',' << t.wall << ','; csv_number(totals_file, t.cpu);
            totals_file << ',' << t.fps() << ',' << ratio << ',' << exact_pass << ',' << compatible
                        << ',' << cert.compatibility.failures << ',' << timed_compatibility.failures
                        << ',' << config.production_compatibility << ',' << exact_pass << '\n';
        }
        const auto json = QJsonDocument(root).toJson(QJsonDocument::Indented);
        source.write(json.constData(), json.size());
        for (auto* file : {&samples, &summary, &detections, &parity, &totals_file, &source}) file->flush();
        std::cout << "exact_sigmoid_parity=" << (exact_pass ? "PASS" : "FAIL")
                  << " exact_scalar_parity=" << (exact_pass ? "PASS" : "FAIL")
                  << " semantic_compatibility=" << (compatible ? "PASS" : "FAIL")
                  << " certification_difference_frames=" << cert.compatibility.failures
                  << " timed_difference_completions=" << timed_compatibility.failures << '\n'
                  << "completed_inference_baseline_fps=" << baseline_total.fps() << " native_fps=" << native_total.fps()
                  << " native_over_baseline_fps_ratio=" << ratio << " (paired pipeline completions; not viewer FPS)\n"
                  << "benchmark_status=" << (exact_pass && compatible ? "PASS" : "FAIL") << '\n';
        if (!compatible) std::cout << "FAIL compatibility: native is not certified as a drop-in replacement; inspect parity/detections/source JSON.\n";
        return exact_pass && compatible ? 0 : 1;
    } catch (const std::exception& e) {
        std::cerr << "benchmark_status=FAIL ERROR " << e.what() << '\n';
        return 1;
    }
}
