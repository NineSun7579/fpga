#include "hardware_inference.h"
#include <cassert>
#include <cstdio>
#include <cstring>

extern "C" void mock_reset();
extern "C" void mock_fail(const char *, int);
extern "C" int mock_stat(const char *);
extern "C" int mock_live_contexts();
extern "C" int mock_live_memories();
extern "C" int mock_input_equal(rknn_context, const void *, uint32_t);
extern "C" void mock_runtime_supported(int);

static rknn_context legacy(std::vector<rknn_tensor_attr> &attrs) {
    rknn_context ctx = 0;
    assert(rknn_init(&ctx, nullptr, 1, 0, nullptr) == 0);
    attrs.resize(4);
    for (uint32_t i = 0; i < 4; ++i) {
        attrs[i] = rknn_tensor_attr{}; attrs[i].index = i;
        assert(rknn_query(ctx, RKNN_QUERY_OUTPUT_ATTR, &attrs[i], sizeof(attrs[i])) == 0);
    }
    return ctx;
}
static void failure(const char *stage, int at) {
    mock_reset(); std::vector<rknn_tensor_attr> attrs;
    const auto old = legacy(attrs);
    // Call counters include the original context init and its attr queries.
    mock_fail(stage, at);
    std::string reason; const char model = 0;
    auto candidate = HardwareInference::create(&model, 1, attrs, true, reason);
    assert(!candidate && !reason.empty());
    assert(mock_live_contexts() == 1 && mock_live_memories() == 0);
    assert(mock_stat("run_calls") == 0);
    assert(rknn_destroy(old) == 0 && mock_live_contexts() == 0);
}

static void rejectOutputOnly() {
    mock_reset(); std::vector<rknn_tensor_attr> attrs;
    const auto old = legacy(attrs);
    std::string reason; const char model = 0;
    auto declined = HardwareInference::create(&model, 1, attrs, false, reason);
    assert(!declined && reason == "native_output_only_not_certified_target_runtime");
    assert(mock_live_contexts() == 1 && mock_live_memories() == 0);
    assert(mock_stat("init_calls") == 1 && mock_stat("query_calls") == 4);
    assert(mock_stat("allocate_calls") == 0 && mock_stat("bind_calls") == 0 && mock_stat("sync_calls") == 0);
    // Rejection leaves the existing context usable for subsequent legacy work.
    assert(rknn_run(old, nullptr) == 0 && mock_stat("run_calls") == 1);
    rknn_destroy(old);
    std::puts("PASS output-only rejected before native setup; legacy context remains usable");
}

int main(int argc, char **argv) {
    const bool missingSync = argc > 1 && std::strcmp(argv[1], "missing-sync") == 0;
    const bool oldAllocator = argc > 1 && std::strcmp(argv[1], "old-allocator") == 0;
    rejectOutputOnly();
    if (missingSync) {
        mock_reset(); std::vector<rknn_tensor_attr> attrs;
        const auto old = legacy(attrs); std::string reason; const char model = 0;
        auto declined = HardwareInference::create(&model, 1, attrs, true, reason);
        assert(!declined && reason == "native_runtime_symbols_unavailable");
        assert(mock_live_contexts() == 1 && mock_stat("allocate_calls") == 0);
        rknn_destroy(old);
        std::puts("PASS optional symbol absent: legacy context untouched"); return 0;
    }
    failure("init", 2);
    failure("query", 8);     // Candidate logical query after version, count and input.
    failure("query", 15);    // Last native output query: no allocations yet.
    failure("allocate", 3); // Unwind two successfully bound memories.
    failure("allocate", 5); // Unwind all outputs when input allocation fails.
    failure("bind", 3);
    failure("bind", 5);
    failure("sync", 2);
    failure("sync", 5);
    {
        mock_reset(); std::vector<rknn_tensor_attr> attrs;
        const auto old = legacy(attrs); std::string reason; const char model = 0;
        mock_runtime_supported(false);
        auto declined = HardwareInference::create(&model, 1, attrs, true, reason);
        assert(!declined && reason == "runtime_not_eligible_for_target_FP16_scale_policy");
        assert(mock_live_contexts() == 1 && mock_live_memories() == 0);
        rknn_destroy(old);
    }

    {
        mock_reset(); std::vector<rknn_tensor_attr> attrs;
        const auto old = legacy(attrs); std::string reason; const char model = 0;
        auto candidate = HardwareInference::create(&model, 1, attrs, true, reason);
        assert(candidate && reason == "all_native_bindings_and_sync_validated");
        assert(candidate->context() != old && candidate->usesNativeInput());
        assert(mock_live_contexts() == 2 && mock_live_memories() == 5);
        assert(mock_stat("input_bindings") == 1 && mock_stat("output_bindings") == 4);
        assert(mock_stat("create_mem_calls") == (oldAllocator ? 5 : 0));
        assert(mock_stat("create_mem2_calls") == (oldAllocator ? 0 : 5));
        std::vector<void *> outputPointers;
        for (const auto &out : candidate->outputs()) {
            assert(out.want_float == 1 && out.is_prealloc == 1 && out.buf && out.size);
            outputPointers.push_back(out.buf);
        }
        std::vector<unsigned char> input(HardwareInference::InputBytes);
        for (size_t i = 0; i < input.size(); ++i) input[i] = static_cast<unsigned char>(i);
        for (int frame = 1; frame <= 2; ++frame) {
            assert(candidate->writeInput(input.data(), input.size()));
            assert(mock_input_equal(candidate->context(), input.data(), uint32_t(input.size())));
            assert(rknn_run(candidate->context(), nullptr) == 0);
            assert(candidate->readOutputs());
            for (size_t i = 0; i < attrs.size(); ++i) {
                const auto &out = candidate->outputs()[i];
                assert(out.buf == outputPointers[i] && out.index == i && out.size == attrs[i].n_elems * 4);
                const float *values = static_cast<const float *>(out.buf);
                const float scale = NativePlan::half(NativePlan::halfBits(attrs[i].scale));
                assert(scale != attrs[i].scale); // The mock exercises policy selection.
                assert(values[0] == float(i + frame + 5) * scale);
                assert(values[attrs[i].n_elems - 1] == values[0]);
            }
        }
        assert(mock_stat("bind_calls") == 5); // No per-frame binds.
        assert(mock_stat("to_device") == 3);
        assert(mock_stat("from_device") == 12);
        const float before = static_cast<float *>(candidate->outputs()[0].buf)[0];
        assert(rknn_run(candidate->context(), nullptr) == 0);
        mock_fail("sync", mock_stat("sync_calls") + 2);
        assert(!candidate->readOutputs() && !candidate->error().empty());
        // A failure on the second sync publishes no first-tensor conversion.
        assert(static_cast<float *>(candidate->outputs()[0].buf)[0] == before);
        auto cachedCopy = candidate;
        candidate.reset();
        assert(mock_live_contexts() == 2); // QVector copies share one owner.
        cachedCopy.reset();
        assert(mock_live_contexts() == 1 && mock_live_memories() == 0);
        assert(mock_stat("destroy_mem_calls") == 5);
        rknn_destroy(old);
    }
    std::puts("PASS separate-context rollback, ownership, persistent descriptors, UINT8 input bytes, sync and optional allocator");
}
