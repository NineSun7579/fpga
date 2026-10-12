#include <climits>
#include <cstdlib>
#include <fstream>
#include "provider.hpp"
#include "cooperative_paired_bench/rknn_runner.hpp"
#include <iomanip>
#include <iostream>
#include <numeric>
#include <set>
#include <tuple>

namespace {
std::vector<std::uint8_t> cpu_preprocess(const std::vector<std::uint8_t>& raw) {
    paired_bench::require(raw.size()==640*480*2,"RAW length mismatch");
    std::vector<std::uint8_t> rgb(640*640*3,114);
    for (std::size_t i=0;i<640*480;++i) {
        const unsigned p=raw[2*i] | (unsigned(raw[2*i+1])<<8);
        const unsigned r=(p>>11)&31, g=(p>>5)&63, b=p&31;
        const auto j=(640*80+i)*3;
        rgb[j]=(r<<3)|(r>>2); rgb[j+1]=(g<<2)|(g>>4); rgb[j+2]=(b<<3)|(b>>2);
    }
    return rgb;
}
double inference_ms(const paired_bench::Inference& result) {
    return std::accumulate(result.stages.begin(),result.stages.end(),0.0);
}
struct Row {
    delivery::Lease lease;
    std::string raw_sha,rgb_sha;
    double claim,raw,prep,fpga,cpu_infer,fpga_infer,release;
};
}

int main(int argc,char** argv) {
    std::unique_ptr<delivery::Provider> provider;
    try {
        paired_bench::require(argc==4,"usage: paired_preprocess PINNED_MODEL WARMUP PAIRS");
        const int warmup=std::stoi(argv[2]), count=std::stoi(argv[3]);
        paired_bench::require(warmup>=0 && warmup<=1000 && count>=1 && count<=10000,"invalid counts");
        paired_bench::NpuRunner npu(argv[1]);
        provider=delivery::bind_provider();
        paired_bench::require(bool(provider),"no hardware provider");
        const auto signature=provider->rtl_signature();
        paired_bench::require(signature==0x444c5632,"wrong RTL signature");
        std::set<std::tuple<std::uint32_t,std::uint32_t,std::uint32_t>> seen;
        std::vector<Row> rows;
        for (int i=0;i<warmup+count;++i) {
            Row row{};
            const auto c0=paired_bench::Clock::now(); row.lease=provider->claim();
            row.claim=paired_bench::ms(c0,paired_bench::Clock::now());
            paired_bench::require(seen.emplace(row.lease.generation,row.lease.sequence,row.lease.camera).second,
                                  "duplicate frame lease");
            std::vector<std::uint8_t> raw,cpu,fpga;
            const auto baseline=[&] {
                const auto t0=paired_bench::Clock::now(); raw=provider->read_raw(row.lease);
                const auto t1=paired_bench::Clock::now(); cpu=cpu_preprocess(raw);
                const auto t2=paired_bench::Clock::now();
                row.raw=paired_bench::ms(t0,t1); row.prep=paired_bench::ms(t1,t2);
            };
            const auto accelerated=[&] {
                const auto t0=paired_bench::Clock::now(); fpga=provider->preprocess_and_read_rgb(row.lease);
                row.fpga=paired_bench::ms(t0,paired_bench::Clock::now());
            };
            if (i&1) { accelerated(); baseline(); } else { baseline(); accelerated(); }
            if (cpu!=fpga) {
                const auto count=std::min(cpu.size(),fpga.size());
                std::size_t differences=0;
                for (std::size_t j=0;j<count;++j) if (cpu[j]!=fpga[j]) {
                    if (differences<12) std::cerr<<"byte-mismatch offset="<<j
                        <<" cpu="<<unsigned(cpu[j])<<" fpga="<<unsigned(fpga[j])<<std::endl;
                    ++differences;
                }
                std::cerr<<"byte-parity sizes="<<cpu.size()<<","<<fpga.size()
                         <<" differences="<<differences<<std::endl;
                if (const auto prefix=std::getenv("DELIVERY_MISMATCH_PREFIX")) {
                    const auto save=[&](const char* suffix,const std::vector<std::uint8_t>& bytes) {
                        std::ofstream out(std::string(prefix)+suffix,std::ios::binary);
                        out.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());
                        paired_bench::require(bool(out),"cannot save mismatch evidence");
                    };
                    save(".raw",raw); save(".cpu.rgb",cpu); save(".fpga.rgb",fpga);
                }
            }
            paired_bench::require(cpu==fpga,"FPGA input byte mismatch");
            row.raw_sha=paired_bench::sha256(raw.data(),raw.size());
            row.rgb_sha=paired_bench::sha256(cpu.data(),cpu.size());
            paired_bench::Inference a,b;
            // Identical model/context, UINT8 NHWC input, native outputs and decoder
            // for BOTH arms. Alternating execution reduces order bias.
            if (i&1) {
                b=npu.complete(paired_bench::Profile::Cooperative,fpga);
                a=npu.complete(paired_bench::Profile::Cooperative,cpu);
            } else {
                a=npu.complete(paired_bench::Profile::Cooperative,cpu);
                b=npu.complete(paired_bench::Profile::Cooperative,fpga);
            }
            paired_bench::require(paired_bench::parity(a.owned,b.owned),"detection parity failure");
            row.cpu_infer=inference_ms(a); row.fpga_infer=inference_ms(b);
            const auto release_start=paired_bench::Clock::now();
            provider->release(row.lease); // a failure goes directly to quarantine
            row.release=paired_bench::ms(release_start,paired_bench::Clock::now());
            if (i>=warmup) rows.push_back(row);
        }
        npu.close(); provider->finish();
        paired_bench::require(npu.verified_hardware(),"NPU completion not verified");
        std::cout<<std::fixed<<std::setprecision(6);
        std::cout<<"{\"kind\":\"identity\",\"model_sha256\":\""<<npu.model_sha
                 <<"\",\"runtime_sha256\":\""<<npu.runtime_sha
                 <<"\",\"rtl_signature\":"<<signature<<"}\n";
        for (const auto& r:rows) {
            std::cout<<"{\"kind\":\"pair\",\"generation\":"<<r.lease.generation
                <<",\"sequence\":"<<r.lease.sequence<<",\"camera\":"<<r.lease.camera
                <<",\"source_ddr\":"<<r.lease.source_ddr
                <<",\"raw_sha256\":\""<<r.raw_sha<<"\",\"rgb_sha256\":\""<<r.rgb_sha
                <<"\",\"claim_ms\":"<<r.claim<<",\"raw_dma_ms\":"<<r.raw
                <<",\"cpu_preprocess_ms\":"<<r.prep<<",\"fpga_preprocess_and_dma_ms\":"<<r.fpga
                <<",\"cpu_inference_ms\":"<<r.cpu_infer<<",\"fpga_inference_ms\":"<<r.fpga_infer
                <<",\"release_ms\":"<<r.release
                <<",\"cpu_total_ms\":"<<r.claim+r.raw+r.prep+r.cpu_infer+r.release
                <<",\"fpga_total_ms\":"<<r.claim+r.fpga+r.fpga_infer+r.release<<"}\n";
        }
        std::cout<<"{\"kind\":\"pass\",\"pairs\":"<<rows.size()<<"}\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr<<"FAIL: "<<e.what()<<std::endl;
        if (provider) provider->quarantine();
        return 2;
    }
}
