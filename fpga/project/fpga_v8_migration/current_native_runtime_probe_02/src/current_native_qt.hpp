#pragma once
#include "viewer_native_qt.hpp"
#include "current_native_gate.hpp"

namespace viewer_native {
// Consume the production cache; never requery input/output attributes.
inline Session prepare_current(rknn_context context, const QByteArray& model_bytes,
                               const QString& model_path, unsigned inputs, unsigned outputs,
                               int classes, bool lane, bool trafficlight, int width, int height,
                               const rknn_tensor_attr& input,
                               const std::vector<rknn_tensor_attr>& attrs, quint64 serial) {
    Session session;
    session.context_serial = serial;
    if (!opt_in(qgetenv("DET_V8_NATIVE").toStdString())) return session;
    auto fallback = [&](const std::string& reason) {
        report(model_path, serial, false, reason);
        session.attrs.clear();
        return session;
    };
    const int channels = input.n_dims == 4 ? static_cast<int>(
        input.fmt == RKNN_TENSOR_NHWC ? input.dims[3] :
        input.fmt == RKNN_TENSOR_NCHW ? input.dims[1] : 0) : 0;
    if (!current_geometry_gate(trafficlight, width, height, channels))
        return fallback("current native requires non-trafficlight 640x640 RGB3");
    try {
        Identity id;
        id.model_sha = QCryptographicHash::hash(model_bytes, QCryptographicHash::Sha256).toHex().toStdString();
        if (id.model_sha != kModelSha) return fallback("model SHA256 is outside pinned V8 profile");
        id.inputs = inputs; id.outputs = outputs; id.classes = classes; id.lane = lane;
        id.int8_input_override = qEnvironmentVariableIsSet("DET_INT8_IN");
        if (inputs != 1 || outputs != 6 || classes != 3 || lane || id.int8_input_override)
            return fallback("current input/model settings require existing float path");
        std::string reason;
        id.runtime_sha = hash_mapped_runtime(id.one_canonical_mapped_runtime, reason);
        if (!id.one_canonical_mapped_runtime) return fallback(reason);
        rknn_sdk_version version{};
        const int ret = rknn_query(context, RKNN_QUERY_SDK_VERSION, &version, sizeof(version));
        if (ret != RKNN_SUCC) return fallback("RKNN_QUERY_SDK_VERSION ret=" + std::to_string(ret));
        if (!terminated(version.api_version, sizeof(version.api_version)) ||
            !terminated(version.drv_version, sizeof(version.drv_version)))
            return fallback("unterminated SDK/driver version");
        id.api = version.api_version; id.driver = version.drv_version;
        const auto decision = check_current_profile(true, id, input, attrs, trafficlight, width, height, channels);
        if (!decision.enabled) return fallback(decision.reason);
        session.attrs = attrs;
        session.enabled = true;
        report(model_path, serial, true, decision.reason);
        return session;
    } catch (const std::exception& e) { return fallback(e.what()); }
      catch (...) { return fallback("unexpected native profile preparation failure"); }
}
} // namespace viewer_native
