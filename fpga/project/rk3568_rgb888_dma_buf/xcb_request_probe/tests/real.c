#include "../xcb_abi.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
int main(void)
{
    /* Explicit invalid local display: no functioning X server is needed. */
    xcb_connection_t *c = xcb_connect("invalid-display", NULL);
    assert(xcb_connection_has_error(c));
    unsigned char payload[4] = {0};
    struct iovec vectors[3] = {{NULL, 0}, {NULL, 0}, {payload, sizeof payload}}, saved[3];
    memcpy(saved, vectors, sizeof saved);
    xcb_protocol_request_t request = {1, NULL, 127, 1};
    errno = EDOM;
    unsigned seq = xcb_send_request(c, 1, vectors + 2, &request);
    assert(seq == 0 && errno == EDOM);
    assert(memcmp(vectors, saved, sizeof saved) == 0);
    xcb_generic_error_t *error = xcb_request_check(c, (xcb_void_cookie_t){seq});
    assert(error == NULL);
    xcb_disconnect(c);
    puts("real libxcb error connection: zero cookie and vector preserved");
    return 0;
}
