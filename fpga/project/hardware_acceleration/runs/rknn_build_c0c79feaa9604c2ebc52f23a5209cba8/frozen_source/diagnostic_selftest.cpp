// Host-only tests for diagnostic evidence handling. Never constructs Api,
// calls benchmark main(), loads librknnrt, or simulates NPU execution.
#define main rknn_io_benchmark_main_unused
#include "bench.cpp"
#undef main
#include <QTemporaryDir>
#include <climits>
#include <iostream>

static void require(bool ok, const char *why) { if (!ok) throw std::runtime_error(why); }
template<class F> static void rejects(F f, const char *why) {
    bool rejected = false;
    try { f(); } catch (const std::runtime_error &) { rejected = true; }
    require(rejected, why);
}
static std::vector<float> evidenceArray(const QString &root, const QJsonObject &row) {
    const QByteArray bytes = fileBytes(root + "/" + QFileInfo(row["path"].toString()).fileName());
    require(hash(bytes) == row["sha256"].toString(), "downloaded FP32 hash mismatch");
    require(bytes.size() == row["bytes"].toInt() && bytes.size() % int(sizeof(float)) == 0, "snapshot bytes");
    std::vector<float> result(size_t(bytes.size()) / sizeof(float));
    std::memcpy(result.data(), bytes.constData(), size_t(bytes.size()));
    return result;
}
static void checkEvidence(const QString &root) {
    std::vector<std::vector<float>> baseline(4), candidate(4);
    std::vector<rknn_tensor_attr> native(4);
    for (const QString &kind : {QString("baseline"), QString("candidate")}) {
        const auto lines = fileBytes(root + "/native_bright_baseline_cam1_cert_" + kind + ".stdout").split('\n');
        for (const auto &line : lines) {
            const auto row = QJsonDocument::fromJson(line).object();
            if (kind == "candidate" && row["event"] == "tensor" && row["query"].toInt() == 9) {
                const auto a = row["attr"].toObject(); const int i = a["index"].toInt();
                require(i >= 0 && i < 4, "reported native output index");
                native[size_t(i)].zp = a["zp"].toInt(); native[size_t(i)].scale = float(a["scale"].toDouble());
            }
            if (row["event"] == "output_snapshot" && row["completion"].toInt() == 1) {
                const int i = row["output"].toInt(); require(i >= 0 && i < 4, "snapshot output index");
                (kind == "baseline" ? baseline : candidate)[size_t(i)] = evidenceArray(root, row);
            }
        }
    }
    for (size_t i = 0; i < baseline.size(); ++i) {
        const auto report = diagnosticCompare(baseline[i], candidate[i]);
        require(!report["within_epsilon"].toBool() && report["outside_epsilon"].toDouble() > 0,
                "actual failed hardware arrays must fail diagnostic epsilon gate");
        const float zeroByte = float(-native[i].zp) * native[i].scale;
        require(std::all_of(candidate[i].begin(), candidate[i].end(), [=](float f) { return f == zeroByte; }),
                "downloaded native arrays equal reported dequantization of byte zero");
        emitJson({{"event", "local_archived_evidence"}, {"root", root}, {"output", double(i)},
                  {"zero_byte_affine", double(zeroByte)}, {"comparison", report}, {"new_hardware_execution", false}});
    }
}
static void checkScaleEvidence(const QString &nativeRoot, const QString &baselineRoot) {
    Meta m; m.outputs.resize(4);
    std::vector<std::vector<float>> oldNative(4), baseline(4), corrected(4);
    QJsonArray expectedDets;
    for (const auto &line : fileBytes(nativeRoot + "/supervisor.stdout").split('\n')) {
        const auto row = QJsonDocument::fromJson(line).object();
        if (row["event"] == "tensor" && row["query"].toInt() == 2) {
            const auto attr = row["attr"].toObject(); const int i = attr["index"].toInt();
            require(i >= 0 && i < 4, "full IO logical output index");
            auto &a = m.outputs[size_t(i)]; a.index = uint32_t(i); a.n_dims = uint32_t(attr["n_dims"].toInt());
            require(a.n_dims == 4, "full IO logical rank");
            for (uint32_t j = 0; j < a.n_dims; ++j) a.dims[j] = uint32_t(attr["dims"].toArray()[int(j)].toInt());
            a.n_elems = uint32_t(attr["n_elems"].toInt()); a.size = a.n_elems;
            a.fmt = static_cast<rknn_tensor_format>(attr["fmt"].toInt());
            a.type = static_cast<rknn_tensor_type>(attr["type"].toInt());
            a.qnt_type = static_cast<rknn_tensor_qnt_type>(attr["qnt_type"].toInt());
            a.zp = attr["zp"].toInt(); a.scale = float(attr["scale"].toDouble());
        }
        if (row["event"] == "output_snapshot" && row["completion"].toInt() == 1) {
            const int i = row["output"].toInt(); require(i >= 0 && i < 4, "full IO snapshot index");
            oldNative[size_t(i)] = evidenceArray(nativeRoot, row);
        }
    }
    for (const auto &line : fileBytes(baselineRoot + "/native_bright_baseline_cam1_cert_baseline.stdout").split('\n')) {
        const auto row = QJsonDocument::fromJson(line).object();
        if (row["event"] == "completion" && row["completion"].toInt() == 1) expectedDets = row["detections"].toArray();
        if (row["event"] == "output_snapshot" && row["completion"].toInt() == 1) {
            const int i = row["output"].toInt(); require(i >= 0 && i < 4, "full IO baseline index");
            baseline[size_t(i)] = evidenceArray(baselineRoot, row);
        }
    }
    for (size_t i = 0; i < 4; ++i) {
        const auto &a = m.outputs[i];
        require(a.type == RKNN_TENSOR_INT8 && oldNative[i].size() == a.n_elems &&
                baseline[i].size() == a.n_elems, "full IO archived logical elements");
        // Recover integer logical samples from the old FP32 adapter output.
        // This exercises scale arithmetic on archived data, NOT native layout
        // certification: actual raw memory must come from the new real probe.
        std::vector<uint8_t> logicalBytes(a.n_elems);
        for (size_t j = 0; j < oldNative[i].size(); ++j) {
            const long delta = std::lround(double(oldNative[i][j]) / a.scale), q = delta + a.zp;
            require(q >= -128 && q <= 127 && float(delta) * a.scale == oldNative[i][j], "recover exact old affine integer");
            logicalBytes[j] = uint8_t(q < 0 ? q + 256 : q);
        }
        auto contiguous = a;
        contiguous.n_dims = 3; contiguous.dims[0] = 1; contiguous.dims[1] = 1;
        contiguous.dims[2] = a.n_elems; contiguous.dims[3] = 0;
        const auto plan = NativePlan::make(contiguous, contiguous, NativePlan::DequantScale::Fp16);
        corrected[i].resize(a.n_elems);
        plan.convert(logicalBytes.data(), logicalBytes.size(), corrected[i]);
        require(corrected[i] == baseline[i], "archive scale-only conversion exactly equals every baseline float");
        emitJson({{"event", "local_archived_scale_evidence"}, {"output", double(i)},
                  {"effective_scale", double(plan.effectiveScale)}, {"elements", double(a.n_elems)},
                  {"exact_array_match", true}, {"raw_native_layout_certified", false}});
    }
    const auto decoded = detections(diagnosticDecode(corrected, m));
    require(expectedDets.size() == 2 && decoded == expectedDets, "archive corrected arrays reproduce exact baseline decoder tuples");
    emitJson({{"event", "local_archived_scale_detections"}, {"exact_tuple_match", true},
              {"detections", decoded}, {"new_hardware_execution", false}, {"fixtures", 1}});
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    try {
        const std::vector<float> reference{0, 1, -1000}, equal = reference;
        require(diagnosticCompare(reference, equal)["within_epsilon"].toBool(), "identical arrays");
        auto changed = reference; changed[0] = 0.5e-6f;
        require(diagnosticCompare(reference, changed)["within_epsilon"].toBool(), "absolute tolerance");
        changed[2] += 0.0005f;
        require(diagnosticCompare(reference, changed)["within_epsilon"].toBool(), "relative tolerance");
        changed[1] = 1.01f;
        auto report = diagnosticCompare(reference, changed);
        require(!report["within_epsilon"].toBool() && report["outside_epsilon"].toInt() == 1 &&
                report["first_mismatch"].toObject()["index"].toInt() == 1, "first numerical mismatch");
        changed[1] = std::numeric_limits<float>::quiet_NaN();
        require(!diagnosticCompare(reference, changed)["within_epsilon"].toBool(), "NaN rejects parity");
        changed[1] = std::numeric_limits<float>::infinity();
        require(diagnosticCompare(reference, changed)["nonfinite_elements"].toInt() == 1, "infinity counted");
        rejects([&] { diagnosticCompare({}, equal); }, "empty comparison rejected");
        rejects([&] { diagnosticCompare(reference, {0}); }, "size mismatch rejected");
        rejects([&] { diagnosticBytes(nullptr, 8); }, "null byte buffer rejected");
        rejects([&] { diagnosticBytes(reference.data(), 0); }, "empty byte buffer rejected");
        rejects([&] { diagnosticBytes(reference.data(), size_t(INT_MAX) + 1); }, "QByteArray overflow rejected");
        QTemporaryDir dir("validation/diagnostic_selftest_XXXXXX");
        require(dir.isValid(), "owned temporary directory");
        const QString path = dir.path() + "/raw.u8";
        const QByteArray blob = QByteArray::fromHex("00a57f80ff");
        const QJsonObject binding{{"dims", QJsonArray{1, 2, 80, 80, 8}}, {"pass_through", 0}, {"zp", 83}};
        diagnosticSave(path, blob, {{"phase", "native_before_get"}, {"binding_attr", binding}});
        const auto metadata = QJsonDocument::fromJson(fileBytes(path + ".json")).object();
        require(fileBytes(path) == blob && metadata["sha256"].toString() == hash(blob), "raw bytes and hash roundtrip");
        require(metadata["binding_attr"].toObject() == binding && metadata["binding_attr_sha256"].toString() ==
                hash(QJsonDocument(binding).toJson(QJsonDocument::Compact)), "exact binding attrs and hash roundtrip");
        rejects([&] { diagnosticSave(path, QByteArray("changed"), {}); }, "existing evidence cannot be overwritten");
        require(fileBytes(path) == blob, "existing evidence preserved");
        for (int i = 1; i < argc; ++i) {
            const QString root = QString::fromLocal8Bit(argv[i]);
            if (QFileInfo::exists(root + "/supervisor.stdout")) {
                require(argc >= 2, "archived full IO comparison needs baseline directory");
                checkScaleEvidence(root, QString::fromLocal8Bit(argv[1]));
            } else checkEvidence(root);
        }
        std::cout << "diagnostic evidence handling completed; no RKNN library or hardware execution\n";
        return 0;
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 1; }
}
