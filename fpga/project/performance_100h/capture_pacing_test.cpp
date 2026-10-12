#include "capture_pacing.h"
#include <cassert>

int main() {
    tdm::CapturePacing unrestricted;
    unrestricted.delivered(100);
    assert(unrestricted.waitNs(100) == 0);
    tdm::CapturePacing paced(30);
    assert(paced.waitNs(0) == 0);
    paced.delivered(0);
    assert(paced.waitNs(10000000) == 23333334);
    assert(paced.waitNs(33333334) == 0);
    // A delayed worker starts from its real next transfer, without catch-up bursts.
    paced.delivered(90000000);
    assert(paced.waitNs(95000000) == 28333334);
    paced.reset();
    assert(paced.waitNs(95000000) == 0);
    // At 30/s, a stream with 26/s source availability can deliver each source frame.
    for (int index = 0; index < 260; ++index) {
        const int64_t now = int64_t(index) * 38461539;
        assert(paced.waitNs(now) == 0);
        paced.delivered(now);
    }
}
