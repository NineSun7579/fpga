#pragma once
#include "rknn_api.h"
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

namespace offload {
using Clock = std::chrono::steady_clock;
inline double elapsed(Clock::time_point a, Clock::time_point b) {
    return std::chrono::duration<double, std::milli>(b-a).count();
}
inline void require(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
inline void rcheck(int rc, const char* why) {
    if (rc) throw std::runtime_error(std::string(why)+" rc="+std::to_string(rc));
}
struct NativeResult {
    std::vector<std::vector<uint8_t>> outputs;
    // submit or sync, blocking run, output acquisition, output release.
    // CPU output copying for parity is outside these timing intervals.
    std::array<double, 4> stages{};
};
class BoundRknn {
    rknn_context ctx_ = 0;
    rknn_tensor_mem* input_mem_ = nullptr;
    rknn_tensor_attr input_{};
    std::vector<rknn_tensor_attr> output_attrs_;
    bool failed_ = false;
    bool coherent_input_ = false;
    NativeResult execute(Clock::time_point started, Clock::time_point submitted) {
        NativeResult result;
        std::vector<rknn_output> outputs(output_attrs_.size());
        for (unsigned i=0; i<outputs.size(); ++i) outputs[i].index=i;
        bool acquired=false;
        try {
            rcheck(rknn_run(ctx_, nullptr), "rknn_run");
            const auto ran=Clock::now();
            rcheck(rknn_outputs_get(ctx_, outputs.size(), outputs.data(), nullptr), "rknn_outputs_get");
            acquired=true;
            const auto got=Clock::now();
            for (unsigned i=0; i<outputs.size(); ++i) {
                require(outputs[i].buf && outputs[i].size == output_attrs_[i].size,
                        "Unexpected packed native output");
                const auto* p=static_cast<const uint8_t*>(outputs[i].buf);
                result.outputs.emplace_back(p,p+outputs[i].size);
            }
            const auto release_start=Clock::now();
            acquired=false; // uncertain release must never be retried
            rcheck(rknn_outputs_release(ctx_, outputs.size(), outputs.data()), "rknn_outputs_release");
            const auto released=Clock::now();
            result.stages={elapsed(started,submitted),elapsed(submitted,ran),elapsed(ran,got),elapsed(release_start,released)};
            return result;
        } catch (...) {
            failed_=true;
            if (acquired) rknn_outputs_release(ctx_, outputs.size(), outputs.data());
            throw;
        }
    }
public:
    static constexpr uint32_t InputBytes=640*640*3;
    BoundRknn(const BoundRknn&)=delete;
    BoundRknn& operator=(const BoundRknn&)=delete;
    explicit BoundRknn(const char* model_path, bool coherent_input=false) : coherent_input_(coherent_input) {
        try {
            std::ifstream f(model_path,std::ios::binary);
            std::vector<char> model((std::istreambuf_iterator<char>(f)),{});
            require(bool(f) && !model.empty(),"Cannot read model");
            const uint32_t flags=coherent_input_ ? RKNN_FLAG_DISABLE_FLUSH_INPUT_MEM_CACHE : 0;
            rcheck(rknn_init(&ctx_,model.data(),model.size(),flags,nullptr),"rknn_init");
            rknn_input_output_num io{};
            rcheck(rknn_query(ctx_,RKNN_QUERY_IN_OUT_NUM,&io,sizeof(io)),"query IO");
            require(io.n_input==1 && io.n_output==6,"Pinned V8 IO expected");
            rcheck(rknn_query(ctx_,RKNN_QUERY_INPUT_ATTR,&input_,sizeof(input_)),"query input");
            require(input_.n_dims==4 && input_.dims[0]==1 && input_.dims[1]==640 &&
                    input_.dims[2]==640 && input_.dims[3]==3 && input_.fmt==RKNN_TENSOR_NHWC &&
                    input_.size==InputBytes,"Pinned V8 input geometry expected");
            output_attrs_.resize(io.n_output);
            for (unsigned i=0;i<io.n_output;++i) {
                output_attrs_[i].index=i;
                rcheck(rknn_query(ctx_,RKNN_QUERY_OUTPUT_ATTR,&output_attrs_[i],sizeof(rknn_tensor_attr)),"query output");
            }
        } catch (...) {
            if (ctx_) rknn_destroy(ctx_);
            ctx_=0;
            throw;
        }
    }
    ~BoundRknn() {
        if (input_mem_) rknn_destroy_mem(ctx_,input_mem_);
        if (ctx_) rknn_destroy(ctx_);
    }
    // The caller retains fd, mmap and slot lease until this object is destroyed.
    // base is the full DMA-BUF mapping's start, not base+offset.
    void bind(int fd,void* base,uint32_t offset) {
        require(!input_mem_ && !failed_ && fd>=0 && base,"Invalid shared input binding");
        input_mem_=rknn_create_mem_from_fd(ctx_,fd,base,InputBytes,offset);
        require(input_mem_!=nullptr,"RKNN DMA-BUF import failed");
        auto attr=input_;
        attr.type=RKNN_TENSOR_UINT8; attr.fmt=RKNN_TENSOR_NHWC; attr.pass_through=0;
        rcheck(rknn_set_io_mem(ctx_,input_mem_,&attr),"rknn_set_io_mem");
    }
    NativeResult conventional(const uint8_t* rgb,uint32_t size) {
        require(!input_mem_ && !coherent_input_ && !failed_ && rgb && size==InputBytes,"Invalid conventional input");
        rknn_input in{};
        in.buf=const_cast<uint8_t*>(rgb); in.size=size;
        in.type=RKNN_TENSOR_UINT8; in.fmt=RKNN_TENSOR_NHWC;
        const auto started=Clock::now();
        rcheck(rknn_inputs_set(ctx_,1,&in),"rknn_inputs_set");
        return execute(started,Clock::now());
    }
    NativeResult bound() {
        require(input_mem_ && coherent_input_ && !failed_,"Coherent shared input not bound");
        // Producer completion and cross-device DMA-BUF ownership are the
        // caller's responsibility. No input memcpy or inputs_set occurs here.
        const auto started=Clock::now();
        // PCIe writes coherent allocator backing. Its completed DMA plus the
        // driver's lease barriers publishes it to the NPU importer. Flushing a
        // cached CPU alias would be wrong; there is no CPU producer here.
        return execute(started,Clock::now());
    }
};
} // namespace offload
