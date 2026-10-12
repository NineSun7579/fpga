#define _GNU_SOURCE
#include "egl_abi.h"
#include <dlfcn.h>
#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <stdatomic.h>

typedef EGLBoolean (EGLAPIENTRY *swap_fn)(EGLDisplay, EGLSurface);
typedef EGLBoolean (EGLAPIENTRY *interval_fn)(EGLDisplay, EGLint);
typedef __eglMustCastToProperFunctionPointerType
    (EGLAPIENTRY *getproc_fn)(const char *);
static swap_fn next_swap;
static interval_fn next_interval;
static getproc_fn next_getproc;
static atomic_int ready;
static int enabled;
/* Startup LD_PRELOAD: avoid dynamic TLS allocation on a thread's first call. */
static _Thread_local unsigned in_probe __attribute__((tls_model("initial-exec")));
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static struct totals {
    uint64_t calls, successes, timed, invalid, sum_ns, max_ns, bins[5];
    uint64_t start_ns;
    int have_start;
} totals;

EGLBoolean EGLAPIENTRY eglSwapBuffers(EGLDisplay, EGLSurface);
EGLBoolean EGLAPIENTRY eglSwapInterval(EGLDisplay, EGLint);
__eglMustCastToProperFunctionPointerType EGLAPIENTRY eglGetProcAddress(const char *);

/* Resolve outside the call path. No lazy pthread_once/dlsym recursion. */
__attribute__((constructor)) static void initialize(void)
{
    int saved = errno;
    void *symbol;
    const char *value;
    ++in_probe;
    symbol = dlsym(RTLD_NEXT, "eglSwapBuffers");
    _Static_assert(sizeof next_swap == sizeof symbol, "POSIX function pointer ABI");
    memcpy(&next_swap, &symbol, sizeof next_swap);
    symbol = dlsym(RTLD_NEXT, "eglSwapInterval");
    memcpy(&next_interval, &symbol, sizeof next_interval);
    symbol = dlsym(RTLD_NEXT, "eglGetProcAddress");
    memcpy(&next_getproc, &symbol, sizeof next_getproc);
    value = getenv("DETVIEW_EGL_SWAP_PROBE");
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

/* One bounded, stack-backed write. Diagnostic output may itself block. */
static void emit(const char *text, int size, size_t capacity)
{
    if (size > 0) {
        size_t n = (size_t)size < capacity ? (size_t)size : capacity - 1;
        ssize_t written = write(STDERR_FILENO, text, n);
        (void)written;
    }
}

static void record_swap(EGLBoolean result, int start_ok, uint64_t start,
                        int end_ok, uint64_t end)
{
    struct totals report;
    uint64_t wall = 0;
    int flush = 0;
    pthread_mutex_lock(&lock);
    if (!totals.have_start && (start_ok || end_ok)) {
        totals.start_ns = start_ok ? start : end;
        totals.have_start = 1;
    }
    ++totals.calls;
    totals.successes += result != 0;
    if (start_ok && end_ok && end >= start) {
        uint64_t elapsed = end - start;
        unsigned bin = elapsed < 1000000ULL ? 0 : elapsed < 5000000ULL ? 1 :
                       elapsed < 10000000ULL ? 2 : elapsed < 20000000ULL ? 3 : 4;
        ++totals.timed;
        totals.sum_ns += elapsed;
        if (elapsed > totals.max_ns) totals.max_ns = elapsed;
        ++totals.bins[bin];
    } else {
        ++totals.invalid;
    }
    if (end_ok && totals.have_start && end >= totals.start_ns &&
        end - totals.start_ns >= 5000000000ULL) {
        wall = end - totals.start_ns;
        report = totals;
        memset(&totals, 0, sizeof totals);
        totals.start_ns = end;
        totals.have_start = 1;
        flush = 1;
    }
    pthread_mutex_unlock(&lock);
    if (flush) {
        char text[768];
        double seconds = (double)wall / 1e9;
        int n = snprintf(text, sizeof text,
            "egl_swap_probe wall_s=%.6f calls=%" PRIu64 " success=%" PRIu64
            " timed=%" PRIu64 " invalid_clock=%" PRIu64
            " sum_ms=%.6f max_ms=%.6f mean_ms=%.6f calls_per_wall_s=%.6f"
            " swap_time_per_wall=%.6f buckets_lt1_lt5_lt10_lt20_ge20="
            "%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64
            " longswap_ge20ms=%" PRIu64 "\n",
            seconds, report.calls, report.successes, report.timed, report.invalid,
            (double)report.sum_ns / 1e6, (double)report.max_ns / 1e6,
            report.timed ? (double)report.sum_ns / 1e6 / (double)report.timed : 0.0,
            (double)report.calls / seconds, (double)report.sum_ns / (double)wall,
            report.bins[0], report.bins[1], report.bins[2], report.bins[3],
            report.bins[4], report.bins[4]);
        emit(text, n, sizeof text);
    }
}

EGLBoolean EGLAPIENTRY eglSwapBuffers(EGLDisplay display, EGLSurface surface)
{
    int incoming = errno, outgoing, start_ok, end_ok;
    uint64_t start = 0, end = 0;
    EGLBoolean result;
    if (!atomic_load_explicit(&ready, memory_order_acquire)) {
        /* A loader callback before construction cannot safely resolve here. */
        errno = incoming;
        return 0;
    }
    if (!next_swap) { errno = incoming; return 0; }
    if (!enabled || in_probe) return next_swap(display, surface);
    ++in_probe;
    start_ok = now_ns(&start);
    errno = incoming;
    result = next_swap(display, surface);
    outgoing = errno;
    end_ok = now_ns(&end);
    record_swap(result, start_ok, start, end_ok, end);
    --in_probe;
    errno = outgoing;
    return result;
}

EGLBoolean EGLAPIENTRY eglSwapInterval(EGLDisplay display, EGLint interval)
{
    int incoming = errno, outgoing;
    EGLBoolean result;
    if (!atomic_load_explicit(&ready, memory_order_acquire) || !next_interval) {
        errno = incoming;
        return 0;
    }
    if (!enabled || in_probe) return next_interval(display, interval);
    ++in_probe;
    errno = incoming;
    result = next_interval(display, interval);
    outgoing = errno;
    {
        char text[192];
        int n = snprintf(text, sizeof text,
            "egl_swap_probe interval_request=%d return=%u success=%d\n",
            interval, result, result != 0);
        emit(text, n, sizeof text);
    }
    --in_probe;
    errno = outgoing;
    return result;
}

__eglMustCastToProperFunctionPointerType EGLAPIENTRY eglGetProcAddress(const char *name)
{
    __eglMustCastToProperFunctionPointerType result;
    int incoming = errno, outgoing;
    if (!atomic_load_explicit(&ready, memory_order_acquire) || !next_getproc) {
        errno = incoming;
        return NULL;
    }
    if (!enabled || in_probe) return next_getproc(name);
    ++in_probe;
    errno = incoming;
    result = next_getproc(name);
    outgoing = errno;
    /* Keep unsupported functions NULL; leave all other names untouched. */
    if (result && name) {
        if (strcmp(name, "eglSwapBuffers") == 0 &&
            result == (__eglMustCastToProperFunctionPointerType)next_swap)
            result = (__eglMustCastToProperFunctionPointerType)eglSwapBuffers;
        else if (strcmp(name, "eglSwapInterval") == 0 &&
                 result == (__eglMustCastToProperFunctionPointerType)next_interval)
            result = (__eglMustCastToProperFunctionPointerType)eglSwapInterval;
    }
    --in_probe;
    errno = outgoing;
    return result;
}
