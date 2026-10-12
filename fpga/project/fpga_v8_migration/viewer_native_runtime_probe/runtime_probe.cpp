#include "src/viewer_native_qt.hpp"
#include "host_acceleration/legacy_production_adapter.h"
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QVector>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include "viewer_detection.inc"

namespace {
QJsonObject result;
QJsonArray cases, acquisitions;
std::map<rknn_output*, QJsonObject> active;
unsigned successful_gets = 0, release_calls = 0, released_buffers = 0, runs = 0;
unsigned prepare_checks = 0, failed_checks = 0;
const std::array<float, 4> confidences{{0.05f, 0.25f, 0.32f, 0.95f}};

void require(bool value, const std::string& why) {
    if (!value) throw std::runtime_error(why);
}
void checked(int code, const char* operation) {
    require(code == RKNN_SUCC, std::string(operation) + " ret=" + std::to_string(code));
}
QByteArray bytes(const QString& path) {
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "cannot read " + path.toStdString());
    const auto data = file.readAll();
    require(file.error() == QFile::NoError, "file read failed");
    return data;
}
QString sha(const QByteArray& data) {
    return QCryptographicHash::hash(data, QCryptographicHash::Sha256).toHex();
}
QJsonObject attr(const rknn_tensor_attr& a) {
    QJsonArray dims;
    for (unsigned i = 0; i < a.n_dims && i < RKNN_MAX_DIMS; ++i) dims.append(int(a.dims[i]));
    return {{"index", int(a.index)}, {"name", QString::fromLatin1(a.name)}, {"n_dims", int(a.n_dims)}, {"dims", dims},
        {"fmt", int(a.fmt)}, {"type", int(a.type)}, {"qnt_type", int(a.qnt_type)}, {"zp", a.zp},
        {"scale", a.scale}, {"scale_bits", double(raw_dfl::detail::float_bits(a.scale))},
        {"n_elems", int(a.n_elems)}, {"size", int(a.size)}, {"w_stride", int(a.w_stride)},
        {"size_with_stride", int(a.size_with_stride)}};
}
QJsonObject detection(const Detection& d) {
    return {{"class", d.cls}, {"score", d.score}, {"x1", d.x1}, {"y1", d.y1}, {"x2", d.x2}, {"y2", d.y2}};
}
int tracked_release(rknn_context context, std::uint32_t count, rknn_output* outputs) {
    ++release_calls;
    auto it = active.find(outputs);
    if (it == active.end()) { ++failed_checks; return -999; }
    QJsonObject record = it->second;
    active.erase(it); // One attempt even on runtime failure.
    released_buffers += count;
    const int code = rknn_outputs_release(context, count, outputs);
    record.insert("release_calls", 1);
    record.insert("released_buffers", int(count));
    record.insert("release_ret", code);
    acquisitions.append(record);
    return code;
}
void get(rknn_context context, std::vector<rknn_output>& outputs, bool want_float,
         const std::vector<rknn_tensor_attr>& attrs, int frame) {
    outputs.assign(6, {});
    for (unsigned i = 0; i < 6; ++i) { outputs[i].index = i; outputs[i].want_float = want_float ? 1 : 0; }
    checked(rknn_outputs_get(context, 6, outputs.data(), nullptr), "rknn_outputs_get");
    ++successful_gets;
    QJsonObject record{{"acquisition", int(successful_gets)}, {"frame", frame}, {"want_float", want_float ? 1 : 0}};
    require(active.emplace(outputs.data(), record).second, "duplicate active output storage");
    // Every successful get is leased before buffer validation or decoding.
    (void)attrs;
}
void validate_and_hash(std::vector<rknn_output>& outputs, const std::vector<rknn_tensor_attr>& attrs, bool want_float) {
    QJsonArray heads;
    for (unsigned i = 0; i < 6; ++i) {
        const auto& o = outputs[i];
        require(o.index == i && !o.is_prealloc && o.want_float == (want_float ? 1 : 0) && o.buf &&
            o.size == attrs[i].n_elems * (want_float ? 4u : 1u), "runtime output metadata mismatch");
        heads.append(QJsonObject{{"index", int(i)}, {"bytes", int(o.size)},
            {"sha256", sha(QByteArray::fromRawData(static_cast<const char*>(o.buf), int(o.size)))}});
    }
    active.at(outputs.data()).insert("heads", heads);
}

QVector<Detection> candidate_decode(viewer_native::Session& session, float confidence,
    const std::vector<rknn_output>& outs) {
    auto* m_nativeSession = &session;
    const auto m_nOutput = unsigned(session.attrs.size());
    const auto& attrs = session.attrs;
    const auto config = viewer_native::decoder_config(confidence);
    if (!m_nativeSession->decoder || m_nativeSession->confidence != confidence) {
        m_nativeSession->decoder.emplace(config);
        m_nativeSession->confidence = confidence;
    }
    QVector<Detection> dets;
    // This include is extracted byte-for-byte from the actual candidate main.
#include "candidate_conversion.inc"
    require(dets.size() == int(owned.size()), "QVector conversion count mismatch");
    for (int i = 0; i < dets.size(); ++i) {
        const auto& a = dets[i]; const auto& b = owned[std::size_t(i)];
        require(a.cls == b.cls && raw_dfl::detail::float_bits(a.score) == raw_dfl::detail::float_bits(b.score) &&
            raw_dfl::detail::float_bits(a.x1) == raw_dfl::detail::float_bits(b.x1) &&
            raw_dfl::detail::float_bits(a.y1) == raw_dfl::detail::float_bits(b.y1) &&
            raw_dfl::detail::float_bits(a.x2) == raw_dfl::detail::float_bits(b.x2) &&
            raw_dfl::detail::float_bits(a.y2) == raw_dfl::detail::float_bits(b.y2), "QVector conversion changed field bits");
        require(a.trackId == 0 && a.matchScore == 0 && !a.predicted && std::isnan(a.depthMeters) &&
            a.depthAgeMs == 0 && a.depthCapturedMs == 0 && a.validUntilMs == 0 && a.depthStatus.isEmpty() && !a.depthTrial,
            "QVector conversion changed production default fields");
    }
    return dets;
}

QJsonObject compare(const QVector<Detection>& native, const QVector<raw_dfl_legacy::Detection>& production) {
    QJsonArray differences, native_json, production_json;
    float max_score = 0, max_coord = 0;
    unsigned class_differences = 0, score_differences = 0, coord_differences = 0;
    for (const auto& d : native) native_json.append(detection(d));
    for (const auto& d : production)
        production_json.append(QJsonObject{{"class", d.cls}, {"score", d.score}, {"x1", d.x1}, {"y1", d.y1}, {"x2", d.x2}, {"y2", d.y2}});
    for (int i = 0; i < std::min(native.size(), production.size()); ++i) {
        const auto& a = native[i]; const auto& b = production[i];
        const auto score_error = std::abs(a.score - b.score);
        const auto coord_error = std::max({std::abs(a.x1-b.x1), std::abs(a.y1-b.y1), std::abs(a.x2-b.x2), std::abs(a.y2-b.y2)});
        max_score = std::max(max_score, score_error); max_coord = std::max(max_coord, coord_error);
        const bool finite = std::isfinite(a.score) && std::isfinite(b.score) &&
            std::isfinite(a.x1) && std::isfinite(a.y1) && std::isfinite(a.x2) && std::isfinite(a.y2) &&
            std::isfinite(b.x1) && std::isfinite(b.y1) && std::isfinite(b.x2) && std::isfinite(b.y2);
        class_differences += a.cls != b.cls;
        score_differences += score_error > 1e-6f;
        coord_differences += coord_error > 1e-3f;
        if (!finite || a.cls != b.cls || score_error > 1e-6f || coord_error > 1e-3f)
            differences.append(QJsonObject{{"index", i}, {"class_equal", a.cls == b.cls},
                {"score_error", score_error}, {"coordinate_error", coord_error}, {"finite", finite}});
    }
    // Also report unordered matching separately; strict index comparison decides acceptance.
    std::vector<raw_dfl::Detection> owned;
    for (const auto& d : native) { raw_dfl::Detection v; v.cls=d.cls; v.score=d.score; v.x1=d.x1; v.y1=d.y1; v.x2=d.x2; v.y2=d.y2; owned.push_back(v); }
    const auto matching = raw_dfl_legacy::compare(owned, production);
    const bool pass = native.size() == production.size() && differences.isEmpty() &&
        matching.native_unmatched == 0 && matching.legacy_unmatched == 0 && matching.score_mismatches == 0;
    return {{"passed", pass}, {"native_count", native.size()}, {"production_count", production.size()},
        {"count_difference", native.size() != production.size()}, {"class_differences_at_index", int(class_differences)},
        {"score_differences_at_index", int(score_differences)}, {"coordinate_differences_at_index", int(coord_differences)},
        {"ordered_differences", differences}, {"native_unmatched", int(matching.native_unmatched)},
        {"production_unmatched", int(matching.legacy_unmatched)}, {"max_score_error", max_score}, {"max_coordinate_error", max_coord},
        {"qvector_conversion_field_bits_exact", true}, {"native_detections", native_json}, {"production_detections", production_json}};
}
void write_profile(const QString& path, const QString& model_sha, const std::string& runtime_sha,
                   const rknn_sdk_version& version, const rknn_tensor_attr& input, const std::vector<rknn_tensor_attr>& attrs) {
    std::ofstream stream(path.toStdString());
    stream << model_sha.toStdString() << ' ' << runtime_sha << ' ' << std::quoted(version.api_version) << ' ' << version.drv_version << '\n';
    auto row = [&](const rknn_tensor_attr& a) {
        stream << a.index << ' ' << a.name << ' ' << a.n_dims;
        for (unsigned i = 0; i < 4; ++i) stream << ' ' << a.dims[i];
        stream << ' ' << unsigned(a.fmt) << ' ' << unsigned(a.type) << ' ' << unsigned(a.qnt_type)
            << ' ' << a.n_elems << ' ' << a.size << ' ' << a.w_stride << ' ' << a.size_with_stride
            << ' ' << a.zp << ' ' << raw_dfl::detail::float_bits(a.scale) << '\n';
    };
    row(input); for (const auto& a : attrs) row(a);
    require(bool(stream), "failed to save actual runtime guard profile");
}
void save(const QString& path) {
    result.insert("certification_rknn_run_calls", int(runs)); result.insert("successful_gets", int(successful_gets));
    result.insert("release_calls", int(release_calls)); result.insert("released_buffers", int(released_buffers));
    result.insert("active_output_leases", int(active.size())); result.insert("prepare_checks", int(prepare_checks));
    result.insert("failed_checks", int(failed_checks)); result.insert("cases", cases); result.insert("acquisitions", acquisitions);
    QFile file(path);
    require(file.open(QIODevice::WriteOnly), "cannot save report");
    require(file.write(QJsonDocument(result).toJson(QJsonDocument::Indented)) > 0, "report write failed");
}
struct Context {
    rknn_context context = 0;
    ~Context() { if (context) { result.insert("rknn_destroy_ret", rknn_destroy(context)); context = 0; } }
};
void validate(const QString& model_path, const QString& manifest_path, const QString& stage) {
    const auto model = bytes(model_path);
    result.insert("model", QJsonObject{{"path", model_path}, {"bytes", model.size()}, {"sha256", sha(model)}});
    require(sha(model).toStdString() == viewer_native::kModelSha, "actual model hash is outside pinned profile");
    Context owner;
    QByteArray mutable_model = model;
    checked(rknn_init(&owner.context, mutable_model.data(), std::uint32_t(mutable_model.size()), 0, nullptr), "rknn_init");
    result.insert("init_flags", 0);
    rknn_input_output_num io{};
    rknn_sdk_version version{};
    rknn_tensor_attr input{};
    checked(rknn_query(owner.context, RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io)), "query counts");
    checked(rknn_query(owner.context, RKNN_QUERY_SDK_VERSION, &version, sizeof(version)), "query version");
    checked(rknn_query(owner.context, RKNN_QUERY_INPUT_ATTR, &input, sizeof(input)), "query input");
    require(viewer_native::terminated(version.api_version, sizeof(version.api_version)) &&
        viewer_native::terminated(version.drv_version, sizeof(version.drv_version)), "unterminated version");
    std::vector<rknn_tensor_attr> attrs(io.n_output);
    QJsonArray observed_attrs;
    for (unsigned i = 0; i < io.n_output; ++i) {
        attrs[i].index = i;
        checked(rknn_query(owner.context, RKNN_QUERY_OUTPUT_ATTR, &attrs[i], sizeof(attrs[i])), "query output");
        require(viewer_native::terminated(attrs[i].name, sizeof(attrs[i].name)), "unterminated output name");
        observed_attrs.append(attr(attrs[i]));
    }
    result.insert("actual_profile", QJsonObject{{"n_input", int(io.n_input)}, {"n_output", int(io.n_output)},
        {"api", QString::fromLatin1(version.api_version)}, {"driver", QString::fromLatin1(version.drv_version)},
        {"input", attr(input)}, {"outputs", observed_attrs}});
    const auto maps = bytes("/proc/self/maps");
    QFile maps_file(stage + "/probe_runtime_maps.txt");
    require(maps_file.open(QIODevice::WriteOnly), "cannot save mappings"); maps_file.write(maps); maps_file.close();
    bool verified = false; std::string mapping_reason;
    const auto runtime_sha = viewer_native::hash_mapped_runtime(verified, mapping_reason);
    QJsonArray paths;
    for (const auto& path : viewer_native::mapped_runtime_paths(maps.toStdString()).paths) paths.append(QString::fromStdString(path));
    result.insert("mapped_runtime", QJsonObject{{"verified", verified}, {"sha256", QString::fromStdString(runtime_sha)},
        {"paths", paths}, {"reason", QString::fromStdString(mapping_reason)}});
    write_profile(stage + "/actual_guard_profile.txt", sha(model), runtime_sha, version, input, attrs);
    QJsonArray preparations;
    quint64 serial = 0;
    auto prepare_case = [&](const QString& label, const QByteArray& supplied, bool expected,
                            const QString& diagnostic) {
        auto session = viewer_native::prepare(owner.context, supplied, model_path, io.n_output, 3, false, ++serial);
        const bool passed = session.enabled == expected && session.context_serial == serial &&
            (expected ? session.attrs.size() == 6 : session.attrs.empty()) && !session.decoder;
        ++prepare_checks; if (!passed) ++failed_checks;
        preparations.append(QJsonObject{{"case", label}, {"expected_enabled", expected}, {"observed_enabled", session.enabled},
            {"passed", passed}, {"serial", double(serial)}, {"attrs_count", int(session.attrs.size())},
            {"DET_V8_NATIVE_present", qEnvironmentVariableIsSet("DET_V8_NATIVE")}, {"DET_V8_NATIVE", QString::fromLatin1(qgetenv("DET_V8_NATIVE"))},
            {"DET_INT8_IN_present", qEnvironmentVariableIsSet("DET_INT8_IN")}, {"supplied_model_sha256", sha(supplied)},
            {"expected_diagnostic", diagnostic}});
        return session;
    };
    qunsetenv("DET_V8_NATIVE"); qunsetenv("DET_INT8_IN");
    prepare_case("environment missing", model, false, "none: opt-out returns silently before RKNN queries");
    qputenv("DET_V8_NATIVE", "true");
    prepare_case("environment other value", model, false, "none: opt-out returns silently before RKNN queries");
    qputenv("DET_V8_NATIVE", "1");
    auto bad_model = model; bad_model[0] = char(static_cast<unsigned char>(bad_model[0]) ^ 1u);
    prepare_case("bad model byte hash on actual valid context", bad_model, false, "model SHA256 is outside pinned V8 profile");
    qputenv("DET_INT8_IN", "");
    prepare_case("DET_INT8_IN present empty", model, false, "DET_INT8_IN override requires existing float path");
    qputenv("DET_INT8_IN", "0");
    prepare_case("DET_INT8_IN present zero", model, false, "DET_INT8_IN override requires existing float path");
    qunsetenv("DET_INT8_IN");
    auto session = prepare_case("pinned actual profile enabled", model, true, "pinned V8 native profile verified");
    result.insert("prepare_cases", preparations);
    result.insert("session_enabled", session.enabled);
    require(session.enabled && failed_checks == 0, "actual Session::prepare rejected profile or fallback checks failed; recorded exact observed attrs");
    require(io.n_input == 1 && io.n_output == 6, "queried IO counts outside required profile");
    const auto manifest = QJsonDocument::fromJson(bytes(manifest_path)).object();
    const auto inputs = manifest.value("inputs").toArray();
    require(inputs.size() == 30, "requires exactly 30 retained prepared inputs");
    raw_dfl_legacy::ProductionDecoder production;
    std::vector<rknn_output> outputs;
    for (int frame = 0; frame < inputs.size(); ++frame) {
        const auto row = inputs[frame].toObject();
        const auto prepared = bytes(row.value("prepared_path").toString());
        require(prepared.size() == 1228800 && sha(prepared) == row.value("rgb_sha256").toString(), "prepared RGB hash mismatch");
        rknn_input supplied{};
        supplied.buf = const_cast<char*>(prepared.constData()); supplied.size = prepared.size();
        supplied.type = RKNN_TENSOR_UINT8; supplied.fmt = RKNN_TENSOR_NHWC; supplied.pass_through = 0;
        checked(rknn_inputs_set(owner.context, 1, &supplied), "rknn_inputs_set");
        checked(rknn_run(owner.context, nullptr), "rknn_run"); ++runs;
        std::array<QVector<Detection>, 4> native;
        get(owner.context, outputs, false, attrs, frame);
        {
            viewer_native::OutputLease lease(owner.context, outputs, tracked_release);
            validate_and_hash(outputs, attrs, false);
            for (unsigned c = 0; c < confidences.size(); ++c) native[c] = candidate_decode(session, confidences[c], outputs);
            checked(lease.finish(), "native outputs_release");
        }
        // No inputs_set or rknn_run between gets: float outputs belong to that same inference.
        get(owner.context, outputs, true, attrs, frame);
        {
            viewer_native::OutputLease lease(owner.context, outputs, tracked_release);
            validate_and_hash(outputs, attrs, true);
            for (unsigned c = 0; c < confidences.size(); ++c) {
                production.m_conf.store(confidences[c]);
                const auto reference = production.decode(outputs, attrs);
                auto comparison = compare(native[c], reference);
                comparison.insert("frame", frame); comparison.insert("source_board_path", row.value("board_path"));
                comparison.insert("rgb_sha256", sha(prepared)); comparison.insert("confidence", confidences[c]);
                comparison.insert("same_inference_run", int(runs));
                if (!comparison.value("passed").toBool()) ++failed_checks;
                cases.append(comparison);
            }
            checked(lease.finish(), "float outputs_release");
        }
        std::cout << "FRAME " << frame + 1 << " paired_gets=2 confidence_cases=4" << std::endl;
    }
    require(runs == 30 && successful_gets == 60 && release_calls == 60 && released_buffers == 360 && active.empty(), "release/run accounting mismatch");
    require(cases.size() == 120 && failed_checks == 0, "one or more strict detection comparisons failed");
    result.insert("passed", true);
}
} // namespace

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    if (argc != 4) { std::cerr << "usage: runtime_probe MODEL PREPARED_MANIFEST STAGE\n"; return 2; }
    result.insert("scope", "headless RK3568 runtime integration; no timing or throughput claim");
    result.insert("score_tolerance", 1e-6); result.insert("coordinate_tolerance", 1e-3);
    result.insert("passed", false);
    int code = 0;
    try { validate(QString::fromLocal8Bit(argv[1]), QString::fromLocal8Bit(argv[2]), QString::fromLocal8Bit(argv[3])); }
    catch (const std::exception& error) { result.insert("error", QString::fromLocal8Bit(error.what())); std::cerr << "PROBE_FAIL " << error.what() << '\n'; code = 1; }
    try { save(QString::fromLocal8Bit(argv[3]) + "/runtime_report.json"); }
    catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 3; }
    std::cout << (code == 0 ? "RUNTIME_PROBE_PASS" : "RUNTIME_PROBE_FAIL") << " runs=" << runs << " gets=" << successful_gets
        << " release_calls=" << release_calls << " released_buffers=" << released_buffers << " cases=" << cases.size() << std::endl;
    return code;
}
