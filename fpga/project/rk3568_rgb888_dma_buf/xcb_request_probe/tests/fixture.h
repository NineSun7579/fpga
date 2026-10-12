#include "../xcb_abi.h"
#include <stdint.h>
extern uint64_t fixture_sequence;
extern int fixture_nested, fixture_recheck;
extern unsigned fixture_sends, fixture_checks;
extern xcb_connection_t *expected_connection;
extern int expected_flags;
extern struct iovec *expected_vector;
extern const xcb_protocol_request_t *expected_request;
extern unsigned expected_num_fds;
extern int *expected_fds;
extern xcb_generic_error_t fixture_error;
