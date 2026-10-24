#include "source_acceptance.h"
#include <cassert>
#include <cstdio>
#include <utility>
#include <vector>

using source_acceptance::Evidence;
using source_acceptance::Result;
constexpr uint32_t pixels=921600;

struct FakeTransport {
    int64_t now=0;
    Evidence source;
    FakeTransport() { source.baselineValid=true;source.baseline=source.seq=5323; }
    // A transport attempt takes queue + MMIO time. Torn reads cannot reach
    // the evaluator, exactly as production's before/after snapshot guard.
    Result read(uint32_t seq,int64_t queue,int64_t mmio,uint32_t input=pixels,
                uint32_t drop=0,bool torn=false) {
        now+=queue+mmio;
        source.stable=false;
        if(torn) return Result::Ok;
        const auto previous=source.seq;
        source.before=source.after=source.seq=seq;
        source.input=input;source.drop=drop;source.stable=true;source.lastStableMs=now;
        return source_acceptance::observe(source,previous,now,pixels);
    }
    Result at(int64_t time,uint32_t seq) { return read(seq,0,time-now); }
};

int main() {
    FakeTransport old;
    for(auto sample:std::vector<std::pair<int64_t,uint32_t>>{{1,5323},{33,5324},{51,5324},{57,5325},{89,5326},{103,5326}})
        assert(old.at(sample.first,sample.second)==Result::Ok);
    assert(old.source.settledMs<0);
    // Old fresh-only handoff enters the full audit at 103 ms. Tag reads
    // complete at 378; cadence and delayed MMIO return the source at 673.
    old.now+=275;assert(old.now==378);
    old.now+=100;
    assert(old.read(5343,180,15)==Result::Deadline);
    assert(old.now==673 && old.source.advances==0);

    FakeTransport fixed;
    assert(fixed.at(89,5326)==Result::Ok);
    assert(fixed.at(103,5326)==Result::Ok);
    assert(!source_acceptance::readyForRestart(true,fixed.source));
    assert(fixed.read(5327,7,5)==Result::Ok);
    assert(fixed.source.settledMs==115 && fixed.source.advances==1);
    assert(!source_acceptance::readyForRestart(true,fixed.source));
    assert(fixed.at(120,5327)==Result::Ok); // repeated snapshot adds nothing
    assert(fixed.source.advances==1);
    assert(fixed.at(145,5328)==Result::Ok);
    assert(!source_acceptance::readyForRestart(false,fixed.source));
    assert(source_acceptance::readyForRestart(true,fixed.source));
    assert(fixed.read(5345,180,390)==Result::Ok); // subsequent audit delay
    assert(fixed.source.settledMs==115); // no reset/extension of source clock

    FakeTransport delayed;
    assert(delayed.at(103,5323)==Result::Ok);
    assert(delayed.read(5343,555,15)==Result::Deadline);
    assert(delayed.now==673 && delayed.source.settledMs<0);
    FakeTransport baselineDelay;
    baselineDelay.now=510; // baseline acquisition consumes real source time
    assert(baselineDelay.read(5324,0,1)==Result::Deadline);

    FakeTransport repeated;
    assert(repeated.at(100,5323)==Result::Ok);
    assert(repeated.at(500,5323)==Result::Deadline);
    FakeTransport torn;
    assert(torn.read(5324,100,0,pixels,0,true)==Result::Ok);
    assert(torn.read(5325,100,0,pixels,0,true)==Result::Ok);
    assert(torn.read(5326,100,0,pixels,0,true)==Result::Ok);
    assert(!torn.source.stable && torn.source.seq==5323 && torn.source.advances==0);
    assert(!source_acceptance::readyForRestart(true,torn.source));
    assert(torn.at(501,5327)==Result::Deadline);
    FakeTransport reset;
    assert(reset.at(120,1)==Result::Reset);
    for(bool drop:{false,true}) {
        FakeTransport bad;
        assert(bad.read(5324,120,0,drop?pixels:pixels-1,drop?1:0)==Result::Ok);
        assert(bad.source.settledMs<0);
        assert(bad.read(5325,381,0,drop?pixels:pixels-1,drop?1:0)==Result::Deadline);
        FakeTransport settled;
        assert(settled.at(120,5324)==Result::Ok);
        assert(settled.read(5325,30,0,drop?pixels:pixels-1,drop?1:0)==Result::BadFrame);
        assert(settled.source.advances==1);
    }
    FakeTransport wrap;
    wrap.source.seq=0xffffffffu;
    assert(wrap.at(100,0)==Result::Ok);
    assert(wrap.at(130,1)==Result::Ok);
    assert(source_acceptance::readyForRestart(true,wrap.source));
    std::puts("SOURCE_ACCEPTANCE_SELFTEST_PASS old_miss=673 new_settle=115 new_restart=145 delayed_deadline_preserved=1 repeated_torn_reset_pixels_drop_postsettle_wrap=1");
}
