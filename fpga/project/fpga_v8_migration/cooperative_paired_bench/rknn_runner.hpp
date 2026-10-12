#pragma once
#include "bench.hpp"
#include "../current_viewer_native_candidate_02/src/current_native_gate.hpp"
#include <QByteArray>
#include <QCryptographicHash>
#include <QVector>
#include <atomic>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>

namespace paired_bench {
inline std::string sha256(const void* p,std::size_t n) {
    require(n<=std::size_t(INT_MAX),"SHA input too large");
    return QCryptographicHash::hash(QByteArray::fromRawData(static_cast<const char*>(p),int(n)),
                                  QCryptographicHash::Sha256).toHex().toStdString();
}
inline std::vector<char> read_bytes(const std::string& path) {
    std::ifstream f(path,std::ios::binary); require(bool(f),"cannot read pinned file");
    std::vector<char> b((std::istreambuf_iterator<char>(f)),{});
    require(!f.bad() && !b.empty(),"empty or failed file read"); return b;
}
// Current decoder's only geometry dependency is .width; square coordinates
// already occupy canonical RGB640, so there is no +80 detection transform.
namespace current_float {
constexpr float IOU_THRESH=0.45f;
using Detection=paired_bench::Detection;
struct Geometry { int width=640,height=640; };
class Decoder {
public:
    int m_nc=3;
    bool m_xyxy=false,m_trafficlight=false;
    Geometry m_geometry;
    std::atomic<float> m_conf{0.25f};
#include "../current_viewer_native_candidate_02/current_retained_decoder.inc"
};
}
class NpuRunner final : public Runner {
    rknn_context ctx_=0;
    bool acquired_=false,terminal_=false,closed_=false;
    std::vector<rknn_tensor_attr> attrs_=std::vector<rknn_tensor_attr>(6);
    rknn_tensor_attr input_{};
    std::vector<rknn_output> outputs_=std::vector<rknn_output>(6);
    raw_dfl::NativeDecoder native_{viewer_native::decoder_config(0.25f)};
    current_float::Decoder production_;
    static void check(int code,const char* operation) {
        if (code!=RKNN_SUCC) throw std::runtime_error(std::string(operation)+" ret="+std::to_string(code));
    }
    void release() {
        // Consume ownership BEFORE the call: uncertain release is never retried.
        acquired_=false;
        check(rknn_outputs_release(ctx_,6,outputs_.data()),"outputs_release");
        for (auto& o:outputs_) o.buf=nullptr;
    }
public:
    std::string model_sha,runtime_sha,api,driver;
    explicit NpuRunner(const std::string& model) {
        try {
            require(!std::getenv("DET_INT8_IN"),"INT8 override forbidden");
            require(std::filesystem::path(model).filename()==
                "det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn","pinned model filename required");
            auto bytes=read_bytes(model); model_sha=sha256(bytes.data(),bytes.size());
            require(model_sha==viewer_native::kModelSha,"model SHA mismatch");
            check(rknn_init(&ctx_,bytes.data(),std::uint32_t(bytes.size()),0,nullptr),"init flags=0");
            auto maps=read_bytes("/proc/self/maps");
            auto paths=viewer_native::mapped_runtime_paths(std::string(maps.begin(),maps.end()));
            require(paths.error.empty(),"runtime mapping invalid");
            std::vector<std::filesystem::path> canonical;
            for (const auto& p:paths.paths) {
                auto c=std::filesystem::canonical(p);
                if (std::find(canonical.begin(),canonical.end(),c)==canonical.end()) canonical.push_back(c);
            }
            require(canonical.size()==1,"ambiguous loaded RKNN runtime");
            auto runtime=read_bytes(canonical[0].string()); runtime_sha=sha256(runtime.data(),runtime.size());
            rknn_input_output_num io{};
            check(rknn_query(ctx_,RKNN_QUERY_IN_OUT_NUM,&io,sizeof(io)),"query IO");
            check(rknn_query(ctx_,RKNN_QUERY_INPUT_ATTR,&input_,sizeof(input_)),"query input");
            for (unsigned i=0;i<6;++i) { attrs_[i].index=i;
                check(rknn_query(ctx_,RKNN_QUERY_OUTPUT_ATTR,&attrs_[i],sizeof(attrs_[i])),"query output"); }
            rknn_sdk_version version{};
            check(rknn_query(ctx_,RKNN_QUERY_SDK_VERSION,&version,sizeof(version)),"query SDK");
            require(viewer_native::terminated(version.api_version,sizeof(version.api_version)) &&
                viewer_native::terminated(version.drv_version,sizeof(version.drv_version)),"SDK unterminated");
            api=version.api_version; driver=version.drv_version;
            viewer_native::Identity id{model_sha,runtime_sha,api,driver,true,io.n_input,io.n_output,3,false,false};
            auto gate=viewer_native::check_current_profile(true,id,input_,attrs_,false,640,640,3);
            if (!gate.enabled) throw std::runtime_error(gate.reason);
        } catch (...) { if (ctx_) { rknn_destroy(ctx_); ctx_=0; } throw; }
    }
    ~NpuRunner() override { if (ctx_) rknn_destroy(ctx_); } // No second output release.
    bool verified_hardware() const override { return closed_ && !terminal_; }
    const auto& input_attr() const { return input_; }
    const auto& output_attrs() const { return attrs_; }
    Inference complete(Profile p,const std::vector<std::uint8_t>& rgb) override {
        require(!terminal_ && !closed_ && !acquired_,"NPU runner terminal");
        Inference result;
        try {
            require(rgb.size()==coop_host::kFrameBytes,"RGB input size");
            std::array<Clock::time_point,6> ticks; ticks[0]=Clock::now();
            rknn_input in{}; in.buf=const_cast<std::uint8_t*>(rgb.data()); in.size=std::uint32_t(rgb.size());
            in.type=RKNN_TENSOR_UINT8; in.fmt=RKNN_TENSOR_NHWC; in.pass_through=0;
            check(rknn_inputs_set(ctx_,1,&in),"inputs_set"); ticks[1]=Clock::now();
            check(rknn_run(ctx_,nullptr),"blocking_run"); ticks[2]=Clock::now();
            const bool floats=p==Profile::Baseline;
            for (unsigned i=0;i<6;++i) { outputs_[i]={}; outputs_[i].index=i; outputs_[i].want_float=floats; }
            check(rknn_outputs_get(ctx_,6,outputs_.data(),nullptr),"outputs_get"); acquired_=true;
            for (unsigned i=0;i<6;++i) {
                const auto& o=outputs_[i];
                require(o.index==attrs_[i].index && o.buf && !o.is_prealloc && o.want_float==floats &&
                    o.size==attrs_[i].n_elems*(floats ? sizeof(float) : 1),"packed output contract");
                require(!floats || reinterpret_cast<std::uintptr_t>(o.buf)%alignof(float)==0,"unaligned float");
            }
            ticks[3]=Clock::now();
            if (floats) { const auto decoded=production_.decode(outputs_,attrs_);
                result.owned.assign(decoded.begin(),decoded.end()); }
            else { const auto decoded=native_.decode(outputs_,attrs_);
                result.owned.reserve(decoded.size());
                for (const auto& d:decoded) result.owned.push_back({d.x1,d.y1,d.x2,d.y2,d.score,d.cls}); }
            ticks[4]=Clock::now(); release(); ticks[5]=Clock::now();
            for (unsigned i=0;i<5;++i) result.stages[i]=ms(ticks[i],ticks[i+1]);
            return result;
        } catch (...) {
            terminal_=true;
            if (acquired_) { try { release(); } catch (...) {} }
            throw;
        }
    }
    void close() override {
        require(!terminal_ && !acquired_ && !closed_,"cannot close failed NPU runner");
        const auto ctx=ctx_; ctx_=0;
        try { check(rknn_destroy(ctx),"destroy"); closed_=true; }
        catch (...) { terminal_=true; throw; }
    }
};
} // namespace paired_bench
