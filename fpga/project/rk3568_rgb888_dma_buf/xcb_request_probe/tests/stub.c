#define _GNU_SOURCE
#include "fixture.h"
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <string.h>
uint64_t fixture_sequence;
int fixture_nested, fixture_recheck;
unsigned fixture_sends, fixture_checks;
xcb_connection_t *expected_connection;
int expected_flags;
struct iovec *expected_vector;
const xcb_protocol_request_t *expected_request;
unsigned expected_num_fds;
int *expected_fds;
xcb_generic_error_t fixture_error;
static void verify(xcb_connection_t *c, int flags, struct iovec *v, const xcb_protocol_request_t *r)
{
    assert(errno == EDOM);
    assert(c == expected_connection && flags == expected_flags);
    assert(v == expected_vector && r == expected_request);
    ++fixture_sends;
    errno = ERANGE;
}
#ifndef OMIT_OPTIONALS
uint64_t xcb_send_request64(xcb_connection_t *c, int f, struct iovec *v, const xcb_protocol_request_t *r)
{ verify(c, f, v, r); return fixture_sequence; }
unsigned int xcb_send_request_with_fds(xcb_connection_t *c, int f, struct iovec *v, const xcb_protocol_request_t *r, unsigned n, int *fds)
{ verify(c, f, v, r); assert(n == expected_num_fds && fds == expected_fds); return (unsigned)fixture_sequence; }
uint64_t xcb_send_request_with_fds64(xcb_connection_t *c, int f, struct iovec *v, const xcb_protocol_request_t *r, unsigned n, int *fds)
{ verify(c, f, v, r); assert(n == expected_num_fds && fds == expected_fds); return fixture_sequence; }
#endif
unsigned int xcb_send_request(xcb_connection_t *c, int f, struct iovec *v, const xcb_protocol_request_t *r)
{
    verify(c, f, v, r);
    if (fixture_nested) {
        uint64_t (*fn)(xcb_connection_t *, int, struct iovec *, const xcb_protocol_request_t *);
        void *p = dlsym(RTLD_DEFAULT, "xcb_send_request64");
        memcpy(&fn, &p, sizeof fn);
        errno = EDOM;
        return (unsigned)fn(c, f, v, r);
    }
    return (unsigned)fixture_sequence;
}
xcb_generic_error_t *xcb_request_check(xcb_connection_t *c, xcb_void_cookie_t cookie)
{
    assert(errno == EDOM);
    assert(c == expected_connection && cookie.sequence == (unsigned)fixture_sequence);
    ++fixture_checks;
    if (fixture_recheck) {
        xcb_generic_error_t *(*fn)(xcb_connection_t *, xcb_void_cookie_t);
        void *p = dlsym(RTLD_DEFAULT, "xcb_request_check");
        memcpy(&fn, &p, sizeof fn);
        fixture_recheck = 0;
        assert(fn(c, cookie) == &fixture_error);
    }
    errno = EILSEQ;
    return &fixture_error;
}
