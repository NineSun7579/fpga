#include "presentation_timing.h"
#include <cassert>
#include <cmath>
#include <cstdio>

int main() {
    tdm::PresentationTiming t;
    t.swapped(0); // No preceding paint: no fabricated duration.
    t.paintStart(0); // Cold first paint: no fabricated interval/update delay.
    assert(t.unmatchedSwaps == 1);
    assert(t.perf.time[tdm::BetweenPaints].count == 0);
    assert(t.perf.time[tdm::UpdateToPaint].count == 0);
    t.paintEnd(1000000); t.swapped(4000000); t.swapped(5000000);
    assert(t.perf.time[tdm::SwapAfterPaint].count == 1);
    assert(t.perf.time[tdm::SwapAfterPaint].mean() == 3);
    t.request(6000000); t.request(9000000); t.paintStart(16000000);
    assert(t.requests == 2 && t.coalesced == 1);
    assert(t.perf.time[tdm::UpdateToPaint].mean() == 10);
    assert(t.perf.time[tdm::BetweenPaints].mean() == 16);
    t.paintEnd(18000000); t.request(19000000); t.resetWindow();
    t.swapped(20000000); t.paintStart(32000000);
    assert(t.perf.time[tdm::SwapAfterPaint].mean() == 2);
    assert(t.perf.time[tdm::BetweenPaints].mean() == 16);
    assert(t.perf.time[tdm::UpdateToPaint].mean() == 13);
    assert(t.requests == 0 && t.paints == 1 && t.swaps == 1);
    t.swapped(33000000); // Old paint-end was invalidated by new paint.
    assert(t.unmatchedSwaps == 1);
    tdm::PresentationTiming zero;
    zero.request(0); zero.request(1000000); zero.paintStart(2000000);
    assert(zero.perf.time[tdm::UpdateToPaint].mean() == 2);
    assert(zero.perf.time[tdm::BetweenPaints].count == 0);
    puts("PRESENTATION_TIMING_SELFTEST_PASS");
}
