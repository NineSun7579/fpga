#ifndef FIXTURE_H
#define FIXTURE_H
#include "../xcb_abi.h"
#include <stdint.h>
struct fixture {
    xcb_connection_t *connection;
    unsigned sequence, calls, clock_reads, extra_calls, writes;
    int incoming, outgoing, null_result, reentry, nested, clock_mode;
    uint64_t duration, step;
    xcb_generic_error_t *returned;
};
extern _Thread_local struct fixture fixture;
void fixture_reset(void);
#endif
