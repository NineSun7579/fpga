#include "stall_timing.h"
#include <atomic>
#include <cassert>
#include <chrono>
#include <mutex>
#include <thread>
#include <vector>

using namespace StallTiming;

static Span synthetic(Ns wall, Ns cpu) {
    Stamp begin, end;
    begin.wall = 1000000000; begin.cpu = 1000000; begin.valid = true;
    end.wall = begin.wall + wall; end.cpu = begin.cpu + cpu; end.valid = true;
    return Span::between(begin, end);
}

int main() {
    errno = EDOM;
    const Stamp sleepBegin = Stamp::now();
    assert(errno == EDOM);
    std::this_thread::sleep_for(std::chrono::milliseconds(40));
    const Span slept = Span::between(sleepBegin, Stamp::now());
    assert(slept.valid && slept.wall >= 30000000 && slept.cpu < slept.wall / 5);
    assert(slept.lowThreadCpu());
    const Stamp busyBegin = Stamp::now();
    volatile uint64_t busy = 1;
    Stamp busyEnd;
    do { for (unsigned index = 0; index < 10000; ++index) busy = busy * 1664525 + 1013904223; busyEnd = Stamp::now(); }
    while (busyEnd.cpu - busyBegin.cpu < 30000000);
    const Span worked = Span::between(busyBegin, busyEnd);
    assert(worked.valid && worked.cpu >= 30000000 && worked.wall >= worked.cpu / 2);

    IoctlBucket bucket;
    IoctlRecord good, alarm, error;
    good.syscall = synthetic(40000000, 2000000); good.wrapperBegin = good.syscall.begin; good.wrapperEnd = good.syscall.end;
    good.sequence = 1; good.rc = 0; good.applicationRc = 0; good.savedErrno = EAGAIN;
    alarm = good; alarm.sequence = 2; alarm.syscall = synthetic(10000000000ULL, 3000000);
    alarm.wrapperEnd = alarm.wrapperBegin + alarm.syscall.wall; alarm.alarm = 1; alarm.applicationRc = -1;
    error = good; error.sequence = 3; error.rc = -1; error.applicationRc = -1; error.savedErrno = EIO;
    error.syscall = synthetic(50000000, 4000000); error.wrapperEnd = error.wrapperBegin + error.syscall.wall;
    bucket.add(good, good.wrapperBegin); bucket.add(alarm, good.wrapperBegin); bucket.add(error, good.wrapperBegin);
    assert(bucket.count == 3 && bucket.failed == 2 && bucket.alarms == 1 && bucket.rcFailed == 1);
    assert(bucket.syscall[0].wallSum == 40000000 && bucket.syscall[1].wallSum == 10050000000ULL);
    assert(bucket.syscall[1].wallMax == 10000000000ULL && bucket.syscall[1].cpuSum == 7000000);
    Stats stats; stats.add(synthetic(50000000, 1000000)); stats.add(Span{});
    assert(stats.count == 2 && stats.invalid == 1 && stats.wallSum == 50000000);
    assert(uint32_t(uint32_t(2) - uint32_t(0xfffffffe)) == 4);

    IoctlBucket crossing;
    crossing.add(good, good.wrapperBegin + 1);
    assert(crossing.spansWindow == 1 && crossing.syscall[0].wallSum == good.syscall.wall);

    const long mainTid = tid();
    long otherTid = 0;
    std::thread isolated([&] { otherTid = tid(); assert(ioctls().sequence == 0); IoctlDrain drain; ioctls().record(good); });
    isolated.join(); assert(otherTid != mainTid && ioctls().sequence == 0);
    {
        IoctlDrain drain;
        ioctls().record(good); ioctls().record(alarm); ioctls().record(error);
    }
    ioctls().drain(true);
    {
        CameraWindow window(1);
        CameraAttempt first(window); first.tag(10, 11); first.finish(1);
        CameraAttempt noNew(window); noNew.tag(11, 5000); noNew.finish(0);
        CameraAttempt unstable(window); unstable.tag(11, 5000); unstable.finish(2);
        CameraAttempt failed(window); failed.tag(11, 5000); failed.finish(-1);
        CameraAttempt last(window); last.tag(11, 14); last.finish(1);
    }
    std::mutex dmaMutex;
    dmaMutex.lock();
    std::atomic<bool> waiterReady{false};
    std::thread waiter([&] {
        CameraWindow window(2);
        CameraAttempt attempt(window);
        const Stamp waitBegin = Stamp::now();
        waiterReady.store(true);
        std::unique_lock<std::mutex> lock(dmaMutex);
        const Stamp acquired = Stamp::now();
        const Span waited = Span::between(waitBegin, acquired);
        assert(waited.wall >= 20000000 && waited.cpu < waited.wall / 5);
        attempt.add(DmaWait, waitBegin, acquired);
        ioctls().record(good);
        IoctlDrain drain;
        assert(ioctls().defer && ioctls().pending == 1);
        ioctls().drain();
        assert(ioctls().pending == 1);
        lock.unlock();
        attempt.add(DmaHold, acquired, Stamp::now());
        const Stamp copyBegin = Stamp::now();
        std::this_thread::sleep_for(std::chrono::milliseconds(25));
        attempt.add(Copy, copyBegin, Stamp::now());
        attempt.finish(1);
        assert(!ioctls().defer && ioctls().pending == 0);
    });
    while (!waiterReady.load()) std::this_thread::yield();
    std::this_thread::sleep_for(std::chrono::milliseconds(40));
    dmaMutex.unlock();
    waiter.join();

    const unsigned samples = 200000;
    const Stamp benchBegin = Stamp::now();
    for (unsigned sample = 0; sample < samples; ++sample) {
        const Stamp first = Stamp::now(); const Span elapsed = Span::between(first, Stamp::now());
        stats.add(elapsed);
    }
    const Span bench = Span::between(benchBegin, Stamp::now());
    std::printf("STALL_TIMING_SELFTEST_PASS sleep_wall_ns=%llu sleep_cpu_ns=%llu busy_wall_ns=%llu busy_cpu_ns=%llu pair_samples=%u pair_wall_mean_ns=%.1f pair_cpu_mean_ns=%.1f\n",
        (unsigned long long)slept.wall, (unsigned long long)slept.cpu, (unsigned long long)worked.wall,
        (unsigned long long)worked.cpu, samples, double(bench.wall) / samples, double(bench.cpu) / samples);
}
