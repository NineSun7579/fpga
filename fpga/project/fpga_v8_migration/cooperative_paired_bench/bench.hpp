#pragma once
#include "../paired_input_guard/paired_input_guard.hpp"
#include "../reset_fault_guard/session_fault_transport.hpp"
#include <chrono>
#include <cmath>
#include <functional>
#include <ostream>
#include <thread>

namespace paired_bench {
using Clock = std::chrono::steady_clock;
inline void require(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
inline double ms(Clock::time_point a, Clock::time_point b) {
    return std::chrono::duration<double,std::milli>(b-a).count();
}
enum class Profile { Baseline, Cooperative };
struct Detection { float x1, y1, x2, y2, score; int cls; };
using Detections = std::vector<Detection>;
struct Inference {
    Detections owned;
    // inputs_set, blocking run, outputs_get+validation, decode+owned copy, release.
    std::array<double,5> stages{};
};
class Runner {
public:
    virtual ~Runner() = default;
    // Must return only after successful outputs_release. Throws on ANY failure.
    virtual Inference complete(Profile, const std::vector<std::uint8_t>& rgb) = 0;
    virtual bool verified_hardware() const { return false; }
    virtual void close() = 0;
};
inline bool parity(const Detections& a, const Detections& b) {
    if (a.size()!=b.size()) return false;
    auto finite=[](const Detection& d) {
        return d.cls>=0 && d.cls<3 && std::isfinite(d.score) && std::isfinite(d.x1) &&
            std::isfinite(d.y1) && std::isfinite(d.x2) && std::isfinite(d.y2);
    };
    std::vector<int> right(b.size(),-1);
    std::vector<bool> seen(b.size());
    std::function<bool(int)> augment=[&](int i) {
        for (std::size_t j=0;j<b.size();++j) {
            if (seen[j] || !finite(b[j]) || a[i].cls!=b[j].cls ||
                std::abs(a[i].score-b[j].score)>1e-6f ||
                std::max({std::abs(a[i].x1-b[j].x1),std::abs(a[i].y1-b[j].y1),
                          std::abs(a[i].x2-b[j].x2),std::abs(a[i].y2-b[j].y2)})>1e-3f) continue;
            seen[j]=true;
            if (right[j]<0 || augment(right[j])) { right[j]=i; return true; }
        }
        return false;
    };
    for (std::size_t i=0;i<a.size();++i) {
        if (!finite(a[i])) return false;
        std::fill(seen.begin(),seen.end(),false);
        if (!augment(int(i))) return false;
    }
    return true;
}
struct AcquisitionTimes {
    double claim_wait=0, raw_copy_ack=0, output_copy_ack=0, certification=0, total=0;
};
struct Pair {
    capture_host::OwnedRawFrame raw;
    coop_host::OwnedFrame output;
    AcquisitionTimes times;
};
class Receiver {
    std::mutex& coordinator_;
    reset_fault_guard::SessionFaultTransport guarded_;
    capture_host::CandidateRAW raw_;
    coop_host::Candidate output_;
    std::uint32_t generation_;
    std::uint32_t last_sequence_=0;
    bool terminal_=false, armed_=false;
    std::function<bool()> interrupted_;
    std::vector<std::uint8_t> raw_storage_=std::vector<std::uint8_t>(capture_host::kRawBytes);
    std::vector<std::uint8_t> output_storage_=std::vector<std::uint8_t>(coop_host::kFrameBytes);
    Pair evidence_; // Keeps complete/partial CPU bytes even after ACK/failure.
    template<class F> decltype(auto) output_io(F&& f) {
        return capture_host::with_exclusive_io(coordinator_,std::forward<F>(f));
    }
public:
    Receiver(coop_host::Transport& backend, std::mutex& coordinator,
             capture_host::Config raw_config, capture_host::RuntimeReservation raw_reservation,
             coop_host::Config output_config, coop_host::RuntimeReservation output_reservation,
             std::function<bool()> interrupted={})
        : coordinator_(coordinator), guarded_(backend,0x40010410U),
          raw_(guarded_,raw_config,raw_reservation,coordinator),
          output_(guarded_,output_config,output_reservation),
          generation_(output_config.expected_generation),interrupted_(std::move(interrupted)) {}
    // Never called automatically; no discovery/reset/recovery/epoch allocation.
    void arm(const capture_host::ArmRequest& request) {
        require(!terminal_ && !armed_ && request.generation==generation_,"invalid explicit ARM");
        require(!interrupted_ || !interrupted_(),"termination requested before ARM");
        try { require(raw_.arm(request)==capture_host::Result::OK,"ARM not confirmed"); armed_=true; }
        catch (...) { terminal_=true; throw; }
    }
    const Pair& evidence() const { return evidence_; }
    bool terminal() const { return terminal_; }
    bool lease_uncertain() const {
        const auto r=raw_.snapshot();
        const auto o=capture_host::with_exclusive_io(coordinator_,[&] { return output_.snapshot(); });
        return r.state!=capture_host::State::Idle || o.state!=coop_host::State::Idle ||
            r.arm_may_be_pending || r.claim_may_exist || r.release_may_be_pending || o.claim_may_exist;
    }
    const Pair& acquire(std::chrono::milliseconds budget=std::chrono::milliseconds(1000)) {
        require(!terminal_ && armed_ && budget.count()>0,"receiver not armed or terminal");
        const auto begin=Clock::now(), deadline=begin+budget;
        bool r=false,o=false;
        try {
            require(!interrupted_ || !interrupted_(),"termination requested at acquisition boundary");
            // Each pass has at most one RAW and one output claim operation.
            while (!r || !o) {
                require(!interrupted_ || !interrupted_(),"termination requested during claim wait");
                require(Clock::now()<deadline,"acquisition deadline");
                if (!r) {
                    auto result=raw_.claim_one_poll();
                    require(result==capture_host::Result::OK || result==capture_host::Result::Busy,"RAW claim failed");
                    r=result==capture_host::Result::OK;
                }
                require(Clock::now()<deadline,"acquisition deadline");
                if (!o) {
                    auto result=output_io([&] { return output_.claim_one_poll(); });
                    require(result==coop_host::Result::OK || result==coop_host::Result::Busy,"output claim failed");
                    o=result==coop_host::Result::OK;
                }
                if (!r || !o) std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            auto claims=Clock::now();
            auto raw=raw_.copy_owned(std::move(raw_storage_));
            if (raw.frame) evidence_.raw=std::move(*raw.frame);
            require(raw.result==capture_host::Result::OK && evidence_.raw.complete,"RAW incomplete");
            require(raw_.acknowledge()==capture_host::Result::OK,"RAW ACK failed; no retry");
            auto raw_done=Clock::now();
            require(raw_done<deadline,"copy/ACK deadline");
            auto output=output_io([&] { return output_.copy_owned(std::move(output_storage_)); });
            if (output.frame) evidence_.output=std::move(*output.frame);
            require(output.result==coop_host::Result::OK && evidence_.output.complete,"output incomplete");
            require(output_io([&] { return output_.acknowledge(); })==coop_host::Result::OK,"output ACK failed; no retry");
            auto output_done=Clock::now();
            require(output_done<deadline,"copy/ACK deadline");
            // Guard checks exact dimensions/completeness before its byte comparison.
            require(paired_input::certify(evidence_.raw,evidence_.output,generation_).error==paired_input::Error::None,
                    "physical source identity or prepared bytes mismatch");
            auto end=Clock::now();
            require(end<deadline,"certification deadline");
            require(evidence_.raw.descriptor.sequence>last_sequence_,"duplicate or regressed physical frame");
            last_sequence_=evidence_.raw.descriptor.sequence;
            evidence_.times={ms(begin,claims),ms(claims,raw_done),ms(raw_done,output_done),
                             ms(output_done,end),ms(begin,end)};
            return evidence_;
        } catch (...) { terminal_=true; throw; }
    }
    void recycle() {
        require(!terminal_,"terminal receiver cannot recycle");
        raw_storage_=std::move(evidence_.raw.bytes);
        output_storage_=std::move(evidence_.output.bytes);
        evidence_=Pair{};
    }
};
struct Sample {
    capture_host::Descriptor source;
    AcquisitionTimes acquisition;
    double cpu_prepare=0, processing=0, completion_from_capture=0;
    Inference inference;
};
inline Sample process(Runner& runner,Profile profile,const Pair& pair,Clock::time_point capture_start) {
    Sample result; result.source=pair.raw.descriptor; result.acquisition=pair.times;
    auto begin=Clock::now();
    std::vector<std::uint8_t> rgb;
    if (profile==Profile::Baseline) rgb=fpga_v8_raw::prepare(pair.raw.bytes.data(),pair.raw.bytes.size());
    auto prepared=Clock::now();
    result.cpu_prepare=ms(begin,prepared);
    result.inference=runner.complete(profile,profile==Profile::Baseline ? rgb : pair.output.bytes);
    auto end=Clock::now(); result.processing=ms(begin,end);
    result.completion_from_capture=ms(capture_start,end);
    return result;
}
struct Block {
    Profile profile;
    std::vector<Sample> samples;
    std::vector<std::vector<std::uint8_t>> raw_inventory;
    double wall_ms=0;
};
inline Block measure(Receiver& receiver,Runner& runner,Profile p,std::size_t count) {
    require(count>0,"empty measurement block");
    Block block{p, std::vector<Sample>(count),
        std::vector<std::vector<std::uint8_t>>(count,std::vector<std::uint8_t>(capture_host::kRawBytes)),0};
    const auto begin=Clock::now();
    for (std::size_t i=0;i<count;++i) {
        auto start=Clock::now(); const auto& pair=receiver.acquire();
        // Inventory copy + byte certification are deliberately INCLUDED for BOTH profiles.
        std::copy(pair.raw.bytes.begin(),pair.raw.bytes.end(),block.raw_inventory[i].begin());
        block.samples[i]=process(runner,p,pair,start);
        receiver.recycle();
    }
    block.wall_ms=ms(begin,Clock::now());
    return block;
}
struct Experiment {
    std::vector<std::array<Sample,2>> paired;
    std::vector<Block> blocks;
    bool input_sequence_equal=true, detections_equal=true, acceptance=false, hardware=false;
};
inline Experiment run(Receiver& receiver,Runner& runner,std::size_t pairs=240,
                      std::size_t rounds=4,std::size_t jobs=30,
                      const std::function<void(std::size_t,const Pair&)>& save_pair={}) {
    require(pairs && rounds && jobs,"empty experiment");
    Experiment result; result.paired.resize(pairs);
    for (std::size_t i=0;i<pairs;++i) {
        const auto begin=Clock::now(); const auto& pair=receiver.acquire();
        // AB then BA: independent processing intervals; absolute response includes
        // the other profile if scheduled second. No per-profile FPS here.
        const int first=int(i%2),second=1-first;
        for (int role : {first,second}) result.paired[i][role]=process(runner,
            role==0 ? Profile::Baseline : Profile::Cooperative,pair,begin);
        result.detections_equal &= parity(result.paired[i][0].inference.owned,result.paired[i][1].inference.owned);
        if (save_pair) save_pair(i,pair); // Correctness export outside all timing windows.
        receiver.recycle();
    }
    result.blocks.reserve(rounds*4);
    for (std::size_t round=0;round<rounds;++round) {
        const auto base=result.blocks.size();
        for (Profile p : {Profile::Baseline,Profile::Cooperative,Profile::Cooperative,Profile::Baseline})
            result.blocks.push_back(measure(receiver,runner,p,jobs));
        for (auto positions : {std::array<int,2>{0,1},std::array<int,2>{3,2}}) {
            const auto& a=result.blocks[base+positions[0]]; const auto& b=result.blocks[base+positions[1]];
            result.input_sequence_equal &= a.raw_inventory==b.raw_inventory;
            for (std::size_t i=0;i<jobs;++i)
                result.detections_equal &= parity(a.samples[i].inference.owned,b.samples[i].inference.owned);
        }
    }
    runner.close(); // Destruction/release errors must reject the experiment too.
    result.hardware=runner.verified_hardware();
    result.acceptance=result.hardware && result.input_sequence_equal && result.detections_equal;
    return result;
}
inline void report(std::ostream& out,const Experiment& e) {
    out << std::boolalpha << "{\"acceptance\":" << e.acceptance
        << ",\"input_sequence_byte_equal\":" << e.input_sequence_equal
        << ",\"detections_equal\":" << e.detections_equal
        << ",\"paired_count\":" << e.paired.size()
        << ",\"paired_sustained_fps\":null,\"certification_cost_in_both_profiles\":true,\"blocks\":[";
    for (std::size_t i=0;i<e.blocks.size();++i) {
        const auto& b=e.blocks[i]; if (i) out << ',';
        out << "{\"profile\":\"" << (b.profile==Profile::Baseline ? "raw_cpu_float" : "cooperative_native")
            << "\",\"completed\":" << b.samples.size() << ",\"wall_ms\":" << b.wall_ms
            << ",\"observed_completed_fps\":";
        if (e.hardware) out << b.samples.size()*1000.0/b.wall_ms; else out << "null";
        out << '}';
    }
    out << "]}\n";
}
} // namespace paired_bench
