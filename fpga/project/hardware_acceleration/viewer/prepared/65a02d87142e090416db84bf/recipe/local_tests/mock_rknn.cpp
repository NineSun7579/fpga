// Local mock only. It does not execute an NPU or establish hardware parity.
#include "rknn_api.h"
#include <algorithm>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>

namespace {
struct Context {
    std::vector<rknn_tensor_mem *> memories;
    std::map<uint32_t, rknn_tensor_mem *> outputs;
    rknn_tensor_mem *input = nullptr;
    int frames = 0;
};
std::map<rknn_context, Context> contexts;
std::map<std::string, int> stats;
std::string failure;
int failAt = 0;
bool supportedRuntime = true;
rknn_context serial = 0;
bool fail(const char *stage) {
    const int count = ++stats[std::string(stage) + "_calls"];
    return failure == stage && count == failAt;
}
rknn_tensor_attr attr(uint32_t index, bool native) {
    rknn_tensor_attr a{};
    a.index = index; a.n_dims = native ? 5 : 4;
    const uint32_t channels = index < 2 ? 64 : 3;
    const uint32_t hw = index % 2 ? 40 : 80;
    a.dims[0] = 1;
    if (native) {
        a.dims[1] = index < 2 ? 8 : 2;
        a.dims[2] = hw; a.dims[3] = hw; a.dims[4] = 8;
    } else {
        a.dims[1] = channels; a.dims[2] = hw; a.dims[3] = hw;
    }
    a.fmt = native ? RKNN_TENSOR_NC1HWC2 : RKNN_TENSOR_NCHW;
    a.type = RKNN_TENSOR_INT8;
    a.qnt_type = RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC;
    a.scale = index < 2 ? 0.0784313753247261f : index == 2 ? 0.04749705642461777f : 0.049998946487903595f;
    a.n_elems = native ? a.dims[1] * hw * hw * 8 : channels * hw * hw;
    a.size = a.size_with_stride = a.n_elems;
    return a;
}
}

extern "C" void mock_reset() {
    assert(contexts.empty()); stats.clear(); failure.clear(); failAt = 0; serial = 0; supportedRuntime = true;
}
extern "C" void mock_runtime_supported(int supported) { supportedRuntime = supported; }
extern "C" void mock_fail(const char *stage, int at) { failure = stage; failAt = at; }
extern "C" int mock_stat(const char *name) { return stats[name]; }
extern "C" int mock_live_contexts() { return int(contexts.size()); }
extern "C" int mock_live_memories() {
    int n = 0; for (const auto &ctx : contexts) n += int(ctx.second.memories.size()); return n;
}
extern "C" int mock_input_equal(rknn_context ctx, const void *bytes, uint32_t size) {
    const auto *mem = contexts.at(ctx).input;
    return mem && mem->size == size && std::memcmp(mem->virt_addr, bytes, size) == 0;
}

extern "C" int rknn_init(rknn_context *ctx, void *, uint32_t, uint32_t flags, rknn_init_extend *) {
    assert(flags == 0); assert(*ctx == 0);
    if (fail("init")) return -1;
    *ctx = ++serial; contexts.emplace(*ctx, Context{}); return 0;
}
extern "C" int rknn_destroy(rknn_context ctx) {
    // A bound allocation must be destroyed before its owning context.
    assert(contexts.at(ctx).memories.empty()); contexts.erase(ctx); ++stats["destroy_calls"]; return 0;
}
extern "C" int rknn_query(rknn_context ctx, rknn_query_cmd cmd, void *ptr, uint32_t) {
    assert(contexts.count(ctx));
    if (fail("query")) return -2;
    if (cmd == RKNN_QUERY_SDK_VERSION) {
        auto *version = static_cast<rknn_sdk_version *>(ptr);
        *version = rknn_sdk_version{};
        std::strcpy(version->api_version, supportedRuntime ? "2.3.0 (local mock)" : "2.4.0 (local mock)");
        std::strcpy(version->drv_version, "0.9.8");
        return 0;
    }
    if (cmd == RKNN_QUERY_IN_OUT_NUM) {
        *static_cast<rknn_input_output_num *>(ptr) = {1,4}; return 0;
    }
    auto *a = static_cast<rknn_tensor_attr *>(ptr);
    if (cmd == RKNN_QUERY_INPUT_ATTR) {
        *a = rknn_tensor_attr{}; a->n_dims = 4;
        a->dims[0] = 1; a->dims[1] = a->dims[2] = 640; a->dims[3] = 3;
        a->fmt = RKNN_TENSOR_NHWC; a->type = RKNN_TENSOR_INT8;
        a->qnt_type = RKNN_TENSOR_QNT_AFFINE_ASYMMETRIC;
        a->zp = -128; a->scale = 1.0f/255;
        a->n_elems = a->size = a->size_with_stride = 640*640*3; a->w_stride = 640;
        return 0;
    }
    if (cmd == RKNN_QUERY_OUTPUT_ATTR || cmd == RKNN_QUERY_NATIVE_OUTPUT_ATTR) {
        const uint32_t index = a->index;
        *a = attr(index, cmd == RKNN_QUERY_NATIVE_OUTPUT_ATTR); return 0;
    }
    return -3;
}

static rknn_tensor_mem *allocate(rknn_context ctx, uint32_t size) {
    assert(contexts.count(ctx));
    if (fail("allocate")) return nullptr;
    auto *mem = new rknn_tensor_mem{};
    mem->size = size; mem->virt_addr = std::calloc(size, 1);
    assert(mem->virt_addr); contexts.at(ctx).memories.push_back(mem); return mem;
}
extern "C" rknn_tensor_mem *rknn_create_mem(rknn_context ctx, uint32_t size) {
    ++stats["create_mem_calls"]; return allocate(ctx, size);
}
#ifndef OMIT_CREATE2
extern "C" rknn_tensor_mem *rknn_create_mem2(rknn_context ctx, uint64_t size, uint64_t flags) {
    assert(flags == RKNN_FLAG_MEMORY_CACHEABLE); assert(size <= UINT32_MAX);
    ++stats["create_mem2_calls"]; return allocate(ctx, uint32_t(size));
}
#endif
extern "C" int rknn_destroy_mem(rknn_context ctx, rknn_tensor_mem *mem) {
    auto &c = contexts.at(ctx);
    const auto it = std::find(c.memories.begin(), c.memories.end(), mem);
    assert(it != c.memories.end()); c.memories.erase(it);
    for (auto it = c.outputs.begin(); it != c.outputs.end();) {
        if (it->second == mem) it = c.outputs.erase(it); else ++it;
    }
    if (c.input == mem) c.input = nullptr;
    std::free(mem->virt_addr); delete mem; ++stats["destroy_mem_calls"]; return 0;
}
extern "C" int rknn_set_io_mem(rknn_context ctx, rknn_tensor_mem *mem, rknn_tensor_attr *a) {
    assert(ctx != 1);  // The original legacy context is never rebound.
    if (fail("bind")) return -4;
    if (a->n_dims == 4 && a->dims[1] == 640) {
        assert(a->index == 0 && a->type == RKNN_TENSOR_UINT8 && a->fmt == RKNN_TENSOR_NHWC);
        assert(a->pass_through == 0 && a->size == 640*640*3 && mem->size == a->size);
        assert(a->h_stride == 640);
        contexts.at(ctx).input = mem; ++stats["input_bindings"];
    } else {
        assert(a->fmt == RKNN_TENSOR_NC1HWC2 && a->n_dims == 5);
        contexts.at(ctx).outputs[a->index] = mem; ++stats["output_bindings"];
    }
    return 0;
}
#ifndef OMIT_SYNC
extern "C" int rknn_mem_sync(rknn_context ctx, rknn_tensor_mem *, rknn_mem_sync_mode mode) {
    assert(contexts.count(ctx));
    if (fail("sync")) return -5;
    if (mode == RKNN_MEMORY_SYNC_TO_DEVICE) ++stats["to_device"];
    else { assert(mode == RKNN_MEMORY_SYNC_FROM_DEVICE); ++stats["from_device"]; }
    return 0;
}
#endif
extern "C" int rknn_run(rknn_context ctx, rknn_run_extend *) {
    auto &c = contexts.at(ctx); ++c.frames;
    for (const auto &out : c.outputs)
        std::memset(out.second->virt_addr, int(out.first) + c.frames + 5, out.second->size);
    ++stats["run_calls"]; return 0;
}
