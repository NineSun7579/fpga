#ifndef XCB_REPLY_PROBE_ABI_H
#define XCB_REPLY_PROBE_ABI_H
/* Prefer the installed public ABI; fallback permits header-free host fixtures. */
#if !defined(PROBE_NO_XCB_HEADERS) && defined(__has_include)
#if __has_include(<xcb/xcb.h>)
#include <xcb/xcb.h>
#define PROBE_HAS_XCB_HEADERS 1
#endif
#endif
#ifndef PROBE_HAS_XCB_HEADERS
#include <stdint.h>
typedef struct xcb_connection_t xcb_connection_t;
typedef struct { unsigned int sequence; } xcb_void_cookie_t;
typedef struct {
    uint8_t response_type, error_code;
    uint16_t sequence;
    uint32_t resource_id;
    uint16_t minor_code;
    uint8_t major_code, pad0;
    uint32_t pad[5];
    uint32_t full_sequence;
} xcb_generic_error_t;
xcb_generic_error_t *xcb_request_check(xcb_connection_t *, xcb_void_cookie_t);
#endif
#endif
