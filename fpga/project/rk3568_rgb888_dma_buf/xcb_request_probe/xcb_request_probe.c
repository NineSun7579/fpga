#define _GNU_SOURCE
#include "xcb_abi.h"
#include <dlfcn.h>
#include <errno.h>
#include <inttypes.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#define CAP 64
#define NAME_CAP 64
#define TLS __attribute__((tls_model("initial-exec")))
typedef xcb_generic_error_t *(*check_fn)(xcb_connection_t *, xcb_void_cookie_t);
typedef unsigned int (*send_fn)(xcb_connection_t *, int, struct iovec *, const xcb_protocol_request_t *);
typedef uint64_t (*send64_fn)(xcb_connection_t *, int, struct iovec *, const xcb_protocol_request_t *);
typedef unsigned int (*fds_fn)(xcb_connection_t *, int, struct iovec *, const xcb_protocol_request_t *, unsigned int, int *);
typedef uint64_t (*fds64_fn)(xcb_connection_t *, int, struct iovec *, const xcb_protocol_request_t *, unsigned int, int *);
static check_fn next_check;
static send_fn next_send;
static send64_fn next_send64;
static fds_fn next_fds;
static fds64_fn next_fds64;
static atomic_int ready;
static int enabled;
static _Thread_local unsigned in_probe TLS;
struct metadata { char extension[NAME_CAP]; int flags; unsigned opcode, isvoid, known; };
struct entry { xcb_connection_t *connection; uint32_t sequence; unsigned valid; struct metadata meta; };
static _Thread_local struct entry cache[CAP] TLS;
static _Thread_local unsigned cursor TLS;
struct aggregate { struct metadata meta; uint64_t calls, timed, invalid, sum, max, slow; };
static _Thread_local struct aggregate classes[CAP + 1] TLS;
static _Thread_local unsigned class_count TLS;
static _Thread_local uint64_t window_start TLS;
static _Thread_local unsigned have_start TLS;

static _Noreturn void reject_loader(void)
{
    static const char text[] = "xcb_request_probe: original symbol unavailable; cannot forward safely\n";
    ssize_t n = write(2, text, sizeof text - 1);
    (void)n;
    _exit(127);
}
#define RESOLVE(target, name) do { void *p = dlsym(RTLD_NEXT, name); \
    _Static_assert(sizeof target == sizeof p, "POSIX function pointer ABI"); \
    memcpy(&target, &p, sizeof target); } while (0)
__attribute__((constructor)) static void initialize(void)
{
    int saved = errno;
    ++in_probe;
    RESOLVE(next_check, "xcb_request_check");
    RESOLVE(next_send, "xcb_send_request");
    RESOLVE(next_send64, "xcb_send_request64");
    RESOLVE(next_fds, "xcb_send_request_with_fds");
    RESOLVE(next_fds64, "xcb_send_request_with_fds64");
    if (!next_check || !next_send) reject_loader();
    const char *v = getenv("DETVIEW_XCB_REQUEST_PROBE");
    enabled = v && strcmp(v, "1") == 0;
    atomic_store_explicit(&ready, 1, memory_order_release);
    --in_probe;
    errno = saved;
}

static struct metadata describe(int flags, const xcb_protocol_request_t *request)
{
    struct metadata m = {0};
    if (!request) return m;
    const char *name = request->ext ? request->ext->name : "core";
    if (!name) return m;
    size_t n = strnlen(name, NAME_CAP);
    if (n == NAME_CAP) return m; /* Never label a truncated name as exact. */
    memcpy(m.extension, name, n + 1);
    m.flags = flags;
    m.opcode = request->opcode;
    m.isvoid = request->isvoid;
    m.known = 1;
    return m;
}
static void remember(xcb_connection_t *c, uint64_t seq, struct metadata m)
{
    /* Sequence zero denotes failed send, never a successful cookie. */
    if (!seq) return;
    struct entry *e = &cache[cursor++ % CAP];
    *e = (struct entry){c, (uint32_t)seq, 1, m};
}
static struct metadata take(xcb_connection_t *c, uint32_t seq)
{
    struct metadata m = {0};
    unsigned matches = 0;
    for (unsigned i = 0; i < CAP; ++i) {
        if (cache[i].valid && cache[i].connection == c && cache[i].sequence == seq) {
            m = cache[i].meta;
            cache[i].valid = 0;
            ++matches;
        }
    }
    if (matches != 1) memset(&m, 0, sizeof m);
    return m;
}
/* Nested libxcb send forwarding must still call its original exactly once,
 * but only the outer caller's cookie/metadata enters the cache. */
#define SEND_BODY(original, invocation) \
    int incoming = errno, outgoing; \
    if (!atomic_load_explicit(&ready, memory_order_acquire) || !original) reject_loader(); \
    if (!enabled || in_probe) return invocation; \
    ++in_probe; \
    struct metadata m = describe(flags, request); \
    errno = incoming; \
    uint64_t seq = invocation; \
    outgoing = errno; \
    remember(connection, seq, m); \
    --in_probe; \
    errno = outgoing; \
    return seq
unsigned int xcb_send_request(xcb_connection_t *connection, int flags, struct iovec *vector, const xcb_protocol_request_t *request)
{ SEND_BODY(next_send, next_send(connection, flags, vector, request)); }
uint64_t xcb_send_request64(xcb_connection_t *connection, int flags, struct iovec *vector, const xcb_protocol_request_t *request)
{ SEND_BODY(next_send64, next_send64(connection, flags, vector, request)); }
unsigned int xcb_send_request_with_fds(xcb_connection_t *connection, int flags, struct iovec *vector, const xcb_protocol_request_t *request, unsigned int num_fds, int *fds)
{ SEND_BODY(next_fds, next_fds(connection, flags, vector, request, num_fds, fds)); }
uint64_t xcb_send_request_with_fds64(xcb_connection_t *connection, int flags, struct iovec *vector, const xcb_protocol_request_t *request, unsigned int num_fds, int *fds)
{ SEND_BODY(next_fds64, next_fds64(connection, flags, vector, request, num_fds, fds)); }

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
        (uint64_t)ts.tv_sec > (UINT64_MAX - (uint64_t)ts.tv_nsec) / 1000000000ULL) return 0;
    *value = (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
    return 1;
}
static int same(struct metadata a, struct metadata b)
{
    return a.known == b.known && (!a.known ||
        (a.opcode == b.opcode && a.isvoid == b.isvoid && a.flags == b.flags &&
         strcmp(a.extension, b.extension) == 0));
}
static void report(uint64_t end)
{
    long tid = syscall(SYS_gettid);
    for (unsigned i = 0; i <= CAP; ++i) {
        struct aggregate *a = &classes[i];
        if (!a->calls) continue;
        char text[512], opcode[16], flags[24], isvoid[16], checked[16];
        if (a->meta.known) {
            snprintf(opcode, sizeof opcode, "%u", a->meta.opcode);
            snprintf(flags, sizeof flags, "%d", a->meta.flags);
            snprintf(isvoid, sizeof isvoid, "%u", a->meta.isvoid);
            snprintf(checked, sizeof checked, "%u", !!(a->meta.flags & 1));
        } else {
            strcpy(opcode, "unknown"); strcpy(flags, "unknown"); strcpy(isvoid, "unknown");
            strcpy(checked, "unknown");
        }
        int n = snprintf(text, sizeof text,
            "xcb_request_probe tid=%ld unknown=%u extension=%s opcode=%s flags=%s isvoid=%s checked=%s"
            " wall_ns=%" PRIu64 " calls=%" PRIu64 " timed=%" PRIu64
            " invalid_clock=%" PRIu64 " sum_ns=%" PRIu64 " max_ns=%" PRIu64 " slow_ge20ms=%" PRIu64 "\n",
            tid, !a->meta.known, a->meta.known ? a->meta.extension : "unknown", opcode, flags, isvoid, checked,
            end - window_start, a->calls, a->timed, a->invalid, a->sum, a->max, a->slow);
        if (n > 0) { ssize_t written = write(2, text, (size_t)n < sizeof text ? (size_t)n : sizeof text - 1); (void)written; }
    }
    memset(classes, 0, sizeof classes);
    class_count = 0;
    window_start = end;
}
static void record(struct metadata m, int ok1, uint64_t start, int ok2, uint64_t end)
{
    if (!have_start && (ok1 || ok2)) { window_start = ok1 ? start : end; have_start = 1; }
    unsigned slot = CAP; /* Dedicated unknown/aggregate-overflow bucket. */
    if (m.known) {
        for (unsigned i = 0; i < class_count; ++i) if (same(classes[i].meta, m)) { slot = i; break; }
        if (slot == CAP && class_count < CAP) { slot = class_count++; classes[slot].meta = m; }
    }
    struct aggregate *a = &classes[slot];
    ++a->calls;
    if (ok1 && ok2 && end >= start) {
        uint64_t elapsed = end - start;
        ++a->timed; a->sum += elapsed;
        if (elapsed > a->max) a->max = elapsed;
        if (elapsed >= 20000000ULL) ++a->slow;
    } else ++a->invalid;
    if (ok2 && have_start && end >= window_start && end - window_start >= 5000000000ULL) report(end);
}
xcb_generic_error_t *xcb_request_check(xcb_connection_t *connection, xcb_void_cookie_t cookie)
{
    int incoming = errno, outgoing, ok1, ok2;
    uint64_t start = 0, end = 0;
    if (!atomic_load_explicit(&ready, memory_order_acquire) || !next_check) reject_loader();
    if (!enabled || in_probe) return next_check(connection, cookie);
    ++in_probe;
    struct metadata m = take(connection, cookie.sequence);
    ok1 = now_ns(&start);
    errno = incoming;
    xcb_generic_error_t *result = next_check(connection, cookie);
    outgoing = errno;
    ok2 = now_ns(&end);
    record(m, ok1, start, ok2, end);
    --in_probe;
    errno = outgoing;
    return result;
}
