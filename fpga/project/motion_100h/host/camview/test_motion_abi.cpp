#include "motion_abi.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#ifdef NDEBUG
#error "Build this test with assertions enabled (do not define NDEBUG)."
#endif

// Fake the frozen register bank and verify exact ABI transaction ordering.
struct Bank {
    std::array<uint32_t,10> words{{0xffffffffu,3u,0xab4b0031u,0xffffb0f0u,
        1u,0x80000000u,0x12345678u,0xffffffffu,0u,0x80000001u}};
    unsigned calls=0, failAt=0, captures=0, selected=0, reads=0;
    unsigned camera=3;
    bool torn=false;
    bool write(uint32_t addr,uint32_t value) {
        if (++calls==failAt) return false;
        assert(addr==motion::Selector);
        assert(((value>>8)&7u)==camera);
        assert((value&0x7ffff8f0u)==0u);
        if (value&0x80000000u) { assert(calls==1); ++captures; selected=0; }
        else { assert(captures==1); selected=value&15u; assert(selected==reads); }
        return true;
    }
    bool read(uint32_t addr,uint32_t &value) {
        if (++calls==failAt) return false;
        if (addr==motion::Generation) {
            assert(calls==2 || calls==23);
            value=17u+(torn && calls==23 ? 1u : 0u);
        } else {
            assert(addr==motion::Data && selected<10); value=words[selected]; ++reads;
        }
        return true;
    }
    bool run(motion::Record &r) {
        return motion::capture(camera,r,[&](uint32_t a,uint32_t v){return write(a,v);},
            [&](uint32_t a,uint32_t &v){return read(a,v);});
    }
};
int main() {
    static_assert(motion::Magic==0x4d4f5431u && motion::Geometry==0x01e00280u,"probe ABI");
    static_assert(motion::SupportedCameras==4,"CAM1-4 motion only");
    static_assert(6u*0x97000u < motion::Scratch && motion::Scratch+16u < 0x3ff000u,"isolated RX scratch");
    assert(motion::selector(0,0,true)==0x80000000u);
    assert(motion::selector(3,9,false)==0x309u);
    for (unsigned camera=0; camera<motion::SupportedCameras; ++camera) {
        Bank mapped; mapped.camera=camera; motion::Record record;
        assert(mapped.run(record));
        assert(mapped.calls==23 && mapped.captures==1 && mapped.reads==10);
    }
    Bank bank; motion::Record r;
    assert(bank.run(r)); assert(bank.calls==23 && bank.captures==1 && bank.reads==10);
    assert(r.seq==0xffffffffu && r.generation==17u);
    assert(r.referenceValid && r.bboxValid && !r.error);
    assert(r.blocks==49 && r.samples==19200);
    assert(r.minX==0 && r.maxX==15 && r.minY==0 && r.maxY==11);
    for(unsigned i=0;i<6;++i) assert(r.bitmap[i]==bank.words[4+i]);
    char hex[49];
    const int length=std::snprintf(hex,sizeof(hex),"%08x%08x%08x%08x%08x%08x",
        r.bitmap[5],r.bitmap[4],r.bitmap[3],r.bitmap[2],r.bitmap[1],r.bitmap[0]);
    assert(length==48);
    assert(std::strcmp(hex,"8000000100000000ffffffff123456788000000000000001")==0);
    // Raw bitfield decoding is independent of capture validity checks.
    auto pathological=bank.words;
    pathological[1]=7u; pathological[2]=0xabffffffu; pathological[3]=0xffffbaedu;
    auto raw=motion::decode(pathological);
    assert(raw.blocks==255 && raw.samples==65535 && raw.error);
    assert(raw.minX==13 && raw.maxX==14 && raw.minY==10 && raw.maxY==11);
    bank.words.fill(0); auto empty=motion::decode(bank.words);
    assert(!empty.referenceValid && !empty.bboxValid && !empty.error && empty.samples==0);
    // Reserved flag/count/bbox bits cannot leak into decoded fields.
    bank.words[1]=0xfffffff8u; bank.words[2]=0xff000000u; bank.words[3]=0xffff0000u;
    auto reserved=motion::decode(bank.words);
    assert(!reserved.referenceValid && !reserved.bboxValid && !reserved.error);
    assert(reserved.blocks==0 && reserved.samples==0 && reserved.maxY==0);
    // Every failing ioctl and torn generation leave caller's old record intact.
    for(unsigned fail=1;fail<=23;++fail) {
        Bank broken; broken.failAt=fail; motion::Record old; old.seq=123; old.bitmap[5]=42;
        assert(!broken.run(old)); assert(old.seq==123 && old.bitmap[5]==42);
    }
    Bank torn; torn.torn=true; motion::Record old; old.seq=123;
    assert(!torn.run(old) && old.seq==123);
    for (uint32_t malformed : {0x000000c1u, 0x000000ffu}) {
        Bank bad; bad.words[2]=malformed; old.seq=123;
        assert(!bad.run(old) && old.seq==123);
    }
    for (unsigned samples : {19201u,65535u}) {
        Bank bad; bad.words[2]=(samples<<8)|49u; old.seq=123;
        assert(!bad.run(old) && old.seq==123);
    }
    for (uint32_t malformed : {0x0000c000u, 0x00000012u, 0x00001200u}) {
        Bank bad; bad.words[3]=malformed; old.seq=123;
        assert(!bad.run(old) && old.seq==123);
    }
    for (unsigned camera : {4u,5u,6u}) {
        unsigned calls=0; old.seq=123; old.bitmap[5]=42;
        assert(!motion::capture(camera,old,[&](uint32_t,uint32_t){++calls;return true;},
            [&](uint32_t,uint32_t&){++calls;return true;}));
        assert(calls==0 && old.seq==123 && old.bitmap[5]==42);
    }
    std::puts("motion ABI: decode, selectors, frozen capture, generation, ranges and 23 failure paths PASS");
}
