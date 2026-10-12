#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStringList>
#include <dlfcn.h>
#include <time.h>
#include <cstdio>
#include <memory>
#include <stdexcept>
#include "prepared/frozen_decoder.h"
#include "native_adapter.h"
#include "single_copy_input.h"
#include "dma_heap_import.h"
#include "fd_binding_policy.h"

static const char *MODEL_SHA = "21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31";
static void emitJson(QJsonObject o) {
    const QByteArray b = QJsonDocument(o).toJson(QJsonDocument::Compact);
    std::printf("%s\n", b.constData()); std::fflush(stdout);
}
static QString text(const char *data, size_t size) {
    return QString::fromUtf8(data, int(strnlen(data, size)));
}
static QByteArray fileBytes(const QString &path) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) throw std::runtime_error(("cannot open " + path).toStdString());
    const QByteArray data = f.readAll();
    if (f.error() != QFile::NoError) throw std::runtime_error("file read failed");
    return data;
}
static QString hash(const QByteArray &bytes) {
    return QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex();
}
static void check(int rc, const std::string &stage) {
    if (rc != RKNN_SUCC) throw std::runtime_error(stage + " rc=" + std::to_string(rc));
}
static double now(clockid_t id) {
    timespec ts{};
    if (clock_gettime(id, &ts)) throw std::runtime_error("clock_gettime failed");
    return double(ts.tv_sec) * 1000.0 + double(ts.tv_nsec) / 1e6;
}
struct Stamp {
    double wall = now(CLOCK_MONOTONIC), cpu = now(CLOCK_THREAD_CPUTIME_ID);
};
struct Duration {
    double wall, cpu;
    Duration(double w = 0, double c = 0) : wall(w), cpu(c) {}
};
static Duration since(const Stamp &s) { return {now(CLOCK_MONOTONIC) - s.wall, now(CLOCK_THREAD_CPUTIME_ID) - s.cpu}; }
static QJsonObject timing(const Duration &t) { return {{"wall_ms", t.wall}, {"thread_cpu_ms", t.cpu}}; }

// Bind all declarations directly to the retained SDK. Optional newer symbols
// are resolved separately so their absence cannot break the baseline/probe.
struct Api {
    void *lib = nullptr;
    DmaHeapImport::RuntimeLibraryLifetime runtimeLifetime;
    QString runtimeSha;
    decltype(&rknn_init) init = nullptr;
    decltype(&rknn_destroy) destroy = nullptr;
    decltype(&rknn_query) query = nullptr;
    decltype(&rknn_inputs_set) inputs = nullptr;
    decltype(&rknn_run) run = nullptr;
    decltype(&rknn_outputs_get) get = nullptr;
    decltype(&rknn_outputs_release) release = nullptr;
    decltype(&rknn_create_mem) create = nullptr;
    decltype(&rknn_create_mem2) create2 = nullptr;
    decltype(&rknn_create_mem_from_fd) importFd = nullptr;
    decltype(&rknn_destroy_mem) destroyMem = nullptr;
    decltype(&rknn_set_io_mem) setMem = nullptr;
    decltype(&rknn_mem_sync) sync = nullptr;
    template<class F> F symbol(const char *name, bool required) {
        dlerror();
        F f = reinterpret_cast<F>(dlsym(lib, name));
        if (!f && required) throw std::runtime_error(std::string("missing runtime symbol ") + name);
        return f;
    }
    explicit Api(const QString &path) {
        lib = dlopen(path.toLocal8Bit().constData(), RTLD_NOW | RTLD_LOCAL);
        if (!lib) { const char *e = dlerror(); throw std::runtime_error(e ? e : "dlopen failed"); }
        init = symbol<decltype(init)>("rknn_init", true);
        destroy = symbol<decltype(destroy)>("rknn_destroy", true);
        query = symbol<decltype(query)>("rknn_query", true);
        inputs = symbol<decltype(inputs)>("rknn_inputs_set", true);
        run = symbol<decltype(run)>("rknn_run", true);
        get = symbol<decltype(get)>("rknn_outputs_get", true);
        release = symbol<decltype(release)>("rknn_outputs_release", true);
        create = symbol<decltype(create)>("rknn_create_mem", false);
        create2 = symbol<decltype(create2)>("rknn_create_mem2", false);
        importFd = symbol<decltype(importFd)>("rknn_create_mem_from_fd", false);
        destroyMem = symbol<decltype(destroyMem)>("rknn_destroy_mem", false);
        setMem = symbol<decltype(setMem)>("rknn_set_io_mem", false);
        sync = symbol<decltype(sync)>("rknn_mem_sync", false);
        Dl_info info{};
        if (!dladdr(reinterpret_cast<void *>(init), &info) || !info.dli_fname)
            throw std::runtime_error("cannot identify resolved runtime library");
        const QString resolved = QFileInfo(QString::fromLocal8Bit(info.dli_fname)).canonicalFilePath();
        runtimeSha = hash(fileBytes(resolved));
        emitJson({{"event", "runtime_library"}, {"path", resolved}, {"sha256", runtimeSha},
                  {"create_mem", bool(create)}, {"create_mem2", bool(create2)}, {"create_mem_from_fd", bool(importFd)},
                  {"destroy_mem", bool(destroyMem)}, {"set_io_mem", bool(setMem)}, {"mem_sync", bool(sync)},
                  {"sizeof_context", int(sizeof(rknn_context))}, {"sizeof_tensor_attr", int(sizeof(rknn_tensor_attr))},
                  {"sizeof_tensor_mem", int(sizeof(rknn_tensor_mem))}, {"sizeof_input", int(sizeof(rknn_input))},
                  {"sizeof_output", int(sizeof(rknn_output))}, {"sizeof_sdk_version", int(sizeof(rknn_sdk_version))}});
    }
    ~Api() { runtimeLifetime.unload(lib, &dlclose); }
};

// Separate ownership domain; legacy Session allocation/teardown stays unchanged.
static QJsonObject memoryJson(const rknn_tensor_mem *m);
static QJsonObject importedRetirementJson(const DmaHeapImport::MemorySessionOwnedRAII &owned,
                                         const DmaHeapImport::RuntimeLibraryLifetime &runtime, const QString &purpose, bool ok) {
    QJsonArray buffers;
    // Only caller-owned bookkeeping is read. Runtime descriptors may already
    // be invalid or still device-owned and must never be dereferenced here.
    for (const auto &ptr : owned.buffers) {
        const auto &b = *ptr;
        QJsonObject counts;
        const char *names[] = {"start_read", "end_read", "start_write", "end_write"};
        for (int i = 0; i < 4; ++i) {
            const auto &c = b.sync[i];
            counts[names[i]] = QJsonObject{{"attempts", double(c.attempts)}, {"success", double(c.success)},
                {"failures", double(c.failures)}, {"eintr", double(c.interrupted)}, {"last_rc", c.lastRc}};
        }
        buffers.append(QJsonObject{{"role", QString::fromStdString(b.role)}, {"mapping_bytes", double(b.mappingBytes)},
            {"st_dev", QString::number(b.original.device)}, {"st_ino", QString::number(b.original.inode)},
            {"before_destroy_fd_identity", b.beforeFd}, {"before_destroy_mapping", b.beforeMap},
            {"after_import_destroy_fd_identity", b.afterImportFd}, {"after_import_destroy_mapping", b.afterImportMap},
            {"after_context_destroy_fd_identity", b.afterContextFd}, {"after_context_destroy_mapping", b.afterContextMap},
            {"before_destroy_inspected", b.beforeInspected}, {"after_import_destroy_inspected", b.afterImportInspected},
            {"after_context_destroy_inspected", b.afterContextInspected},
            {"destroy_mem_attempted", b.destroyAttempted}, {"destroy_mem_skipped", !b.destroyAttempted},
            {"destroy_mem_rc", b.destroyAttempted ? QJsonValue(b.destroyRc) : QJsonValue()},
            {"munmap_attempted", b.unmapAttempted}, {"munmap_skipped", !b.unmapAttempted},
            {"munmap_rc", b.unmapAttempted ? QJsonValue(b.unmapRc) : QJsonValue()},
            {"close_attempted", b.closeAttempted}, {"close_skipped", !b.closeAttempted},
            {"close_rc", b.closeAttempted ? QJsonValue(b.closeRc) : QJsonValue()},
            {"import_descriptor_retained", b.memory != nullptr}, {"owned_buffer_retained", b.fd >= 0 || b.mapping != nullptr},
            {"cpu_access", counts}, {"cpu_active", b.cpuActive}});
    }
    return {{"event", "dma_heap_retirement"}, {"purpose", purpose}, {"cleanup_ok", ok},
            {"retirement_branch", owned.retirementBranch}, {"process_teardown_only", owned.processTeardownOnly},
            {"release_boundary", owned.processTeardownOnly ? "process_teardown" : "explicit_retirement"},
            {"context_destroy_attempted", owned.contextDestroyAttempted}, {"context_destroy_skipped", !owned.contextDestroyAttempted},
            {"context_destroy_rc", owned.contextDestroyAttempted ? QJsonValue(owned.contextDestroyRc) : QJsonValue()},
            {"context_retained", owned.retainedContext != 0}, {"retained_context_hex", QString::number(owned.retainedContext, 16)},
            {"runtime_library_retained", runtime.retainedUntilProcessTeardown},
            {"fatal_no_continue", owned.processTeardownOnly}, {"buffers", buffers},
            {"order", owned.processTeardownOnly ? "external_release_skipped_process_teardown_only" :
                      "paired_cpu_end_then_imports_then_context_then_owned_munmap_close"},
            {"hardware_certified", false}, {"performance_claim", false}};
}
struct ImportedSession {
    Api &api;
    DmaHeapImport::LinuxOperations operations;
    DmaHeapImport::MemorySessionOwnedRAII owned;
    QString purpose;
    bool reported = false;
    ImportedSession(Api &api, rknn_context &ctx, const QString &why)
        : api(api), operations(api.importFd, api.destroyMem, api.destroy), owned(operations, ctx, api.runtimeLifetime), purpose(why) {
        emitJson({{"event", "dma_heap_session_started"}, {"purpose", purpose}});
    }
    ~ImportedSession() { retire(); }
    rknn_tensor_mem *allocate(size_t bytes, const QString &role) {
        auto &b = owned.allocate(bytes, role.toStdString());
        emitJson({{"event", "memory"}, {"role", role}, {"allocator", "dma_heap_system_fd_import"},
                  {"purpose", purpose}, {"heap_path", "/dev/dma_heap/system"}, {"offset", 0},
                  {"page_size", double(operations.pageSize())}, {"requested_size", double(bytes)},
                  {"mapping_bytes", double(b.mappingBytes)}, {"size", double(b.memory->size)}, {"fd", b.fd},
                  {"st_dev", QString::number(b.original.device)}, {"st_ino", QString::number(b.original.inode)},
                  {"metadata", memoryJson(b.memory)}, {"map_shared", true}, {"flags_modified", false}});
        return b.memory;
    }
    bool retire() noexcept {
        const bool ok = owned.retire();
        if (reported) return ok;
        reported = true;
        try {
            emitJson(importedRetirementJson(owned, api.runtimeLifetime, purpose, ok));
        } catch (...) { return false; }
        return ok;
    }
};

static void verifyImportSymbol(Api &api) {
    if (!api.importFd || !api.destroyMem || !api.setMem || !api.sync)
        throw std::runtime_error("FD import symbols unavailable (from_fd/destroy/set/sync)");
    Dl_info info{};
    if (!dladdr(reinterpret_cast<void *>(api.importFd), &info) || !info.dli_fname)
        throw std::runtime_error("cannot identify FD importer symbol provider");
    const QString provider = QFileInfo(QString::fromLocal8Bit(info.dli_fname)).canonicalFilePath();
    const QString providerSha = hash(fileBytes(provider));
    emitJson({{"event", "dma_heap_import_symbol"}, {"symbol", "rknn_create_mem_from_fd"},
              {"address_hex", QString::number(reinterpret_cast<uintptr_t>(api.importFd), 16)},
              {"provider_path", provider}, {"provider_sha256", providerSha}, {"runtime_sha256", api.runtimeSha},
              {"exact_sdk_signature", true}, {"offset", 0}});
    if (providerSha != api.runtimeSha) throw std::runtime_error("FD importer provider differs from resolved RKNN runtime");
}

static QJsonObject attrJson(const rknn_tensor_attr &a) {
    QJsonArray dims, allDims;
    for (uint32_t i = 0; i < RKNN_MAX_DIMS; ++i) {
        allDims.append(double(a.dims[i]));
        if (i < a.n_dims) dims.append(double(a.dims[i]));
    }
    return {{"index", double(a.index)}, {"name", text(a.name, sizeof(a.name))},
            {"n_dims", double(a.n_dims)}, {"dims", dims}, {"dims_all", allDims},
            {"n_elems", double(a.n_elems)}, {"size", double(a.size)},
            {"fmt", int(a.fmt)}, {"fmt_name", get_format_string(a.fmt)},
            {"type", int(a.type)}, {"type_name", get_type_string(a.type)},
            {"qnt_type", int(a.qnt_type)}, {"qnt_name", get_qnt_type_string(a.qnt_type)},
            {"fl", int(a.fl)}, {"zp", double(a.zp)}, {"scale", double(a.scale)},
            {"w_stride", double(a.w_stride)}, {"size_with_stride", double(a.size_with_stride)},
            {"pass_through", int(a.pass_through)}, {"h_stride", double(a.h_stride)}};
}
static QJsonObject memoryJson(const rknn_tensor_mem *m) {
    if (!m) return {};
    return {{"descriptor_hex", QString::number(reinterpret_cast<uintptr_t>(m), 16)},
            {"virt_addr_hex", QString::number(reinterpret_cast<uintptr_t>(m->virt_addr), 16)},
            {"phys_addr_hex", QString::number(m->phys_addr, 16)}, {"fd", m->fd}, {"offset", m->offset},
            {"size", double(m->size)}, {"flags", double(m->flags)}};
}
static void emitBinding(QJsonObject event, bool fdImport) {
    std::string policyError;
    if (fdImport) {
        event["binding_device_address_policy"] = FdBindingDeviceAddressPolicy;
        event["binding_device_address_resolved"] = false;
        if (event["rc"].toInt() == RKNN_SUCC) {
            try {
                event["binding_device_address_resolved"] = validateFdBinding(event["before"].toObject(), event["after"].toObject(),
                    event["memory_before"].toObject(), event["memory_after"].toObject());
            } catch (const std::runtime_error &e) {
                policyError = e.what();
                event["binding_policy_error"] = QString::fromStdString(policyError);
            }
        }
    }
    emitJson(event); // Preserve truthful memory_changed and failed binding evidence.
    if (!policyError.empty()) throw std::runtime_error(policyError);
}
static QJsonArray detections(const QVector<Detection> &ds) {
    QJsonArray result;
    for (const auto &d : ds) result.append(QJsonObject{{"class", d.cls}, {"score", double(d.score)},
        {"x1", double(d.x1)}, {"y1", double(d.y1)}, {"x2", double(d.x2)}, {"y2", double(d.y2)}});
    return result;
}
struct Meta {
    rknn_tensor_attr input{};
    std::vector<rknn_tensor_attr> outputs, native;
    std::vector<int> nativeRc;
};
static Meta queryMeta(Api &api, rknn_context ctx, int nativeQuery) {
    rknn_sdk_version version{};
    const int vrc = api.query(ctx, RKNN_QUERY_SDK_VERSION, &version, sizeof(version));
    emitJson({{"event", "version"}, {"rc", vrc}, {"api", text(version.api_version, sizeof(version.api_version))},
              {"driver", text(version.drv_version, sizeof(version.drv_version))}});
    check(vrc, "RKNN_QUERY_SDK_VERSION");
    rknn_input_output_num io{};
    check(api.query(ctx, RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io)), "RKNN_QUERY_IN_OUT_NUM");
    emitJson({{"event", "io_count"}, {"n_input", double(io.n_input)}, {"n_output", double(io.n_output)}});
    if (io.n_input != 1 || !io.n_output || io.n_output > 64) throw std::runtime_error("unsupported input/output count");
    Meta m;
    check(api.query(ctx, RKNN_QUERY_INPUT_ATTR, &m.input, sizeof(m.input)), "RKNN_QUERY_INPUT_ATTR");
    emitJson({{"event", "tensor"}, {"query", int(RKNN_QUERY_INPUT_ATTR)}, {"rc", 0}, {"attr", attrJson(m.input)}});
    // Report both SDK-supported native query variants even when one is absent.
    for (int q : {int(RKNN_QUERY_NATIVE_INPUT_ATTR), int(RKNN_QUERY_NATIVE_NHWC_INPUT_ATTR)}) {
        rknn_tensor_attr a{};
        int rc = api.query(ctx, static_cast<rknn_query_cmd>(q), &a, sizeof(a));
        emitJson({{"event", "tensor"}, {"query", q}, {"rc", rc}, {"attr", attrJson(a)}});
    }
    m.outputs.resize(io.n_output); m.native.resize(io.n_output); m.nativeRc.resize(io.n_output);
    for (uint32_t i = 0; i < io.n_output; ++i) {
        auto &l = m.outputs[i]; l.index = i;
        check(api.query(ctx, RKNN_QUERY_OUTPUT_ATTR, &l, sizeof(l)), "RKNN_QUERY_OUTPUT_ATTR");
        emitJson({{"event", "tensor"}, {"query", int(RKNN_QUERY_OUTPUT_ATTR)}, {"rc", 0}, {"attr", attrJson(l)}});
        if (NativePlan::product(l) != l.n_elems) throw std::runtime_error("logical element product mismatch");
        for (int q : {int(RKNN_QUERY_NATIVE_OUTPUT_ATTR), int(RKNN_QUERY_NATIVE_NHWC_OUTPUT_ATTR)}) {
            rknn_tensor_attr a{}; a.index = i;
            const int rc = api.query(ctx, static_cast<rknn_query_cmd>(q), &a, sizeof(a));
            emitJson({{"event", "tensor"}, {"query", q}, {"rc", rc}, {"attr", attrJson(a)}});
            if (q == nativeQuery) { m.native[i] = a; m.nativeRc[i] = rc; }
        }
    }
    return m;
}

struct Session {
    Api &api;
    rknn_context ctx = 0;
    std::vector<rknn_tensor_mem *> memories;
    explicit Session(Api &a) : api(a) {}
    ~Session() {
        if (ctx) {
            for (auto *m : memories) if (m && api.destroyMem) api.destroyMem(ctx, m);
            api.destroy(ctx);
        }
    }
    rknn_tensor_mem *allocate(uint32_t bytes, const QString &role, const QString &allocator = "auto") {
        if ((!api.create && !api.create2) || !api.destroyMem || !api.setMem || !api.sync)
            throw std::runtime_error("native memory symbols unavailable (create/destroy/set/sync)");
        const QString choice = allocator == "auto" ? (api.create2 ? "cacheable2" : "create") : allocator;
        const bool useCreate2 = choice != "create";
        const uint64_t flags = choice == "noncacheable2" ? RKNN_FLAG_MEMORY_NON_CACHEABLE :
                               choice == "cacheable2" ? RKNN_FLAG_MEMORY_CACHEABLE : RKNN_FLAG_MEMORY_FLAGS_DEFAULT;
        if (choice != "create" && choice != "default2" && choice != "cacheable2" && choice != "noncacheable2")
            throw std::runtime_error("invalid native allocator");
        if ((useCreate2 && !api.create2) || (!useCreate2 && !api.create))
            throw std::runtime_error("requested diagnostic allocator symbol unavailable");
        rknn_tensor_mem *m = useCreate2 ? api.create2(ctx, uint64_t(bytes), flags) : api.create(ctx, bytes);
        if (!m) throw std::runtime_error("rknn_create_mem allocation failed");
        memories.push_back(m);
        if (!m->virt_addr || m->size < bytes) throw std::runtime_error("runtime returned undersized/unmapped memory");
        emitJson({{"event", "memory"}, {"role", role}, {"allocator", useCreate2 ? "create_mem2_" + choice : "create_mem"},
                  {"native_allocator", choice}, {"alloc_flags", useCreate2 ? QJsonValue(double(flags)) : QJsonValue()},
                  {"metadata", memoryJson(m)},
                  {"requested_size", double(bytes)}, {"size", double(m->size)}, {"fd", m->fd},
                  {"offset", m->offset}, {"flags", double(m->flags)}, {"phys_addr_hex", QString::number(m->phys_addr, 16)}});
        return m;
    }
};
struct Fixture { QByteArray rgb, source; QString path, kind; };
static Fixture loadFixture(const QString &path, const QString &kind) {
    Fixture f; f.path = path; f.kind = kind; f.source = fileBytes(path);
    f.rgb.resize(MODEL_SIZE); std::memset(f.rgb.data(), 114, MODEL_SIZE);
    if (kind == "rgb565_le") {
        if (f.source.size() != 640 * 480 * 2) throw std::runtime_error("RGB565 fixture size must be 640x480x2");
        const uint16_t endian = 1;
        if (*reinterpret_cast<const unsigned char *>(&endian) != 1) throw std::runtime_error("RGB565 fixture requires little-endian host");
        for (int y = 0; y < 480; ++y)
            rgb565ToRgb888Line(reinterpret_cast<const uint8_t *>(f.source.constData()) + y * 1280, 640,
                             reinterpret_cast<uint8_t *>(f.rgb.data()) + (y + 80) * 1920);
    } else if (kind == "png") {
        QImage im = QImage::fromData(f.source, "PNG").convertToFormat(QImage::Format_RGB888);
        if (im.isNull() || im.width() != 640 || im.height() != 480) throw std::runtime_error("PNG fixture must be full 640x480");
        for (int y = 0; y < 480; ++y) std::memcpy(f.rgb.data() + (y + 80) * 1920, im.constScanLine(y), 1920);
    } else throw std::runtime_error("unknown fixture kind");
    emitJson({{"event", "fixture"}, {"path", path}, {"kind", kind}, {"source_sha256", hash(f.source)},
              {"input_sha256", hash(f.rgb)}, {"input_bytes", f.rgb.size()}, {"pad_value", 114},
              {"content_y", 80}, {"content_width", 640}, {"content_height", 480}});
    return f;
}
static void validateInput(const rknn_tensor_attr &a) {
    if (a.n_dims != 4 || a.dims[0] != 1 || a.n_elems != MODEL_SIZE ||
        !((a.fmt == RKNN_TENSOR_NHWC && a.dims[1] == 640 && a.dims[2] == 640 && a.dims[3] == 3) ||
          (a.fmt == RKNN_TENSOR_NCHW && a.dims[1] == 3 && a.dims[2] == 640 && a.dims[3] == 640)))
        throw std::runtime_error("queried input is not batch1 RGB 640x640");
}
enum Stage { InputSet, InputSync, Run, OutputsGet, OutputSync, Conversion, Decode, SnapshotCopy, Release, StageCount };
static const char *stageNames[StageCount] = {"input_set_or_copy", "input_sync", "run", "outputs_get",
    "output_sync", "deblock_dequantize", "decode", "snapshot_copy", "release"};
struct Record {
    Duration stages[StageCount];
    QVector<Detection> dets;
    Duration total;
};
static QJsonObject stagesJson(const Record &r) {
    QJsonObject result;
    for (int i = 0; i < StageCount; ++i) result[stageNames[i]] = timing(r.stages[i]);
    return result;
}
struct Snapshot {
    int completion = 0;
    std::vector<std::vector<float>> arrays;
    QVector<Detection> dets;
};
static void writeSnapshot(const QString &prefix, const Snapshot &s) {
    for (size_t i = 0; i < s.arrays.size(); ++i) {
        const auto &v = s.arrays[i];
        for (float x : v) if (!std::isfinite(x)) throw std::runtime_error("nonfinite float output");
        const QString path = prefix + ".c" + QString::number(s.completion) + ".o" + QString::number(i) + ".f32";
        QFile f(path);
        if (!f.open(QIODevice::WriteOnly | QIODevice::NewOnly)) throw std::runtime_error("snapshot exists or cannot be created");
        const qint64 bytes = qint64(v.size() * sizeof(float));
        if (f.write(reinterpret_cast<const char *>(v.data()), bytes) != bytes) throw std::runtime_error("snapshot write failed");
        f.close();
        emitJson({{"event", "output_snapshot"}, {"completion", s.completion}, {"output", double(i)},
                  {"path", path}, {"bytes", double(bytes)}, {"encoding", "little_endian_fp32"},
                  {"sha256", hash(fileBytes(path))}});
    }
}

// Diagnostics deliberately use real runtime retrieval after native binding.
// They are separate from certification/timing and cannot certify a layout.
static QJsonObject diagnosticCompare(const std::vector<float> &reference, const std::vector<float> &actual) {
    if (reference.empty() || reference.size() != actual.size())
        throw std::runtime_error("diagnostic comparison element count mismatch");
    size_t unequal = 0, outside = 0, nonfinite = 0;
    double maxAbs = 0, sumAbs = 0, squares = 0;
    QJsonObject first;
    for (size_t i = 0; i < actual.size(); ++i) {
        const double r = reference[i], a = actual[i];
        if (!std::isfinite(r) || !std::isfinite(a)) { ++nonfinite; continue; }
        const double delta = std::abs(r - a);
        unequal += r != a;
        if (delta > 1e-6 + 1e-6 * std::abs(r)) {
            ++outside;
            if (first.isEmpty()) first = {{"index", double(i)}, {"reference", r}, {"actual", a}};
        }
        maxAbs = std::max(maxAbs, delta); sumAbs += delta; squares += delta * delta;
    }
    return {{"elements", double(actual.size())}, {"unequal_elements", double(unequal)},
            {"outside_epsilon", double(outside)}, {"nonfinite_elements", double(nonfinite)},
            {"max_abs", maxAbs}, {"mean_abs", sumAbs / actual.size()},
            {"rmse", std::sqrt(squares / actual.size())}, {"first_mismatch", first},
            {"atol", 1e-6}, {"rtol", 1e-6}, {"within_epsilon", outside == 0 && nonfinite == 0}};
}
static QByteArray diagnosticBytes(const void *p, size_t size) {
    if (!p || !size || size > size_t(std::numeric_limits<int>::max()))
        throw std::runtime_error("invalid diagnostic snapshot buffer/size");
    return QByteArray(static_cast<const char *>(p), int(size));
}
static void diagnosticSave(const QString &path, const QByteArray &data, QJsonObject metadata) {
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::NewOnly) || file.write(data) != data.size())
        throw std::runtime_error("cannot create diagnostic snapshot");
    file.close();
    metadata["event"] = "diagnostic_snapshot"; metadata["path"] = path;
    metadata["bytes"] = data.size(); metadata["sha256"] = hash(data);
    for (const QString &key : {QString("logical_attr"), QString("native_attr"), QString("binding_attr")})
        if (metadata.contains(key))
            metadata[key + "_sha256"] = hash(QJsonDocument(metadata[key].toObject()).toJson(QJsonDocument::Compact));
    // Persist metadata beside each blob even if a later optional API fails.
    QFile sidecar(path + ".json");
    const QByteArray json = QJsonDocument(metadata).toJson(QJsonDocument::Indented);
    if (!sidecar.open(QIODevice::WriteOnly | QIODevice::NewOnly) || sidecar.write(json) != json.size())
        throw std::runtime_error("cannot create diagnostic snapshot metadata");
    emitJson(metadata);
}
static QVector<Detection> diagnosticDecode(const std::vector<std::vector<float>> &arrays, const Meta &m) {
    std::vector<rknn_output> outs(arrays.size());
    for (size_t i = 0; i < outs.size(); ++i) {
        outs[i].index = uint32_t(i); outs[i].want_float = 1; outs[i].is_prealloc = 1;
        outs[i].buf = const_cast<float *>(arrays[i].data()); outs[i].size = uint32_t(arrays[i].size() * sizeof(float));
    }
    FrozenDecoder decoder;
    return decoder.decode(outs, m.outputs);
}
static void diagnosticInput(Api &api, rknn_context ctx, const Fixture &f, rknn_tensor_mem *mem, size_t rowBytes) {
    if (mem) {
        std::memset(mem->virt_addr, 114, mem->size);
        for (int y = 0; y < 640; ++y)
            std::memcpy(static_cast<unsigned char *>(mem->virt_addr) + y * rowBytes, f.rgb.constData() + y * 1920, 1920);
        check(api.sync(ctx, mem, RKNN_MEMORY_SYNC_TO_DEVICE), "diagnostic input sync TO_DEVICE");
    } else {
        rknn_input in{}; in.index = 0; in.buf = const_cast<char *>(f.rgb.constData());
        in.size = MODEL_SIZE; in.type = RKNN_TENSOR_UINT8; in.fmt = RKNN_TENSOR_NHWC; in.pass_through = 0;
        check(api.inputs(ctx, 1, &in), "diagnostic rknn_inputs_set");
    }
}
struct DiagnosticOutputs {
    Api &api; rknn_context ctx; bool acquired = false;
    std::vector<rknn_output> outs;
    DiagnosticOutputs(Api &a, rknn_context c, size_t count, bool wantFloat) : api(a), ctx(c), outs(count) {
        for (size_t i = 0; i < count; ++i) { outs[i].index = uint32_t(i); outs[i].want_float = wantFloat ? 1 : 0; }
    }
    ~DiagnosticOutputs() { if (acquired) api.release(ctx, uint32_t(outs.size()), outs.data()); }
    int get(const QString &phase, int frame) {
        const int rc = api.get(ctx, uint32_t(outs.size()), outs.data(), nullptr);
        acquired = rc == RKNN_SUCC;
        emitJson({{"event", "diagnostic_get"}, {"phase", phase}, {"frame", frame}, {"rc", rc},
                  {"want_float", int(outs[0].want_float)}, {"is_prealloc", 0}});
        return rc;
    }
    void release(const QString &phase, int frame) {
        if (!acquired) return;
        acquired = false;
        const int rc = api.release(ctx, uint32_t(outs.size()), outs.data());
        emitJson({{"event", "diagnostic_release"}, {"phase", phase}, {"frame", frame}, {"rc", rc}});
        check(rc, "diagnostic outputs_release");
    }
    std::vector<std::vector<float>> floats(const Meta &m) const {
        std::vector<std::vector<float>> result(outs.size());
        for (size_t i = 0; i < outs.size(); ++i) {
            const size_t bytes = NativePlan::mul(m.outputs[i].n_elems, sizeof(float));
            if (!outs[i].buf || outs[i].size < bytes || !outs[i].want_float || !acquired)
                throw std::runtime_error("invalid runtime diagnostic FP32 output");
            result[i].resize(m.outputs[i].n_elems);
            std::memcpy(result[i].data(), outs[i].buf, bytes);
        }
        return result;
    }
};
static int diagnoseNative(Api &api, Session &bound, const QByteArray &model, const Meta &m,
                          const std::vector<NativePlan> &plans, const std::vector<rknn_tensor_mem *> &memories,
                          const std::vector<rknn_tensor_attr> &bindings, const Fixture &fixture,
                          rknn_tensor_mem *inputMem, size_t rowBytes, const QString &prefix, int iterations) {
    emitJson({{"event", "diagnostic_config"}, {"performance_claim", false}, {"hardware_certified", false},
              {"sync_to_device", int(RKNN_MEMORY_SYNC_TO_DEVICE)}, {"sync_from_device", int(RKNN_MEMORY_SYNC_FROM_DEVICE)},
              {"sizeof_sync_mode", int(sizeof(rknn_mem_sync_mode))}, {"cacheable_alloc_flag", int(RKNN_FLAG_MEMORY_CACHEABLE)},
              {"output_poison_byte", 165}, {"capture_frames", "first_and_last"},
              {"reference_context", "fresh_unbound_same_model"}, {"bound_get_context", "same_native_run"},
              {"dequant_scale", plans[0].dequantScale == NativePlan::DequantScale::Fp16 ? "fp16" : "fp32"}});
    Session baseline(api);
    check(api.init(&baseline.ctx, const_cast<char *>(model.constData()), uint32_t(model.size()), 0, nullptr), "diagnostic baseline init");
    // Separate real baseline runs avoid relying on repeated retrieval/release
    // of the same frame. The immutable image/model are identical for both.
    diagnosticInput(api, baseline.ctx, fixture, nullptr, 0);
    check(api.run(baseline.ctx, nullptr), "diagnostic baseline float run");
    DiagnosticOutputs baselineFloat(api, baseline.ctx, m.outputs.size(), true);
    check(baselineFloat.get("baseline_float", 1), "diagnostic baseline float get");
    const auto reference = baselineFloat.floats(m);
    const auto referenceDets = diagnosticDecode(reference, m);
    for (size_t i = 0; i < reference.size(); ++i)
        diagnosticSave(prefix + ".baseline.o" + QString::number(i) + ".f32",
                       diagnosticBytes(reference[i].data(), reference[i].size() * sizeof(float)),
                       {{"phase", "baseline_float"}, {"output", double(i)}, {"logical_attr", attrJson(m.outputs[i])},
                        {"encoding", "little_endian_fp32"}, {"returned_size", double(baselineFloat.outs[i].size)}});
    baselineFloat.release("baseline_float", 1);
    diagnosticInput(api, baseline.ctx, fixture, nullptr, 0);
    check(api.run(baseline.ctx, nullptr), "diagnostic baseline quantized run");
    DiagnosticOutputs baselineQuant(api, baseline.ctx, m.outputs.size(), false);
    const int quantRc = baselineQuant.get("baseline_quantized", 2);
    std::vector<std::vector<float>> logicalAffine(m.outputs.size());
    if (quantRc == RKNN_SUCC) for (size_t i = 0; i < m.outputs.size(); ++i) {
        const auto &out = baselineQuant.outs[i]; const auto &attr = m.outputs[i];
        const QByteArray bytes = diagnosticBytes(out.buf, out.size);
        diagnosticSave(prefix + ".baseline.o" + QString::number(i) + ".logical_quant.u8", bytes,
                       {{"phase", "baseline_quantized"}, {"output", double(i)}, {"logical_attr", attrJson(attr)},
                        {"encoding", "raw_bytes_want_float0"}, {"returned_size", double(out.size)}});
        if ((attr.type == RKNN_TENSOR_INT8 || attr.type == RKNN_TENSOR_UINT8) &&
            attr.qnt_type == RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC && out.size == attr.n_elems) {
            std::vector<float> affine(attr.n_elems);
            std::vector<float> mappingAffine(attr.n_elems);
            double scaleMin = std::numeric_limits<double>::infinity(), scaleMax = -scaleMin;
            for (size_t j = 0; j < affine.size(); ++j) {
                const unsigned char byte = static_cast<unsigned char>(bytes[int(j)]);
                const int q = attr.type == RKNN_TENSOR_INT8 ? int(static_cast<int8_t>(byte)) : int(byte);
                const int delta = q - attr.zp;
                affine[j] = float(delta) * attr.scale;
                mappingAffine[j] = float(delta) * plans[i].effectiveScale;
                if (delta && std::isfinite(reference[i][j])) {
                    const double ratio = double(reference[i][j]) / delta;
                    scaleMin = std::min(scaleMin, ratio); scaleMax = std::max(scaleMax, ratio);
                }
            }
            QJsonObject report{{"event", "diagnostic_quantization"}, {"output", double(i)},
                {"reported_scale", double(attr.scale)}, {"reported_zp", attr.zp},
                {"reported_affine_vs_sdk_float", diagnosticCompare(reference[i], affine)},
                {"interpretation", "SDK logical packed bytes; separate identical baseline run"}};
            if (std::isfinite(scaleMin)) { report["observed_float_per_quant_step_min"] = scaleMin; report["observed_float_per_quant_step_max"] = scaleMax; }
            emitJson(report);
            logicalAffine[i] = std::move(mappingAffine);
        } else emitJson({{"event", "diagnostic_quantization"}, {"output", double(i)},
                         {"interpreted", false}, {"reason", "returned raw size/type not packed logical affine byte tensor"}});
    }
    baselineQuant.release("baseline_quantized", 2);
    emitJson({{"event", "diagnostic_detections"}, {"phase", "baseline"}, {"count", referenceDets.size()}, {"detections", detections(referenceDets)}});
    int supportedGets = 0;
    for (int frame = 1; frame <= iterations; ++frame) {
        const bool capture = frame == 1 || frame == iterations;
        for (auto *mem : memories) {
            // Poison + TO_DEVICE makes an untouched allocation observable.
            // This is diagnostic output memory only, not an input/model change.
            std::memset(mem->virt_addr, 165, mem->size);
            check(api.sync(bound.ctx, mem, RKNN_MEMORY_SYNC_TO_DEVICE), "diagnostic output poison TO_DEVICE");
        }
        diagnosticInput(api, bound.ctx, fixture, inputMem, rowBytes);
        check(api.run(bound.ctx, nullptr), "diagnostic native run");
        for (auto *mem : memories) check(api.sync(bound.ctx, mem, RKNN_MEMORY_SYNC_FROM_DEVICE), "diagnostic native FROM_DEVICE");
        std::vector<std::vector<float>> adapter(plans.size());
        const QString framePrefix = prefix + ".c" + QString::number(frame);
        for (size_t i = 0; i < plans.size(); ++i) {
            adapter[i].resize(plans[i].elements);
            plans[i].convert(memories[i]->virt_addr, memories[i]->size, adapter[i]);
            if (capture) {
                const auto raw = diagnosticBytes(memories[i]->virt_addr, memories[i]->size);
                size_t nonzero = 0, poison = 0;
                for (char b : raw) { const auto byte = static_cast<unsigned char>(b); nonzero += byte != 0; poison += byte == 165; }
                diagnosticSave(framePrefix + ".o" + QString::number(i) + ".native_before_get.u8", raw,
                               {{"phase", "native_before_get"}, {"frame", frame}, {"output", double(i)},
                                {"logical_attr", attrJson(m.outputs[i])}, {"native_attr", attrJson(m.native[i])},
                                {"binding_attr", attrJson(bindings[i])}, {"encoding", "raw_native_allocation_bytes"},
                                {"allocation_size", double(memories[i]->size)}, {"plan_bytes", double(plans[i].bytes)},
                                {"nonzero_bytes", double(nonzero)}, {"poison_bytes", double(poison)},
                                {"memory", memoryJson(memories[i])}, {"effective_scale", double(plans[i].effectiveScale)}});
                diagnosticSave(framePrefix + ".o" + QString::number(i) + ".adapter.f32",
                               diagnosticBytes(adapter[i].data(), adapter[i].size() * sizeof(float)),
                               {{"phase", "native_adapter_before_get"}, {"frame", frame}, {"output", double(i)},
                                {"logical_attr", attrJson(m.outputs[i])}, {"encoding", "little_endian_fp32"},
                                {"effective_scale", double(plans[i].effectiveScale)}});
                emitJson({{"event", "diagnostic_comparison"}, {"frame", frame}, {"output", double(i)},
                          {"comparison", "adapter_vs_unbound_baseline"}, {"metrics", diagnosticCompare(reference[i], adapter[i])}});
                if (!logicalAffine[i].empty())
                    emitJson({{"event", "diagnostic_comparison"}, {"frame", frame}, {"output", double(i)},
                              {"comparison", "native_vs_logical_quantized_same_scale_policy"},
                              {"metrics", diagnosticCompare(logicalAffine[i], adapter[i])},
                              {"interpretation", "tests candidate mapping with identical explicit scale policy, independent of SDK want_float arithmetic"}});
            }
        }
        const auto adapterDets = diagnosticDecode(adapter, m);
        emitJson({{"event", "diagnostic_detections"}, {"phase", "adapter_before_get"}, {"frame", frame},
                  {"count", adapterDets.size()}, {"detections", detections(adapterDets)}});
        DiagnosticOutputs boundFloat(api, bound.ctx, m.outputs.size(), true);
        const int getRc = boundFloat.get("bound_context_float", frame);
        if (getRc == RKNN_SUCC) {
            ++supportedGets;
            const auto sdkFloat = boundFloat.floats(m);
            const auto sdkDets = diagnosticDecode(sdkFloat, m);
            emitJson({{"event", "diagnostic_detections"}, {"phase", "bound_context_float"}, {"frame", frame},
                      {"count", sdkDets.size()}, {"detections", detections(sdkDets)}});
            if (capture) for (size_t i = 0; i < plans.size(); ++i) {
                diagnosticSave(framePrefix + ".o" + QString::number(i) + ".bound_get.f32",
                               diagnosticBytes(sdkFloat[i].data(), sdkFloat[i].size() * sizeof(float)),
                               {{"phase", "bound_context_float"}, {"frame", frame}, {"output", double(i)},
                                {"logical_attr", attrJson(m.outputs[i])}, {"encoding", "little_endian_fp32"},
                                {"returned_size", double(boundFloat.outs[i].size)}});
                emitJson({{"event", "diagnostic_comparison"}, {"frame", frame}, {"output", double(i)},
                          {"comparison", "adapter_vs_same_bound_context_sdk_float"}, {"metrics", diagnosticCompare(sdkFloat[i], adapter[i])}});
                emitJson({{"event", "diagnostic_comparison"}, {"frame", frame}, {"output", double(i)},
                          {"comparison", "bound_context_sdk_float_vs_unbound_baseline"}, {"metrics", diagnosticCompare(reference[i], sdkFloat[i])}});
            }
        }
        // Capture while runtime FP32 buffers are still acquired so release
        // cannot obscure whether outputs_get itself wrote the bound memory.
        if (capture) for (size_t i = 0; i < plans.size(); ++i) {
            check(api.sync(bound.ctx, memories[i], RKNN_MEMORY_SYNC_FROM_DEVICE), "diagnostic after get FROM_DEVICE");
            diagnosticSave(framePrefix + ".o" + QString::number(i) + ".native_after_get.u8",
                           diagnosticBytes(memories[i]->virt_addr, memories[i]->size),
                           {{"phase", "native_after_get"}, {"frame", frame}, {"output", double(i)},
                            {"native_attr", attrJson(m.native[i])}, {"binding_attr", attrJson(bindings[i])},
                            {"encoding", "raw_native_allocation_bytes"}, {"outputs_get_rc", getRc},
                            {"before_outputs_release", true}, {"memory", memoryJson(memories[i])}});
        }
        boundFloat.release("bound_context_float", frame);
    }
    emitJson({{"event", "summary"}, {"status", "diagnostic_bytes_collected_no_certification"}, {"diagnose_native", true},
              {"native_runs", iterations}, {"baseline_runs", 2}, {"supported_bound_float_gets", supportedGets},
              {"baseline_quant_get_rc", quantRc}, {"hardware_certified", false}, {"performance_claim", false}});
    return 0;
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    const QStringList args = app.arguments();
    auto arg = [&](const QString &key, const QString &def = QString()) {
        const int i = args.indexOf(key);
        if (i < 0) return def;
        if (i + 1 >= args.size()) throw std::runtime_error("missing argument value");
        return args[i + 1];
    };
    int attempted = 0, completed = 0, warmed = 0;
    QString mode;
    bool nativeMode = false, setupReady = false;
    try {
        mode = arg("--mode", "probe");
        const bool fdImport = mode == "native_io_fd_import";
        const bool singleCopy = mode == "native_io_single_copy" || fdImport;
        nativeMode = mode == "native" || mode == "native_io" || singleCopy;
        if (mode != "probe" && mode != "baseline" && mode != "prealloc" && !nativeMode)
            throw std::runtime_error("unsupported mode");
        const bool diagnose = args.contains("--diagnose-native");
        if (diagnose && singleCopy)
            throw std::runtime_error(mode.toStdString() + " diagnostic mode unsupported; use its baseline certification");
        if (diagnose && !nativeMode) throw std::runtime_error("--diagnose-native requires native or native_io mode");
        const QString dequantScale = arg("--dequant-scale", "fp32");
        if (dequantScale != "fp32" && dequantScale != "fp16")
            throw std::runtime_error("dequant scale must be fp32 or fp16");
        if (fdImport && (arg("--native-query", "9") != "9" || dequantScale != "fp16" ||
                         arg("--timing-reference") != "native_io_single_copy"))
            throw std::runtime_error("native_io_fd_import requires native-query9, dequant-scale fp16 and timing-reference native_io_single_copy");
        const auto dequantPolicy = dequantScale == "fp16" ? NativePlan::DequantScale::Fp16 : NativePlan::DequantScale::Fp32;
        if (!diagnose && args.contains("--native-allocator"))
            throw std::runtime_error("--native-allocator requires --diagnose-native; timing profiles retain their allocator");
        const QString allocator = diagnose ? arg("--native-allocator", "cacheable2") : QString("auto");
        if (diagnose && allocator != "create" && allocator != "default2" &&
            allocator != "cacheable2" && allocator != "noncacheable2")
            throw std::runtime_error("native allocator must be create, default2, cacheable2 or noncacheable2");
        const QString modelPath = arg("--model");
        const QByteArray model = fileBytes(modelPath);
        if (hash(model) != MODEL_SHA) throw std::runtime_error("model SHA256 mismatch");
        const QString manifestPath = arg("--manifest");
        emitJson({{"event", "identity"}, {"mode", mode}, {"model_path", modelPath}, {"model_sha256", hash(model)},
                  {"executable_sha256", hash(fileBytes(app.applicationFilePath()))},
                  {"manifest_sha256", manifestPath.isEmpty() ? QString() : hash(fileBytes(manifestPath))},
                  {"rknn_flags", 0}, {"async", false}, {"diagnose_native", diagnose}, {"dequant_scale", dequantScale},
                  {"cache_sync", "explicit and runtime default enabled"}});
        Api api(arg("--lib", "librknnrt.so"));
        Session sess(api);
        std::unique_ptr<ImportedSession> imported;
        const Stamp initStamp;
        check(api.init(&sess.ctx, const_cast<char *>(model.constData()), uint32_t(model.size()), 0, nullptr), "rknn_init");
        emitJson({{"event", "load"}, {"timing", timing(since(initStamp))}});
        const int nativeQuery = arg("--native-query", "9").toInt();
        if (nativeQuery != 9 && nativeQuery != 11) throw std::runtime_error("native query must be SDK command 9 or 11");
        if (singleCopy && (nativeQuery != 9 || dequantScale != "fp16"))
            throw std::runtime_error("single-copy profiles require native-query9 and dequant-scale fp16");
        const Meta m = queryMeta(api, sess.ctx, nativeQuery);
        validateInput(m.input);
        std::vector<NativePlan> plans;
        bool eligible = true;
        for (size_t i = 0; i < m.outputs.size(); ++i) {
            try {
                check(m.nativeRc[i], "native output query");
                auto plan = NativePlan::make(m.outputs[i], m.native[i], dequantPolicy);
                emitJson({{"event", "native_plan"}, {"output", double(i)}, {"query", nativeQuery},
                          {"metadata_eligible", true}, {"hardware_certified", false},
                          {"allocation_bytes", double(plan.bytes)}, {"float_elements", double(plan.elements)},
                          {"dequant_scale", dequantScale}, {"effective_scale", double(plan.effectiveScale)},
                          {"conversion_kernel", plan.conversionKernel()}});
                plans.push_back(plan);
            } catch (const std::exception &e) {
                eligible = false;
                emitJson({{"event", "native_plan"}, {"output", double(i)}, {"query", nativeQuery},
                          {"metadata_eligible", false}, {"hardware_certified", false}, {"reason", e.what()}});
            }
        }
        if (mode == "probe") {
            emitJson({{"event", "summary"}, {"mode", mode}, {"status", "queried_only"},
                      {"native_metadata_eligible", eligible}, {"completed", 0}, {"performance_claim", false}});
            return 0;
        }
        if (nativeMode && !eligible) throw std::runtime_error("native declined: at least one queried output layout unsupported");
        if (fdImport) {
            if (plans.size() != 4) throw std::runtime_error("FD candidate requires the pinned four-output model");
            for (const auto &plan : plans) if (!plan.usesNeon())
                throw std::runtime_error("FD candidate requires the existing AArch64 query9 NEON plans");
            verifyImportSymbol(api);
            // Fresh context, unused import: inspect ownership before/after both
            // destroy_mem and context destruction without reading retired memory.
            Session probe(api);
            check(api.init(&probe.ctx, const_cast<char *>(model.constData()), uint32_t(model.size()), 0, nullptr), "FD ownership probe init");
            ImportedSession probeOwned(api, probe.ctx, "ownership_probe");
            const long page = probeOwned.operations.pageSize();
            const uint32_t probeBytes = DmaHeapImport::alignedBytes(1, page);
            auto *mem = probeOwned.allocate(probeBytes, "unused_probe");
            {
                DmaHeapImport::CpuAccess access(probeOwned.owned, probeOwned.owned.find(mem), DMA_BUF_SYNC_WRITE);
                std::memset(mem->virt_addr, 0, mem->size);
                access.finish();
            }
            if (!probeOwned.retire()) throw std::runtime_error("FD import declined: ownership/sync/teardown probe failed");
            imported.reset(new ImportedSession(api, sess.ctx, "native_io_fd_import"));
            emitJson({{"event", "dma_heap_import_config"}, {"heap_path", "/dev/dma_heap/system"},
                      {"page_size", double(page)}, {"persistent_imports", 5}, {"context_flags", 0},
                      {"timing_reference", "native_io_single_copy"}, {"ownership_probe_passed", true},
                      {"cpu_access_sessions_span_run", false}, {"flags_or_priv_data_modified", false},
                      {"eintr_attempt_limit", int(DmaHeapImport::MaxEintrAttempts)},
                      {"acceleration_scope", "native_npu_allocator_and_software_cpu_sync_copy"}, {"hardware_certified", false}});
        }
        if (mode == "native" && !diagnose &&
            api.runtimeSha == "73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885")
            throw std::runtime_error("native declined: output-only bindings returned zero logical slots on this pinned runtime/model "
                                     "for queries9/11 (parent runs892e53bc/71d10840); use native_io with full parity gates. "
                                     "--diagnose-native remains available to investigate output-only binding");
        const Fixture fixture = loadFixture(arg("--fixture"), arg("--kind"));
        const int warmup = arg("--warmup", diagnose ? "0" : "5").toInt();
        const int iterations = arg("--iterations", diagnose ? "3" : "50").toInt();
        if (warmup < 0 || warmup > 1000 || iterations < 1 || iterations > 10000)
            throw std::runtime_error("invalid warmup/iteration count");
        if (diagnose && (warmup != 0 || iterations > 16))
            throw std::runtime_error("native diagnostics require warmup0 and at most16 iterations");
        const QString prefix = arg("--prefix");
        if (prefix.isEmpty()) throw std::runtime_error("snapshot prefix required");
        const bool allSnapshots = args.contains("--snapshot-all");
        std::vector<std::vector<float>> persistent(m.outputs.size());
        for (size_t i = 0; i < persistent.size(); ++i) {
            const size_t bytes = NativePlan::mul(m.outputs[i].n_elems, sizeof(float));
            if (bytes > UINT32_MAX) throw std::runtime_error("FP32 output exceeds API size");
            if (mode != "baseline") persistent[i].resize(m.outputs[i].n_elems);
        }
        std::vector<rknn_tensor_mem *> outputMem;
        std::vector<rknn_tensor_attr> outputBindings;
        if (nativeMode) for (size_t i = 0; i < plans.size(); ++i) {
            if (plans[i].bytes > UINT32_MAX) throw std::runtime_error("native output size overflow");
            auto *mem = fdImport ? imported->allocate(plans[i].bytes, "output" + QString::number(i)) :
                                  sess.allocate(uint32_t(plans[i].bytes), "output" + QString::number(i), allocator);
            auto bind = m.native[i];
            const auto before = bind;
            const auto memoryBefore = memoryJson(mem);
            const int bindRc = api.setMem(sess.ctx, mem, &bind);
            emitBinding({{"event", "output_binding"}, {"output", double(i)}, {"rc", bindRc},
                      {"before", attrJson(before)}, {"after", attrJson(bind)},
                      {"attributes_changed", attrJson(before) != attrJson(bind)},
                      {"memory_before", memoryBefore}, {"memory_after", memoryJson(mem)},
                      {"memory_changed", memoryBefore != memoryJson(mem)}}, fdImport);
            check(bindRc, "rknn_set_io_mem output " + std::to_string(i));
            if (fdImport) {
                imported->owned.validate(imported->owned.find(mem));
            }
            outputMem.push_back(mem);
            outputBindings.push_back(bind);
        }
        rknn_tensor_mem *inputMem = nullptr;
        size_t inputRowBytes = 1920;
        rknn_tensor_attr inputBinding{};
        QString copiedInputSourceSha;
        if (mode == "native_io" || singleCopy) {
            if (singleCopy && (m.input.fmt != RKNN_TENSOR_NHWC || m.input.dims[1] != 640 ||
                               m.input.dims[2] != 640 || m.input.dims[3] != 3 || m.input.w_stride != 640))
                throw std::runtime_error("native_io_single_copy declined: queried graph input must be exact NHWC with width stride640");
            auto bind = m.input;
            const uint32_t ws = bind.w_stride ? bind.w_stride : 640;
            if (ws < 640 || (bind.h_stride && bind.h_stride != 640))
                throw std::runtime_error("unsupported graph input width/height stride");
            inputRowBytes = NativePlan::mul(ws, 3);
            const size_t allocation = NativePlan::mul(inputRowBytes, 640);
            if (allocation > UINT32_MAX) throw std::runtime_error("native input allocation overflow");
            // This is a UINT8 RGB memory binding with runtime conversion. It
            // does not pretend raw pixels are the model's quantized INT8 data.
            bind.type = RKNN_TENSOR_UINT8; bind.fmt = RKNN_TENSOR_NHWC; bind.pass_through = 0;
            bind.n_dims = 4; bind.dims[0] = 1; bind.dims[1] = 640; bind.dims[2] = 640; bind.dims[3] = 3;
            bind.n_elems = MODEL_SIZE; bind.size = MODEL_SIZE; bind.size_with_stride = uint32_t(allocation);
            bind.h_stride = 640;
            inputMem = fdImport ? imported->allocate(allocation, "input_UINT8_NHWC_runtime_conversion") :
                                 sess.allocate(uint32_t(allocation), "input_UINT8_NHWC_runtime_conversion", allocator);
            emitJson({{"event", "input_binding"}, {"attr", attrJson(bind)}, {"subtract_128", false},
                      {"driver_conversion_required", true}, {"hardware_certified", false}});
            const auto before = bind;
            const auto memoryBefore = memoryJson(inputMem);
            const int bindRc = api.setMem(sess.ctx, inputMem, &bind);
            emitBinding({{"event", "input_binding_result"}, {"rc", bindRc},
                      {"before", attrJson(before)}, {"after", attrJson(bind)},
                      {"attributes_changed", attrJson(before) != attrJson(bind)},
                      {"memory_before", memoryBefore}, {"memory_after", memoryJson(inputMem)},
                      {"memory_changed", memoryBefore != memoryJson(inputMem)}}, fdImport);
            check(bindRc, "rknn_set_io_mem UINT8 input conversion");
            if (fdImport) {
                imported->owned.validate(imported->owned.find(inputMem));
                if (imported->owned.find(inputMem).mappingBytes != SingleCopyInput::Bytes)
                    throw std::runtime_error("FD input binding/mapping metadata changed");
            }
            inputBinding = bind;
        }
        if (singleCopy) {
            static_assert(MODEL_SIZE == SingleCopyInput::Bytes, "single-copy model size must match frozen input");
            // Before any inference/window, validate the actual returned memory
            // and post-binding attributes, then hash a complete preflight copy.
            if (fdImport) {
                DmaHeapImport::CpuAccess access(imported->owned, imported->owned.find(inputMem), DMA_BUF_SYNC_WRITE);
                SingleCopyInput::copy(inputMem->virt_addr, inputMem->size, fixture.rgb.constData(), size_t(fixture.rgb.size()),
                                      inputBinding, inputRowBytes);
                access.finish();
            } else SingleCopyInput::copy(inputMem->virt_addr, inputMem->size, fixture.rgb.constData(), size_t(fixture.rgb.size()),
                                        inputBinding, inputRowBytes);
            copiedInputSourceSha = hash(fixture.rgb);
            QString copiedSha;
            if (fdImport) {
                DmaHeapImport::CpuAccess access(imported->owned, imported->owned.find(inputMem), DMA_BUF_SYNC_READ);
                copiedSha = hash(QByteArray::fromRawData(static_cast<const char *>(inputMem->virt_addr), MODEL_SIZE));
                access.finish();
            } else copiedSha = hash(QByteArray::fromRawData(static_cast<const char *>(inputMem->virt_addr), MODEL_SIZE));
            emitJson({{"event", "native_input_copy"}, {"mode", mode}, {"policy", "one_memcpy_full_model_input_each_frame"},
                      {"source_bytes", fixture.rgb.size()}, {"allocation_bytes", double(inputMem->size)},
                      {"input_row_bytes", double(inputRowBytes)}, {"binding_attr", attrJson(inputBinding)},
                      {"source_sha256", copiedInputSourceSha}, {"copied_sha256", copiedSha}, {"byte_match", copiedInputSourceSha == copiedSha},
                      {"hash_scope", "setup_preflight_before_warmups_and_timing"},
                      {"certification_hash_scope", "each_snapshot_all_completion_before_sync_and_run"},
                      {"timed_frame_input_hashes", false},
                      {"per_frame_input_bytes_written", double(MODEL_SIZE)}, {"includes_warmups", true},
                      {"source_includes_gray114_padding", true}, {"acceleration_scope", fdImport ?
                          "native_npu_allocator_and_software_cpu_sync_copy" : "software_input_copy_only"}});
            if (copiedInputSourceSha != copiedSha) throw std::runtime_error("native_io_single_copy preflight input hash mismatch");
        }
        QJsonArray importedMetadataBefore;
        QJsonArray importedOutputBindings;
        if (fdImport) {
            importedMetadataBefore.append(memoryJson(inputMem));
            for (auto *mem : outputMem) importedMetadataBefore.append(memoryJson(mem));
            for (const auto &bind : outputBindings) importedOutputBindings.append(attrJson(bind));
            emitJson({{"event", "dma_heap_binding_snapshot"}, {"phase", "before_frames"},
                      {"input_binding", attrJson(inputBinding)}, {"output_bindings", importedOutputBindings},
                      {"memories", importedMetadataBefore}});
        }
        setupReady = true;
        if (diagnose) return diagnoseNative(api, sess, model, m, plans, outputMem, outputBindings, fixture,
                                          inputMem, inputRowBytes, prefix, iterations);
        FrozenDecoder decoder;
        std::vector<Record> records; records.reserve(iterations);
        std::vector<Snapshot> snapshots; snapshots.reserve(allSnapshots ? iterations : 2);
        std::vector<QString> inputCopyHashes;
        if (singleCopy && allSnapshots) inputCopyHashes.reserve(iterations);
        std::vector<rknn_output> outs(m.outputs.size());
        Stamp window;
        Duration windowDuration;
        for (int frame = -warmup; frame < iterations; ++frame) {
            if (frame == 0) window = Stamp{};
            ++attempted;
            const Stamp total;
            Record rec;
            bool acquired = false;
            // Reset every descriptor after release. is_prealloc=1 ensures the
            // runtime never frees the user-owned FP32 vectors.
            for (size_t i = 0; i < outs.size(); ++i) {
                outs[i] = rknn_output{}; outs[i].index = uint32_t(i); outs[i].want_float = 1;
                if (mode != "baseline") {
                    outs[i].is_prealloc = 1; outs[i].buf = persistent[i].data();
                    outs[i].size = uint32_t(persistent[i].size() * sizeof(float));
                }
            }
            try {
                const Stamp inputStamp;
                if (fdImport) {
                    DmaHeapImport::CpuAccess access(imported->owned, imported->owned.find(inputMem), DMA_BUF_SYNC_WRITE);
                    SingleCopyInput::copy(inputMem->virt_addr, inputMem->size, fixture.rgb.constData(), size_t(fixture.rgb.size()),
                                          inputBinding, inputRowBytes);
                    access.finish();
                } else if (singleCopy) {
                    SingleCopyInput::copy(inputMem->virt_addr, inputMem->size, fixture.rgb.constData(), size_t(fixture.rgb.size()),
                                          inputBinding, inputRowBytes);
                } else if (inputMem) {
                    std::memset(inputMem->virt_addr, 114, inputMem->size);
                    for (int y = 0; y < 640; ++y)
                        std::memcpy(static_cast<unsigned char *>(inputMem->virt_addr) + y * inputRowBytes,
                                    fixture.rgb.constData() + y * 1920, 1920);
                } else {
                    rknn_input in{}; in.index = 0; in.buf = const_cast<char *>(fixture.rgb.constData());
                    in.size = MODEL_SIZE; in.type = RKNN_TENSOR_UINT8; in.fmt = RKNN_TENSOR_NHWC; in.pass_through = 0;
                    check(api.inputs(sess.ctx, 1, &in), "rknn_inputs_set");
                }
                rec.stages[InputSet] = since(inputStamp);
                // Certification uses --snapshot-all and its FPS is never used
                // for performance. Validate each entire input before execution;
                // paired timing has no per-frame hashing or extra snapshots.
                if (singleCopy && allSnapshots && frame >= 0) {
                    QString copiedSha;
                    if (fdImport) {
                        DmaHeapImport::CpuAccess access(imported->owned, imported->owned.find(inputMem), DMA_BUF_SYNC_READ);
                        copiedSha = hash(QByteArray::fromRawData(static_cast<const char *>(inputMem->virt_addr), MODEL_SIZE));
                        access.finish();
                    } else copiedSha = hash(QByteArray::fromRawData(static_cast<const char *>(inputMem->virt_addr), MODEL_SIZE));
                    if (copiedSha != copiedInputSourceSha)
                        throw std::runtime_error("native_io_single_copy certification input hash mismatch");
                    inputCopyHashes.push_back(copiedSha);
                }
                const Stamp inputSync;
                if (inputMem) check(api.sync(sess.ctx, inputMem, RKNN_MEMORY_SYNC_TO_DEVICE), "input mem_sync TO_DEVICE");
                rec.stages[InputSync] = since(inputSync);
                const Stamp runStamp;
                // Blocking genuine NPU execution for every attempted frame.
                if (fdImport) imported->owned.beforeRun();
                const int runRc = api.run(sess.ctx, nullptr);
                if (fdImport) imported->owned.runReturned(runRc);
                check(runRc, "rknn_run");
                rec.stages[Run] = since(runStamp);
                const Stamp getStamp;
                if (!nativeMode) {
                    check(api.get(sess.ctx, uint32_t(outs.size()), outs.data(), nullptr), "rknn_outputs_get want_float");
                    acquired = true;
                    for (size_t i = 0; i < outs.size(); ++i) {
                        const uint32_t expected = uint32_t(m.outputs[i].n_elems * sizeof(float));
                        if (!outs[i].buf || outs[i].size < expected) throw std::runtime_error("float output buffer too short");
                        if (mode == "prealloc" && (!outs[i].is_prealloc || outs[i].buf != persistent[i].data()))
                            throw std::runtime_error("preallocated descriptor ownership/pointer changed");
                    }
                }
                rec.stages[OutputsGet] = since(getStamp);
                if (fdImport) {
                    // Each output has its own complete CPU session, after the
                    // successful blocking run. No CPU session crosses NPU work.
                    for (size_t i = 0; i < plans.size(); ++i) {
                        const Stamp syncStamp;
                        DmaHeapImport::CpuAccess access(imported->owned, imported->owned.find(outputMem[i]), DMA_BUF_SYNC_READ);
                        check(api.sync(sess.ctx, outputMem[i], RKNN_MEMORY_SYNC_FROM_DEVICE), "output mem_sync FROM_DEVICE");
                        const Duration syncTime = since(syncStamp);
                        const Stamp convertStamp;
                        plans[i].convert(outputMem[i]->virt_addr, outputMem[i]->size, persistent[i]);
                        const Duration convertTime = since(convertStamp);
                        const Stamp endStamp;
                        access.finish();
                        const Duration endTime = since(endStamp);
                        rec.stages[OutputSync].wall += syncTime.wall + endTime.wall;
                        rec.stages[OutputSync].cpu += syncTime.cpu + endTime.cpu;
                        rec.stages[Conversion].wall += convertTime.wall;
                        rec.stages[Conversion].cpu += convertTime.cpu;
                    }
                } else {
                    const Stamp syncStamp;
                    if (nativeMode) for (auto *mem : outputMem)
                        check(api.sync(sess.ctx, mem, RKNN_MEMORY_SYNC_FROM_DEVICE), "output mem_sync FROM_DEVICE");
                    rec.stages[OutputSync] = since(syncStamp);
                    const Stamp convertStamp;
                    if (nativeMode) for (size_t i = 0; i < plans.size(); ++i)
                        plans[i].convert(outputMem[i]->virt_addr, outputMem[i]->size, persistent[i]);
                    rec.stages[Conversion] = since(convertStamp);
                }
                const Stamp decodeStamp;
                rec.dets = decoder.decode(outs, m.outputs);
                rec.stages[Decode] = since(decodeStamp);
                const Stamp snapshotStamp;
                if (frame >= 0 && (allSnapshots || frame == 0 || frame == iterations - 1)) {
                    Snapshot s; s.completion = frame + 1; s.dets = rec.dets;
                    s.arrays.resize(outs.size());
                    for (size_t i = 0; i < outs.size(); ++i) {
                        const auto *v = static_cast<const float *>(outs[i].buf);
                        s.arrays[i].assign(v, v + m.outputs[i].n_elems);
                    }
                    snapshots.push_back(std::move(s));
                }
                rec.stages[SnapshotCopy] = since(snapshotStamp);
                const Stamp releaseStamp;
                if (acquired) {
                    acquired = false;
                    check(api.release(sess.ctx, uint32_t(outs.size()), outs.data()), "rknn_outputs_release");
                }
                rec.stages[Release] = since(releaseStamp);
                rec.total = since(total);
                if (frame >= 0) { ++completed; records.push_back(std::move(rec)); }
                else ++warmed;
            } catch (...) {
                if (acquired) api.release(sess.ctx, uint32_t(outs.size()), outs.data());
                throw;
            }
        }
        windowDuration = since(window);
        if (fdImport) {
            QJsonArray after;
            imported->owned.validate(imported->owned.find(inputMem));
            after.append(memoryJson(inputMem));
            for (auto *mem : outputMem) {
                imported->owned.validate(imported->owned.find(mem));
                after.append(memoryJson(mem));
            }
            emitJson({{"event", "dma_heap_binding_snapshot"}, {"phase", "after_frames"},
                      {"input_binding", attrJson(inputBinding)}, {"output_bindings", importedOutputBindings}, {"memories", after},
                      {"metadata_stable", after == importedMetadataBefore}});
            if (after != importedMetadataBefore) throw std::runtime_error("FD import metadata changed during frames");
            if (!imported->retire()) throw std::runtime_error("FD import ownership/sync/retirement failed after frames");
        }
        // Output file I/O, hashing, printing and comparison happen after timing. The
        // in-loop snapshot copies ARE included in the completion window.
        for (int i = 0; i < int(records.size()); ++i)
            emitJson({{"event", "completion"}, {"mode", mode}, {"completion", i + 1}, {"stages", stagesJson(records[i])},
                      {"total", timing(records[i].total)}, {"count", records[i].dets.size()},
                      {"detections", detections(records[i].dets)}});
        for (const auto &s : snapshots) writeSnapshot(prefix, s);
        for (size_t i = 0; i < inputCopyHashes.size(); ++i)
            emitJson({{"event", "native_input_copy_verification"}, {"mode", mode}, {"completion", double(i + 1)},
                      {"copied_sha256", inputCopyHashes[i]}, {"source_sha256", copiedInputSourceSha}, {"byte_match", true},
                      {"checked_before_sync_and_run", true}, {"certification_only", true}});
        QFile maps("/proc/self/maps");
        if (maps.open(QIODevice::ReadOnly)) {
            const QByteArray data = maps.readAll();
            QFile saved(prefix + ".maps");
            if (!saved.open(QIODevice::WriteOnly | QIODevice::NewOnly) || saved.write(data) != data.size())
                throw std::runtime_error("cannot retain loaded dependency maps");
        }
        emitJson({{"event", "summary"}, {"mode", mode}, {"status", "hardware_completed_requires_external_parity"},
                  {"attempted", attempted}, {"warmed", warmed}, {"requested", iterations}, {"completed", completed},
                  {"failed", 0}, {"window", timing(windowDuration)},
                  {"completed_fps", completed * 1000.0 / windowDuration.wall},
                  {"snapshot_policy", allSnapshots ? "every_timed_completion" : "first_and_last_timed_completion"},
                  {"input_preprocess_timed", false}, {"full_viewer_fps_claim", false}, {"hardware_certified", false}});
        return 0;
    } catch (const std::exception &e) {
        const bool declined = nativeMode && !setupReady;
        emitJson({{"event", declined ? "unsupported" : "error"}, {"mode", mode}, {"reason", e.what()},
                  {"attempted", attempted}, {"warmed", warmed}, {"completed", completed},
                  {"failed_attempts", attempted - warmed - completed},
                  {"hardware_certified", false}, {"performance_claim", false}});
        return declined ? 3 : 2;
    }
}
