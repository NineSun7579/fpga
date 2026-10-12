#include "pcie_session.hpp"
#include "background_thumbnail_reader.hpp"
#include <algorithm>
#include <memory>
#include <sstream>

namespace {
using offload::require;
using background_thumbnail::Order;
constexpr uint32_t Base=0x40020000, Bytes=153600;
using Record=std::array<uint32_t,8>;
struct Observation {
    bool seen=false;
    uint32_t guard=0, guard_after=0, sequence=0;
};
struct AttemptDiagnostic {
    Observation baseline, running, frozen;
    std::array<Observation,2> baseline_banks{}, frozen_banks{};
    uint64_t polls=0, torn=0, busy=0, invalid=0, cursor_stale=0, baseline_stale=0;
    std::optional<uint32_t> control_running, control_disabled, control_claimed, status_claimed;
    std::optional<offload::Lease> raw;
    const char* reason="in_progress";
};
struct Diagnostics {
    bool enabled=false, active=false;
    unsigned camera=0, bank=0, sample=0;
    const char* stage="setup";
    std::vector<AttemptDiagnostic> attempts;
    void emit(std::ostream& out) const {
        if (!enabled || !active) return;
        unsigned no_publication=0, frozen_not_fresh=0, sequence_mismatch=0, exceptions=0, no_exact_bank=0;
        uint64_t polls=0,torn=0,busy=0,invalid=0,cursor_stale=0,baseline_stale=0;
        for (const auto& a:attempts) {
            no_publication+=std::strcmp(a.reason,"no_fresh_publication")==0;
            frozen_not_fresh+=std::strcmp(a.reason,"frozen_not_fresh")==0;
            sequence_mismatch+=std::strcmp(a.reason,"raw_sequence_mismatch")==0;
            exceptions+=std::strcmp(a.reason,"exception")==0;
            no_exact_bank+=std::strcmp(a.reason,"no_exact_eligible_bank")==0;
            polls+=a.polls; torn+=a.torn; busy+=a.busy; invalid+=a.invalid;
            cursor_stale+=a.cursor_stale; baseline_stale+=a.baseline_stale;
        }
        out<<"{\"diagnostics\":true,\"pass\":false,\"camera\":"<<camera+1
           <<",\"bank\":"<<bank<<",\"sample\":"<<sample<<",\"stage\":\""<<stage
           <<"\",\"attempts\":"<<attempts.size()<<",\"reason_counts\":{\"no_fresh_publication\":"<<no_publication
           <<",\"frozen_not_fresh\":"<<frozen_not_fresh<<",\"raw_sequence_mismatch\":"<<sequence_mismatch
           <<",\"exception\":"<<exceptions<<",\"no_exact_eligible_bank\":"<<no_exact_bank
           <<"},\"poll_counts\":{\"total\":"<<polls<<",\"torn_guard\":"<<torn
           <<",\"busy_guard\":"<<busy<<",\"invalid_guard\":"<<invalid<<",\"cursor_not_fresh\":"<<cursor_stale
           <<",\"baseline_not_advanced\":"<<baseline_stale<<"},\"observations\":[";
        auto observation=[&](const Observation& o) {
            if (!o.seen) { out<<"null"; return; }
            out<<"{\"guard\":"<<o.guard<<",\"guard_after\":"<<o.guard_after<<",\"sequence\":"<<o.sequence<<"}";
        };
        auto value=[&](const std::optional<uint32_t>& v) { if (v) out<<*v; else out<<"null"; };
        for (size_t i=0;i<attempts.size();++i) {
            const auto& a=attempts[i];
            out<<(i?",":"")<<"{\"attempt\":"<<i+1<<",\"reason\":\""<<a.reason<<"\",\"polls\":"<<a.polls<<",\"baseline\":";
            observation(a.baseline); out<<",\"last_running\":"; observation(a.running);
            out<<",\"frozen\":"; observation(a.frozen);
            out<<",\"baseline_banks\":["; observation(a.baseline_banks[0]); out<<","; observation(a.baseline_banks[1]); out<<"]";
            out<<",\"frozen_banks\":["; observation(a.frozen_banks[0]); out<<","; observation(a.frozen_banks[1]); out<<"]";
            out<<",\"control_running\":"; value(a.control_running);
            out<<",\"control_disabled\":"; value(a.control_disabled);
            out<<",\"control_claimed\":"; value(a.control_claimed);
            out<<",\"status_claimed\":"; value(a.status_claimed);
            out<<",\"raw\":";
            if (a.raw) out<<"{\"sequence\":"<<a.raw->sequence<<",\"generation\":"<<a.raw->generation
                          <<",\"source\":"<<a.raw->source<<",\"published\":"<<(a.raw->published?"true":"false")<<"}";
            else out<<"null";
            out<<"}";
        }
        out<<"]}"<<std::endl;
    }
};
uint32_t destination(unsigned camera,unsigned bank) {
    const unsigned slot=camera==4 ? 0 : (camera<4 ? camera+1 : 5);
    return 0x0a200000+slot*0x80000+bank*0x40000;
}
void identity(const Record& r,unsigned camera,unsigned bank) {
    require(r[1]==camera+1 && r[2]==bank && r[3]==destination(camera,bank) &&
            r[5]==Bytes && r[6]==(320u|(240u<<16)) && r[7]==r[3]+Bytes,
            "Background record ABI/camera/bank/destination/geometry/tag mismatch");
}
bool usable(const Record& r) { return background_thumbnail::usableGuard(r[0]); }
bool newer(uint32_t candidate,uint32_t reference) {
    const auto order=background_thumbnail::sequenceOrder(candidate,reference);
    require(order!=Order::ambiguous,"Ambiguous half-range sequence; parity not passed");
    return order==Order::newer;
}
struct Cursor { bool seen=false; uint32_t sequence=0; };
bool fresh(const Record& r,const Cursor& cursor) {
    return usable(r) && (!cursor.seen || newer(r[4],cursor.sequence));
}
std::optional<unsigned> matchingBank(const std::array<Record,2>& records,
                                    const std::array<Record,2>& baselines,
                                    const std::array<Cursor,2>& cursors,
                                    const std::array<unsigned,2>& completed,unsigned count,
                                    uint32_t sequence) {
    std::optional<unsigned> match;
    for (unsigned b=0;b<2;++b) {
        const auto& r=records[b]; const auto& baseline=baselines[b];
        if (completed[b]>=count || !fresh(r,cursors[b]) || r[4]!=sequence) continue;
        if (usable(baseline) && !(r[0]!=baseline[0] && newer(r[4],baseline[4]))) continue;
        require(!match,"Duplicate background banks claim same RAW sequence");
        match=b;
    }
    return match;
}
uint32_t checkTag(const std::vector<uint8_t>& payload,uint32_t sequence) {
    require(payload.size()==Bytes+16,"Background payload/tag size mismatch");
    uint32_t tag; std::memcpy(&tag,payload.data()+Bytes,4);
    require(tag==sequence && std::all_of(payload.begin()+Bytes+4,payload.end(),
                                       [](uint8_t v) { return v==0; }),
            "Background 128-bit tag/RAW sequence mismatch");
    return tag;
}
Record record(offload::PcieSession& session,unsigned camera,unsigned bank,Observation* observed=nullptr) {
    const auto address=Base+0x200+32*(2*camera+bank);
    Record r{};
    const auto first=session.background_read(address,16);
    const auto second=session.background_read(address+16,16);
    std::memcpy(r.data(),first.data(),16);
    std::memcpy(r.data()+4,second.data(),16);
    const auto guard=session.background_read(address,16);
    uint32_t after; std::memcpy(&after,guard.data(),4);
    if (observed) *observed={true,r[0],after,r[4]};
    if (after!=r[0]) { r[0]=0; return r; }
    identity(r,camera,bank);
    return r;
}
void compare(const std::vector<uint8_t>& raw,const std::vector<uint8_t>& thumbnail) {
    require(raw.size()==640*480*2 && thumbnail.size()==Bytes+16,"Payload length mismatch");
    for (size_t y=0;y<240;++y) for (size_t x=0;x<320;++x) {
        const auto src=(2*y*640+2*x)*2, dst=(y*320+x)*2;
        require(raw[src]==thumbnail[dst] && raw[src+1]==thumbnail[dst+1],
                ("Even-x/even-y RGB565 mismatch x="+std::to_string(x)+" y="+std::to_string(y)).c_str());
    }
}
template<class F> void mustFail(F f) {
    bool rejected=false;
    try { f(); } catch (const std::exception&) { rejected=true; }
    require(rejected,"Self-test expected rejection");
}
void selftest() {
    require(newer(0,0xffffffffu) && !newer(7,7) && !newer(6,7),"Sequence wrap/order");
    mustFail([] { newer(0x80000000u,0); });
    using offload::BackgroundClaim;
    require(offload::backgroundClaimAllowed(BackgroundClaim::disabled,0,31,2,false,false) &&
            !offload::backgroundClaimAllowed(BackgroundClaim::disabled,0,31,1,true,true),
            "Legacy RAW claim must still require disabled/drained background");
    for (auto control:{1u,3u})
        require(offload::backgroundClaimAllowed(BackgroundClaim::enabled_rgb_freeze,0,31,control,true,true),
                "RGB freeze allowed while owned background enabled");
    for (auto control:{0u,2u,4u,5u,7u,9u})
        require(!offload::backgroundClaimAllowed(BackgroundClaim::enabled_rgb_freeze,0,31,control,true,true),
                "Reject disabled/quarantined/unknown background state");
    require(!offload::backgroundClaimAllowed(BackgroundClaim::enabled_rgb_freeze,1,31,1,true,true) &&
            !offload::backgroundClaimAllowed(BackgroundClaim::enabled_rgb_freeze,0,15,1,true,true) &&
            !offload::backgroundClaimAllowed(BackgroundClaim::enabled_rgb_freeze,0,31,1,false,true) &&
            !offload::backgroundClaimAllowed(BackgroundClaim::enabled_rgb_freeze,0,31,1,true,false),
            "Enabled freeze must be RGB/exact caps/owned enabled state");
    std::array<Record,2> candidates{},baselines{};
    std::array<Cursor,2> bank_cursors{};
    std::array<unsigned,2> completed{};
    candidates[0][0]=6; candidates[0][4]=10;
    candidates[1][0]=5; candidates[1][4]=11; // pending payload/tag for leased RAW 11
    require(!matchingBank(candidates,baselines,bank_cursors,completed,10,11),
            "Pending guard cannot count as exact publication");
    candidates[1][0]=6; // successful tag retirement makes it usable
    require(matchingBank(candidates,baselines,bank_cursors,completed,10,11)==1,
            "Exact drained match must select bank1 over nearby bank0");
    candidates[1][0]=4;
    require(!matchingBank(candidates,baselines,bank_cursors,completed,10,11),"Failed retirement rejected");
    candidates[1][0]=6;
    baselines[1]=candidates[1];
    require(!matchingBank(candidates,baselines,bank_cursors,completed,10,11),"Baseline publication excluded");
    candidates[1][0]=10;
    require(!matchingBank(candidates,baselines,bank_cursors,completed,10,11),"New guard with equal sequence excluded");
    baselines[1][4]=10;
    bank_cursors[1]={true,11};
    require(!matchingBank(candidates,baselines,bank_cursors,completed,10,11),"Previously counted sequence excluded");
    bank_cursors[1]={true,10}; completed[1]=10;
    require(!matchingBank(candidates,baselines,bank_cursors,completed,10,11),"Completed bank cannot replace needed bank coverage");
    completed[1]=9;
    require(matchingBank(candidates,baselines,bank_cursors,completed,10,11)==1,"Tenth bank sample remains eligible");
    candidates[1][4]=0; baselines[1][4]=0xffffffffu; bank_cursors[1]={true,0xffffffffu};
    require(matchingBank(candidates,baselines,bank_cursors,completed,10,0)==1,"Exact wrap/zero sequence match");
    candidates[1][4]=0x7fffffffu;
    mustFail([&] { matchingBank(candidates,baselines,bank_cursors,completed,10,0x7fffffffu); });
    baselines={}; bank_cursors={}; completed={}; candidates[0][4]=11; candidates[1][4]=11;
    mustFail([&] { matchingBank(candidates,baselines,bank_cursors,completed,10,11); });
    for (unsigned c=0;c<6;++c) for (unsigned b=0;b<2;++b) {
        Record r{2,c+1,b,destination(c,b),0,Bytes,320u|(240u<<16),destination(c,b)+Bytes};
        identity(r,c,b);
        require(fresh(r,Cursor{}) && fresh(r,Cursor{true,0xffffffffu}) &&
                !fresh(r,Cursor{true,0}),"Zero-valid publication/freshness");
        for (unsigned field : {1u,2u,3u,5u,6u,7u}) {
            auto corrupt=r; corrupt[field]^=1;
            mustFail([&] { identity(corrupt,c,b); });
        }
        r[0]=3; require(!fresh(r,Cursor{}),"Busy record rejected");
        r[0]=0; require(!fresh(r,Cursor{}),"Invalid record rejected");
    }
    std::vector<uint8_t> raw(640*480*2),thumb(Bytes+16);
    for (size_t i=0;i<raw.size();++i) raw[i]=uint8_t((i*37+i/1283)%251);
    for (size_t y=0;y<240;++y) for (size_t x=0;x<320;++x)
        std::copy_n(raw.begin()+(2*y*640+2*x)*2,2,thumb.begin()+(y*320+x)*2);
    compare(raw,thumb);
    require(checkTag(thumb,0)==0,"Zero tag allowed");
    thumb[Bytes+4]=1; mustFail([&] { checkTag(thumb,0); }); thumb[Bytes+4]=0;
    mustFail([&] { checkTag(thumb,1); });
    thumb[Bytes-1]^=1; mustFail([&] { compare(raw,thumb); });
    Diagnostics d; d.enabled=true; d.active=true;
    d.attempts.resize(5);
    d.attempts[0].reason="no_fresh_publication";
    d.attempts[0].running={true,6,10,0}; // preserve torn guard and valid zero sequence
    d.attempts[0].polls=3; d.attempts[0].torn=1; d.attempts[0].busy=1; d.attempts[0].invalid=1;
    d.attempts[1].reason="frozen_not_fresh";
    d.attempts[2].reason="raw_sequence_mismatch";
    d.attempts[2].raw=offload::Lease{9,0,0x00800000,0,0,0,0,true};
    d.attempts[3].reason="raw_sequence_mismatch";
    d.attempts[3].raw=offload::Lease{10,1,0x00a00000,0,0,0,0,true};
    d.attempts[4].reason="no_exact_eligible_bank";
    d.attempts[4].frozen_banks[1]={true,6,6,11};
    std::ostringstream diagnostic_output; d.emit(diagnostic_output);
    const auto diagnostic_text=diagnostic_output.str();
    require(diagnostic_text.find("\"reason_counts\":{\"no_fresh_publication\":1,\"frozen_not_fresh\":1,\"raw_sequence_mismatch\":2,\"exception\":0,\"no_exact_eligible_bank\":1}")!=std::string::npos &&
            diagnostic_text.find("\"total\":3,\"torn_guard\":1,\"busy_guard\":1,\"invalid_guard\":1")!=std::string::npos &&
            diagnostic_text.find("\"guard\":6,\"guard_after\":10,\"sequence\":0")!=std::string::npos &&
            diagnostic_text.find("\"raw\":null")!=std::string::npos &&
            diagnostic_text.find("\"frozen_banks\":[null,{\"guard\":6,\"guard_after\":6,\"sequence\":11}]")!=std::string::npos &&
            diagnostic_text.find("\"raw\":{\"sequence\":0,\"generation\":9")!=std::string::npos,
            "Diagnostic aggregate/observations lost failure evidence");
    d.enabled=false; std::ostringstream disabled_output; d.emit(disabled_output);
    require(disabled_output.str().empty(),"Diagnostics must be opt-in");
    std::cout<<"{\"self_test\":true,\"hardware_executed\":false,\"pass\":true}"<<std::endl;
}
unsigned number(const std::string& s,unsigned low,unsigned high) {
    require(!s.empty() && s.find_first_not_of("0123456789")==std::string::npos,"Invalid integer");
    const auto n=std::stoul(s); require(n>=low && n<=high,"Integer out of range");
    return unsigned(n);
}
}

int main(int argc,char** argv) {
    unsigned count=10, attempts=128, timeout=30;
    bool snapshots=false, freeze_first=false;
    std::vector<unsigned> cameras{0,1,2,3};
    Diagnostics diagnostics;
    try {
        for (int i=1;i<argc;++i) {
            const std::string arg=argv[i];
            if (arg=="--help") {
                std::cout<<"background_thumbnail_parity [--cameras 1,2,3,4] [--count 10] "
                             "[--attempts 128] [--timeout 30] [--snapshots] [--diagnostics] [--freeze-first]\n"
                             "--self-test opens no device. Hardware mode requires caps exactly 31.\n"
                             "Each selected physical camera requires count fresh matches in EACH bank.\n"
                             "--diagnostics emits failure-only aggregate/attempt JSON to stderr (extra control reads).\n"
                             "--freeze-first claims RGB RAW while enabled, then drains and matches either needed bank exactly.\n";
                return 0;
            }
            if (arg=="--self-test") { require(argc==2,"Self-test must be used alone"); selftest(); return 0; }
            if (arg=="--snapshots") { snapshots=true; continue; }
            if (arg=="--diagnostics") { diagnostics.enabled=true; continue; }
            if (arg=="--freeze-first") { freeze_first=true; continue; }
            require(i+1<argc,"Missing option value");
            const std::string value=argv[++i];
            if (arg=="--count") count=number(value,10,100000);
            else if (arg=="--attempts") attempts=number(value,1,10000);
            else if (arg=="--timeout") timeout=number(value,1,3600);
            else if (arg=="--cameras") {
                cameras.clear();
                require(!value.empty() && value.size()%2==1,"Invalid camera list");
                for (size_t j=0;j<value.size();j+=2) {
                    require(value[j]>='1' && value[j]<='6' && (j==0 || value[j-1]==','),"Invalid camera list");
                    const auto c=unsigned(value[j]-'1');
                    require(std::find(cameras.begin(),cameras.end(),c)==cameras.end(),"Duplicate camera");
                    cameras.push_back(c);
                }
            } else throw std::runtime_error("Unknown option "+arg);
        }
    } catch (const std::exception& e) { std::cerr<<e.what()<<'\n'; return 2; }

    std::unique_ptr<offload::PcieSession> session;
    try {
        session=std::make_unique<offload::PcieSession>();
        // Caps-15 images leave here BEFORE any control/selector/lease write.
        require(session->reg(0xa0)==31 && session->reg(0xf0)==0x3f &&
                session->reg(0x80)==640*480*2,"Requires exact background caps 31/RAW geometry");
        require(session->reg(0x180)==2,"Existing active/quarantined background owner; refuse takeover");
        std::array<std::array<Cursor,2>,6> cursors{};
        auto epoch=session->reg(0x50);
        unsigned passed=0;
        for (const auto camera:cameras) {
            std::array<unsigned,2> completed{};
            while (completed[0]<count || completed[1]<count) {
                unsigned bank=completed[0]<count ? 0 : 1;
                unsigned sample=completed[bank];
                diagnostics.active=true; diagnostics.camera=camera; diagnostics.bank=bank;
                diagnostics.sample=sample; diagnostics.attempts.clear();
                bool accepted=false;
                unsigned tries=0;
                const auto deadline=offload::Clock::now()+std::chrono::seconds(timeout);
                while (!accepted && tries<attempts && offload::Clock::now()<deadline) {
                    ++tries;
                    AttemptDiagnostic* diagnostic=nullptr;
                    if (diagnostics.enabled) {
                        diagnostics.attempts.emplace_back(); diagnostic=&diagnostics.attempts.back();
                    }
                    diagnostics.stage="baseline";
                    // Baseline excludes previously completed/stale records even on first sample.
                    const auto baseline=record(*session,camera,bank,diagnostic?&diagnostic->baseline:nullptr);
                    std::array<Record,2> baselines{};
                    baselines[bank]=baseline;
                    if (freeze_first) {
                        baselines[1-bank]=record(*session,camera,1-bank,
                                                diagnostic?&diagnostic->baseline_banks[1-bank]:nullptr);
                        if (diagnostic) diagnostic->baseline_banks[bank]=diagnostic->baseline;
                    }
                    diagnostics.stage="enable";
                    session->background_enable();
                    diagnostics.stage="publication_poll";
                    bool published=false;
                    do {
                        const auto control=session->reg(0x180);
                        if (diagnostic) diagnostic->control_running=control;
                        require(!(control&4),"Background AXI quarantine");
                        const auto running=record(*session,camera,bank,diagnostic?&diagnostic->running:nullptr);
                        const bool cursor_fresh=fresh(running,cursors[camera][bank]);
                        const bool publication_fresh=cursor_fresh &&
                            (!usable(baseline) || (running[0]!=baseline[0] && newer(running[4],baseline[4])));
                        if (diagnostic) {
                            ++diagnostic->polls;
                            if (diagnostic->running.guard!=diagnostic->running.guard_after) ++diagnostic->torn;
                            else if (running[0]&1) ++diagnostic->busy;
                            else if (!usable(running)) ++diagnostic->invalid;
                            else if (!cursor_fresh) ++diagnostic->cursor_stale;
                            else if (!publication_fresh) ++diagnostic->baseline_stale;
                        }
                        if (publication_fresh) {
                            published=true; break;
                        }
                        std::this_thread::sleep_for(std::chrono::milliseconds(1));
                    } while (offload::Clock::now()<deadline);
                    offload::Lease lease{};
                    auto claim=[&](offload::BackgroundClaim policy) {
                        diagnostics.stage="raw_claim";
                        const auto claimed=session->claim_rgb(0,camera,0,policy);
                        if (diagnostic) {
                            diagnostic->raw=claimed;
                            diagnostic->control_claimed=session->reg(0x180);
                            diagnostic->status_claimed=session->reg(0x10);
                        }
                        require(claimed.published && claimed.generation==uint32_t(epoch+1),
                                "RAW publication/generation mismatch");
                        epoch=claimed.generation;
                        return claimed;
                    };
                    if (freeze_first && published)
                        lease=claim(offload::BackgroundClaim::enabled_rgb_freeze);
                    diagnostics.stage="disable_drain";
                    session->background_disable(); // drains thumbnail payload/tag writes, including under RAW hold
                    if (diagnostic) diagnostic->control_disabled=session->reg(0x180);
                    if (!published) { if (diagnostic) diagnostic->reason="no_fresh_publication"; break; }
                    diagnostics.stage="frozen_record";
                    auto frozen=record(*session,camera,bank,diagnostic?&diagnostic->frozen:nullptr);
                    if (freeze_first) {
                        std::array<Record,2> frozen_records{};
                        frozen_records[bank]=frozen;
                        frozen_records[1-bank]=record(*session,camera,1-bank,
                                                      diagnostic?&diagnostic->frozen_banks[1-bank]:nullptr);
                        if (diagnostic) diagnostic->frozen_banks[bank]=diagnostic->frozen;
                        const auto match=matchingBank(frozen_records,baselines,cursors[camera],completed,count,lease.sequence);
                        if (!match) {
                            if (diagnostic) diagnostic->reason="no_exact_eligible_bank";
                            diagnostics.stage="release_mismatched_raw";
                            session->release(); continue;
                        }
                        bank=*match; sample=completed[bank]; frozen=frozen_records[bank];
                        diagnostics.bank=bank; diagnostics.sample=sample;
                        if (diagnostic) diagnostic->frozen=diagnostic->frozen_banks[bank];
                    }
                    if (!fresh(frozen,cursors[camera][bank])) {
                        if (diagnostic) diagnostic->reason="frozen_not_fresh";
                        if (freeze_first) { diagnostics.stage="release_unfresh_raw"; session->release(); }
                        continue;
                    }
                    const auto& chosen_baseline=freeze_first ? baselines[bank] : baseline;
                    require(!usable(chosen_baseline) || (frozen[0]!=chosen_baseline[0] && newer(frozen[4],chosen_baseline[4])),
                            "Disabled record lost fresh publication identity");
                    if (!freeze_first) lease=claim(offload::BackgroundClaim::disabled);
                    if (lease.sequence!=frozen[4]) {
                        if (diagnostic) diagnostic->reason="raw_sequence_mismatch";
                        diagnostics.stage="release_mismatched_raw";
                        session->release(); continue;
                    }
                    diagnostics.stage="snapshot_and_payload_parity";
                    auto verifySnapshot=[&] {
                        if (!snapshots) return;
                        diagnostics.stage="register_snapshot";
                        const auto before=session->register_snapshot();
                        diagnostics.stage="snapshot_scalar_parity";
                        for (size_t k=0;k<before.size();++k)
                            require(before[k]==session->reg(uint32_t(k*16)),"Frozen snapshot/scalar mismatch");
                        diagnostics.stage="snapshot_repeat_parity";
                        require(session->register_snapshot()==before,"Frozen snapshot changed");
                    };
                    verifySnapshot();
                    diagnostics.stage="metadata_after_claim";
                    require(record(*session,camera,bank)==frozen,"Background metadata changed after RAW claim");
                    diagnostics.stage="raw_payload";
                    const auto raw=session->raw();
                    diagnostics.stage="thumbnail_payload_and_tag";
                    const auto thumbnail=session->background_read(frozen[3],Bytes+16);
                    const auto tag=checkTag(thumbnail,frozen[4]);
                    diagnostics.stage="metadata_after_dma";
                    require(record(*session,camera,bank)==frozen,"Background metadata changed during DMA");
                    diagnostics.stage="pixel_parity";
                    compare(raw,thumbnail);
                    diagnostics.stage="raw_repeat_parity";
                    require(session->raw()==raw,"Frozen RAW changed after thumbnail read");
                    verifySnapshot();
                    diagnostics.stage="release_accepted_raw";
                    session->release();
                    if (diagnostic) diagnostic->reason="accepted";
                    cursors[camera][bank]={true,frozen[4]}; ++completed[bank]; ++passed; accepted=true;
                    std::cout<<"{\"camera\":"<<camera+1<<",\"bank\":"<<bank<<",\"sample\":"<<sample
                             <<",\"attempts\":"<<tries<<",\"raw_generation\":"<<lease.generation
                             <<",\"raw_source\":"<<lease.source<<",\"sequence\":"<<frozen[4]
                             <<",\"guard\":"<<frozen[0]<<",\"destination\":"<<frozen[3]
                             <<",\"tag\":"<<tag<<",\"bytes_compared\":"<<Bytes
                             <<",\"freeze_first\":"<<(freeze_first?"true":"false")
                             <<",\"snapshot_parity\":"<<(snapshots?"true":"null")<<",\"pass\":true}"<<std::endl;
                }
                diagnostics.stage="bounded_alignment";
                require(accepted,("Bounded fresh RAW/background alignment failed camera="+std::to_string(camera+1)+
                        " bank="+std::to_string(bank)+" sample="+std::to_string(sample)+
                        "; parity not passed (no substitution of unrelated RAW)").c_str());
                diagnostics.active=false;
            }
        }
        session->finish(); session.reset();
        std::cout<<"{\"summary\":true,\"selected_cameras\":[";
        for (size_t i=0;i<cameras.size();++i) std::cout<<(i?",":"")<<cameras[i]+1;
        std::cout<<"],\"banks\":2,\"count_per_bank\":"<<count<<",\"frames_passed\":"<<passed
                 <<",\"pass\":true}"<<std::endl;
        return 0;
    } catch (const std::exception& e) {
        if (!diagnostics.attempts.empty() &&
            std::strcmp(diagnostics.attempts.back().reason,"in_progress")==0)
            diagnostics.attempts.back().reason="exception";
        diagnostics.emit(std::cerr);
        std::cerr<<"Background parity failed: "<<e.what()<<std::endl;
        if (session && !session->close_if_safe()) session->quarantine();
        return 2;
    }
}
