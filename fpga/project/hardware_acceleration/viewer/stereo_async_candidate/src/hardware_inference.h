#pragma once
#include "rknn_api.h"
#include "native_adapter.h"
#include <dlfcn.h>
#include <cstdint>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

// A session owns its context, native buffers, and persistent logical FP32
// outputs. The caller keeps its legacy context until create() fully succeeds.
// This header uses the retained SDK declarations, including optional symbols.
class HardwareInference {
public:
    static constexpr size_t InputBytes = size_t(640) * 640 * 3;

    static std::shared_ptr<HardwareInference> create(
            const void *model, size_t bytes,
            const std::vector<rknn_tensor_attr> &logical,
            bool nativeInput, std::string &reason) {
        // The measured target runtime leaves bound output buffers zero when
        // inputs_set is used. Decline before creating or binding any context.
        if (!nativeInput) {
            reason = "native_output_only_not_certified_target_runtime";
            return {};
        }
        std::shared_ptr<HardwareInference> candidate(new HardwareInference);
        try {
            candidate->setup(model, bytes, logical);
            reason = "all_native_bindings_and_sync_validated";
            return candidate;
        } catch (const std::exception &e) {
            reason = e.what();
            // Destruction unwinds even a partially bound candidate context.
            // No rknn_set_io_mem call ever touches the legacy context.
            return {};
        }
    }

    ~HardwareInference() {
        if (m_context) {
            for (auto *mem : m_memories)
                if (mem) m_destroyMem(m_context, mem);
            rknn_destroy(m_context);
        }
        if (m_library) dlclose(m_library);
    }
    HardwareInference(const HardwareInference &) = delete;
    HardwareInference &operator=(const HardwareInference &) = delete;

    rknn_context context() const { return m_context; }
    bool usesNativeInput() const { return m_input != nullptr; }
    const std::string &error() const { return m_error; }
    std::vector<rknn_output> &outputs() { return m_outputs; }

    bool writeInput(const void *rgb, size_t bytes) {
        if (!m_input || !rgb || bytes != InputBytes) {
            m_error = "native_input_buffer_invalid";
            return false;
        }
        // The complete CPU letterbox remains UINT8 RGB888, without -128.
        // Its driver binding has pass_through=0, just like rknn_inputs_set.
        std::memcpy(m_input->virt_addr, rgb, InputBytes);
        return sync(m_input, RKNN_MEMORY_SYNC_TO_DEVICE, "input_sync_TO_DEVICE");
    }

    bool readOutputs() {
        // Sync all tensors before publishing any converted logical output.
        for (auto *mem : m_outputMem)
            if (!sync(mem, RKNN_MEMORY_SYNC_FROM_DEVICE, "output_sync_FROM_DEVICE"))
                return false;
        try {
            for (size_t i = 0; i < m_plans.size(); ++i)
                m_plans[i].convert(m_outputMem[i]->virt_addr, m_outputMem[i]->size, m_float[i]);
        } catch (const std::exception &e) {
            m_error = e.what();
            return false;
        }
        return true;
    }

    static bool sameLogical(const rknn_tensor_attr &a, const rknn_tensor_attr &b) {
        if (a.n_dims > RKNN_MAX_DIMS || b.n_dims > RKNN_MAX_DIMS) return false;
        return a.index == b.index && a.n_dims == b.n_dims &&
               std::equal(a.dims, a.dims + a.n_dims, b.dims) &&
               a.n_elems == b.n_elems && a.size == b.size &&
               a.fmt == b.fmt && a.type == b.type && a.qnt_type == b.qnt_type &&
               a.fl == b.fl && a.zp == b.zp && a.scale == b.scale &&
               a.w_stride == b.w_stride && a.size_with_stride == b.size_with_stride &&
               a.h_stride == b.h_stride && a.pass_through == b.pass_through;
    }

private:
    HardwareInference() = default;
    void *m_library = nullptr;
    rknn_context m_context = 0;
    decltype(&rknn_create_mem) m_create = nullptr;
    decltype(&rknn_create_mem2) m_create2 = nullptr;
    decltype(&rknn_destroy_mem) m_destroyMem = nullptr;
    decltype(&rknn_set_io_mem) m_setMem = nullptr;
    decltype(&rknn_mem_sync) m_sync = nullptr;
    std::vector<rknn_tensor_mem *> m_memories, m_outputMem;
    rknn_tensor_mem *m_input = nullptr;
    std::vector<NativePlan> m_plans;
    std::vector<std::vector<float>> m_float;
    std::vector<rknn_output> m_outputs;
    std::string m_error;

    static void check(int rc, const std::string &stage) {
        if (rc != RKNN_SUCC)
            throw std::runtime_error(stage + "_rc=" + std::to_string(rc));
    }
    template<class F> F symbol(const char *name) {
        return reinterpret_cast<F>(dlsym(m_library, name));
    }
    void openApi() {
        // Resolve optional APIs from the same library as the linked rknn_init,
        // rather than from a potentially different runtime in the loader path.
        Dl_info info{};
        if (!dladdr(reinterpret_cast<void *>(&rknn_init), &info) || !info.dli_fname)
            throw std::runtime_error("cannot_identify_linked_RKNN_runtime");
        m_library = dlopen(info.dli_fname, RTLD_NOW | RTLD_LOCAL);
        if (!m_library) throw std::runtime_error("cannot_open_linked_RKNN_runtime");
        m_create = symbol<decltype(m_create)>("rknn_create_mem");
        m_create2 = symbol<decltype(m_create2)>("rknn_create_mem2");
        m_destroyMem = symbol<decltype(m_destroyMem)>("rknn_destroy_mem");
        m_setMem = symbol<decltype(m_setMem)>("rknn_set_io_mem");
        m_sync = symbol<decltype(m_sync)>("rknn_mem_sync");
        if ((!m_create && !m_create2) || !m_destroyMem || !m_setMem || !m_sync)
            throw std::runtime_error("native_runtime_symbols_unavailable");
    }
    rknn_tensor_mem *allocate(size_t bytes) {
        if (!bytes || bytes > UINT32_MAX) throw std::runtime_error("native_allocation_size_invalid");
        // create_mem2 is optional; use the retained create_mem API if absent.
        auto *mem = m_create2 ? m_create2(m_context, bytes, RKNN_FLAG_MEMORY_CACHEABLE) :
                               m_create(m_context, static_cast<uint32_t>(bytes));
        if (!mem) throw std::runtime_error("native_allocation_failed");
        m_memories.push_back(mem);
        if (!mem->virt_addr || mem->size < bytes)
            throw std::runtime_error("native_allocation_unmapped_or_undersized");
        return mem;
    }
    bool sync(rknn_tensor_mem *mem, rknn_mem_sync_mode mode, const char *stage) {
        const int rc = m_sync(m_context, mem, mode);
        if (rc == RKNN_SUCC) return true;
        m_error = std::string(stage) + "_rc=" + std::to_string(rc);
        return false;
    }
    void setup(const void *model, size_t bytes,
               const std::vector<rknn_tensor_attr> &logical) {
        static_assert(int(RKNN_QUERY_NATIVE_OUTPUT_ATTR) == 9, "retained SDK query ABI");
        if (!model || !bytes || bytes > UINT32_MAX)
            throw std::runtime_error("model_bytes_invalid");
        // This integration is deliberately restricted to the pinned wb_v4
        // model's queried two-scale raw-DFL contract, not its filename.
        const uint32_t shapes[4][4] = {{1,64,80,80}, {1,64,40,40}, {1,3,80,80}, {1,3,40,40}};
        if (logical.size() != 4) throw std::runtime_error("unsupported_raw_DFL_output_count");
        for (size_t i = 0; i < logical.size(); ++i) {
            const auto &a = logical[i];
            if (a.index != i || a.n_dims != 4 || a.fmt != RKNN_TENSOR_NCHW ||
                !std::equal(a.dims, a.dims + 4, shapes[i]))
                throw std::runtime_error("unsupported_raw_DFL_logical_shapes");
        }
        openApi();
        check(rknn_init(&m_context, const_cast<void *>(model), static_cast<uint32_t>(bytes), 0, nullptr),
              "native_context_init");
        // The caller checks pinned model bytes before reaching this helper.
        // FP16 scale reconstruction is supported only for the measured runtime;
        // an SDK/driver change must use legacy until the parent has new parity.
        rknn_sdk_version version{};
        check(rknn_query(m_context, RKNN_QUERY_SDK_VERSION, &version, sizeof(version)), "native_runtime_version_query");
        if (std::strncmp(version.api_version, "2.3.0", 5) != 0 ||
            (version.api_version[5] != ' ' && version.api_version[5] != '\0') ||
            std::strncmp(version.drv_version, "0.9.8", 6) != 0)
            throw std::runtime_error("runtime_not_eligible_for_target_FP16_scale_policy");
        rknn_input_output_num io{};
        check(rknn_query(m_context, RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io)), "native_IO_count_query");
        if (io.n_input != 1 || io.n_output != logical.size())
            throw std::runtime_error("native_context_IO_count_changed");
        rknn_tensor_attr input{};
        check(rknn_query(m_context, RKNN_QUERY_INPUT_ATTR, &input, sizeof(input)), "native_input_attr_query");
        const uint32_t inputShape[4] = {1,640,640,3};
        if (input.index != 0 || input.n_dims != 4 || input.fmt != RKNN_TENSOR_NHWC ||
            !std::equal(input.dims, input.dims + 4, inputShape) || input.n_elems != InputBytes ||
            input.size != InputBytes || input.type != RKNN_TENSOR_INT8 ||
            input.qnt_type != RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC ||
            !std::isfinite(input.scale) || input.scale <= 0 || input.zp < -128 || input.zp > 127 ||
            (input.w_stride && input.w_stride != 640) || (input.h_stride && input.h_stride != 640) ||
            (input.size_with_stride && input.size_with_stride != InputBytes))
            throw std::runtime_error("unsupported_UINT8_NHWC_driver_input_binding");

        // Query and validate every output before allocating or binding any.
        m_plans.reserve(logical.size());
        for (size_t i = 0; i < logical.size(); ++i) {
            rknn_tensor_attr l{}, a{}; l.index = a.index = static_cast<uint32_t>(i);
            check(rknn_query(m_context, RKNN_QUERY_OUTPUT_ATTR, &l, sizeof(l)), "native_logical_attr_query");
            if (!sameLogical(l, logical[i])) throw std::runtime_error("native_logical_metadata_changed");
            check(rknn_query(m_context, RKNN_QUERY_NATIVE_OUTPUT_ATTR, &a, sizeof(a)), "native_output_attr_query9");
            m_plans.push_back(NativePlan::make(l, a, NativePlan::DequantScale::Fp16));
        }
        m_memories.reserve(logical.size() + 1);
        m_outputMem.reserve(logical.size());
        m_float.resize(logical.size());
        m_outputs.resize(logical.size());
        for (size_t i = 0; i < logical.size(); ++i) {
            const auto &plan = m_plans[i];
            m_float[i].resize(plan.elements);
            if (plan.elements > UINT32_MAX / sizeof(float))
                throw std::runtime_error("logical_FP32_size_overflow");
            auto *mem = allocate(plan.bytes);
            auto binding = plan.native;
            check(m_setMem(m_context, mem, &binding), "native_output_bind");
            m_outputMem.push_back(mem);
            if (!sync(mem, RKNN_MEMORY_SYNC_FROM_DEVICE, "native_output_setup_sync"))
                throw std::runtime_error(m_error);
            auto &out = m_outputs[i];
            out = rknn_output{};
            out.index = static_cast<uint32_t>(i);
            out.want_float = 1;
            out.is_prealloc = 1;
            out.buf = m_float[i].data();
            out.size = static_cast<uint32_t>(plan.elements * sizeof(float));
        }
        // Both input and output must be bound on the measured target runtime.
        // Override only the SDK-documented driver-facing input fields.
        // Keep graph metadata, dimensions, strides and allocation intact.
        input.type = RKNN_TENSOR_UINT8;
        input.fmt = RKNN_TENSOR_NHWC;
        input.pass_through = 0;
        input.h_stride = 640; // Same driver-facing binding as the parent's benchmark.
        m_input = allocate(InputBytes);
        std::memset(m_input->virt_addr, 114, InputBytes);
        check(m_setMem(m_context, m_input, &input), "native_UINT8_input_bind");
        if (!sync(m_input, RKNN_MEMORY_SYNC_TO_DEVICE, "native_input_setup_sync"))
            throw std::runtime_error(m_error);
    }
};
