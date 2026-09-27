#!/usr/bin/env python3
"""Read-only probe of RK3568 i2c buses and camera-related ground truth.

Does not write to any bus or register. Only reports what is present.
"""
import fcntl
import os
import struct

I2C_SLAVE = 0x0703
BUSES = (0, 2, 3, 5, 6)
CANDIDATES = (0x3c, 0x3d, 0x30, 0x21, 0x36)  # OV5640/OV5645 etc.


def quick_write(fd, addr):
    try:
        fcntl.ioctl(fd, I2C_SLAVE, addr)
        os.write(fd, b"\x00")
        return True
    except OSError:
        return False


def read_regs(fd, addr, reg_hi, reg_lo, count):
    try:
        fcntl.ioctl(fd, I2C_SLAVE, addr)
        os.write(fd, bytes([reg_hi, reg_lo]))
        data = os.read(fd, count)
        return data
    except OSError as exc:
        return ("ERR", str(exc))


for bus in BUSES:
    path = "/dev/i2c-%d" % bus
    try:
        fd = os.open(path, os.O_RDWR)
    except OSError as exc:
        print("BUS %d open failed: %s" % (bus, exc), flush=True)
        continue
    found = []
    for addr in CANDIDATES:
        if quick_write(fd, addr):
            found.append(hex(addr))
    print("BUS %d candidates present: %s" % (bus, found or "none"), flush=True)
    for addr in CANDIDATES:
        if addr in (0x3c, 0x3d):
            data = read_regs(fd, addr, 0x30, 0x0A, 2)
            print("  addr %s reg 0x300A -> %r" % (hex(addr), data), flush=True)
            data = read_regs(fd, addr, 0x30, 0x0B, 2)
            print("  addr %s reg 0x300B -> %r" % (hex(addr), data), flush=True)
    os.close(fd)

print("--- device tree camera/gpio nodes ---", flush=True)
import glob

for pattern in ("/proc/device-tree/*cam*", "/proc/device-tree/*ov*",
                "/proc/device-tree/*light*", "/proc/device-tree/*led*",
                "/proc/device-tree/*pwm*"):
    for entry in sorted(glob.glob(pattern)):
        print(entry, flush=True)

print("--- gpio-leds / gpio lines mentioning cam or light ---", flush=True)
try:
    with open("/sys/kernel/debug/gpio", "rb") as fh:
        for line in fh.read().decode("utf-8", "replace").splitlines():
            if any(k in line.lower() for k in ("cam", "light", "flash", "led", "fmc")):
                print(line, flush=True)
except OSError as exc:
    print("gpio debug unavailable:", exc, flush=True)
print("DONE", flush=True)
