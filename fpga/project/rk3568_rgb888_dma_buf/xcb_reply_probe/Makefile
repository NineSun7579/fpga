CC ?= cc
CFLAGS ?= -O2
.PHONY: all test clean
all: libxcb_reply_probe.so
libxcb_reply_probe.so: xcb_reply_probe.c xcb_abi.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -std=c11 -Wall -Wextra -Werror -fPIC -shared xcb_reply_probe.c -o $@ -ldl
test:
	python3 tests/run_host.py
clean:
	rm -f libxcb_reply_probe.so
	rm -rf host_build
