#include "session_fault_transport.hpp"
#include <cassert>
#include <iostream>
using namespace coop_host;
struct Backend : Transport {
    bool fault=false,uncertain=false;
    unsigned status_reads=0,reads=0,writes=0,copies=0;
    IoStatus read16(std::uint32_t a,Beat& b) override {
        if(a==0x40010410) {++status_reads;b=encode_word(fault?4:0);
            return uncertain?IoStatus::Uncertain:IoStatus::KnownOK;}
        ++reads;b={};return IoStatus::KnownOK;
    }
    IoStatus write16(std::uint32_t,const Beat&) override {++writes;return IoStatus::KnownOK;}
    DmaResult copy_ddr_blocking(std::uint32_t,std::uint64_t,std::vector<std::uint8_t>& b) override {
        ++copies;return {IoStatus::KnownOK,b.size()};
    }
};
int main(){
    for(unsigned op=0;op<3;++op){
        Backend b;reset_fault_guard::SessionFaultTransport t(b,0x40010410);
        Beat beat{};std::vector<std::uint8_t> bytes(16);
        assert(t.write16(physical_address(0x30),beat)==IoStatus::KnownOK);
        assert(t.copy_ddr_blocking(0x8000000,0,bytes).status==IoStatus::KnownOK);
        assert(t.write16(physical_address(0x4c),beat)==IoStatus::KnownOK);
        assert(b.status_reads==3 && b.writes==2 && b.copies==1);
        b.fault=true;
        if(op==0)assert(t.write16(physical_address(0x30),beat)==IoStatus::Uncertain);
        if(op==1)assert(t.copy_ddr_blocking(0x8000000,0,bytes).status==IoStatus::Uncertain);
        if(op==2)assert(t.write16(physical_address(0x4c),beat)==IoStatus::Uncertain);
        assert(t.stopped() && b.writes==2 && b.copies==1);
        b.fault=false;assert(t.read16(0,beat)==IoStatus::Uncertain);
        assert(b.status_reads==4 && b.reads==0);
    }
    Backend b;b.uncertain=true;reset_fault_guard::SessionFaultTransport t(b,0x40010410);
    Beat beat{};assert(t.write16(0,beat)==IoStatus::Uncertain && b.writes==0 && t.stopped());
    std::cout<<"TRANSPORT_PASS CLAIM_COPY_ACK_PRECHECK_STICKY\n";
}
