#ifndef VIEWER_NATIVE_CANDIDATE_QT_HPP
#define VIEWER_NATIVE_CANDIDATE_QT_HPP

#include "viewer_native_guard.hpp"
#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QSet>
#include <cstdio>
#include <optional>

namespace viewer_native {
struct Session {
    bool enabled = false;
    bool run_fallback_reported = false;
    quint64 context_serial = 0;
    std::vector<rknn_tensor_attr> attrs;
    std::optional<raw_dfl::NativeDecoder> decoder;
    float confidence = -1.0f;
};

inline void report(const QString& model, quint64 serial, bool enabled, const std::string& reason) {
    fprintf(stderr, "[v8-native-candidate] context=%llu model=%s mode=%s reason=%s\n",
            static_cast<unsigned long long>(serial), qPrintable(model), enabled ? "native" : "existing-float",
            reason.c_str());
    fflush(stderr);
}

inline std::string hash_mapped_runtime(bool& verified, std::string& reason) {
    verified = false;
    QFile maps("/proc/self/maps");
    if (!maps.open(QIODevice::ReadOnly)) { reason = "cannot read /proc/self/maps"; return {}; }
    const QByteArray original_maps = maps.readAll();
    const auto paths = mapped_runtime_paths(original_maps.toStdString());
    if (!paths.error.empty()) { reason = paths.error; return {}; }
    QSet<QString> canonical_paths;
    for (const auto& path : paths.paths) {
        const QFileInfo info(QString::fromStdString(path));
        const QString canonical = info.canonicalFilePath();
        if (canonical.isEmpty() || !info.isFile()) { reason = "mapped runtime file is unavailable"; return {}; }
        canonical_paths.insert(canonical);
    }
    if (canonical_paths.size() != 1) { reason = "multiple canonical RKNN runtime files are mapped"; return {}; }
    const QString path = *canonical_paths.cbegin();
    QFile library(path);
    if (!library.open(QIODevice::ReadOnly)) { reason = "cannot open canonical loaded runtime file"; return {}; }
    QCryptographicHash hash(QCryptographicHash::Sha256);
    if (!hash.addData(&library)) { reason = "loaded runtime SHA256 read failed"; return {}; }
    // Changes to mapped RKNN path identity during the hash are not accepted.
    maps.close();
    if (!maps.open(QIODevice::ReadOnly)) { reason = "cannot recheck runtime mappings"; return {}; }
    const auto after = mapped_runtime_paths(maps.readAll().toStdString());
    if (!after.error.empty() || after.paths != paths.paths) { reason = "runtime mappings changed during fingerprint"; return {}; }
    verified = true;
    return hash.result().toHex().toStdString();
}

inline Session prepare(rknn_context context, const QByteArray& model_bytes, const QString& model_path,
                       unsigned outputs, int classes, bool lane, quint64 serial) {
    Session session;
    session.context_serial = serial;
    if (!opt_in(qgetenv("DET_V8_NATIVE").toStdString())) return session;
    auto fallback = [&](const std::string& reason) {
        report(model_path, serial, false, reason);
        session.attrs.clear();
        return session;
    };
    try {
        Identity id;
        id.model_sha = QCryptographicHash::hash(model_bytes, QCryptographicHash::Sha256).toHex().toStdString();
        // Other models incur no extra RKNN queries and retain their original decoder.
        if (id.model_sha != kModelSha) return fallback("model SHA256 is outside pinned V8 profile");
        std::string reason;
        id.runtime_sha = hash_mapped_runtime(id.one_canonical_mapped_runtime, reason);
        if (!id.one_canonical_mapped_runtime) return fallback(reason);
        rknn_sdk_version version{};
        int ret = rknn_query(context, RKNN_QUERY_SDK_VERSION, &version, sizeof(version));
        if (ret != RKNN_SUCC) return fallback("RKNN_QUERY_SDK_VERSION ret=" + std::to_string(ret));
        if (!terminated(version.api_version, sizeof(version.api_version)) ||
            !terminated(version.drv_version, sizeof(version.drv_version)))
            return fallback("unterminated SDK/driver version");
        id.api = version.api_version; id.driver = version.drv_version;
        id.inputs = 1; id.outputs = outputs; id.classes = classes; id.lane = lane;
        id.int8_input_override = qEnvironmentVariableIsSet("DET_INT8_IN");
        rknn_tensor_attr input{};
        ret = rknn_query(context, RKNN_QUERY_INPUT_ATTR, &input, sizeof(input));
        if (ret != RKNN_SUCC) return fallback("RKNN_QUERY_INPUT_ATTR ret=" + std::to_string(ret));
        if (outputs != 6) return fallback("native profile requires six outputs");
        session.attrs.resize(6);
        for (unsigned i = 0; i != 6; ++i) {
            session.attrs[i].index = i;
            ret = rknn_query(context, RKNN_QUERY_OUTPUT_ATTR, &session.attrs[i], sizeof(rknn_tensor_attr));
            if (ret != RKNN_SUCC)
                return fallback("RKNN_QUERY_OUTPUT_ATTR index=" + std::to_string(i) + " ret=" + std::to_string(ret));
        }
        const auto decision = check_profile(true, id, input, session.attrs);
        if (!decision.enabled) return fallback(decision.reason);
        session.enabled = true;
        report(model_path, serial, true, decision.reason);
        return session;
    } catch (const std::exception& e) { return fallback(e.what()); }
      catch (...) { return fallback("unexpected native profile preparation failure"); }
}
} // namespace viewer_native
#endif
