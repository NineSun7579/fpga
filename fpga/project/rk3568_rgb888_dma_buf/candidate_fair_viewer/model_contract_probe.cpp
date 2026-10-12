// Standalone target RKNN probe. No Qt, PCIe, DMA-BUF or viewer/device access.
// Build: g++ -std=c++17 -O2 model_contract_probe.cpp -lrknnrt -o model_contract_probe
#include "scheme2_contract.h"
#include "scheme2_verify.h"
#include <cstdio>
#include <fstream>
#include <iterator>
#include <stdexcept>

static void check(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
static void api(int rc, const char* why) {
    if (rc) throw std::runtime_error(std::string(why) + " rc=" + std::to_string(rc));
}
static void logAttr(const char* kind, const rknn_tensor_attr& a) {
    std::printf("[contract-probe] %s index=%u fmt=%d type=%d size=%u stride_bytes=%u w_stride=%u h_stride=%u elems=%u dims=",
        kind,a.index,int(a.fmt),int(a.type),a.size,a.size_with_stride,a.w_stride,a.h_stride,a.n_elems);
    for (uint32_t i=0;i<a.n_dims;++i) std::printf("%s%u",i?"/":"",a.dims[i]);
    std::printf(" zp=%d scale=%.9g pass_through=%u\n",a.zp,a.scale,a.pass_through);
}
struct Context {
    rknn_context ctx=0;
    rknn_tensor_mem* mem=nullptr;
    rknn_tensor_attr input{};
    std::vector<rknn_tensor_attr> outputs;
    void init(std::vector<char>& bytes) {
        api(rknn_init(&ctx,bytes.data(),uint32_t(bytes.size()),0,nullptr),"init default flags");
        rknn_input_output_num io{};
        api(rknn_query(ctx,RKNN_QUERY_IN_OUT_NUM,&io,sizeof(io)),"query IO");
        check(io.n_input==1 && io.n_output>0,"one input and nonempty outputs required");
        api(rknn_query(ctx,RKNN_QUERY_INPUT_ATTR,&input,sizeof(input)),"query input");
        outputs.resize(io.n_output);
        for(uint32_t i=0;i<io.n_output;++i) {
            outputs[i].index=i;
            api(rknn_query(ctx,RKNN_QUERY_OUTPUT_ATTR,&outputs[i],sizeof(outputs[i])),"query output");
        }
    }
    std::vector<std::vector<uint8_t>> run() {
        api(rknn_run(ctx,nullptr),"run");
        std::vector<rknn_output> out(outputs.size());
        for(size_t i=0;i<out.size();++i) out[i].index=uint32_t(i);
        api(rknn_outputs_get(ctx,uint32_t(out.size()),out.data(),nullptr),"get native outputs");
        std::vector<std::vector<uint8_t>> result;
        try {
            for(size_t i=0;i<out.size();++i) {
                check(out[i].buf && out[i].size==outputs[i].size && out[i].size>0,"native output size unsupported");
                const auto* p=static_cast<const uint8_t*>(out[i].buf);
                result.emplace_back(p,p+out[i].size);
            }
        } catch (...) { rknn_outputs_release(ctx,uint32_t(out.size()),out.data()); throw; }
        api(rknn_outputs_release(ctx,uint32_t(out.size()),out.data()),"release native outputs");
        return result;
    }
    ~Context() { if(mem) rknn_destroy_mem(ctx,mem); if(ctx) rknn_destroy(ctx); }
};
int main(int argc,char** argv) {
    if(argc!=2) { std::fprintf(stderr,"usage: model_contract_probe MODEL.rknn\n"); return 2; }
    try {
        std::ifstream file(argv[1],std::ios::binary);
        std::vector<char> model((std::istreambuf_iterator<char>(file)),{});
        check(bool(file)&&!model.empty(),"cannot read model");
        Context conventional,bound; conventional.init(model); bound.init(model);
        logAttr("conventional-native",conventional.input); logAttr("bound-native-before-bind",bound.input);
        check(scheme2::sameTensor(conventional.input,bound.input),"input contexts differ");
        const int height=int(bound.input.dims[1]);
        check(scheme2::packedInput(bound.input,height),"dense NHWC INT8/UINT8 contract required");
        check(conventional.outputs.size()==bound.outputs.size(),"output count differs");
        for(size_t i=0;i<bound.outputs.size();++i) {
            logAttr("native-output",bound.outputs[i]);
            check(scheme2::sameTensor(conventional.outputs[i],bound.outputs[i]),"output contexts differ");
        }
        const uint32_t size=scheme2::bytes(height);
        bound.mem=rknn_create_mem(bound.ctx,size);
        check(bound.mem && bound.mem->virt_addr && bound.mem->size>=size,"ordinary RKNN memory allocation failed");
        auto user=scheme2::userInput(bound.input); logAttr("bound-user-before-bind",user);
        api(rknn_set_io_mem(bound.ctx,bound.mem,&user),"bind UINT8 user input pass_through=0");
        std::vector<uint8_t> pattern(size);
        for(unsigned pair=0;pair<3;++pair) {
            for(size_t i=0;i<pattern.size();++i)
                pattern[i]=pair==0 ? uint8_t(i) : pair==1 ? uint8_t((i*73+(i>>8)*19+41)&255) : uint8_t(((i/3)^((i/1920)*17)^0xa5)&255);
            rknn_input input{}; input.buf=pattern.data(); input.size=size;
            input.type=RKNN_TENSOR_UINT8; input.fmt=RKNN_TENSOR_NHWC;
            api(rknn_inputs_set(conventional.ctx,1,&input),"set conventional UINT8 input");
            const auto expected=conventional.run();
            std::memcpy(bound.mem->virt_addr,pattern.data(),size);
            // Default runtime flags retain ordinary-memory input cache handling.
            const auto actual=bound.run();
            size_t total=0;
            for(size_t i=0;i<expected.size();++i) {
                check(expected[i].size()==actual[i].size(),"native sizes differ");
                const size_t bad=scheme2::mismatch(expected[i].data(),actual[i].data(),expected[i].size());
                if(bad!=expected[i].size()) {
                    std::fprintf(stderr,"[contract-probe] FAIL pair=%u output=%zu byte=%zu expected=%u actual=%u\n",pair+1,i,bad,expected[i][bad],actual[i][bad]);
                    return 1;
                }
                total+=actual[i].size();
            }
            std::printf("[contract-probe] PASS pair=%u input_bytes=%u outputs=%zu native_bytes=%zu exact=1 want_float=0 flags=0 ordinary_mem=1 pci_access=0\n",pair+1,size,actual.size(),total);
        }
        std::puts("[contract-probe] ALL_3_PAIRS_PASS runtime_uint8_to_native_binding=1 dma_buf_parity_pending=1");
        return 0;
    } catch(const std::exception& e) {
        std::fprintf(stderr,"[contract-probe] ERROR %s\n",e.what()); return 1;
    }
}
