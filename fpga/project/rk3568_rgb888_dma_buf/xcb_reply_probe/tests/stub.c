#define _GNU_SOURCE
#include "fixture.h"
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

_Thread_local struct fixture fixture;
void fixture_reset(void) { memset(&fixture, 0, sizeof fixture); }

xcb_generic_error_t *xcb_request_check(xcb_connection_t *connection,
                                      xcb_void_cookie_t cookie)
{
    assert(connection == fixture.connection);
    assert(cookie.sequence == fixture.sequence);
    assert(errno == fixture.incoming);
    ++fixture.calls;
    if (fixture.reentry && !fixture.nested) {
        void *symbol = dlsym(RTLD_DEFAULT, "xcb_request_check");
        xcb_generic_error_t *(*check)(xcb_connection_t *, xcb_void_cookie_t);
        memcpy(&check, &symbol, sizeof check);
        fixture.nested = 1;
        errno = fixture.incoming;
        xcb_generic_error_t *inner = check(connection, cookie);
        assert(inner == fixture.returned);
        free(inner);
        fixture.nested = 0;
    }
    fixture.returned = fixture.null_result ? NULL : malloc(sizeof *fixture.returned);
    assert(fixture.null_result || fixture.returned);
    if (fixture.returned) {
        memset(fixture.returned, 0xa5, sizeof *fixture.returned);
        fixture.returned->full_sequence = cookie.sequence;
    }
    errno = fixture.outgoing;
    return fixture.returned;
}

/* Any accidental auxiliary XCB call fails instead of touching an X server. */
int xcb_flush(xcb_connection_t *connection)
{
    (void)connection;
    ++fixture.extra_calls;
    abort();
}
