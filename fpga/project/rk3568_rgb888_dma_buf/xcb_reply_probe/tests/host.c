#define _GNU_SOURCE
#include "fixture.h"
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
#include <stdlib.h>

/* Exercise errno clobbering and a short diagnostic write without retries. */
ssize_t write(int fd, const void *buffer, size_t size)
{
    assert(fd == STDERR_FILENO && size <= 512);
    ++fixture.writes;
    ssize_t result = getenv("FIXTURE_SHORT_WRITE") ? 1 : syscall(SYS_write, fd, buffer, size);
    errno = EIO;
    return result;
}

int probe_test_clock(clockid_t id, struct timespec *ts)
{
    unsigned read = fixture.clock_reads++;
    unsigned call = read / 2;
    int end = read % 2;
    uint64_t value = 10000000000ULL + call * fixture.step +
                     (end ? fixture.duration : 0);
    assert(id == CLOCK_MONOTONIC);
    errno = ERANGE;
    if ((fixture.clock_mode == 1 && read == 0) ||
        (fixture.clock_mode == 2 && read == 1) ||
        (fixture.clock_mode == 3 && read < 2) || fixture.clock_mode == 7) return -1;
    if (fixture.clock_mode == 4 && read == 1) value -= 1000000000ULL;
    ts->tv_sec = (time_t)(value / 1000000000ULL);
    ts->tv_nsec = (long)(value % 1000000000ULL);
    if (fixture.clock_mode == 5 && read == 1) ts->tv_nsec = 1000000000L;
    if (fixture.clock_mode == 6 && read == 1) ts->tv_sec = -1;
    if (fixture.clock_mode == 8 && read == 1) ts->tv_sec = (time_t)INT64_MAX;
    return 0;
}

static void run(const char *case_name)
{
    static const unsigned sequences[] = {UINT_MAX - 1U, UINT_MAX, 0, 1, 65536, 42};
    static const uint64_t durations[] = {500000, 1000000, 5000000, 10000000, 20000000, 25000000};
    int disabled = strcmp(case_name, "disabled") == 0;
    int buckets = strcmp(case_name, "buckets") == 0;
    int windows = strcmp(case_name, "windows") == 0;
    unsigned count = windows ? 7 : buckets ? 6 : 4;
    fixture_reset();
    fixture.step = buckets ? 1000000000ULL : 2000000000ULL;
    fixture.connection = (xcb_connection_t *)(void *)&fixture;
    fixture.reentry = strcmp(case_name, "reentry") == 0;
    if (strncmp(case_name, "clock", 5) == 0) fixture.clock_mode = atoi(case_name + 5);
    if (fixture.clock_mode == 3) count = 5;
    for (unsigned i = 0; i < count; ++i) {
        fixture.sequence = sequences[i % 6];
        fixture.incoming = i % 2 ? EDOM : EINVAL;
        fixture.outgoing = i % 2 ? fixture.incoming : EBUSY;
        fixture.null_result = i % 2;
        fixture.duration = buckets ? durations[i] : 500000;
        errno = fixture.incoming;
        xcb_generic_error_t *result = xcb_request_check(fixture.connection,
            (xcb_void_cookie_t){fixture.sequence});
        assert(errno == fixture.outgoing);
        assert(result == fixture.returned);
        if (result) {
            assert(result->full_sequence == fixture.sequence);
            assert(result->error_code == 0xa5);
            /* Caller owns this exact allocation; probe must never free it. */
            free(result);
        } else assert(fixture.null_result);
    }
    assert(fixture.calls == count * (fixture.reentry ? 2U : 1U));
    assert(fixture.extra_calls == 0);
    const char *real_clock = getenv("FIXTURE_REAL_CLOCK");
    assert(fixture.clock_reads == (disabled || real_clock ? 0U : count * 2U));
    assert(fixture.writes == (disabled || real_clock || fixture.clock_mode == 7 ? 0U : windows ? 2U : 1U));
    printf("fixture tid=%ld calls=%u clock_reads=%u extra_xcb_calls=%u writes=%u\n",
           syscall(SYS_gettid), fixture.calls, fixture.clock_reads, fixture.extra_calls, fixture.writes);
}

static void *worker(void *name) { run(name); return NULL; }
int main(int argc, char **argv)
{
    assert(argc == 2);
    if (strcmp(argv[1], "threads") == 0) {
        pthread_t a, b;
        assert(pthread_create(&a, NULL, worker, "forward") == 0);
        assert(pthread_create(&b, NULL, worker, "forward") == 0);
        run("forward");
        assert(pthread_join(a, NULL) == 0);
        assert(pthread_join(b, NULL) == 0);
    } else run(argv[1]);
    return 0;
}
