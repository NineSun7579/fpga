CC ?= cc
CFLAGS ?= -O2

.PHONY: all test clean
all: libegl_swap_probe.so

libegl_swap_probe.so: egl_swap_probe.c egl_abi.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -std=c11 -Wall -Wextra -Werror -fPIC -shared egl_swap_probe.c -o $@ -ldl -pthread

test:
	python3 tests/run_host.py

clean:
	rm -f libegl_swap_probe.so
	rm -rf host_build
