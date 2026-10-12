#define _GNU_SOURCE
#include "../xcb_abi.h"
#include <dlfcn.h>
#include <string.h>
int main(void)
{
    /* Force the minimal original library into DT_NEEDED. */
    xcb_generic_error_t *(*volatile linked)(xcb_connection_t *, xcb_void_cookie_t) = xcb_request_check;
    (void)linked;
    uint64_t (*fn)(xcb_connection_t *, int, struct iovec *, const xcb_protocol_request_t *);
    void *p = dlsym(RTLD_DEFAULT, "xcb_send_request64");
    memcpy(&fn, &p, sizeof fn);
    fn(NULL, 0, NULL, NULL);
    return 0;
}
