#include "rknn_api.h"
#include <algorithm>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <vector>

static void check(int rc, const char* name) {
    if (rc) throw std::runtime_error(std::string(name) + " rc=" + std::to_string(rc));
}
static std::vector<char> load(const char* path) {
    std::ifstream f(path, std::ios::binary);
    std::vector<char> v((std::istreambuf_iterator<char>(f)), {});
    if (!f || v.empty()) throw std::runtime_error("Cannot read file");
    return v;
}
int main(int argc, char** argv) {
    if (argc != 3 && argc != 4) return 2;
    rknn_context ctx = 0;
    rknn_tensor_mem *allocation = nullptr, *imported = nullptr;
    try {
        auto model = load(argv[1]);
        auto fixture = load(argv[2]);
        const unsigned offset = argc == 4 ? std::stoul(argv[3]) : 0;
        if (offset > 4*1024*1024) throw std::runtime_error("Offset out of range");
        if (fixture.size() != 640*640*3) throw std::runtime_error("Expected RGB640 input");
        std::vector<std::vector<char>> inputs{fixture, fixture};
        for (auto& byte : inputs[1]) byte = static_cast<char>(static_cast<unsigned char>(byte) ^ 0x5a);
        check(rknn_init(&ctx, model.data(), model.size(), 0, nullptr), "init");
        rknn_input_output_num io{};
        check(rknn_query(ctx, RKNN_QUERY_IN_OUT_NUM, &io, sizeof(io)), "query IO");
        if (io.n_input != 1 || !io.n_output) throw std::runtime_error("Unexpected IO count");
        rknn_tensor_attr attr{};
        check(rknn_query(ctx, RKNN_QUERY_INPUT_ATTR, &attr, sizeof(attr)), "query input");
        if (attr.fmt != RKNN_TENSOR_NHWC || attr.n_dims != 4 || attr.dims[0] != 1 ||
            attr.dims[1] != 640 || attr.dims[2] != 640 || attr.dims[3] != 3)
            throw std::runtime_error("Unexpected input geometry");
        auto infer = [&]() {
            check(rknn_run(ctx, nullptr), "run");
            std::vector<rknn_output> outputs(io.n_output);
            for (unsigned i=0; i<io.n_output; ++i) outputs[i].index=i;
            check(rknn_outputs_get(ctx, io.n_output, outputs.data(), nullptr), "get");
            std::vector<std::vector<char>> copy;
            try {
                for (const auto& output : outputs) {
                    if (!output.buf || !output.size) throw std::runtime_error("Empty output");
                    const char* bytes = static_cast<const char*>(output.buf);
                    copy.emplace_back(bytes, bytes + output.size);
                }
            } catch (...) { rknn_outputs_release(ctx, io.n_output, outputs.data()); throw; }
            check(rknn_outputs_release(ctx, io.n_output, outputs.data()), "release");
            return copy;
        };
        std::vector<std::vector<std::vector<char>>> reference;
        for (auto& rgb : inputs) {
            rknn_input in{};
            in.buf=rgb.data(); in.size=rgb.size(); in.type=RKNN_TENSOR_UINT8; in.fmt=RKNN_TENSOR_NHWC;
            check(rknn_inputs_set(ctx, 1, &in), "inputs_set");
            reference.push_back(infer());
        }
        const uint32_t extent = std::max({attr.size, attr.size_with_stride, uint32_t(fixture.size())});
        allocation = rknn_create_mem(ctx, extent + offset);
        if (!allocation || allocation->fd < 0 || !allocation->virt_addr)
            throw std::runtime_error("Shared allocation failed");
        imported = rknn_create_mem_from_fd(ctx, allocation->fd, allocation->virt_addr, extent, offset);
        if (!imported) throw std::runtime_error("Import failed");
        attr.type=RKNN_TENSOR_UINT8; attr.fmt=RKNN_TENSOR_NHWC; attr.pass_through=0;
        check(rknn_set_io_mem(ctx, imported, &attr), "set_io_mem");
        size_t output_bytes=0;
        for (size_t i=0; i<inputs.size(); ++i) {
            std::memcpy(static_cast<char*>(allocation->virt_addr) + offset, inputs[i].data(), inputs[i].size());
            check(rknn_mem_sync(ctx, imported, RKNN_MEMORY_SYNC_TO_DEVICE), "sync");
            const auto actual = infer();
            if (actual != reference[i]) throw std::runtime_error("Native output bytes differ");
            for (const auto& output : actual) output_bytes += output.size();
        }
        const bool outputs_distinct = reference[0] != reference[1];
        if (!outputs_distinct) throw std::runtime_error("Fixture outputs identical; stale-input check inconclusive");
        std::cout << "{\"pass\":true,\"fixtures\":2,\"outputs_per_fixture\":" << io.n_output
                  << ",\"input_offset\":" << offset << ",\"native_output_bytes_compared\":" << output_bytes
                  << ",\"distinct_outputs\":true,\"scope\":\"RKNN shared memory binding only; CPU memcpy produces input; no PCIe zero-copy claim\"}\n";
        rknn_destroy_mem(ctx, imported); imported=nullptr;
        rknn_destroy_mem(ctx, allocation); allocation=nullptr;
        check(rknn_destroy(ctx), "destroy"); ctx=0;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        if (imported) rknn_destroy_mem(ctx, imported);
        if (allocation) rknn_destroy_mem(ctx, allocation);
        if (ctx) rknn_destroy(ctx);
        return 1;
    }
}
