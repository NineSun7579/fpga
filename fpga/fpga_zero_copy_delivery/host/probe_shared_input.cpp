#include "rknn_api.h"
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

// Capability probe only. No PCIe open, no inference and no performance claim.
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    std::ifstream file(argv[1], std::ios::binary);
    std::vector<char> model((std::istreambuf_iterator<char>(file)), {});
    if (!file || model.empty()) return 3;
    rknn_context ctx = 0;
    int rc = rknn_init(&ctx, model.data(), model.size(), 0, nullptr);
    if (rc) { std::cerr << "rknn_init=" << rc << '\n'; return 4; }
    rknn_tensor_attr logical{}, native{};
    const int logical_rc = rknn_query(ctx, RKNN_QUERY_INPUT_ATTR, &logical, sizeof(logical));
    const int native_rc = rknn_query(ctx, RKNN_QUERY_NATIVE_INPUT_ATTR, &native, sizeof(native));
    if (logical_rc || native_rc) { rknn_destroy(ctx); return 5; }
    // Allocate enough for logical RGB and runtime-reported padded native extent.
    const auto bytes = std::max({logical.size, logical.size_with_stride,
                                native.size, native.size_with_stride, uint32_t(640*640*3)});
    auto* mem = rknn_create_mem(ctx, bytes);
    if (!mem) { rknn_destroy(ctx); return 6; }
    rknn_tensor_mem* imported = nullptr;
    if (mem->fd >= 0 && mem->virt_addr)
        imported = rknn_create_mem_from_fd(ctx, mem->fd, mem->virt_addr, bytes, 0);
    rknn_tensor_attr rgb = logical;
    rgb.type = RKNN_TENSOR_UINT8;
    rgb.fmt = RKNN_TENSOR_NHWC;
    rgb.pass_through = 0;
    const int bind_rc = imported ? rknn_set_io_mem(ctx, imported, &rgb) : -999;
    std::cout << "{\"scope\":\"RKNN input memory capability only; no FPGA DMA or inference\","
              << "\"allocated_bytes\":" << bytes << ",\"fd_available\":" << (mem->fd >= 0 ? "true" : "false")
              << ",\"fd_imported\":" << (imported ? "true" : "false")
              << ",\"rgb_binding_rc\":" << bind_rc
              << ",\"logical_type\":" << logical.type << ",\"logical_format\":" << logical.fmt
              << ",\"logical_size\":" << logical.size << ",\"native_type\":" << native.type
              << ",\"native_format\":" << native.fmt << ",\"native_size\":" << native.size
              << ",\"native_stride_bytes\":" << native.size_with_stride << "}\n";
    // Bound memory stays alive through context teardown; no inference is active.
    if (imported) rknn_destroy_mem(ctx, imported);
    rknn_destroy_mem(ctx, mem);
    rknn_destroy(ctx);
    return bind_rc == 0 ? 0 : 7;
}
