#pragma once
#include "display_perf.h"

namespace tdm {
// All timestamps must come from the same monotonic nanosecond clock. Explicit
// validity flags allow timestamp zero and avoid cold-start subtraction.
struct PresentationTiming {
    DisplayPerfWindow perf;
    int64_t firstUpdateNs = 0, lastPaintStartNs = 0, lastPaintEndNs = 0;
    bool updatePending = false, havePaintStart = false, swapPending = false;
    uint64_t requests = 0, coalesced = 0, paints = 0, swaps = 0, unmatchedSwaps = 0;
    void request(int64_t now) {
        ++requests;
        if (updatePending) { ++coalesced; return; }
        firstUpdateNs = now; updatePending = true;
    }
    void paintStart(int64_t now) {
        ++paints;
        if (havePaintStart && now >= lastPaintStartNs)
            perf.time[BetweenPaints].add((now - lastPaintStartNs) / 1e6);
        if (updatePending && now >= firstUpdateNs)
            perf.time[UpdateToPaint].add((now - firstUpdateNs) / 1e6);
        updatePending = false;
        lastPaintStartNs = now; havePaintStart = true;
        // A new paint cannot reuse an older unswapped paint-end timestamp.
        swapPending = false;
    }
    void paintEnd(int64_t now) { lastPaintEndNs = now; swapPending = true; }
    void swapped(int64_t now) {
        ++swaps;
        if (swapPending && now >= lastPaintEndNs)
            perf.time[SwapAfterPaint].add((now - lastPaintEndNs) / 1e6);
        else ++unmatchedSwaps;
        swapPending = false;
    }
    void resetWindow() {
        perf = {};
        requests = coalesced = paints = swaps = unmatchedSwaps = 0;
        // Preserve pending updates/paint end and cadence across report windows.
    }
};
} // namespace tdm
