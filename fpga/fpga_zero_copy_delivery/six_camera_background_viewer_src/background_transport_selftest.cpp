#include "background_transport.h"
#include <cstdio>
#include <algorithm>
#include <mutex>
#include <future>
#include "endpoint_locks.h"

namespace background_thumbnail {
int runAdapterSelfTest() {
    int failures=0;
    auto expect=[&](bool ok) { if (!ok) ++failures; };
    struct Op { unsigned cmd=0,offset_addr=0,ddr3_addr=0,total_length=0; };
    std::vector<std::uint8_t> rx(sixdma::Allocation,0xa5);
    std::array<std::array<std::array<std::uint32_t,8>,2>,6> records{};
    for(unsigned c=0;c<6;++c) for(unsigned b=0;b<2;++b)
        records[c][b]={2,c+1,b,Destinations[c][b],b+10,153600,320u|(240u<<16),Destinations[c][b]+TagDelta};
    unsigned calls=0,payloads=0,correction=0; bool race=false,badTag=false,payloadCorrection=false;
    Adapter io([&](unsigned address,unsigned offset,std::size_t count,void* out) {
        ++calls;
        Op op{0,offset,address,unsigned(count)};
        if (count==16) {
            expect(offset==sixdma::Metadata && address>=Base+0x200 && address<=Base+0x370 && !(address&15));
            unsigned record=(address-Base-0x200)/32;
            unsigned half=(address&16)?4:0;
            std::memcpy(rx.data()+offset,records[record/2][record%2].data()+half,16);
        } else {
            expect(count==kTransferBytes && offset==0); ++payloads;
            unsigned c=6,b=2;
            for(unsigned i=0;i<6;++i) for(unsigned j=0;j<2;++j)
                if(address==Destinations[i][j]) {c=i;b=j;}
            if(!Adapter::valid(c,b)) return false;
            std::fill(rx.begin(),rx.begin()+kFrameBytes,std::uint8_t(17+c));
            unsigned tag=records[c][b][4]+unsigned(badTag);
            std::memcpy(rx.data()+kFrameBytes,&tag,4);
            if(race) records[c][b][0]+=4;
        }
        if (!payloadCorrection || count==kTransferBytes) {
            if(correction==1) op.offset_addr+=16;
            if(correction==2) op.ddr3_addr+=16;
            if(correction==3) op.total_length+=16;
            if(correction==4) op.cmd=1;
        }
        return checkedCopy(op,address,offset,count,rx.data(),out,count);
    });
    Cursor cursor; Frame frame;
    for(unsigned c=0;c<6;++c) {
        cursor={};
        expect(Reader::read(io,c,31,cursor,frame).outcome==Outcome::accepted);
        expect(frame.bank==1 && frame.sequence==11 && frame.bytes.front()==17+c && !cursor.committed);
        expect(Reader::commit(c,frame,cursor));
        expect(Reader::read(io,c,31,cursor,frame).reason==Reason::no_fresh_bank);
        expect(!Reader::commit(c,frame,cursor));
    }
    auto saved=frame.bytes;
    std::fill(rx.begin(),rx.begin()+kTransferBytes,0);
    expect(frame.bytes==saved); // Owned copy survives scratch reuse.
    expect(std::all_of(rx.begin()+sixdma::SharedInput,rx.end(),[](auto v){return v==0xa5;}));
    unsigned before=calls;
    expect(Reader::read(io,0,15,{},frame).outcome==Outcome::unsupported && calls==before);
    expect(Reader::read(io,6,31,{},frame).outcome==Outcome::invalid_request && calls==before);
    for(correction=1;correction<=4;++correction)
        expect(Reader::read(io,0,31,{},frame).outcome==Outcome::transport_fault);
    payloadCorrection=true;
    for(correction=1;correction<=4;++correction)
        expect(Reader::read(io,0,31,{},frame).outcome==Outcome::transport_fault);
    payloadCorrection=false;
    correction=0;
    // Every non-scalar word is consumed from the original full 128-bit half.
    for(unsigned field : {1u,2u,3u,5u,6u,7u}) {
        records[0][0][field]^=1;
        before=payloads;
        expect(Reader::read(io,0,31,{},frame).outcome==Outcome::transport_fault && payloads==before);
        records[0][0][field]^=1;
    }
    race=true; expect(Reader::read(io,0,31,{},frame).reason==Reason::metadata_changed); race=false;
    badTag=true; expect(Reader::read(io,0,31,{},frame).reason==Reason::tag_mismatch); badTag=false;
    records[0][0][4]=0xffffffffu; records[0][1][4]=0;
    cursor={true,0,0xffffffffu};
    expect(Reader::read(io,0,31,cursor,frame).outcome==Outcome::accepted && frame.sequence==0);
    expect(cursor.sequence==0xffffffffu); // Eligibility rejection must leave cursor alone.
    expect(Reader::commit(0,frame,cursor) && cursor.sequence==0);
    records[0][1][4]=0x80000000u;
    expect(Reader::read(io,0,31,cursor,frame).reason==Reason::ambiguous_sequence);
    std::array<std::uint8_t,48> canary; canary.fill(0x5a);
    Op op{0,sixdma::Metadata,Base+0x200,16};
    expect(checkedCopy(op,op.ddr3_addr,op.offset_addr,16,rx.data(),canary.data()+16,16));
    expect(canary.front()==0x5a && canary.back()==0x5a);
    expect(!checkedCopy(op,op.ddr3_addr,sixdma::SharedInput,16,rx.data(),canary.data(),16));
    // DMA-only metadata remains available while RGB owns lease. Borrow retains both.
    sixdma::EndpointLocks<std::mutex> locks;
    { auto lease=locks.lease();
      expect(std::async(std::launch::async,[&]{return locks.tryDma().owns_lock();}).get()); }
    { auto borrow=locks.borrow();
      expect(std::async(std::launch::async,[&]{return !locks.tryLease().owns_lock() && !locks.tryDma().owns_lock();}).get()); }
    std::printf("BACKGROUND_ADAPTER_SELFTEST_%s failures=%d calls=%u payloads=%u\n",failures?"FAIL":"PASS",failures,calls,payloads);
    return failures?1:0;
}
}
#ifdef BACKGROUND_SELFTEST_STANDALONE
int main() { return background_thumbnail::runAdapterSelfTest(); }
#endif
