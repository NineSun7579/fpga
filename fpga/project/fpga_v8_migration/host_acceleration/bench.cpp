#include "legacy_production_adapter.h"
#include <QByteArray>
#include <QCryptographicHash>
#include <opencv2/opencv.hpp>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>

namespace {
constexpr const char* pinned_sha = "be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9";
constexpr const char* pinned_name = "det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn";
volatile double result_sink = 0;

double ms() {
    return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
void check(int code, const char* operation) {
    if (code != RKNN_SUCC) throw std::runtime_error(std::string(operation) + " ret=" + std::to_string(code));
}
void require(bool ok, const std::string& message) {
    if (!ok) throw std::runtime_error(message);
}
std::ofstream output_file(const std::string& path) {
    std::ofstream stream(path);
    require(bool(stream), "cannot write " + path);
    stream.exceptions(std::ios::badbit | std::ios::failbit);
    stream << std::fixed << std::setprecision(9);
    return stream;
}
std::string csv(const std::string& s) {
    std::string result = "\"";
    for (char c : s) { if (c == '"') result += '"'; result += c; }
    return result + '"';
}

struct Input {
    cv::Mat bgr;
    std::string id;
};

std::vector<Input> capture_images(const std::string& source, int count) {
    std::vector<Input> inputs;
    inputs.reserve(count);
    const auto dot = source.find_last_of('.');
    const std::string extension = dot == std::string::npos ? "" : source.substr(dot);
    if (extension == ".txt" || extension == ".list") {
        std::ifstream list(source);
        require(bool(list), "open frame list " + source);
        std::string path;
        while (int(inputs.size()) < count && std::getline(list, path)) {
            if (!path.empty() && path.back() == '\r') path.pop_back();
            if (path.empty() || path[0] == '#') continue;
            auto image = cv::imread(path, cv::IMREAD_COLOR);
            require(!image.empty(), "cannot read road frame " + path);
            inputs.push_back({image, path});
        }
    } else {
        cv::VideoCapture video(source);
        require(video.isOpened(), "open road video " + source);
        for (int i = 0; i < count; ++i) {
            cv::Mat image;
            require(video.read(image) && !image.empty(), "road video has fewer than requested frames");
            inputs.push_back({image.clone(), source + "#" + std::to_string(i)});
        }
    }
    require(int(inputs.size()) == count, "requires at least " + std::to_string(count) + " road images");
    return inputs;
}

cv::Mat prepare(const cv::Mat& bgr) {
    const double scale = std::min(640.0 / bgr.cols, 640.0 / bgr.rows);
    const int width = std::lround(bgr.cols * scale), height = std::lround(bgr.rows * scale);
    cv::Mat resized, rgb, padded(640, 640, CV_8UC3, cv::Scalar(114, 114, 114));
    cv::resize(bgr, resized, cv::Size(width, height), 0, 0, cv::INTER_LINEAR);
    cv::cvtColor(resized, rgb, cv::COLOR_BGR2RGB);
    rgb.copyTo(padded(cv::Rect((640 - width) / 2, (640 - height) / 2, width, height)));
    return padded;
}

// Benchmark-specific ownership only. The production Model/viewer is untouched.
class RknnSession {
public:
    rknn_context ctx = 0;
    std::vector<rknn_tensor_attr> attrs;
    std::vector<rknn_output> outs;
    bool acquired = false;
    std::size_t model_bytes = 0;
    std::string actual_sha;

    RknnSession(const std::string& path, const std::string& supplied_sha) {
        require(supplied_sha == pinned_sha, "caller MODEL_SHA must equal pinned wb_v8_w25_nop2c2f SHA256");
        const auto slash = path.find_last_of("/\\");
        require(path.substr(slash == std::string::npos ? 0 : slash + 1) == pinned_name,
                "requires pinned raw-dfl6 model filename");
        std::ifstream file(path, std::ios::binary);
        require(bool(file), "open pinned RKNN model " + path);
        std::vector<char> bytes((std::istreambuf_iterator<char>(file)), {});
        require(!bytes.empty() && bytes.size() <= std::size_t(std::numeric_limits<int>::max()), "invalid model size");
        model_bytes = bytes.size();
        actual_sha = QCryptographicHash::hash(QByteArray::fromRawData(bytes.data(), int(bytes.size())),
                                             QCryptographicHash::Sha256).toHex().toStdString();
        require(actual_sha == supplied_sha, "model file SHA256 does not match caller/pin");
        try {
            // Synchronous flags=0: every stored output belongs to this input.
            check(rknn_init(&ctx, bytes.data(), std::uint32_t(bytes.size()), 0, nullptr), "rknn_init");
            rknn_input_output_num io{};
            check(rknn_query(ctx, RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io)), "query IO");
            require(io.n_input == 1 && io.n_output == 6, "pinned model requires 1 input/6 outputs");
            rknn_tensor_attr input{};
            check(rknn_query(ctx, RKNN_QUERY_INPUT_ATTR, &input, sizeof(input)), "query input");
            require(input.n_dims == 4 && input.dims[0] == 1 && input.n_elems == 640 * 640 * 3 &&
                    ((input.fmt == RKNN_TENSOR_NHWC && input.dims[1] == 640 && input.dims[2] == 640 && input.dims[3] == 3) ||
                     (input.fmt == RKNN_TENSOR_NCHW && input.dims[1] == 3 && input.dims[2] == 640 && input.dims[3] == 640)),
                    "requires RGB640 input");
            attrs.resize(6); outs.resize(6);
            for (unsigned i = 0; i < 6; ++i) {
                attrs[i].index = i;
                check(rknn_query(ctx, RKNN_QUERY_OUTPUT_ATTR, &attrs[i], sizeof(attrs[i])), "query output");
            }
            rknn_sdk_version version{};
            if (rknn_query(ctx, RKNN_QUERY_SDK_VERSION, &version, sizeof(version)) == 0)
                std::cout << "RKNN api=" << version.api_version << " driver=" << version.drv_version << '\n';
        } catch (...) { if (ctx) rknn_destroy(ctx); ctx = 0; throw; }
    }
    RknnSession(const RknnSession&) = delete;
    RknnSession& operator=(const RknnSession&) = delete;
    ~RknnSession() {
        if (acquired) rknn_outputs_release(ctx, std::uint32_t(outs.size()), outs.data());
        if (ctx) rknn_destroy(ctx);
    }
    void set(const cv::Mat& rgb) {
        require(rgb.isContinuous() && rgb.type() == CV_8UC3 && rgb.rows == 640 && rgb.cols == 640, "invalid prepared input");
        rknn_input input{};
        input.buf = rgb.data; input.size = 640 * 640 * 3;
        input.type = RKNN_TENSOR_UINT8; input.fmt = RKNN_TENSOR_NHWC; input.pass_through = 0;
        check(rknn_inputs_set(ctx, 1, &input), "inputs_set");
    }
    void run() { check(rknn_run(ctx, nullptr), "rknn_run"); }
    void get() {
        require(!acquired, "output already acquired");
        for (unsigned i = 0; i < outs.size(); ++i) { outs[i] = {}; outs[i].index = i; outs[i].want_float = 0; }
        check(rknn_outputs_get(ctx, std::uint32_t(outs.size()), outs.data(), nullptr), "outputs_get want_float=0");
        acquired = true;
    }
    void release() {
        if (!acquired) return;
        check(rknn_outputs_release(ctx, std::uint32_t(outs.size()), outs.data()), "outputs_release");
        acquired = false;
    }
};

struct Snapshot {
    std::array<std::vector<std::uint8_t>, 6> storage;
    std::vector<rknn_output> outs;
    std::string input_id;
    double preprocess_ms = 0, input_set_ms = 0, run_ms = 0, get_ms = 0, copy_release_ms = 0;
};

void consume(const std::vector<raw_dfl::Detection>& result) {
    double value = result.size();
    for (const auto& d : result) value += d.score + d.x1 + d.y1 + d.x2 + d.y2 + d.cls;
    result_sink = result_sink + value;
}

void stats(std::ofstream& stream, const std::string& stage, const std::string& sha,
           const std::vector<double>& values, bool production_compatibility) {
    require(!values.empty(), "empty timing stage");
    auto sorted = values;
    std::sort(sorted.begin(), sorted.end());
    const double mean = std::accumulate(values.begin(), values.end(), 0.0) / values.size();
    const auto percentile = [&](double p) { return sorted[std::size_t(std::ceil(p * sorted.size())) - 1]; };
    stream << sha << ',' << stage << ',' << values.size() << ',' << sorted.front() << ',' << mean << ','
           << percentile(0.5) << ',' << percentile(0.95) << ',' << sorted.back() << ',' << production_compatibility << '\n';
}

void write_detections(std::ofstream& file, int frame, const char* decoder,
                      const std::vector<raw_dfl::Detection>& detections) {
    for (std::size_t i = 0; i < detections.size(); ++i) {
        const auto& d = detections[i];
        file << frame << ',' << decoder << ',' << i << ',' << d.anchor << ',' << d.cls << ',' << d.score << ','
             << d.x1 << ',' << d.y1 << ',' << d.x2 << ',' << d.y2 << '\n';
    }
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 5 || argc > 10) {
            std::cerr << "usage: raw_dfl_bench MODEL ROAD_FRAME_LIST.txt|ROAD_VIDEO PREFIX MODEL_SHA "
                         "[iters=100] [frames=30] [confidence=0.25] [iou=0.45] [production_compat=0|1]\n";
            return 2;
        }
        const std::string model_path = argv[1], source = argv[2], prefix = argv[3], supplied_sha = argv[4];
        const int iterations = argc > 5 ? std::stoi(argv[5]) : 100;
        const int frame_count = argc > 6 ? std::stoi(argv[6]) : 30;
        raw_dfl::Config config;
        if (argc > 7) config.confidence = std::stof(argv[7]);
        if (argc > 8) config.iou = std::stof(argv[8]);
        if (argc > 9) {
            const std::string compatibility_arg = argv[9];
            require(compatibility_arg == "0" || compatibility_arg == "1", "production_compat must be 0 or 1");
            config.production_compatibility = compatibility_arg == "1";
        }
        require(iterations >= 1 && frame_count >= 30, "requires iters>=1 and at least 30 captured road images");
        // Imported production NMS has a fixed 0.45 constant.
        require(config.iou == 0.45f, "legacy comparison requires IoU=0.45");
        raw_dfl::NativeDecoder native(config);
        const char* reference_contract = config.production_compatibility ? "production_compatibility" : "always_sigmoid_canonical";
        raw_dfl_legacy::ProductionDecoder legacy;
        legacy.m_conf.store(config.confidence);
        cv::setNumThreads(1);
        std::cout << std::fixed << std::setprecision(9);

        // Capture all road images before NPU acquisition or decoder timing loops.
        auto inputs = capture_images(source, frame_count);
        RknnSession session(model_path, supplied_sha);
        auto acquisition = output_file(prefix + "_acquisition.csv");
        auto samples = output_file(prefix + "_samples.csv");
        auto summary = output_file(prefix + "_summary.csv");
        auto parity_file = output_file(prefix + "_parity.csv");
        auto detections_file = output_file(prefix + "_detections.csv");
        auto metadata = output_file(prefix + "_metadata.txt");
        acquisition << "model_sha256,frame,input,preprocess_ms,input_set_ms,run_ms,outputs_get_ms,copy_release_ms\n";
        samples << "model_sha256,frame,iteration,first,full_dequant_scalar_ms,native_ms,qualified,dfl_cells,kept,production_compatibility,used_sigmoid\n";
        summary << "model_sha256,stage,n,min_ms,mean_ms,p50_ms,p95_ms,max_ms,production_compatibility\n";
        parity_file << "model_sha256,frame,exact_pass,native_count,scalar_count,exact_unmatched,exact_mismatched,"
                       "exact_max_score_error,exact_max_box_error,legacy_sigmoid,legacy_count,legacy_matched,"
                       "native_unmatched_legacy,legacy_unmatched_native,legacy_score_mismatches,legacy_max_score_error,legacy_max_box_error,"
                       "production_compatibility,reference_contract,native_sigmoid\n";
        detections_file << "frame,decoder,rank,anchor,class,score,x1,y1,x2,y2\n";
        metadata << "model=" << model_path << "\nmodel_sha256_supplied=" << supplied_sha
                 << "\nmodel_sha256_verified=" << session.actual_sha << "\nmodel_bytes=" << session.model_bytes
                 << "\nsource=" << source << "\nframes=" << frame_count << "\niters_per_frame=" << iterations
                 << "\nconfidence=" << config.confidence << "\niou=" << config.iou << "\ntopk=" << config.topk
                 << "\nproduction_compatibility=" << config.production_compatibility << "\nreference_contract=" << reference_contract
                 << "\nscore_tolerance=0.000001\nbox_tolerance_px=0.001\ncontract="
                 << (config.production_compatibility
                     ? "legacy_sigmoid_heuristic,attrs_scale_order,best_class,top300,two_score_only_sorts,class_agnostic_nms,unclipped640\n"
                     : "always_sigmoid,best_class,top300,canonical_ties,class_agnostic_nms,unclipped640\n")
                 << "decoder_timing=stored_same_raw_outputs,no_rknn_calls,full_dequant_scalar_vs_cached_native\n";
        for (const auto& a : session.attrs)
            metadata << "head=" << a.name << ",index=" << a.index << ",type=" << int(a.type)
                     << ",zp=" << a.zp << ",scale=" << a.scale << ",bytes=" << a.size
                     << ",w_stride=" << a.w_stride << ",size_with_stride=" << a.size_with_stride << '\n';

        std::vector<Snapshot> snapshots;
        snapshots.reserve(frame_count);
        for (int frame = 0; frame < frame_count; ++frame) {
            Snapshot snapshot;
            snapshot.input_id = inputs[frame].id;
            double t = ms(); auto rgb = prepare(inputs[frame].bgr); snapshot.preprocess_ms = ms() - t;
            t = ms(); session.set(rgb); snapshot.input_set_ms = ms() - t;
            t = ms(); session.run(); snapshot.run_ms = ms() - t;
            t = ms(); session.get(); snapshot.get_ms = ms() - t;
            // Reject unsupported heads before dereferencing/copying any buffer.
            raw_dfl::detail::validate(session.outs, session.attrs);
            t = ms(); snapshot.outs = session.outs;
            for (std::size_t i = 0; i < session.outs.size(); ++i) {
                const auto& out = session.outs[i];
                const auto* bytes = static_cast<const std::uint8_t*>(out.buf);
                snapshot.storage[i].assign(bytes, bytes + out.size);
                snapshot.outs[i].buf = snapshot.storage[i].data();
                snapshot.outs[i].is_prealloc = 1;
            }
            session.release(); snapshot.copy_release_ms = ms() - t;
            acquisition << supplied_sha << ',' << frame << ',' << csv(snapshot.input_id) << ',' << snapshot.preprocess_ms << ','
                        << snapshot.input_set_ms << ',' << snapshot.run_ms << ',' << snapshot.get_ms << ',' << snapshot.copy_release_ms << '\n';
            snapshots.push_back(std::move(snapshot));
        }
        std::cout << "Captured " << snapshots.size() << " road images and their fresh want_float=0 outputs; decoder loops use snapshots only.\n";

        bool exact_pass = true;
        std::size_t legacy_difference_frames = 0, legacy_probability_frames = 0;
        std::vector<double> native_ms, scalar_ms, acquisition_run_ms, acquisition_get_ms;
        for (int frame = 0; frame < frame_count; ++frame) {
            auto& snapshot = snapshots[frame];
            raw_dfl::DecodeStats native_stats;
            const auto candidate = native.decode(snapshot.outs, session.attrs, &native_stats);
            auto floats = raw_dfl::full_dequantize(snapshot.outs, session.attrs);
            const auto reference = raw_dfl::scalar_float_decode(floats, config);
            const auto exact = raw_dfl::compare_exact(candidate, reference);
            const auto old = raw_dfl_legacy::decode(legacy, floats, session.attrs);
            const auto compatibility = raw_dfl_legacy::compare(candidate, old);
            const bool old_sigmoid = raw_dfl_legacy::uses_sigmoid(floats, session.attrs);
            exact_pass = exact_pass && exact.pass();
            if (!old_sigmoid) ++legacy_probability_frames;
            if (compatibility.native_unmatched || compatibility.legacy_unmatched || compatibility.score_mismatches) ++legacy_difference_frames;
            parity_file << supplied_sha << ',' << frame << ',' << exact.pass() << ',' << exact.native_count << ',' << exact.reference_count << ','
                        << exact.unmatched << ',' << exact.mismatched << ',' << exact.max_score_error << ',' << exact.max_box_error << ','
                        << old_sigmoid << ',' << compatibility.legacy_count << ',' << compatibility.matched << ','
                        << compatibility.native_unmatched << ',' << compatibility.legacy_unmatched << ',' << compatibility.score_mismatches << ','
                        << compatibility.max_score_error << ',' << compatibility.max_box_error << ','
                        << config.production_compatibility << ',' << reference_contract << ',' << native_stats.used_sigmoid << '\n';
            write_detections(detections_file, frame, config.production_compatibility ? "native_production_compatibility" : "native", candidate);
            write_detections(detections_file, frame, config.production_compatibility ? "scalar_production_compatibility" : "scalar_exact_sigmoid", reference);
            for (int i = 0; i < old.size(); ++i) {
                const auto& d = old[i];
                detections_file << frame << ",legacy_production," << i << ",-1," << d.cls << ',' << d.score << ','
                                << d.x1 << ',' << d.y1 << ',' << d.x2 << ',' << d.y2 << '\n';
            }
            acquisition_run_ms.push_back(snapshot.run_ms); acquisition_get_ms.push_back(snapshot.get_ms);
        }
        // Warm both CPU decoders on all 30+ snapshots outside timings. Tables
        // already exist after parity; native timing measures steady state.
        for (auto& snapshot : snapshots) {
            consume(native.decode(snapshot.outs, session.attrs));
            consume(raw_dfl::scalar_reference(snapshot.outs, session.attrs, config));
        }
        for (int frame = 0; frame < frame_count; ++frame) {
            auto& snapshot = snapshots[frame];
            for (int iteration = 0; iteration < iterations; ++iteration) {
                double nt = 0, st = 0;
                raw_dfl::DecodeStats measured;
                const auto run_native = [&] {
                    const double t = ms();
                    auto d = native.decode(snapshot.outs, session.attrs, &measured);
                    nt = ms() - t; consume(d);
                };
                const auto run_scalar = [&] {
                    const double t = ms();
                    auto d = raw_dfl::scalar_reference(snapshot.outs, session.attrs, config);
                    st = ms() - t; consume(d);
                };
                if ((frame + iteration) % 2) { run_native(); run_scalar(); }
                else { run_scalar(); run_native(); }
                native_ms.push_back(nt); scalar_ms.push_back(st);
                samples << supplied_sha << ',' << frame << ',' << iteration << ','
                        << ((frame + iteration) % 2 ? "native" : "scalar") << ',' << st << ',' << nt << ','
                        << measured.qualified << ',' << measured.dfl_cells << ',' << measured.kept << ','
                        << config.production_compatibility << ',' << measured.used_sigmoid << '\n';
            }
        }
        stats(summary, "full_dequant_scalar_dfl_nms", supplied_sha, scalar_ms, config.production_compatibility);
        stats(summary, "native_quantized_dfl_nms", supplied_sha, native_ms, config.production_compatibility);
        stats(summary, "acquisition_rknn_run_once_per_frame", supplied_sha, acquisition_run_ms, config.production_compatibility);
        stats(summary, "acquisition_outputs_get_once_per_frame", supplied_sha, acquisition_get_ms, config.production_compatibility);
        const double mean_native = std::accumulate(native_ms.begin(), native_ms.end(), 0.0) / native_ms.size();
        const double mean_scalar = std::accumulate(scalar_ms.begin(), scalar_ms.end(), 0.0) / scalar_ms.size();
        const double mean_run = std::accumulate(acquisition_run_ms.begin(), acquisition_run_ms.end(), 0.0) / acquisition_run_ms.size();
        const double mean_get = std::accumulate(acquisition_get_ms.begin(), acquisition_get_ms.end(), 0.0) / acquisition_get_ms.size();
        const bool legacy_pass = legacy_difference_frames == 0;
        const bool required_pass = exact_pass && (!config.production_compatibility || legacy_pass);
        metadata << "exact_parity_pass=" << exact_pass << "\nlegacy_parity_pass=" << legacy_pass
                 << "\nrequired_parity_pass=" << required_pass << "\nlegacy_difference_frames=" << legacy_difference_frames
                 << "\nlegacy_probability_heuristic_frames=" << legacy_probability_frames
                 << "\nclass_luts=" << native.class_table_count() << "\nexp_luts=" << native.exp_table_count()
                 << "\nscalar_mean_ms=" << mean_scalar << "\nnative_mean_ms=" << mean_native
                 << "\ndecoder_speedup=" << mean_scalar / mean_native << "\nresult_sink=" << result_sink << '\n';
        std::cout << "production_compatibility=" << config.production_compatibility << " reference_contract=" << reference_contract << '\n'
                  << (config.production_compatibility ? "production_compat_scalar_parity=" : "exact_sigmoid_parity=")
                  << (exact_pass ? "PASS" : "FAIL") << " legacy_parity=" << (legacy_pass ? "PASS" : "FAIL")
                  << " legacy_difference_frames=" << legacy_difference_frames
                  << " legacy_probability_heuristic_frames=" << legacy_probability_frames << '\n'
                  << "same_output_scalar_mean_ms=" << mean_scalar << " native_mean_ms=" << mean_native
                  << " decoder_speedup=" << mean_scalar / mean_native << '\n'
                  << "acquisition_mean_run_ms=" << mean_run << " get_ms=" << mean_get
                  << " (separate from decoder timing; no end-to-end FPS claim)\n";
        if (legacy_difference_frames)
            std::cout << "COMPATIBILITY DIFFERENCES: inspect _parity.csv and _detections.csv; production score heuristic and score-tie ordering remain unchanged.\n";
        return required_pass ? 0 : 1;
    } catch (const std::exception& e) {
        std::cerr << "ERROR " << e.what() << '\n'; return 1;
    }
}
