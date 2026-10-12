#pragma once
#include <mutex>

namespace sixdma {
// Endpoint ownership and DMA scratch ownership are distinct. Never acquire
// lease while holding DMA. RAW/read-only callers acquire DMA alone. A lease
// owner acquires DMA only for an ioctl plus all associated scratch accesses.
template<class Mutex> class EndpointLocks {
    Mutex leaseMutex_, dmaMutex_;
public:
    using Guard = std::unique_lock<Mutex>;
    Guard lease() { return Guard(leaseMutex_); }
    Guard dma() { return Guard(dmaMutex_); }
    Guard tryLease() { return Guard(leaseMutex_, std::try_to_lock); }
    Guard tryDma() { return Guard(dmaMutex_, std::try_to_lock); }
    struct Borrow {
        Guard lease, dma;
        explicit Borrow(EndpointLocks& locks) : lease(locks.lease()), dma(locks.dma()) {}
    };
    // Callbacks may issue direct ioctls on the borrowed fd. Both locks must
    // therefore remain held, and callbacks must not call locking host methods.
    Borrow borrow() { return Borrow(*this); }
};
} // namespace sixdma
