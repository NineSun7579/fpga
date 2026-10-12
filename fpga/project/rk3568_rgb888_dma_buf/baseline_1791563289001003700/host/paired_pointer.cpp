#include "pcie_session.hpp"
#ifdef OFFLOAD_SHARED_INPUT
#include "shared_consumer.hpp"
#endif
#include <iomanip>
#include <memory>
#include <numeric>
#include <time.h>

static double process_cpu_ms() {
    timespec value{};
    offload::require(clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&value)==0,"Process CPU clock failed");
    return double(value.tv_sec)*1000+double(value.tv_nsec)/1000000;
}

static std::vector<uint8_t> preprocess(const std::vector<uint8_t>& raw) {
    offload::require(raw.size()==640*480*2,"Wrong RAW size");
    std::vector<uint8_t> rgb(640*640*3,114);
    for (size_t i=0;i<640*480;++i) {
        const unsigned p=raw[2*i] | (unsigned(raw[2*i+1])<<8);
        const unsigned r=(p>>11)&31,g=(p>>5)&63,b=p&31;
        const auto j=(640*80+i)*3;
        rgb[j]=(r<<3)|(r>>2); rgb[j+1]=(g<<2)|(g>>4); rgb[j+2]=(b<<3)|(b>>2);
    }
    return rgb;
}
int main(int argc,char** argv) {
    std::unique_ptr<offload::PcieSession> session;
#ifdef OFFLOAD_SHARED_INPUT
    std::unique_ptr<offload::SharedConsumer> consumer;
#endif
    try {
        offload::require(argc==4,"usage: paired_pointer MODEL WARMUP PAIRS");
        const int warmup=std::stoi(argv[2]),pairs=std::stoi(argv[3]);
        offload::require(warmup>=0 && warmup<=100 && pairs>0 && pairs<=10000,"Invalid counts");
        offload::BoundRknn npu(argv[1]);
        session=std::make_unique<offload::PcieSession>();
#ifdef OFFLOAD_SHARED_INPUT
        consumer=std::make_unique<offload::SharedConsumer>(*session,argv[1]);
#endif
        std::cout<<std::fixed<<std::setprecision(6);
#ifdef OFFLOAD_SHARED_INPUT
        std::cout<<"{\"kind\":\"identity\",\"input_mode\":\"PCIe RX DMA-BUF bound to RKNN input, no input memcpy or inputs_set\",\"baseline_init_flags\":0,\"shared_init_flags\":16384,\"input_slot\":"
                 <<offload::PcieSession::InputOffset<<",\"output_comparison\":\"native output byte parity\"}\n";
#else
        std::cout<<"{\"kind\":\"identity\",\"input_mode\":\"borrowed coherent RX pointer with inputs_set; not DMA-BUF zero-copy\",\"input_slot\":"
                 <<offload::PcieSession::InputOffset<<",\"output_comparison\":\"native output byte parity\"}\n";
#endif
        for (int i=0;i<warmup+pairs;++i) {
            const auto claim_start=offload::Clock::now();
            const auto lease=session->claim_rgb();
            const auto claim_ms=offload::elapsed(claim_start,offload::Clock::now());
            double raw_ms=0,prep_ms=0,fpga_ms=0;
            double cpu_path_cpu_ms=0,fpga_path_cpu_ms=0;
            offload::NativeResult a,b;
            std::vector<uint8_t> raw,cpu;
            const uint8_t* fpga=nullptr;
            auto baseline=[&]() {
                const auto cpu_start=process_cpu_ms();
                const auto start=offload::Clock::now(); raw=session->raw();
                const auto copied=offload::Clock::now(); cpu=preprocess(raw);
                const auto prepped=offload::Clock::now();
                raw_ms=offload::elapsed(start,copied); prep_ms=offload::elapsed(copied,prepped);
                a=npu.conventional(cpu.data(),cpu.size());
                cpu_path_cpu_ms=process_cpu_ms()-cpu_start;
            };
            auto candidate=[&]() {
                const auto cpu_start=process_cpu_ms();
                const auto start=offload::Clock::now(); fpga=session->rgb_to_input_slot();
                fpga_ms=offload::elapsed(start,offload::Clock::now());
#ifdef OFFLOAD_SHARED_INPUT
                b=consumer->complete();
#else
                b=npu.conventional(fpga,offload::BoundRknn::InputBytes);
#endif
                fpga_path_cpu_ms=process_cpu_ms()-cpu_start;
            };
            if (i&1) {candidate();baseline();} else {baseline();candidate();}
            offload::require(std::equal(cpu.begin(),cpu.end(),fpga),"FPGA input bytes differ");
            offload::require(a.outputs==b.outputs,"Native inference output bytes differ");
            const auto release_start=offload::Clock::now(); session->release();
            const auto release_ms=offload::elapsed(release_start,offload::Clock::now());
            const auto npu_a=std::accumulate(a.stages.begin(),a.stages.end(),0.0);
            const auto npu_b=std::accumulate(b.stages.begin(),b.stages.end(),0.0);
            if (i>=warmup) {
                std::cout<<"{\"kind\":\"pair\",\"generation\":"<<lease.generation<<",\"sequence\":"<<lease.sequence
                    <<",\"claim_ms\":"<<claim_ms<<",\"raw_dma_copy_ms\":"<<raw_ms<<",\"cpu_preprocess_ms\":"<<prep_ms
                    <<",\"fpga_to_rx_slot_ms\":"<<fpga_ms<<",\"cpu_rknn_ms\":"<<npu_a<<",\"fpga_rknn_ms\":"<<npu_b
                    <<",\"cpu_inputs_set_ms\":"<<a.stages[0]<<",\"fpga_submit_or_lease_ms\":"<<b.stages[0]
                    <<",\"release_ms\":"<<release_ms<<",\"cpu_total_ms\":"<<claim_ms+raw_ms+prep_ms+npu_a+release_ms
                    <<",\"cpu_path_process_cpu_ms\":"<<cpu_path_cpu_ms<<",\"fpga_path_process_cpu_ms\":"<<fpga_path_cpu_ms
                    <<",\"fpga_total_ms\":"<<claim_ms+fpga_ms+npu_b+release_ms<<",\"input_parity\":true,\"output_parity\":true}\n";
            }
        }
#ifdef OFFLOAD_SHARED_INPUT
        consumer.reset();
#endif
        session->finish(); session.reset();
        std::cout<<"{\"kind\":\"pass\",\"pairs\":"<<pairs<<"}\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr<<"FAIL: "<<e.what()<<'\n';
        if (session) session->quarantine();
#ifdef OFFLOAD_SHARED_INPUT
        // On an uncertain failure the process remains stopped for coordinated
        // recovery. Do not run RKNN teardown after merely resuming this catch.
        consumer.release();
#endif
        return 2;
    }
}
