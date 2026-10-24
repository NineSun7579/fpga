#include "capture_pacing.h"
#include "camera_dma.h"
#include "motion_policy.h"
#include "view_capture_evidence.h"
#include <cassert>
#include <cstdio>

int main() {
    // Exercise the production evidence lifecycle without hardware or wall time:
    // a mode change disables samples; acceptance replaces every baseline and
    // immediately permits a new transaction, even when tags reset with geometry.
    struct Clock {
        bool valid=false;
        int64_t now=0;
        void start() { valid=true;now=0; }
        void invalidate() { valid=false; }
        bool isValid() const { return valid; }
        int64_t elapsed() const { return now; }
    };
    tdm::ViewCaptureEvidence<Clock,6> evidence;
    uint32_t evidenceTags[6][2]={};
    uint64_t evidenceReads[6]={},evidencePubs[6]={},evidenceErrors[6]={};
    for(unsigned mode=0;mode<3;++mode) {
        evidence.clock.invalidate();
        assert(!evidence.clock.isValid()); // no samples during transition/failure
        for(int c=0;c<6;++c) {
            evidenceTags[c][0]=1000/(mode+1)+c;
            evidenceTags[c][1]=evidenceTags[c][0]+1;
            evidenceReads[c]=200+mode*100+c;
            evidencePubs[c]=50+mode*10+c;
            evidenceErrors[c]=c;
        }
        evidence.rearm(evidenceTags,evidenceReads,evidencePubs,evidenceErrors);
        assert(evidence.transaction==mode+1 && evidence.clock.isValid());
        assert(evidence.clock.elapsed()-evidence.lastSample>=500);
        for(int c=0;c<6;++c) {
            assert(evidence.tags[c][0]==evidenceTags[c][0] && evidence.tags[c][1]==evidenceTags[c][1]);
            assert(evidenceReads[c]-evidence.reads[c]==0);
            assert(evidencePubs[c]-evidence.publications[c]==0);
            assert(evidenceErrors[c]-evidence.errors[c]==0);
            assert((evidenceReads[c]+2)-evidence.reads[c]==2);
            assert((evidencePubs[c]+1)-evidence.publications[c]==1);
            assert((evidenceErrors[c]+1)-evidence.errors[c]==1);
        }
        evidence.lastSample=0;
        evidence.clock.now=499;
        assert(evidence.clock.elapsed()-evidence.lastSample<500);
        evidence.clock.now=500;
        assert(evidence.clock.elapsed()-evidence.lastSample>=500);
    }
    puts("VIEW_CAPTURE_EVIDENCE_LIFECYCLE_PASS");
    // Model advancing commits during a saturated producer: starts use newest
    // commit, failures/unstable attempts cost a period, and tag-only polls do not.
    tdm::CapturePacing pacing(30);
    constexpr int64_t period = 33333334;
    int64_t now = 1000000000;
    uint32_t last = 100;
    for (int result : {1, -1, 2, 1}) {
        assert(pacing.waitNs(now) == 0);
        const uint32_t ping = last + 3, pong = last + 4;
        assert(tdm::newestCameraBank(ping, pong, true, last) == 1);
        pacing.delivered(now); // frameStartedNs is set before the ioctl.
        assert(pacing.waitNs(now + 1000000) == period - 1000000);
        assert(pacing.waitNs(now + period - 1) == 1);
        if (result == 1) last = pong;
        now += period;
    }
    assert(tdm::newestCameraBank(last, last, true, last) == -1);
    assert(pacing.waitNs(now) == 0); // no full frame start: don't charge a tag poll.
    pacing.reset(); assert(pacing.waitNs(now) == 0);
    tdm::CapturePacing unlimited(0); unlimited.delivered(now);
    assert(unlimited.waitNs(now) == 0);

    // The scheduling policy itself is the unchanged receipt-verified header.
    motion::Observer observed;
    motion::Record quiet; quiet.referenceValid = true; quiet.seq = 10;
    observed.observe(quiet, 0, 7); quiet.seq++; observed.observe(quiet, 100, 7);
    const auto on = motion::decide(true, false, false, 2, 7, observed.evidence, 200, 100, false);
    const auto off = motion::decide(false, false, false, 2, 7, observed.evidence, 200, 100, false);
    assert(!on.request && on.reason == motion::Reason::StaticDeferred);
    assert(off.request && off.reason == motion::Reason::Legacy);
    assert(motion::decide(true, false, false, 2, 8, observed.evidence, 200, 100, false).request);
    assert(motion::decide(true, false, false, 2, 7, {}, 200, 100, false).request);
    tdm::FairDmaMutex mutex;
    assert(mutex.tryLock()); assert(!mutex.tryLock()); mutex.unlock();
    assert(mutex.tryLock()); mutex.unlock();
    if (tdm::runCameraDmaSelfTest()) return 1;
    puts("MOTION_PACING_RX_GEOMETRY_PASS");
}
