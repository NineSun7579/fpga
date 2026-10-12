// Parent-invoked target probe. No camera/DMA access or viewer lifecycle control.
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <dlfcn.h>
#include <algorithm>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>
#include "hardware_inference.h"
#include "inference_preprocess.h"
#include "rgb565_convert.h"

static const char *ModelSha = "21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31";
static const char *FixtureNames[] = {"bright_baseline_cam1", "candidate_cam1", "live_cam1_bank0_0", "live_cam2_bank0_0"};
static const char *FixtureSha[] = {
    "f914a521b554307ab90f3fa93f7233da21b22503dc9c454ad72174197b8afb86",
    "f32cd160163a500df3885af311b23a82783b6aaad14fae2cbd4adf037d93a0ee",
    "d224d92ba0bd04f03dea276f0911396cccbf55b25738d5e00a019a47965dda1f",
    "ae5d4a53794b239f6b6d8330d7abdf42bc4599e476c3f3a49a8baea3e11a49fa"};

static QByteArray bytes(const QString &path) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) throw std::runtime_error(("cannot_read_" + path).toStdString());
    const QByteArray b = f.readAll();
    if (f.error() != QFile::NoError) throw std::runtime_error("file_read_failed");
    return b;
}
static QString hash(const void *p, size_t size) {
    if (size > size_t(INT_MAX)) throw std::runtime_error("hash_size_overflow");
    return QCryptographicHash::hash(QByteArray::fromRawData(static_cast<const char *>(p), int(size)),
                                    QCryptographicHash::Sha256).toHex();
}
static QString fileHash(const QString &path) { const auto b = bytes(path); return hash(b.constData(), size_t(b.size())); }
static void emitJson(const QJsonObject &o) {
    const auto b = QJsonDocument(o).toJson(QJsonDocument::Compact);
    std::printf("%s\n", b.constData()); std::fflush(stdout);
}
static void check(int rc, const char *stage) {
    if (rc) throw std::runtime_error(std::string(stage) + "_rc=" + std::to_string(rc));
}
static QJsonObject attrJson(const rknn_tensor_attr &a) {
    QJsonArray dims; for (uint32_t i = 0; i < a.n_dims && i < RKNN_MAX_DIMS; ++i) dims.append(double(a.dims[i]));
    return {{"index", double(a.index)}, {"dims", dims}, {"fmt", int(a.fmt)}, {"type", int(a.type)},
            {"qnt_type", int(a.qnt_type)}, {"zp", a.zp}, {"scale", double(a.scale)},
            {"n_elems", double(a.n_elems)}, {"size", double(a.size)}, {"w_stride", double(a.w_stride)},
            {"h_stride", double(a.h_stride)}, {"size_with_stride", double(a.size_with_stride)},
            {"pass_through", int(a.pass_through)}};
}
struct Context {
    rknn_context ctx = 0;
    ~Context() { if (ctx) rknn_destroy(ctx); }
};
struct LegacyOutputs {
    rknn_context ctx;
    std::vector<rknn_output> outs;
    bool acquired = false;
    LegacyOutputs(rknn_context c, size_t count) : ctx(c), outs(count) {
        for (size_t i = 0; i < count; ++i) { outs[i] = rknn_output{}; outs[i].index = uint32_t(i); outs[i].want_float = 1; }
    }
    ~LegacyOutputs() { if (acquired) rknn_outputs_release(ctx, uint32_t(outs.size()), outs.data()); }
    void release() {
        check(rknn_outputs_release(ctx, uint32_t(outs.size()), outs.data()), "legacy_outputs_release");
        acquired = false;
    }
};
static void save(const QString &path, const void *data, size_t size) {
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly | QIODevice::NewOnly) || f.write(static_cast<const char *>(data), qint64(size)) != qint64(size))
        throw std::runtime_error("snapshot_write_failed_or_exists");
}
static QByteArray inputImage(const QJsonObject &fixture, const QString &root) {
    const auto raw = bytes(QDir(root).filePath(fixture.value("path").toString()));
    if (hash(raw.constData(), size_t(raw.size())) != fixture.value("sha256").toString())
        throw std::runtime_error("fixture_hash_mismatch");
    QImage image;
    if (fixture.value("kind").toString() == "png") {
        image = QImage::fromData(raw, "PNG").convertToFormat(QImage::Format_RGB888);
    } else if (fixture.value("kind").toString() == "rgb565_le") {
        const uint16_t endian = 1;
        if (*reinterpret_cast<const uint8_t *>(&endian) != 1 || raw.size() != 640 * 480 * 2)
            throw std::runtime_error("RGB565_fixture_size_or_endian_invalid");
        image = QImage(640, 480, QImage::Format_RGB888);
        for (int y = 0; y < 480; ++y)
            tdm::rgb565ToRgb888Line(reinterpret_cast<const uint8_t *>(raw.constData()) + y * 1280, 640, image.scanLine(y));
    } else throw std::runtime_error("unsupported_fixture_kind");
    if (image.isNull() || image.width() != 640 || image.height() != 480)
        throw std::runtime_error("fixture_must_be_full_640x480");
    // Use the actual frozen candidate's converter and preprocessor; no decoder
    // copy. Full pixels at y=80, gray114 padding, without subtracting 128.
    InferencePreprocessor preprocessor;
    const QImage *prepared = preprocessor.prepare(image);
    if (!prepared || prepared->width() != 640 || prepared->height() != 640 ||
        prepared->format() != QImage::Format_RGB888 || prepared->bytesPerLine() < 1920)
        throw std::runtime_error("candidate_preprocessor_failed");
    // Also verify the candidate preprocessor against the retained full-frame
    // contract so matching outputs cannot hide a shared preparation error.
    for (int y = 0; y < 640; ++y) {
        const auto *line = prepared->constScanLine(y);
        if (y >= 80 && y < 560) {
            if (std::memcmp(line, image.constScanLine(y - 80), 1920)) throw std::runtime_error("full_frame_letterbox_pixels_changed");
        } else {
            for (int x = 0; x < 1920; ++x)
                if (line[x] != 114) throw std::runtime_error("letterbox_padding_changed");
        }
    }
    QByteArray rgb(int(HardwareInference::InputBytes), Qt::Uninitialized);
    for (int y = 0; y < 640; ++y) std::memcpy(rgb.data() + y * 1920, prepared->constScanLine(y), 1920);
    return rgb;
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    int compared = 0, failed = 0;
    try {
        const auto args = app.arguments();
        auto arg = [&](const QString &key, const QString &fallback = QString()) {
            const int i = args.indexOf(key);
            if (i < 0) return fallback;
            if (i + 1 >= args.size()) throw std::runtime_error("argument_value_missing");
            return args[i + 1];
        };
        const QString root = arg("--fixtures"), receipt = arg("--receipt"), source = arg("--source");
        const QByteArray model = bytes(arg("--model"));
        if (hash(model.constData(), size_t(model.size())) != ModelSha) throw std::runtime_error("pinned_model_hash_mismatch");
        const auto manifest = QJsonDocument::fromJson(bytes(QDir(root).filePath("manifest.json"))).object();
        if (manifest.value("model_sha256").toString() != ModelSha) throw std::runtime_error("fixture_manifest_model_mismatch");
        const auto fixtures = manifest.value("fixtures").toArray();
        if (fixtures.size() != 4) throw std::runtime_error("all_four_fixtures_required");
        for (int i = 0; i < 4; ++i) {
            const auto f = fixtures[i].toObject();
            if (f.value("name").toString() != FixtureNames[i] || f.value("sha256").toString() != FixtureSha[i])
                throw std::runtime_error("pinned_fixture_identity_mismatch");
        }
        Dl_info dl{};
        if (!dladdr(reinterpret_cast<void *>(&rknn_init), &dl) || !dl.dli_fname)
            throw std::runtime_error("cannot_identify_linked_runtime");
        const QString runtime = QFileInfo(QString::fromLocal8Bit(dl.dli_fname)).canonicalFilePath();
        const QString runtimeSha = fileHash(runtime);
        if (runtimeSha != arg("--runtime-sha256")) throw std::runtime_error("linked_runtime_hash_mismatch");
        const auto build = QJsonDocument::fromJson(bytes(receipt)).object();
        const auto pins = build.value("inputs_sha256").toObject();
        auto pinnedHash = [&](const QString &path) {
            const QString canonical = QFileInfo(path).canonicalFilePath();
            const QString actual = fileHash(canonical);
            if (pins.value(canonical).toString() != actual) throw std::runtime_error("build_receipt_input_mismatch");
            return actual;
        };
        const QString helperSha = pinnedHash(QDir(source).filePath("hardware_inference.h"));
        const QString adapterSha = pinnedHash(QDir(source).filePath("native_adapter.h"));
        const QString sdkSha = pinnedHash(QDir(source).filePath("../sdk/rknn_api.h"));
        emitJson({{"event", "identity"}, {"model_sha256", QString(ModelSha)}, {"runtime_path", runtime},
                  {"runtime_sha256", runtimeSha}, {"executable_sha256", fileHash(app.applicationFilePath())},
                  {"build_receipt_sha256", fileHash(receipt)}, {"fixture_manifest_sha256", fileHash(QDir(root).filePath("manifest.json"))},
                  {"helper_sha256", helperSha}, {"adapter_sha256", adapterSha}, {"sdk_sha256", sdkSha},
                  {"helper", "actual_frozen_candidate_HardwareInference"}, {"dequant_scale", "fp16"},
                  {"input", "candidate_RGB565_bit_replication_and_full_CPU_letterbox_UINT8_NHWC_pass_through_0"}});
        Context baseline;
        check(rknn_init(&baseline.ctx, const_cast<char *>(model.constData()), uint32_t(model.size()), 0, nullptr), "legacy_init");
        rknn_sdk_version version{};
        check(rknn_query(baseline.ctx, RKNN_QUERY_SDK_VERSION, &version, sizeof(version)), "runtime_version_query");
        emitJson({{"event", "version"}, {"api", QString::fromLatin1(version.api_version, int(strnlen(version.api_version, sizeof(version.api_version))))},
                  {"driver", QString::fromLatin1(version.drv_version, int(strnlen(version.drv_version, sizeof(version.drv_version))))}});
        rknn_input_output_num io{};
        check(rknn_query(baseline.ctx, RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io)), "IO_count_query");
        if (io.n_input != 1 || io.n_output != 4) throw std::runtime_error("one_input_four_outputs_required");
        rknn_tensor_attr input{};
        check(rknn_query(baseline.ctx, RKNN_QUERY_INPUT_ATTR, &input, sizeof(input)), "logical_input_query");
        emitJson({{"event", "logical_input"}, {"attr", attrJson(input)}});
        std::vector<rknn_tensor_attr> logical(4);
        const uint32_t expectedElements[] = {409600, 102400, 19200, 4800};
        for (uint32_t i = 0; i < 4; ++i) {
            logical[i].index = i;
            check(rknn_query(baseline.ctx, RKNN_QUERY_OUTPUT_ATTR, &logical[i], sizeof(logical[i])), "logical_attr_query");
            if (logical[i].n_elems != expectedElements[i]) throw std::runtime_error("pinned_output_elements_changed");
            emitJson({{"event", "logical_output"}, {"attr", attrJson(logical[i])}});
        }
        std::string reason;
        auto native = HardwareInference::create(model.constData(), size_t(model.size()), logical, true, reason);
        if (!native || !native->usesNativeInput()) throw std::runtime_error("actual_helper_setup_failed_" + reason);
        rknn_tensor_attr candidateInput{};
        check(rknn_query(native->context(), RKNN_QUERY_INPUT_ATTR, &candidateInput, sizeof(candidateInput)), "helper_input_metadata_query");
        emitJson({{"event", "helper_logical_input"}, {"attr", attrJson(candidateInput)}});
        for (uint32_t i = 0; i < 4; ++i) {
            rknn_tensor_attr attr{}; attr.index = i;
            check(rknn_query(native->context(), RKNN_QUERY_NATIVE_OUTPUT_ATTR, &attr, sizeof(attr)), "helper_native_output_metadata_query");
            emitJson({{"event", "helper_native_output"}, {"attr", attrJson(attr)}});
        }
        const int warmup = arg("--warmup", "5").toInt(), repeats = arg("--repeats", "3").toInt();
        if (warmup < 0 || warmup > 20 || repeats < 1 || repeats > 10) throw std::runtime_error("invalid_bounded_iteration_count");
        const QString prefix = arg("--save-arrays");
        if (!prefix.isEmpty() && !QDir().mkpath(prefix)) throw std::runtime_error("cannot_create_array_directory");
        for (int fi = 0; fi < 4; ++fi) {
            const auto fixture = fixtures[fi].toObject();
            const QByteArray rgb = inputImage(fixture, root);
            emitJson({{"event", "fixture"}, {"name", fixture.value("name")}, {"source_sha256", fixture.value("sha256")},
                      {"input_sha256", hash(rgb.constData(), size_t(rgb.size()))}, {"input_bytes", rgb.size()},
                      {"content_y", 80}, {"pad_value", 114}});
            for (int round = -warmup; round < repeats; ++round) {
                LegacyOutputs legacy(baseline.ctx, 4);
                rknn_input in{}; in.buf = const_cast<char *>(rgb.constData()); in.size = uint32_t(rgb.size());
                in.type = RKNN_TENSOR_UINT8; in.fmt = RKNN_TENSOR_NHWC; in.pass_through = 0;
                check(rknn_inputs_set(baseline.ctx, 1, &in), "legacy_inputs_set");
                check(rknn_run(baseline.ctx, nullptr), "legacy_run");
                check(rknn_outputs_get(baseline.ctx, 4, legacy.outs.data(), nullptr), "legacy_float_outputs_get");
                legacy.acquired = true;
                if (!native->writeInput(rgb.constData(), size_t(rgb.size()))) throw std::runtime_error(native->error());
                check(rknn_run(native->context(), nullptr), "actual_helper_context_run");
                if (!native->readOutputs()) throw std::runtime_error(native->error());
                if (round < 0) { legacy.release(); continue; }
                bool completionPassed = true;
                for (size_t oi = 0; oi < 4; ++oi) {
                    const auto &a = legacy.outs[oi], &b = native->outputs()[oi];
                    const size_t count = logical[oi].n_elems, size = count * sizeof(float);
                    if (!a.buf || !b.buf || a.size < size || b.size < size) throw std::runtime_error("output_buffer_bounds_invalid");
                    const auto *av = static_cast<const float *>(a.buf), *bv = static_cast<const float *>(b.buf);
                    size_t unequal = 0, outsideEpsilon = 0, nonfinite = 0;
                    double maxAbs = 0;
                    for (size_t i = 0; i < count; ++i) {
                        uint32_t ab = 0, bb = 0; std::memcpy(&ab, av + i, 4); std::memcpy(&bb, bv + i, 4);
                        unequal += ab != bb;
                        if (!std::isfinite(av[i]) || !std::isfinite(bv[i])) { ++nonfinite; continue; }
                        const double difference = std::abs(double(av[i]) - double(bv[i]));
                        maxAbs = std::max(maxAbs, difference); outsideEpsilon += difference > 1e-6;
                    }
                    const bool passed = unequal == 0 && outsideEpsilon == 0 && nonfinite == 0;
                    completionPassed &= passed;
                    QJsonObject event{{"event", "output_comparison"}, {"fixture", fixture.value("name")},
                        {"completion", round + 1}, {"output", int(oi)}, {"elements", double(count)},
                        {"bit_unequal", double(unequal)}, {"outside_1e_6", double(outsideEpsilon)},
                        {"nonfinite", double(nonfinite)}, {"max_abs", maxAbs}, {"passed", passed},
                        {"legacy_sha256", hash(a.buf, size)}, {"helper_sha256", hash(b.buf, size)}};
                    if (!prefix.isEmpty()) {
                        const QString stem = QDir(prefix).filePath(fixture.value("name").toString() + ".c" + QString::number(round + 1) + ".o" + QString::number(oi));
                        save(stem + ".legacy.f32", a.buf, size); save(stem + ".helper.f32", b.buf, size);
                        event.insert("legacy_array", stem + ".legacy.f32"); event.insert("helper_array", stem + ".helper.f32");
                    }
                    emitJson(event);
                }
                ++compared; if (!completionPassed) ++failed;
                legacy.release();
            }
        }
        emitJson({{"event", "summary"}, {"fixtures", 4}, {"compared_completions", compared}, {"failed_comparisons", failed},
                  {"warmups_per_fixture", warmup}, {"repeats_per_fixture", repeats}, {"compared_float_elements", double(compared) * 536000},
                  {"status", failed == 0 ? "actual_helper_array_parity_passed" : "actual_helper_array_parity_failed"},
                  {"passed", failed == 0}, {"hardware_parity_complete", failed == 0}, {"elements_per_completion", 536000},
                  {"helper_sha256", helperSha}, {"adapter_sha256", adapterSha}, {"sdk_sha256", sdkSha},
                  {"build_receipt_sha256", fileHash(receipt)}, {"gate", "all_float_bits_exact_and_finite_and_abs_le_1e_6"},
                  {"decoder_tested", false}, {"performance_claim", false}});
        return failed ? 2 : 0;
    } catch (const std::exception &e) {
        emitJson({{"event", "failure"}, {"reason", QString::fromStdString(e.what())}, {"compared_completions", compared},
                  {"failed_comparisons", failed}, {"status", "actual_helper_array_parity_failed"},
                  {"passed", false}, {"hardware_parity_complete", false}});
        return 1;
    }
}
