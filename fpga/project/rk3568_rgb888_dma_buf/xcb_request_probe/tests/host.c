#define _GNU_SOURCE
#include "fixture.h"
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <stddef.h>
_Static_assert(offsetof(xcb_protocol_request_t, count) == 0, "count ABI");
_Static_assert(offsetof(xcb_protocol_request_t, ext) == sizeof(size_t), "ext ABI");
_Static_assert(offsetof(xcb_protocol_request_t, opcode) == sizeof(size_t) + sizeof(void *), "opcode ABI");
_Static_assert(offsetof(xcb_extension_t, global_id) == sizeof(char *), "extension ABI");
static _Thread_local unsigned clock_calls;
static unsigned clock_step = 6;
static int bad_clock;
int probe_test_clock(clockid_t id, struct timespec *t)
{
    assert(id == CLOCK_MONOTONIC);
    t->tv_sec = (time_t)(clock_calls++ * clock_step);
    t->tv_nsec = 0;
    errno = ENOTTY;
    if (bad_clock && clock_calls == 1) return -1;
    return 0;
}
static void *check(void *ignored)
{
    (void)ignored;
    errno = EDOM;
    assert(xcb_request_check(expected_connection, (xcb_void_cookie_t){(unsigned)fixture_sequence}) == &fixture_error);
    assert(errno == EILSEQ);
    return NULL;
}
int main(int argc, char **argv)
{
    assert(argc == 2);
    const char *mode = argv[1];
    if (strcmp(mode, "windows") == 0) clock_step = 1;
    if (strcmp(mode, "invalid") == 0) bad_clock = 1;
    char payload[] = "untouched";
    struct iovec vectors[4] = {{payload, 9}, {payload + 1, 2}, {payload, 9}, {NULL, 0}};
    struct iovec saved[4]; memcpy(saved, vectors, sizeof saved);
    int fds[2] = {71, 72};
    xcb_extension_t extension = {"DRI3", 42};
    xcb_protocol_request_t request = {2, &extension, 7, 1};
    expected_connection = (xcb_connection_t *)(uintptr_t)0x1230;
    expected_flags = strcmp(mode, "flag4") == 0 ? 4 : 1;
    if (strcmp(mode, "flag0") == 0) expected_flags = 0;
    expected_vector = vectors + 2; expected_request = &request;
    expected_num_fds = 2; expected_fds = fds;
    fixture_sequence = 0x100000005ULL;
    if (strcmp(mode, "core") == 0) request.ext = NULL;
    if (strcmp(mode, "wrap") == 0) fixture_sequence = 0x200000000ULL;
    if (strcmp(mode, "failed") == 0) fixture_sequence = 0;
    if (strcmp(mode, "nested") == 0) fixture_nested = 1;
    if (strcmp(mode, "recheck") == 0) fixture_recheck = 1;
    errno = EDOM;
    if (strcmp(mode, "fds") == 0)
        assert(xcb_send_request_with_fds(expected_connection, expected_flags, expected_vector, &request, 2, fds) == (unsigned)fixture_sequence);
    else if (strcmp(mode, "fds64") == 0)
        assert(xcb_send_request_with_fds64(expected_connection, expected_flags, expected_vector, &request, 2, fds) == fixture_sequence);
    else if (strcmp(mode, "send32") == 0 || fixture_nested)
        assert(xcb_send_request(expected_connection, expected_flags, expected_vector, &request) == (unsigned)fixture_sequence);
    else
        assert(xcb_send_request64(expected_connection, expected_flags, expected_vector, &request) == fixture_sequence);
    assert(errno == ERANGE);
    assert(memcmp(saved, vectors, sizeof saved) == 0 && fds[0] == 71 && fds[1] == 72);
    assert(strcmp(payload, "untouched") == 0 && extension.global_id == 42);
    if (strcmp(mode, "collision") == 0) expected_connection = (xcb_connection_t *)(uintptr_t)0x4560;
    if (strcmp(mode, "overwrite") == 0) {
        for (unsigned i = 0; i < 64; ++i) {
            fixture_sequence = 100 + i; errno = EDOM;
            xcb_send_request64(expected_connection, expected_flags, expected_vector, &request);
        }
        fixture_sequence = 0x100000005ULL;
    }
    if (strcmp(mode, "ambiguous") == 0) {
        fixture_sequence += 0x100000000ULL; errno = EDOM;
        xcb_send_request64(expected_connection, expected_flags, expected_vector, &request);
    }
    if (strcmp(mode, "conn_pair") == 0) {
        expected_connection = (xcb_connection_t *)(uintptr_t)0x4560;
        request.opcode = 9; errno = EDOM;
        xcb_send_request64(expected_connection, expected_flags, expected_vector, &request);
        expected_connection = (xcb_connection_t *)(uintptr_t)0x1230;
    }
    if (strcmp(mode, "snapshot") == 0) { request.opcode = 99; extension.name = "CHANGED"; }
    if (strcmp(mode, "thread") == 0) {
        pthread_t thread; assert(pthread_create(&thread, NULL, check, NULL) == 0);
        assert(pthread_join(thread, NULL) == 0);
    } else check(NULL);
    assert(fixture_checks == (strcmp(mode, "recheck") == 0 ? 2u : 1u));
    if (fixture_nested) assert(fixture_sends == 2);
    if (strcmp(mode, "repeat") == 0) check(NULL);
    if (strcmp(mode, "conn_pair") == 0) {
        expected_connection = (xcb_connection_t *)(uintptr_t)0x4560;
        check(NULL);
    }
    if (strcmp(mode, "windows") == 0 || strcmp(mode, "invalid") == 0) {
        unsigned count = bad_clock ? 1 : 5;
        for (unsigned i = 0; i < count; ++i) {
            errno = EDOM;
            xcb_send_request64(expected_connection, expected_flags, expected_vector, &request);
            check(NULL);
        }
    }
    printf("PASS %s sends=%u checks=%u\n", mode, fixture_sends, fixture_checks);
    return 0;
}
