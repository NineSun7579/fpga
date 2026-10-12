#ifndef STALL_TIMING_H
#define STALL_TIMING_H

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

namespace StallTiming {
using Ns = uint64_t;
static const Ns slowNs = 20000000;
static const Ns windowNs = 5000000000ULL;
class LogLock {
public:
    LogLock() { ::flockfile(stderr); }
    ~LogLock() { release(); }
    void release() { if (held_) { ::funlockfile(stderr); held_ = false; } }
private:
    bool held_ = true;
};
inline long tid() { static thread_local const long value = ::syscall(SYS_gettid); return value; }
inline Ns monotonic() {
    timespec value{};
    return ::clock_gettime(CLOCK_MONOTONIC, &value) == 0
        ? Ns(value.tv_sec) * 1000000000ULL + Ns(value.tv_nsec) : 0;
}
struct Stamp {
    Ns wall = 0, cpu = 0;
    bool valid = false;
    static Stamp now() {
        const int saved = errno;
        timespec wall{}, cpu{};
        const int wr = ::clock_gettime(CLOCK_MONOTONIC, &wall);
        const int cr = ::clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cpu);
        Stamp value;
        value.wall = Ns(wall.tv_sec) * 1000000000ULL + Ns(wall.tv_nsec);
        value.cpu = Ns(cpu.tv_sec) * 1000000000ULL + Ns(cpu.tv_nsec);
        value.valid = wr == 0 && cr == 0;
        errno = saved;
        return value;
    }
};
struct Span {
    Ns begin = 0, end = 0, wall = 0, cpu = 0;
    bool valid = false;
    static Span between(const Stamp& first, const Stamp& last) {
        Span value;
        value.begin = first.wall; value.end = last.wall;
        value.valid = first.valid && last.valid && last.wall >= first.wall && last.cpu >= first.cpu;
        if (value.valid) { value.wall = last.wall - first.wall; value.cpu = last.cpu - first.cpu; }
        return value;
    }
    Ns offCpu() const { return wall > cpu ? wall - cpu : 0; }
    bool lowThreadCpu() const { return valid && wall >= slowNs && cpu < wall / 5; }
};
struct Stats {
    uint64_t count = 0, invalid = 0;
    Ns wallSum = 0, wallMax = 0, cpuSum = 0, cpuMax = 0;
    void add(const Span& span) {
        ++count;
        if (!span.valid) { ++invalid; return; }
        wallSum += span.wall; wallMax = std::max(wallMax, span.wall);
        cpuSum += span.cpu; cpuMax = std::max(cpuMax, span.cpu);
    }
    void writeFields(FILE* file, const char* name) const {
        std::fprintf(file, " %s_n=%llu %s_invalid=%llu %s_wall_sum_ns=%llu %s_wall_max_ns=%llu %s_cpu_sum_ns=%llu %s_cpu_max_ns=%llu",
            name, (unsigned long long)count, name, (unsigned long long)invalid,
            name, (unsigned long long)wallSum, name, (unsigned long long)wallMax,
            name, (unsigned long long)cpuSum, name, (unsigned long long)cpuMax);
    }
};
enum Phase { Read, DmaWait, DmaHold, Copy, Alloc, Convert, Sink, PublishWait, PublishHold, PhaseCount };
inline const char* phaseName(unsigned phase) {
    static const char* names[] = {"read", "dma_wait", "dma_hold", "copy", "alloc", "convert", "sink", "publish_wait", "publish_hold"};
    return names[phase];
}
enum Outcome { Success, Error, NoNew, Unstable, OutcomeCount };
inline Outcome outcome(int result) { return result == 1 ? Success : result == 0 ? NoNew : result == 2 ? Unstable : Error; }
inline const char* outcomeName(unsigned value) {
    static const char* names[] = {"success", "error", "no_new", "unstable"}; return names[value];
}
struct IoctlRecord {
    Span syscall, legacyLog;
    Ns wrapperBegin = 0, wrapperEnd = 0;
    uint64_t sequence = 0, attempt = 0;
    uintptr_t device = 0;
    unsigned long command = 0;
    uint32_t address = 0, offset = 0, bytes = 0;
    int camera = 0, role = 0, rc = 0, savedErrno = 0, alarm = 0, applicationRc = 0;
};
struct IoctlBucket {
    uint64_t count = 0, failed = 0, rcFailed = 0, alarms = 0, spansWindow = 0;
    Stats syscall[2], legacyLog;
    Ns wrapperSum[2] = {}, wrapperMax[2] = {};
    Ns firstBegin = 0, lastEnd = 0;
    uint64_t firstSequence = 0, lastSequence = 0;
    void add(const IoctlRecord& record, Ns windowBegin) {
        const unsigned bad = record.applicationRc < 0 ? 1 : 0;
        if (count++ == 0) { firstBegin = record.wrapperBegin; firstSequence = record.sequence; }
        lastEnd = record.wrapperEnd; lastSequence = record.sequence;
        failed += bad; rcFailed += record.rc < 0; alarms += record.alarm != 0;
        spansWindow += record.wrapperBegin < windowBegin;
        syscall[bad].add(record.syscall);
        if (record.legacyLog.valid) legacyLog.add(record.legacyLog);
        const Ns elapsed = record.wrapperEnd >= record.wrapperBegin ? record.wrapperEnd - record.wrapperBegin : 0;
        wrapperSum[bad] += elapsed; wrapperMax[bad] = std::max(wrapperMax[bad], elapsed);
    }
};
struct ThreadIoctls {
    // ddrRead's largest legal request makes at most 1024 scratch submissions.
    std::array<IoctlRecord, 1024> slow{};
    size_t pending = 0;
    uint64_t sequence = 0, activeAttempt = 0, overflow = 0;
    bool defer = false;
    Ns windowBegin = monotonic();
    std::array<std::array<IoctlBucket, 3>, 7> buckets{};
    Stats logger;
    void record(IoctlRecord value) {
        value.sequence = ++sequence; value.attempt = activeAttempt;
        buckets[std::max(0, std::min(6, value.camera))][std::max(0, std::min(2, value.role))].add(value, windowBegin);
        if (value.syscall.wall >= slowNs || value.wrapperEnd - value.wrapperBegin >= slowNs) {
            if (pending < slow.size()) slow[pending++] = value; else ++overflow;
        }
    }
    void drain(bool force = false) {
        if (defer) return;
        const Ns end = monotonic();
        const bool window = force || end - windowBegin >= windowNs;
        if (!pending && !window) return;
        const Stamp logBegin = Stamp::now();
        LogLock logLock;
        static const char* roles[] = {"other", "tag", "frame"};
        for (size_t index = 0; index < pending; ++index) {
            const IoctlRecord& value = slow[index];
            std::fprintf(stderr, "[stall_ioctl] pid=%ld tid=%ld device=0x%llx seq=%llu attempt=%llu camera=%d role=%s cmd=%lx addr=0x%08x rx_offset=0x%08x bytes=%u syscall_begin_ns=%llu syscall_end_ns=%llu syscall_wall_ns=%llu syscall_cpu_ns=%llu off_cpu_ns=%llu low_thread_cpu=%d clock_valid=%d wrapper_begin_ns=%llu wrapper_end_ns=%llu rc=%d errno_valid=%d errno=%d raw_errno=%d alarm=%d application_rc=%d legacy_log_wall_ns=%llu legacy_log_cpu_ns=%llu sched_wait_ns=unmeasured\n",
                (long)::getpid(), tid(), (unsigned long long)value.device,
                (unsigned long long)value.sequence, (unsigned long long)value.attempt,
                value.camera, roles[value.role], value.command, value.address, value.offset, value.bytes,
                (unsigned long long)value.syscall.begin, (unsigned long long)value.syscall.end,
                (unsigned long long)value.syscall.wall, (unsigned long long)value.syscall.cpu,
                (unsigned long long)value.syscall.offCpu(), value.syscall.lowThreadCpu(), value.syscall.valid,
                (unsigned long long)value.wrapperBegin, (unsigned long long)value.wrapperEnd,
                value.rc, value.rc < 0, value.rc < 0 ? value.savedErrno : 0, value.savedErrno,
                value.alarm, value.applicationRc,
                (unsigned long long)value.legacyLog.wall, (unsigned long long)value.legacyLog.cpu);
        }
        pending = 0;
        if (window) {
            for (unsigned camera = 0; camera < buckets.size(); ++camera) {
                for (unsigned role = 0; role < buckets[camera].size(); ++role) {
                    const IoctlBucket& value = buckets[camera][role];
                    if (!value.count) continue;
                    std::fprintf(stderr, "[stall_ioctl_window] pid=%ld tid=%ld camera=%u role=%s window_begin_ns=%llu window_end_ns=%llu first_attempt_begin_ns=%llu last_attempt_end_ns=%llu first_seq=%llu last_seq=%llu attempts=%llu success=%llu failure=%llu rc_failure=%llu alarm_failure=%llu spans_window=%llu slow_overflow=%llu completion_assigned=1 success_wrapper_sum_ns=%llu success_wrapper_max_ns=%llu failure_wrapper_sum_ns=%llu failure_wrapper_max_ns=%llu",
                        (long)::getpid(), tid(), camera, roles[role], (unsigned long long)windowBegin,
                        (unsigned long long)end, (unsigned long long)value.firstBegin, (unsigned long long)value.lastEnd,
                        (unsigned long long)value.firstSequence, (unsigned long long)value.lastSequence,
                        (unsigned long long)value.count, (unsigned long long)(value.count - value.failed),
                        (unsigned long long)value.failed, (unsigned long long)value.rcFailed, (unsigned long long)value.alarms,
                        (unsigned long long)value.spansWindow, (unsigned long long)overflow,
                        (unsigned long long)value.wrapperSum[0], (unsigned long long)value.wrapperMax[0],
                        (unsigned long long)value.wrapperSum[1], (unsigned long long)value.wrapperMax[1]);
                    value.syscall[0].writeFields(stderr, "success_ioctl"); value.syscall[1].writeFields(stderr, "failure_ioctl");
                    value.legacyLog.writeFields(stderr, "legacy_log"); logger.writeFields(stderr, "logger_previous");
                    std::fprintf(stderr, "\n");
                }
            }
            buckets = {}; windowBegin = end; overflow = 0; logger = {};
        }
        logLock.release();
        logger.add(Span::between(logBegin, Stamp::now()));
    }
};
inline ThreadIoctls& ioctls() { static thread_local ThreadIoctls value; return value; }
struct IoctlDrain {
    IoctlDrain() { (void)tid(); (void)ioctls(); }
    ~IoctlDrain() { ioctls().drain(); }
};
struct CameraBucket {
    uint64_t count = 0, spansWindow = 0;
    Stats total;
    std::array<Stats, PhaseCount> phases{};
};
class CameraAttempt;
class CameraWindow {
public:
    explicit CameraWindow(int camera) : camera_(camera), begin_(monotonic()) { (void)tid(); (void)ioctls(); }
    ~CameraWindow() { poll(true); }
    void poll(bool force = false) {
        ioctls().drain(force);
        const Ns end = monotonic();
        if (!force && end - begin_ < windowNs) return;
        const Stamp logBegin = Stamp::now();
        LogLock logLock;
        std::fprintf(stderr, "[stall_camera_window] pid=%ld tid=%ld camera=%d window_begin_ns=%llu window_end_ns=%llu first_attempt_begin_ns=%llu last_attempt_end_ns=%llu first_seq=%llu last_seq=%llu attempts=%llu success=%llu error=%llu no_new=%llu unstable=%llu tag_advance_sum=%llu tag_comparisons=%llu tag_regressions=%llu completion_assigned=1",
            (long)::getpid(), tid(), camera_, (unsigned long long)begin_, (unsigned long long)end,
            (unsigned long long)firstBegin_, (unsigned long long)lastEnd_,
            (unsigned long long)firstSequence_, (unsigned long long)sequence_,
            (unsigned long long)attempts_, (unsigned long long)buckets_[Success].count,
            (unsigned long long)buckets_[Error].count, (unsigned long long)buckets_[NoNew].count,
            (unsigned long long)buckets_[Unstable].count, (unsigned long long)tagAdvance_,
            (unsigned long long)tagComparisons_, (unsigned long long)tagRegressions_);
        logger_.writeFields(stderr, "logger_previous"); std::fprintf(stderr, "\n");
        for (unsigned result = 0; result < OutcomeCount; ++result) {
            const CameraBucket& value = buckets_[result];
            if (!value.count) continue;
            std::fprintf(stderr, "[stall_camera_stages] pid=%ld tid=%ld camera=%d window_begin_ns=%llu window_end_ns=%llu outcome=%s attempts=%llu spans_window=%llu nested_scopes=1",
                (long)::getpid(), tid(), camera_, (unsigned long long)begin_, (unsigned long long)end,
                outcomeName(result), (unsigned long long)value.count, (unsigned long long)value.spansWindow);
            value.total.writeFields(stderr, "attempt");
            for (unsigned phase = 0; phase < PhaseCount; ++phase) value.phases[phase].writeFields(stderr, phaseName(phase));
            std::fprintf(stderr, "\n");
        }
        buckets_ = {}; attempts_ = tagAdvance_ = tagComparisons_ = tagRegressions_ = 0;
        firstBegin_ = lastEnd_ = firstSequence_ = 0; begin_ = end; logger_ = {};
        logLock.release();
        logger_.add(Span::between(logBegin, Stamp::now()));
    }
private:
    friend class CameraAttempt;
    int camera_;
    Ns begin_, firstBegin_ = 0, lastEnd_ = 0;
    uint64_t sequence_ = 0, firstSequence_ = 0, attempts_ = 0;
    uint64_t tagAdvance_ = 0, tagComparisons_ = 0, tagRegressions_ = 0;
    std::array<CameraBucket, OutcomeCount> buckets_{};
    Stats logger_;
};
class CameraAttempt {
public:
    explicit CameraAttempt(CameraWindow& window) : window_(window), begin_(Stamp::now()), sequence_(++window.sequence_) {
        ioctls().defer = true; ioctls().activeAttempt = sequence_;
    }
    void add(Phase phase, const Stamp& begin, const Stamp& end) { phases_[phase].add(Span::between(begin, end)); }
    void tag(uint32_t previous, uint32_t current) { tagDelta_ = uint32_t(current - previous); tagCompared_ = true; tagRegressed_ = current < previous; }
    void finish(int result) {
        const Stamp end = Stamp::now();
        const Span total = Span::between(begin_, end);
        const Outcome state = outcome(result);
        CameraBucket& value = window_.buckets_[state];
        ++value.count; value.spansWindow += begin_.wall < window_.begin_; value.total.add(total);
        for (unsigned phase = 0; phase < PhaseCount; ++phase) {
            Stats& dest = value.phases[phase]; const Stats& source = phases_[phase];
            dest.count += source.count; dest.invalid += source.invalid;
            dest.wallSum += source.wallSum; dest.wallMax = std::max(dest.wallMax, source.wallMax);
            dest.cpuSum += source.cpuSum; dest.cpuMax = std::max(dest.cpuMax, source.cpuMax);
        }
        if (window_.attempts_++ == 0) { window_.firstBegin_ = begin_.wall; window_.firstSequence_ = sequence_; }
        window_.lastEnd_ = end.wall;
        if (state == Success && tagCompared_) {
            window_.tagAdvance_ += tagDelta_; ++window_.tagComparisons_; window_.tagRegressions_ += tagRegressed_;
        }
        ioctls().defer = false; ioctls().activeAttempt = 0;
        if (total.wall >= slowNs) {
            const Stamp logBegin = Stamp::now();
            LogLock logLock;
            std::fprintf(stderr, "[stall_camera] pid=%ld tid=%ld camera=%d seq=%llu outcome=%s attempt_begin_ns=%llu attempt_end_ns=%llu attempt_wall_ns=%llu attempt_cpu_ns=%llu off_cpu_ns=%llu low_thread_cpu=%d clock_valid=%d nested_scopes=1",
                (long)::getpid(), tid(), window_.camera_, (unsigned long long)sequence_, outcomeName(state),
                (unsigned long long)total.begin, (unsigned long long)total.end,
                (unsigned long long)total.wall, (unsigned long long)total.cpu,
                (unsigned long long)total.offCpu(), total.lowThreadCpu(), total.valid);
            for (unsigned phase = 0; phase < PhaseCount; ++phase) phases_[phase].writeFields(stderr, phaseName(phase));
            std::fprintf(stderr, "\n");
            logLock.release();
            window_.logger_.add(Span::between(logBegin, Stamp::now()));
        }
        window_.poll();
    }
private:
    CameraWindow& window_;
    Stamp begin_;
    uint64_t sequence_;
    std::array<Stats, PhaseCount> phases_{};
    uint32_t tagDelta_ = 0;
    bool tagCompared_ = false, tagRegressed_ = false;
};
} // namespace StallTiming
#endif
