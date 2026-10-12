#include "camera_dma.h"
#include "hdmi_view.h"
#include "inference_geometry.h"
#include "endpoint_locks.h"
#include <QMutex>
#include <future>
#include <cstdio>

int main() {
    // Instantiate exactly the QMutex specialization used by PangoDev.
    sixdma::EndpointLocks<QMutex> locks;
    bool excluded = false;
    {
        auto borrow = locks.borrow();
        auto contender = std::async(std::launch::async, [&] {
            return !locks.tryLease().owns_lock() && !locks.tryDma().owns_lock();
        });
        excluded = contender.get();
    }
    auto borrow = locks.borrow();
    if (!excluded) return 1;
    std::puts("QMUTEX_ENDPOINT_LOCKS_PASS");
    const int camera = tdm::runCameraDmaSelfTest();
    const int hdmi = tdm::runHdmiViewSelfTest();
    const int geometry = tdm::runInferenceGeometrySelfTest();
    return camera || hdmi || geometry;
}
