#include "capture_host_protocol.hpp"
#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <string>
#include <thread>

namespace ch=capture_host;
using coop_host::IoStatus;
static unsigned cases=0,checks=0;
static std::uint64_t total_reads=0,total_writes=0,total_dma=0;
static void check(bool value,const char* message) {
    ++checks;if(!value) throw std::runtime_error(message);
}
static ch::RuntimeReservation reservations() { return {true,true,true,true,true,true,true,true,true,true}; }
static ch::Config config(bool tag=false) {
    ch::Config c;
    c.control_rx_slots_end=0x1000;
    c.raw_rx_offset=0x1000;
    c.raw_rx_slot_bytes=ch::kRawBytes+(tag ? 16U : 0U);
    c.output_rx_offset=c.raw_rx_offset+c.raw_rx_slot_bytes;
    c.rx_capacity=c.output_rx_offset+coop_host::kFrameBytes;
    return c;
}
static ch::ArmRequest arm_request(std::uint32_t generation=0x11223345U) {
    return {generation,true,true};
}
static coop_host::RuntimeReservation output_reservations() { return {true,true,true,true,true,true,true}; }
static coop_host::Config output_config(const ch::Config& raw,std::uint32_t generation) {
    coop_host::Config c;
    c.expected_generation=generation;c.rx_capacity=raw.rx_capacity;
    c.control_rx_slots_end=raw.control_rx_slots_end;c.frame_rx_offset=raw.output_rx_offset;
    return c;
}

// Independent hardware contract: each publication creates two consumer
// obligations. Stored bytes are overwritten only when both obligations retire.
class Fake final:public ch::Transport {
public:
    struct Source {
        std::uint32_t seq=0,gen=0;
        bool published=false,writing=false,host_claimed=false,host_done=false;
        bool coop_claimed=false,coop_done=false;
        std::vector<std::uint8_t> memory=std::vector<std::uint8_t>(ch::kRawBytes);
    };
    struct Output { ch::Descriptor source; unsigned state=0; };
    struct Action { IoStatus status; bool apply; bool reject=false; };
    std::array<Source,2> source{};
    std::array<Output,2> output{};
    std::optional<unsigned> host_offer,host_bound,coop_offer,active,out_host;
    std::vector<unsigned> out_ready;
    unsigned host_next=0,coop_next=0;
    std::uint32_t generation=0,next_seq=1,staged=0;
    bool armed=false,engine_idle=true,config_ok=true,protocol_fault=false,coop_enabled=false;
    std::array<std::uint32_t,6> ack{};
    std::array<std::uint32_t,3> out_ack{};
    std::uint32_t rejected_claim=0,bad_ack=0,rejected_config=0,published=0,failed=0,mreject=0;
    std::uint32_t accepted_config=0,accepted_claim=0,accepted_release=0;
    std::uint32_t out_reject_claim=0,out_reject_ack=0,out_accepted=0,out_completed=0,out_released=0,out_error=0;
    std::uint64_t reads=0,writes=0,dmas=0;
    unsigned legacy_notifications=0;
    std::map<std::uint32_t,Action> write_action;
    std::map<std::uint32_t,std::uint32_t> read_override;
    std::optional<std::uint32_t> uncertain_read,throw_read,throw_write;
    bool unknown=false,upper_nonzero=false,throw_dma=false,shrink_dma=false,reset_after_dma=false;
    std::size_t short_by=0;
    IoStatus dma_status=IoStatus::KnownOK;
    std::function<void(std::uint32_t)> on_read;
    std::function<void()> on_dma;
    std::ostream* fixture=nullptr;
    ch::Config cfg=config();
    ~Fake() override { total_reads+=reads;total_writes+=writes;total_dma+=dmas; }

    unsigned state(unsigned b) const {
        if(source[b].writing) return 1;
        return source[b].published && !(source[b].host_done && source[b].coop_done) ? 2U : 0U;
    }
    bool free_banks() const { return state(0)==0 && state(1)==0; }
    std::uint32_t status() const {
        return (armed ? ch::kArmed : 0U)|(config_ok ? ch::kConfigOK : 0U)|
            (protocol_fault ? ch::kProtocolFault : 0U)|(host_bound ? ch::kBound : 0U)|
            (host_offer ? ch::kOffered : 0U)|((free_banks() && engine_idle) ? ch::kConfigReady : 0U)|
            256U|((host_offer && *host_offer==1) ? ch::kOfferBank : 0U);
    }
    ch::Descriptor descriptor(unsigned bank) const {
        const auto& s=source[bank];
        return {bank,s.seq,s.gen,static_cast<std::uint32_t>(ch::kRawBytes),cfg.raw_addresses[bank],4,
                (static_cast<std::uint64_t>(s.gen)<<32)|s.seq};
    }
    void settle() {
        if(!host_offer) for(unsigned i=0;i<2;++i) {
            const unsigned b=(host_next+i)%2;
            if(state(b)==2 && !source[b].host_claimed) { host_offer=b;break; }
        }
        if(!coop_offer) for(unsigned i=0;i<2;++i) {
            const unsigned b=(coop_next+i)%2;
            if(state(b)==2 && !source[b].coop_claimed) { coop_offer=b;break; }
        }
        if(coop_enabled && coop_offer && !active) for(unsigned out=0;out<2;++out) {
            if(output[out].state==0) {
                const unsigned b=*coop_offer;source[b].coop_claimed=true;
                output[out].state=1;output[out].source=descriptor(b);active=out;
                coop_offer.reset();coop_next=1U-b;++out_accepted;
                settle();break;
            }
        }
    }
    void sof(unsigned bank) {
        check(armed && state(bank)==0 && engine_idle,"fake SOF admitted only when free and armed");
        source[bank].writing=true;source[bank].published=false;engine_idle=false;
        if(fixture) *fixture<<"S "<<std::hex<<bank<<'\n';
    }
    void publish(unsigned bank,std::uint32_t seq) {
        check(source[bank].writing,"fake publication requires admitted source");
        if(seq!=next_seq || seq==0) { protocol_fault=true;armed=false;return; }
        auto& s=source[bank];s.writing=false;s.published=true;s.seq=seq;s.gen=generation;
        s.host_claimed=false;s.host_done=false;s.coop_claimed=false;s.coop_done=false;
        for(std::size_t i=0;i<ch::kRawBytes;i+=2) {
            const auto pixel=static_cast<std::uint16_t>((i/2+seq*17U+bank*97U)&0xffffU);
            s.memory[i]=static_cast<std::uint8_t>(pixel);
            s.memory[i+1]=static_cast<std::uint8_t>(pixel>>8);
        }
        ++next_seq;++published;engine_idle=true;
        if(fixture) *fixture<<"P "<<std::hex<<seq<<'\n';
        settle();
    }
    void enable_coop() {
        coop_enabled=true;if(fixture) *fixture<<"E 1\n";settle();
    }
    void legacy_ack() { ++legacy_notifications; } // Cosmetic, no ownership transition.
    void reuse_if_free(unsigned b) {
        if(state(b)==0) std::fill(source[b].memory.begin(),source[b].memory.end(),static_cast<std::uint8_t>(0x9bU));
    }
    void complete_coop() {
        check(active.has_value(),"cooperative operation exists");
        const unsigned out=*active;const unsigned bank=output[out].source.bank;
        output[out].state=2;out_ready.push_back(out);active.reset();
        source[bank].coop_done=true;reuse_if_free(bank);++out_completed;++out_released;
        if(fixture) *fixture<<"D\n";settle();
    }
    std::uint32_t read_register(std::uint32_t local) const {
        if(local<0x100) {
            if(local==0) return coop_host::kDeviceId;
            if(local==8) return coop_host::kVersion;
            if(local==4) return (active ? 33U : 0U)|(out_ready.empty() ? 0U : 4U)|
                (out_host ? 8U : 0U)|(out_error ? 64U : 0U)|(output[0].state<<10)|(output[1].state<<12);
            if(local==0x0c) return out_ready.empty() ? ch::kNoBank : out_ready.front();
            if(local>=0x10 && local<=0x38) {
                std::array<std::uint32_t,11> words{{ch::kNoBank,0,0,0,0,0,0,0,ch::kNoBank,0,0}};
                if(out_host) {
                    const unsigned b=*out_host;const auto& r=output[b].source;
                    words={{b,r.sequence,r.generation,static_cast<std::uint32_t>(coop_host::kFrameBytes),
                        cfg.output_addresses[b],r.camera,r.bank,r.address,b,
                        static_cast<std::uint32_t>(r.token),static_cast<std::uint32_t>(r.token>>32)}};
                }
                return words[(local-0x10)/4];
            }
            if(local>=0x40 && local<=0x48) return out_ack[(local-0x40)/4];
            switch(local) {
                case 0x4c:return 0;case 0x50:return out_reject_ack;case 0x54:return out_reject_claim;
                case 0x58:case 0x5c:return 0;case 0x60:return out_completed;case 0x64:return out_released;
                case 0x68:return out_accepted;case 0x6c:return out_error;default:throw std::runtime_error("fake unknown output read");
            }
        }
        if(local>=0x118 && local<=0x134) {
            std::array<std::uint32_t,8> words{{ch::kNoBank,0,0,0,0,0,0,0}};
            if(host_bound) {
                const auto r=descriptor(*host_bound);
                words={{r.bank,r.sequence,r.generation,r.length,r.address,r.camera,
                    static_cast<std::uint32_t>(r.token),static_cast<std::uint32_t>(r.token>>32)}};
            }
            return words[(local-0x118)/4];
        }
        if(local>=0x138 && local<=0x14c) return ack[(local-0x138)/4];
        switch(local) {
            case 0x100:return ch::kDeviceId;case 0x104:return status();case 0x108:return ch::kVersion;
            case 0x10c:return staged;case 0x110:case 0x150:return 0;
            case 0x114:return host_bound ? *host_bound : ch::kNoBank;
            case 0x154:return rejected_claim;case 0x158:return bad_ack;case 0x15c:return rejected_config;
            case 0x160:return published;case 0x164:return failed;case 0x168:return mreject;
            case 0x16c:return state(0)|(state(1)<<2);case 0x170:return generation;
            case 0x174:return accepted_config;case 0x178:return accepted_release;case 0x17c:return accepted_claim;
            default:throw std::runtime_error("fake unknown capture read");
        }
    }
    unsigned write_register(std::uint32_t local,std::uint32_t word,bool force_reject=false) {
        if(local<0x100) {
            if(local==0x30) {
                const unsigned b=word&1U;
                if(!out_host && !out_ready.empty() && out_ready.front()==b) {
                    out_ready.erase(out_ready.begin());out_host=b;output[b].state=3;return 0;
                }
                ++out_reject_claim;out_error=3;return 2;
            }
            if(local>=0x40 && local<=0x48) { out_ack[(local-0x40)/4]=word;return 0; }
            if(local==0x4c && (word&1U)) {
                if(out_host) {
                    const auto& r=output[*out_host].source;
                    if(out_ack==std::array<std::uint32_t,3>{{*out_host,r.sequence,r.generation}}) {
                        output[*out_host].state=0;out_host.reset();settle();return 0;
                    }
                }
                ++out_reject_ack;out_error=4;return 2;
            }
            return 2;
        }
        if(local==0x10c) { staged=word;return 0; }
        if(local==0x110 && (word&1U)) {
            if(force_reject || host_bound || !free_banks() || !engine_idle || !config_ok ||
               protocol_fault || !staged || staged==generation) { ++rejected_config;return 2; }
            generation=staged;next_seq=1;armed=true;host_next=0;coop_next=0;++accepted_config;return 0;
        }
        if(local==0x114) {
            if(force_reject || host_bound || !host_offer || word!=*host_offer) { ++rejected_claim;return 2; }
            host_bound=host_offer;source[*host_bound].host_claimed=true;host_next=1U-*host_bound;
            host_offer.reset();++accepted_claim;settle();return 0;
        }
        if(local>=0x138 && local<=0x14c) { ack[(local-0x138)/4]=word;return 0; }
        if(local==0x150 && (word&1U)) {
            if(host_bound) {
                const auto r=descriptor(*host_bound);
                if(!force_reject && ack==std::array<std::uint32_t,6>{{r.bank,r.sequence,r.generation,
                    static_cast<std::uint32_t>(r.token),static_cast<std::uint32_t>(r.token>>32),r.camera}}) {
                    const unsigned bank=*host_bound;source[bank].host_done=true;host_bound.reset();
                    ++accepted_release;reuse_if_free(bank);return 0;
                }
            }
            ++bad_ack;return 2;
        }
        return 2;
    }
    static std::uint32_t local_address(std::uint32_t physical) {
        check(physical>=coop_host::kControlBase && physical<coop_host::kControlBase+0x1000U &&
            !(physical&15U),"singleton physical address bounds/alignment");
        return (physical-coop_host::kControlBase)/4U;
    }
    IoStatus read16(std::uint32_t physical,ch::Beat& destination) override {
        ++reads;const auto local=local_address(physical);
        if(throw_read==local) throw std::runtime_error("injected read throw");
        if(uncertain_read==local) return IoStatus::Uncertain;
        if(on_read) on_read(local);
        const auto it=read_override.find(local);
        const auto word=it==read_override.end() ? read_register(local) : it->second;
        destination=ch::encode_word(word);if(upper_nonzero) destination[15]=1;
        if(fixture) *fixture<<"R "<<std::hex<<physical<<' '<<word<<" 0\n";
        return unknown ? IoStatus::DeliveryKnownUnknownResponse : IoStatus::KnownOK;
    }
    IoStatus write16(std::uint32_t physical,const ch::Beat& beat) override {
        ++writes;const auto local=local_address(physical);
        for(std::size_t i=4;i<beat.size();++i) check(beat[i]==0,"helper high write bytes zero");
        if(throw_write==local) throw std::runtime_error("injected write throw");
        const auto word=ch::decode_word(beat);const auto it=write_action.find(local);
        if(it!=write_action.end()) {
            if(it->second.apply) write_register(local,word,it->second.reject);
            return it->second.status;
        }
        const auto response=write_register(local,word);
        if(fixture) *fixture<<"W "<<std::hex<<physical<<' '<<word<<' '<<response<<'\n';
        return unknown ? IoStatus::DeliveryKnownUnknownResponse :
            (response==0 ? IoStatus::KnownOK : IoStatus::KnownRejected);
    }
    ch::DmaResult copy_ddr_blocking(std::uint32_t address,std::uint64_t rx_offset,
                                    std::vector<std::uint8_t>& destination) override {
        ++dmas;
        if(throw_dma) throw std::runtime_error("injected DMA throw");
        if(on_dma) on_dma();
        if(destination.size()==ch::kRawBytes) {
            check(host_bound.has_value(),"DMA holds RAW lease");const unsigned bank=*host_bound;
            check(address==cfg.raw_addresses[bank] && rx_offset==cfg.raw_rx_offset,"RAW DMA reservation");
            destination=source[bank].memory;
        } else {
            check(destination.size()==coop_host::kFrameBytes && out_host.has_value(),"DMA holds output lease");
            check(address==cfg.output_addresses[*out_host] && rx_offset==cfg.output_rx_offset,"output DMA reservation");
            const auto seq=output[*out_host].source.sequence;
            for(std::size_t i=0;i<destination.size();++i) destination[i]=static_cast<std::uint8_t>((i+seq*13U)&0xffU);
        }
        if(fixture) *fixture<<"F "<<std::hex<<address<<' '<<rx_offset<<' '<<destination.size()<<'\n';
        if(shrink_dma) destination.resize(destination.size()-1);
        const auto bytes=destination.size()-short_by;
        if(reset_after_dma) { generation=0;armed=false;host_bound.reset(); }
        return {dma_status,bytes};
    }
};

static void prepare(Fake& f,ch::CandidateRAW& raw) {
    check(raw.arm(arm_request())==ch::Result::OK,"prepare ARM");f.sof(0);f.publish(0,1);
    check(raw.claim_one_poll()==ch::Result::OK,"prepare CLAIM");
}
static void own(Fake& f,ch::CandidateRAW& raw) {
    prepare(f,raw);auto result=raw.copy_owned(std::vector<std::uint8_t>(ch::kRawBytes));
    check(result.result==ch::Result::OK && result.frame && result.frame->complete,"prepare owned RAW");
}
static void validation_cases() {
    for(unsigned i=0;i<10;++i) {
        ++cases;Fake f;std::mutex mutex;auto r=reservations();
        const std::array<bool ch::RuntimeReservation::*,10> flags{{
            &ch::RuntimeReservation::exclusive_controller_client,&ch::RuntimeReservation::shared_operation_coordinator_confirmed,
            &ch::RuntimeReservation::backend_transport_mutex_authoritative,&ch::RuntimeReservation::fixed_source_and_output_layout_validated,
            &ch::RuntimeReservation::exclusive_disjoint_raw_and_output_rx_slots,&ch::RuntimeReservation::transport_control_buffers_reserved,
            &ch::RuntimeReservation::capture_endpoint_loaded_and_decode_reserved,&ch::RuntimeReservation::coordinated_reset_and_external_lease_recovery,
            &ch::RuntimeReservation::selected_unfiltered_rgb565_stream_validated,&ch::RuntimeReservation::single_camera_identity_domain}};
        r.*flags[i]=false;bool threw=false;
        try { ch::CandidateRAW raw(f,config(),r,mutex); } catch(const std::invalid_argument&) { threw=true; }
        check(threw && f.reads==0 && f.writes==0,"missing reservation rejected before I/O");
    }
    const std::vector<std::function<void(ch::Config&)>> mutations{
        [](auto& c){c.camera=5;},[](auto& c){c.width=641;},[](auto& c){c.height=479;},
        [](auto& c){c.raw_bytes=16;},[](auto& c){c.raw_addresses[0]+=16;},[](auto& c){c.output_addresses[0]+=16;},
        [](auto& c){c.ddr_limit=0;},[](auto& c){c.ddr_limit=0x09000001ULL;},
        [](auto& c){c.ddr_limit=0x08000000ULL;},[](auto& c){c.ddr_limit=0x10000001ULL;},
        [](auto& c){c.rx_capacity=0;},[](auto& c){c.rx_capacity-=16;},
        [](auto& c){c.control_rx_slots_end=0;},[](auto& c){c.control_rx_slots_end=17;},
        [](auto& c){c.raw_rx_offset+=1;},[](auto& c){c.raw_rx_offset=0;},
        [](auto& c){c.output_rx_offset=c.raw_rx_offset;},[](auto& c){c.output_rx_offset=8;},
        [](auto& c){c.raw_rx_slot_bytes+=1;},[](auto& c){c.raw_rx_slot_bytes+=16;},
        [](auto& c){c.output_rx_offset=std::numeric_limits<std::uint64_t>::max()-15;}
    };
    for(const auto& mutate:mutations) {
        ++cases;Fake f;auto c=config();mutate(c);std::mutex mutex;bool threw=false;
        try { ch::CandidateRAW raw(f,c,reservations(),mutex); } catch(const std::invalid_argument&) { threw=true; }
        // The one enlarged DDR_LIMIT mutation still fits physical memory and is
        // legal: parent may supply any validated bound up to 256 MiB.
        if(c.ddr_limit==0x09000001ULL) check(!threw && f.reads==0,"smaller valid DDR_LIMIT supported");
        else check(threw && f.reads==0 && f.writes==0,"invalid config rejected before I/O");
    }
    ++cases;Fake f;std::mutex mutex;ch::CandidateRAW raw(f,config(true),reservations(),mutex);
    check(f.reads==0 && f.writes==0,"tag reservation constructor has no I/O");
    check(raw.claim_one_poll()==ch::Result::WrongState,"no constructor arm or inferred epoch");
    check(raw.arm({0,true,true})==ch::Result::InvalidRequest,"zero explicit generation rejected");
    check(raw.arm({1,false,true})==ch::Result::InvalidRequest,"generation persistence required");
    check(raw.arm({1,true,false})==ch::Result::InvalidRequest,"global quiescence required");
    check(f.reads==0 && f.writes==0,"invalid authorization has no I/O");
}
static void clean_fixture(std::ostream& fixture) {
    ++cases;Fake f;f.fixture=&fixture;f.unknown=true;const auto c=config();f.cfg=c;
    std::mutex coordinator;ch::CandidateRAW raw(f,c,reservations(),coordinator);
    coop_host::Candidate out(f,output_config(c,0x11223345U),output_reservations());
    check(raw.arm(arm_request())==ch::Result::OK,"ordered unknown ARM confirmed by actual generation/count");
    const auto writes=f.writes;
    check(raw.arm(arm_request())==ch::Result::Rejected && f.writes==writes,"same epoch never automatically rearmed");
    check(raw.claim_one_poll()==ch::Result::Busy,"no source offer poll busy");
    f.sof(0);f.publish(0,1);
    check(raw.claim_one_poll()==ch::Result::OK,"RAW claim bank0");
    const auto original0=f.source[0].memory;
    f.sof(1);f.publish(1,2);
    auto first=raw.copy_owned(std::vector<std::uint8_t>(ch::kRawBytes));
    check(first.result==ch::Result::OK && first.frame && first.frame->bytes==original0,"owned exact bank0 bytes");
    check(raw.arm(arm_request(0x22334455U))==ch::Result::Busy,"owned RAW blocks ARM");
    f.enable_coop();f.complete_coop();
    check(f.state(0)==2,"cooperative-first source retained for RAW host");
    check(ch::with_exclusive_io(coordinator,[&]{return out.claim_one_poll();})==coop_host::Result::OK,"shared coordinator output CLAIM");
    auto output0=ch::with_exclusive_io(coordinator,[&]{return out.copy_owned(std::vector<std::uint8_t>(coop_host::kFrameBytes));});
    check(output0.result==coop_host::Result::OK && output0.frame && ch::same_source(*first.frame,*output0.frame),"paired bank0 source identity");
    check(raw.acknowledge()==ch::Result::OK && f.state(0)==0,"both consumers release bank0");
    check(first.frame->bytes==original0 && f.source[0].memory!=original0,"owned copy survives DDR bank overwrite");
    check(ch::with_exclusive_io(coordinator,[&]{return out.acknowledge();})==coop_host::Result::OK,"output ACK separate obligation");
    check(raw.claim_one_poll()==ch::Result::OK,"offer STATUS bit10 selects bank1");
    const auto original1=f.source[1].memory;
    auto second=raw.copy_owned(std::vector<std::uint8_t>(ch::kRawBytes));
    check(second.result==ch::Result::OK && second.frame && second.frame->bytes==original1,"owned exact bank1 bytes");
    check(raw.acknowledge()==ch::Result::OK && f.state(1)==2,"host-first source retained for cooperative");
    const auto before_arm=f.writes;
    check(raw.arm(arm_request(0x22334455U))==ch::Result::Busy && f.writes==before_arm,"held other consumer prevents ARM without queue");
    f.complete_coop();check(f.state(1)==0 && second.frame->bytes==original1,"second source freed independently of owned bytes");
    check(ch::with_exclusive_io(coordinator,[&]{return out.claim_one_poll();})==coop_host::Result::OK,"output bank1 CLAIM");
    auto output1=ch::with_exclusive_io(coordinator,[&]{return out.copy_owned(std::vector<std::uint8_t>(coop_host::kFrameBytes));});
    check(output1.frame && ch::same_source(*second.frame,*output1.frame),"pair bank1 source identity after RAW ACK");
    auto wrong=*output1.frame;wrong.descriptor.token^=1;
    check(!ch::same_source(*second.frame,wrong),"pair rejects token mismatch");
    wrong=*output1.frame;wrong.descriptor.sequence+=1;
    check(!ch::same_source(*second.frame,wrong),"pair rejects seq mismatch");
    for(unsigned kind=0;kind<5;++kind) {
        wrong=*output1.frame;
        if(kind==0) ++wrong.descriptor.generation;
        if(kind==1) ++wrong.descriptor.camera;
        if(kind==2) wrong.descriptor.source_bank=0;
        if(kind==3) wrong.descriptor.source_address+=16;
        if(kind==4) wrong.complete=false;
        check(!ch::same_source(*second.frame,wrong),"pair rejects generation/camera/bank/address/incomplete output");
    }
    check(ch::with_exclusive_io(coordinator,[&]{return out.acknowledge();})==coop_host::Result::OK,"output bank1 ACK");
    check(raw.arm(arm_request(0x22334455U))==ch::Result::OK,"explicit fresh rearm after all obligations");
    check(f.accepted_release==2 && f.bad_ack==0 && f.out_reject_ack==0,"clean exact releases only");
}
static void fault_cases() {
    for(unsigned kind=0;kind<9;++kind) {
        ++cases;Fake f;std::mutex mutex;ch::CandidateRAW raw(f,config(),reservations(),mutex);
        if(kind==0) f.config_ok=false;
        if(kind==1) f.protocol_fault=true;
        if(kind==2) f.read_override[0x100]=0;
        if(kind==3) f.read_override[0x108]=2;
        if(kind==4) f.uncertain_read=0x104;
        if(kind==5) f.upper_nonzero=true;
        if(kind==6) f.throw_read=0x108;
        if(kind==7) f.write_action[0x110]={IoStatus::Uncertain,true};
        if(kind==8) f.throw_write=0x110;
        check(raw.arm(arm_request())==ch::Result::Faulted,"bad ARM observation faults permanently");
        const auto count=f.writes;
        check(raw.arm(arm_request(0x22334455U))==ch::Result::Faulted && raw.acknowledge()==ch::Result::Faulted && f.writes==count,"no fault recovery or automatic bell");
    }
    for(unsigned kind=0;kind<4;++kind) {
        ++cases;Fake f;std::mutex mutex;ch::CandidateRAW raw(f,config(),reservations(),mutex);
        if(kind==0) f.engine_idle=false;
        if(kind==1) f.write_action[0x110]={IoStatus::KnownRejected,true,true};
        if(kind==2) f.write_action[0x110]={IoStatus::DeliveryKnownUnknownResponse,true,true};
        if(kind==3) f.write_action[0x10c]={IoStatus::KnownRejected,false};
        const auto result=raw.arm(arm_request());
        check(result==(kind==3 ? ch::Result::Rejected : ch::Result::Busy),"definite/ordered ARM rejection remains recoverable");
        const auto writes=f.writes;check(!raw.snapshot().armed_confirmed && !raw.snapshot().arm_may_be_pending,"rejected ARM has no invented active epoch");
        check(f.writes==writes,"no extra ARM attempt");
    }
    const std::vector<std::pair<std::uint32_t,std::uint32_t>> corrupt{{0x118,2},{0x11c,0},{0x120,0x11223344U},
        {0x124,16},{0x128,0x01800010U},{0x12c,0x104},{0x130,2},{0x134,0xdeadbeefU}};
    for(const auto& field:corrupt) {
        ++cases;Fake f;std::mutex mutex;ch::CandidateRAW raw(f,config(),reservations(),mutex);
        check(raw.arm(arm_request())==ch::Result::OK,"corrupt descriptor ARM");f.sof(0);f.publish(0,1);
        f.read_override[field.first]=field.second;
        check(raw.claim_one_poll()==ch::Result::Faulted,"bad descriptor full token/seq/gen/camera/length/address/bank rejected");
        check(raw.snapshot().claim_may_exist && raw.acknowledge()==ch::Result::Faulted && f.accepted_release==0,"bad descriptor never ACKed");
    }
    for(unsigned kind=0;kind<5;++kind) {
        ++cases;Fake f;std::mutex mutex;ch::CandidateRAW raw(f,config(),reservations(),mutex);
        check(raw.arm(arm_request())==ch::Result::OK,"claim error ARM");f.sof(0);f.publish(0,1);
        if(kind==0) f.write_action[0x114]={IoStatus::KnownRejected,true,true};
        if(kind==1) f.write_action[0x114]={IoStatus::DeliveryKnownUnknownResponse,true,true};
        if(kind==2) f.write_action[0x114]={IoStatus::Uncertain,true};
        if(kind==3) f.throw_write=0x114;
        if(kind==4) f.write_action[0x114]={IoStatus::DeliveryKnownUnknownResponse,false};
        check(raw.claim_one_poll()==(kind<2 ? ch::Result::Busy : ch::Result::Faulted),"claim rejected vs unknown no-observation vs uncertainty");
        check(f.accepted_release==0,"claim failure never releases");
    }
    for(unsigned kind=0;kind<9;++kind) {
        ++cases;Fake f;std::mutex mutex;ch::CandidateRAW raw(f,config(),reservations(),mutex);prepare(f,raw);
        if(kind==0) f.short_by=16;
        if(kind==1) f.dma_status=IoStatus::Uncertain;
        if(kind==2) f.dma_status=IoStatus::DeliveryKnownUnknownResponse;
        if(kind==3) f.shrink_dma=true;
        if(kind==4) f.throw_dma=true;
        if(kind==5) f.reset_after_dma=true;
        if(kind==6) f.on_dma=[&]{f.source[0].seq=2;};
        if(kind==7) f.on_dma=[&]{f.read_override[0x134]=0x11223344U;};
        if(kind==8) f.on_dma=[&]{f.read_override[0x12c]=0x104U;};
        auto copied=raw.copy_owned(std::vector<std::uint8_t>(ch::kRawBytes));
        check(copied.result==ch::Result::Faulted && copied.frame,"partial/uncertain/reset/changed DMA fails with owned storage");
        if(kind<5) check(!copied.frame->complete,"incomplete DMA is not a frame");
        else check(copied.frame->complete && raw.snapshot().stable_copy_completed,"completed copy preserved after lease fault");
        check(raw.acknowledge()==ch::Result::Faulted && f.accepted_release==0,"no ACK after faulty DMA");
        check(raw.snapshot().held_lease && raw.snapshot().held_lease->sequence==1 &&
            raw.snapshot().held_lease->token==0x1122334500000001ULL,"fault diagnostics preserve original bound identity");
    }
    for(unsigned kind=0;kind<10;++kind) {
        ++cases;Fake f;std::mutex mutex;ch::CandidateRAW raw(f,config(),reservations(),mutex);own(f,raw);
        if(kind==0) f.write_action[0x150]={IoStatus::KnownRejected,true,true};
        if(kind==1) f.write_action[0x150]={IoStatus::DeliveryKnownUnknownResponse,true,true};
        if(kind==2) f.write_action[0x150]={IoStatus::Uncertain,true};
        if(kind==3) f.write_action[0x144]={IoStatus::KnownRejected,false};
        if(kind==4) f.write_action[0x148]={IoStatus::DeliveryKnownUnknownResponse,false};
        if(kind==5) f.throw_write=0x150;
        if(kind==6) f.uncertain_read=0x178;
        if(kind==7) f.read_override[0x148]=0x11223344U;
        if(kind==8) f.read_override[0x14c]=0x104U;
        if(kind==9) f.write_action[0x150]={IoStatus::DeliveryKnownUnknownResponse,false};
        const bool retry=kind==0 || kind==1 || kind==3;
        check(raw.acknowledge()==(retry ? ch::Result::Rejected : ch::Result::Faulted),"ACK exact six stages rejected vs uncertain");
        if(retry) {
            check(raw.snapshot().state==ch::State::Owned && f.host_bound.has_value(),"known rejection retains lease");
            f.write_action.clear();check(raw.acknowledge()==ch::Result::OK,"explicit caller ACK retry only after rejection");
        } else {
            const auto n=f.writes;check(raw.acknowledge()==ch::Result::Faulted && f.writes==n,"uncertain ACK never rings again");
        }
    }
    ++cases;Fake f;std::mutex mutex;ch::CandidateRAW raw(f,config(),reservations(),mutex);prepare(f,raw);
    const auto io=f.reads+f.writes+f.dmas;
    check(raw.copy_owned(std::vector<std::uint8_t>(ch::kRawBytes+16)).result==ch::Result::InvalidBuffer,"no implicit tag read or scratch widening");
    check(f.reads+f.writes+f.dmas==io,"invalid destination before I/O");
    check(raw.acknowledge()==ch::Result::WrongState,"claimed un-copied source never released");
    ++cases;Fake destroyed;std::mutex dm;
    { ch::CandidateRAW lease(destroyed,config(),reservations(),dm);own(destroyed,lease); }
    check(destroyed.host_bound.has_value() && destroyed.accepted_release==0,"destructor has no ACK");
    ++cases;Fake legacy;std::mutex lm;ch::CandidateRAW retained(legacy,config(),reservations(),lm);
    own(legacy,retained);legacy.legacy_ack();
    check(legacy.host_bound.has_value() && legacy.state(0)==2 && legacy.accepted_release==0,"legacy boolean ACK cannot free a real lease");
    for(unsigned kind=0;kind<3;++kind) {
        ++cases;Fake reset;std::mutex rm;ch::CandidateRAW client(reset,config(),reservations(),rm);
        if(kind==0) {
            check(client.arm(arm_request())==ch::Result::OK,"reset-before-claim ARM");
            reset.sof(0);reset.publish(0,1);reset.generation=0;reset.armed=false;
            check(client.claim_one_poll()==ch::Result::Faulted && !reset.host_bound,"old epoch cannot claim after common reset");
        } else {
            own(reset,client);
            if(kind==1) { reset.generation=0;reset.armed=false;reset.host_bound.reset(); }
            else ++reset.source[0].gen;
            const auto write_count=reset.writes;
            check(client.acknowledge()==ch::Result::Faulted && reset.writes==write_count,"reset/stale epoch stops ACK before staging");
        }
        check(client.arm(arm_request(0x22334455U))==ch::Result::Faulted,"ARM is not fault/reset recovery");
    }
    ++cases;Fake bad_publish;std::mutex pm;ch::CandidateRAW publish_client(bad_publish,config(),reservations(),pm);
    check(publish_client.arm(arm_request())==ch::Result::OK,"publication identity ARM");
    bad_publish.sof(0);bad_publish.publish(0,2);
    check(publish_client.claim_one_poll()==ch::Result::Faulted && bad_publish.protocol_fault &&
        !bad_publish.armed && !bad_publish.host_bound,"bad publication sequence blocks host claim");
    ++cases;Fake last;std::mutex sm;ch::CandidateRAW sequence_client(last,config(),reservations(),sm);
    check(sequence_client.arm(arm_request())==ch::Result::OK,"final-sequence ARM");
    last.next_seq=0xffffffffU;last.sof(0);last.publish(0,0xffffffffU);last.armed=false;
    check(sequence_client.claim_one_poll()==ch::Result::OK,"final valid offer remains claimable after sequence-exhaustion disarm");
    ++cases;Fake thrown;std::mutex tm;ch::CandidateRAW thrown_client(thrown,config(),reservations(),tm);
    prepare(thrown,thrown_client);thrown.on_read=[&](std::uint32_t local) {
        if(local==0x130) throw std::runtime_error("held-token read throw");
    };
    const auto writes_before=thrown.writes;
    check(thrown_client.copy_owned(std::vector<std::uint8_t>(ch::kRawBytes)).result==ch::Result::Faulted &&
        thrown_client.acknowledge()==ch::Result::Faulted && thrown.writes==writes_before,"token verification exception never ACKs");
}

static void coordinator_case() {
    ++cases;Fake f;std::mutex coordinator;ch::CandidateRAW raw(f,config(),reservations(),coordinator);prepare(f,raw);
    coop_host::Candidate out(f,output_config(config(),0x11223345U),output_reservations());
    f.enable_coop();f.complete_coop();
    std::mutex gate;std::condition_variable cv;
    bool dma_entered=false,output_attempted=false,allow_dma=false,output_entered=false;
    std::atomic<bool> output_done{false};
    f.on_dma=[&]{
        std::unique_lock<std::mutex> lock(gate);dma_entered=true;cv.notify_all();
        cv.wait(lock,[&]{return allow_dma;});
    };
    ch::CopyResult copied;
    std::thread reader([&]{copied=raw.copy_owned(std::vector<std::uint8_t>(ch::kRawBytes));});
    { std::unique_lock<std::mutex> lock(gate);cv.wait(lock,[&]{return dma_entered;}); }
    std::thread output_reader([&]{
        { std::lock_guard<std::mutex> lock(gate);output_attempted=true;cv.notify_all(); }
        ch::with_exclusive_io(coordinator,[&]{
            { std::lock_guard<std::mutex> lock(gate);output_entered=true; }
            check(out.claim_one_poll()==coop_host::Result::OK,"coordinated output after RAW DMA");
        });
        output_done=true;
    });
    { std::unique_lock<std::mutex> lock(gate);cv.wait(lock,[&]{return output_attempted;});
      check(!output_entered && !output_done,"shared lock covers entire RAW DMA and blocks output operation");
      allow_dma=true;cv.notify_all(); }
    reader.join();output_reader.join();
    check(copied.result==ch::Result::OK && output_entered,"both operations finish without nested-lock deadlock");
}

int main(int argc,char** argv) {
    try {
        if(argc==2 && std::string(argv[1])=="--map") {
            for(const auto& r:ch::kRegisters) std::cout<<r.name<<' '<<std::hex<<r.local<<' '<<ch::physical_address(r.local)<<'\n';
            return 0;
        }
        std::ofstream fixture;
        if(argc==3 && std::string(argv[1])=="--fixture") {
            fixture.open(argv[2]);check(static_cast<bool>(fixture),"fixture file opened");
        } else throw std::invalid_argument("--fixture PATH or --map required");
        validation_cases();clean_fixture(fixture);fault_cases();coordinator_case();
        std::cout<<"CAPTURE_HOST_PASS cases="<<cases<<" checks="<<checks<<" writes="<<total_writes
            <<" reads="<<total_reads<<" dma="<<total_dma<<'\n';return 0;
    } catch(const std::exception& error) { std::cerr<<error.what()<<'\n';return 1; }
}
