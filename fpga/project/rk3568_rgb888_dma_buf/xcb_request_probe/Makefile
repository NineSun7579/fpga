CC ?= cc
CFLAGS ?= -O2
.PHONY: all test clean
all: libxcb_request_probe.so
libxcb_request_probe.so: xcb_request_probe.c xcb_abi.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -std=c11 -Wall -Wextra -Werror -fPIC -shared xcb_request_probe.c -o $@ -ldl
test:
	python3 tests/run_host.py
clean:
	rm -f libxcb_request_probe.so
	rm -rf host_build
