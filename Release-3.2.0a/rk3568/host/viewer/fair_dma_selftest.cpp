#include "fair_dma.h"
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <thread>
#include <vector>

namespace tdm {
struct FairDmaSelfTestAccess {
    static bool queued(FairDmaMutex& mutex, uint64_t normal, unsigned retirements) {
        std::lock_guard<std::mutex> lock(mutex.state_);
        return mutex.issued_ - mutex.serving_ == normal && mutex.retirements_ == retirements;
    }
};
}

template<class Predicate> void await(Predicate predicate) {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (!predicate()) {
        assert(std::chrono::steady_clock::now() < deadline);
        std::this_thread::yield();
    }
}

int main() {
    tdm::FairDmaMutex mutex;
    std::vector<int> order;
    std::vector<std::thread> callers;
    mutex.lock(); // Simulate one executing transfer; everyone else must wait.
    for (int camera = 0; camera < 6; ++camera) {
        callers.emplace_back([&, camera] {
            tdm::FairDmaGuard guard(&mutex);
            order.push_back(camera);
        });
        await([&] { return tdm::FairDmaSelfTestAccess::queued(mutex, camera + 1, 0); });
    }
    std::thread end([&] { tdm::FairDmaGuard guard(&mutex, true); order.push_back(99); });
    await([&] { return tdm::FairDmaSelfTestAccess::queued(mutex, 6, 1); });
    assert(order.empty()); // END cannot pass the executing transfer.
    mutex.unlock();
    end.join();
    for (auto& caller : callers) caller.join();
    assert((order == std::vector<int>{99, 0, 1, 2, 3, 4, 5}));

    // Reproduce metadata starvation: tryLock cannot enter while even one
    // image is executing or queued. FIFO metadata keeps its place ahead of
    // subsequent images, including across a finite converter retirement.
    order.clear(); callers.clear();
    mutex.lock();
    for (int camera=0; camera<6; ++camera) {
        callers.emplace_back([&,camera] {
            tdm::FairDmaGuard guard(&mutex); order.push_back(camera);
        });
        await([&] { return tdm::FairDmaSelfTestAccess::queued(mutex,camera+1,0); });
        assert(!mutex.tryLock());
    }
    std::thread metadata([&] {
        // Same lock/RAII ownership as motionHint; no outer DMA owner.
        mutex.lock();
        struct Unlock { tdm::FairDmaMutex& m; ~Unlock() { m.unlock(); } } unlock{mutex};
        order.push_back(42);
    });
    await([&] { return tdm::FairDmaSelfTestAccess::queued(mutex,7,0); });
    for (int camera=6; camera<12; ++camera) {
        callers.emplace_back([&,camera] {
            tdm::FairDmaGuard guard(&mutex); order.push_back(camera);
        });
        await([&] { return tdm::FairDmaSelfTestAccess::queued(mutex,camera+2,0); });
    }
    std::thread retirement([&] { tdm::FairDmaGuard guard(&mutex,true); order.push_back(99); });
    await([&] { return tdm::FairDmaSelfTestAccess::queued(mutex,13,1); });
    mutex.unlock();
    retirement.join(); metadata.join();
    for (auto& caller:callers) caller.join();
    assert((order==std::vector<int>{99,0,1,2,3,4,5,42,6,7,8,9,10,11}));
    assert(mutex.tryLock()); mutex.unlock(); // metadata RAII released ownership

    // Saturated camera callers and repeated retirements: mutual exclusion,
    // progress for all six, and unlock/relock of the converter polling guard.
    std::atomic<int> inside{0};
    std::atomic<int> completed{0};
    callers.clear();
    for (int camera = 0; camera < 6; ++camera) callers.emplace_back([&] {
        for (int frame = 0; frame < 1000; ++frame) {
            tdm::FairDmaGuard guard(&mutex);
            assert(inside.fetch_add(1) == 0);
            std::this_thread::yield();
            assert(inside.fetch_sub(1) == 1);
            guard.unlock();
            guard.relock();
            assert(inside.fetch_add(1) == 0);
            assert(inside.fetch_sub(1) == 1);
            ++completed;
        }
    });
    std::thread retirements([&] {
        for (int i = 0; i < 1000; ++i) {
            tdm::FairDmaGuard guard(&mutex, true);
            assert(inside.fetch_add(1) == 0);
            assert(inside.fetch_sub(1) == 1);
            std::this_thread::yield();
        }
    });
    for (auto& caller : callers) caller.join();
    retirements.join();
    assert(completed == 6000);
    puts("FAIR_DMA_SELFTEST_PASS fifo=6 end_priority=1 concurrent_frames=6000 retirements=1000 metadata_fifo=1 trylock_starvation_reproduced=1");
}
