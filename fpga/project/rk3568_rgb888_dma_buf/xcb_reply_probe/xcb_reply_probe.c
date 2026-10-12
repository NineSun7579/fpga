#define _GNU_SOURCE
#include "xcb_abi.h"
#include <dlfcn.h>
#include <errno.h>
#include <inttypes.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

typedef xcb_generic_error_t *(*check_fn)(xcb_connection_t *, xcb_void_cookie_t);
static check_fn next_check;
static atomic_int ready;
static int enabled;
/* Startup preload only: TLS storage is allocated by the loader, not on calls. */
static _Thread_local unsigned in_probe __attribute__((tls_model("initial-exec")));
static _Thread_local struct totals {
    uint64_t calls, timed, invalid, sum_ns, max_ns, bins[5], start_ns;
    long tid;
    int have_start;
} totals __attribute__((tls_model("initial-exec")));

static _Noreturn void reject_loader(void)
{
    static const char message[] =
        "xcb_reply_probe: startup resolution unavailable; require linked libxcb and completed constructor\n";
    /* Never fabricate NULL (which the caller interprets as successful check). */
    ssize_t written = write(STDERR_FILENO, message, sizeof message - 1);
    (void)written;
    _exit(127);
}

__attribute__((constructor)) static void initialize(void)
{
    int saved = errno;
    void *symbol;
    const char *value;
    ++in_probe;
    symbol = dlsym(RTLD_NEXT, "xcb_request_check");
    _Static_assert(sizeof next_check == sizeof symbol, "POSIX function pointer ABI");
    memcpy(&next_check, &symbol, sizeof next_check);
    if (!next_check) reject_loader();
    value = getenv("DETVIEW_XCB_REPLY_PROBE");
    enabled = value && strcmp(value, "1") == 0;
    atomic_store_explicit(&ready, 1, memory_order_release);
    --in_probe;
    errno = saved;
}

#ifdef PROBE_TEST_CLOCK
extern int probe_test_clock(clockid_t, struct timespec *);
#define READ_CLOCK probe_test_clock
#else
#define READ_CLOCK clock_gettime
#endif

static int now_ns(uint64_t *value)
{
    struct timespec ts;
    if (READ_CLOCK(CLOCK_MONOTONIC, &ts) != 0 || ts.tv_sec < 0 ||
        ts.tv_nsec < 0 || ts.tv_nsec >= 1000000000L ||
        (uint64_t)ts.tv_sec > (UINT64_MAX - (uint64_t)ts.tv_nsec) / 1000000000ULL)
        return 0;
    *value = (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
    return 1;
}

static void record(int start_ok, uint64_t start, int end_ok, uint64_t end)
{
    if (!totals.tid) totals.tid = syscall(SYS_gettid);
    if (!totals.have_start && (start_ok || end_ok)) {
        totals.start_ns = start_ok ? start : end;
        totals.have_start = 1;
    }
    ++totals.calls;
    if (start_ok && end_ok && end >= start) {
        uint64_t elapsed = end - start;
        unsigned bin = elapsed < 1000000ULL ? 0 : elapsed < 5000000ULL ? 1 :
                       elapsed < 10000000ULL ? 2 : elapsed < 20000000ULL ? 3 : 4;
        ++totals.timed;
        totals.sum_ns += elapsed;
        if (elapsed > totals.max_ns) totals.max_ns = elapsed;
        ++totals.bins[bin];
    } else ++totals.invalid;
    if (end_ok && totals.have_start && end >= totals.start_ns &&
        end - totals.start_ns >= 5000000000ULL) {
        char text[512];
        int n = snprintf(text, sizeof text,
            "xcb_reply_probe tid=%ld wall_ns=%" PRIu64 " calls=%" PRIu64
            " timed=%" PRIu64 " invalid_clock=%" PRIu64 " sum_ns=%" PRIu64
            " max_ns=%" PRIu64 " buckets_lt1_lt5_lt10_lt20_ge20_ms="
            "%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 "\n",
            totals.tid, end - totals.start_ns, totals.calls, totals.timed,
            totals.invalid, totals.sum_ns, totals.max_ns, totals.bins[0],
            totals.bins[1], totals.bins[2], totals.bins[3], totals.bins[4]);
        long tid = totals.tid;
        memset(&totals, 0, sizeof totals);
        totals.tid = tid;
        totals.start_ns = end;
        totals.have_start = 1;
        /* Bounded stack buffer, one write, no retry on short write/EINTR. */
        if (n > 0) {
            size_t size = (size_t)n < sizeof text ? (size_t)n : sizeof text - 1;
            ssize_t written = write(STDERR_FILENO, text, size);
            (void)written;
        }
    }
}

xcb_generic_error_t *xcb_request_check(xcb_connection_t *connection,
                                      xcb_void_cookie_t cookie)
{
    int incoming = errno, outgoing, start_ok, end_ok;
    uint64_t start = 0, end = 0;
    xcb_generic_error_t *result;
    if (!atomic_load_explicit(&ready, memory_order_acquire) || !next_check)
        reject_loader();
    if (!enabled || in_probe) return next_check(connection, cookie);
    ++in_probe;
    start_ok = now_ns(&start);
    errno = incoming;
    result = next_check(connection, cookie);
    outgoing = errno;
    end_ok = now_ns(&end);
    record(start_ok, start, end_ok, end);
    --in_probe;
    errno = outgoing;
    return result;
}
