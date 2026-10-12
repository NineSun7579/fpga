#!/usr/bin/env python3
"""Identify RK3568 i2c buses and whether the sensor is reachable; read-only."""
import glob
import os

for entry in sorted(glob.glob("/sys/bus/i2c/devices/i2c-*")):
    name = "?"
    try:
        with open(os.path.join(entry, "name")) as fh:
            name = fh.read().strip()
    except OSError:
        pass
    of = "-"
    link = os.path.join(entry, "of_node")
    if os.path.islink(link):
        of = os.path.basename(os.readlink(link))
    print("%s name=%s of_node=%s" % (os.path.basename(entry), name, of), flush=True)

print("--- device tree i2c nodes ---", flush=True)
for entry in sorted(glob.glob("/proc/device-tree/i2c@*")):
    compat = "?"
    status = "-"
    for probe, var in (("compatible", "compat"), ("status", "status")):
        path = os.path.join(entry, probe)
        try:
            with open(path, "rb") as fh:
                value = fh.read().decode("utf-8", "replace").split("\x00")[0]
        except OSError:
            value = "?"
        if var == "compat":
            compat = value
        else:
            status = value
    print("%s compatible=%s status=%s" % (os.path.basename(entry), compat, status), flush=True)

print("--- bus 6 raw device list ---", flush=True)
for entry in sorted(glob.glob("/sys/bus/i2c/devices/6-*")):
    print(entry, flush=True)

print("--- pinctrl i2c6 consumers (who owns the pins) ---", flush=True)
try:
    with open("/sys/kernel/debug/pinctrl/pinctrl-rockchip-pinctrl/pinmux-pins", "rb") as fh:
        for line in fh.read().decode("utf-8", "replace").splitlines():
            low = line.lower()
            if "i2c" in low or "gpio4" in low or "gpio0" in low:
                print(line, flush=True)
except OSError as exc:
    print("pinmux unavailable:", exc, flush=True)
print("DONE", flush=True)
