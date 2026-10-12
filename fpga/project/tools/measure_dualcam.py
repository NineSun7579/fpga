#!/usr/bin/env python3
"""Read-only RK3568 dual-camera throughput and RTL-diagnostic probe.

The caller should stop camview/detview before running this tool.  The tool only
uses the driver's FPGA-to-host read path; it does not write camera registers.
The two tag locations are ping/pong buffers for one camera, so frame_done is the
primary FPS metric and tag changes are a secondary cross-check.
"""
import ctypes
import fcntl
import mmap
import os
import signal
import struct
import time


class Timeout(Exception):
    pass


def alarm_handler(_signum, _frame):
    raise Timeout()


class DmaOp(ctypes.Structure):
    _fields_ = [
        ("current_len", ctypes.c_uint32),
        ("offset_addr", ctypes.c_uint32),
        ("cmd", ctypes.c_uint32),
        ("ddr3_addr", ctypes.c_uint32),
        ("total_length", ctypes.c_uint32),
        ("read_buf", ctypes.c_void_p),
        ("write_buf", ctypes.c_void_p),
    ]


def ioctl_code(number):
    return 0xC0000000 | (4 << 16) | (0x53 << 8) | number


MAP_CMD = ioctl_code(2)
F2H_CMD = ioctl_code(5)
FRAME_BYTES = 640 * 480 * 2
TAG_BASES = {
    "cam1_a": 0x00800000,
    "cam1_b": 0x00A00000,
    "cam2_a": 0x00C00000,
    "cam2_b": 0x00E00000,
}
TAGS = {name + "_tag": base + FRAME_BYTES for name, base in TAG_BASES.items()}

# ov5640_reg.v current map.  Names intentionally describe the actual signal;
# old aliases (href_raw/beat_last) were misleading after the 2026-09-18 probe.
REG_OFFSETS = {
    "pclk_count": 0x10,
    "vsync_count": 0x20,
    "camera_word_count": 0x30,
    "zero_in_or_diag": 0x50,
    "state_cmd_wd": 0x60,       # {wd_cnt[7:0], state[7:0], cmd_cnt[15:0]}
    "aw_b_count": 0x70,         # {b_cnt[15:0], aw_cnt[15:0]}
    "zout_or_diag": 0x90,
    "beat_current": 0xA0,
    "xdma_request": 0xB0,
    "axi_expected_last": 0xD0, # dbg_axi_num, expected last 128-bit beat=38399
    "vsync_raw_count": 0xE0,
    "frame_done_count": 0xF0,   # dbg_last_cnt, completed frame-write count
}


def make_regs(base):
    return {"%s_%s" % (cam, name): base + off
            for cam, base in (("cam1", 0x20000000), ("cam2", 0x20000200))
            for name, off in REG_OFFSETS.items()}


REGS = {}
for cam, base in (("cam1", 0x20000000), ("cam2", 0x20000200)):
    for name, off in REG_OFFSETS.items():
        REGS["%s_%s" % (cam, name)] = base + off


def timed_ioctl(fd, command, op, timeout=12):
    signal.alarm(timeout)
    try:
        fcntl.ioctl(fd, command, op, True)
    finally:
        signal.alarm(0)


def delta32(after, before):
    if after is None or before is None:
        return None
    return (after - before) & 0xFFFFFFFF


def delta16(after, before):
    if after is None or before is None:
        return None
    return (after - before) & 0xFFFF


def unpack_diag(values, cam):
    packed = values.get(cam + "_state_cmd_wd")
    awb = values.get(cam + "_aw_b_count")
    if packed is not None:
        values[cam + "_watchdog_low8"] = (packed >> 24) & 0xFF
        values[cam + "_state"] = (packed >> 16) & 0xFF
        values[cam + "_command_count_low16"] = packed & 0xFFFF
    if awb is not None:
        values[cam + "_b_count_low16"] = (awb >> 16) & 0xFFFF
        values[cam + "_aw_count_low16"] = awb & 0xFFFF


def main():
    signal.signal(signal.SIGALRM, alarm_handler)
    fd = os.open("/dev/pango_pci_driver", os.O_RDWR | os.O_SYNC)
    try:
        for mapping in (0, 1):
            op = DmaOp()
            op.cmd = mapping
            op.total_length = 4 * 1024 * 1024
            timed_ioctl(fd, MAP_CMD, op)
        rx = mmap.mmap(fd, 4 * 1024 * 1024,
                       prot=mmap.PROT_READ | mmap.PROT_WRITE,
                       flags=mmap.MAP_SHARED, offset=1024 * 1024)

        def read_bytes(address, length):
            op = DmaOp()
            op.offset_addr = 0
            op.ddr3_addr = address
            op.total_length = length
            start = time.perf_counter_ns()
            timed_out = False
            try:
                timed_ioctl(fd, F2H_CMD, op)
            except Timeout:
                timed_out = True
            elapsed = (time.perf_counter_ns() - start) / 1e6
            if timed_out:
                return None, elapsed
            return bytes(rx[:length]), elapsed

        def read_u32(address):
            data, elapsed = read_bytes(address, 16)
            return (None if data is None else struct.unpack_from("<I", data)[0]), elapsed

        def read_regs():
            values = {}
            read_ms = []
            for name, address in REGS.items():
                try:
                    value, elapsed = read_u32(address)
                except (Timeout, OSError):
                    value, elapsed = None, 0.0
                values[name] = value
                read_ms.append(elapsed)
            unpack_diag(values, "cam1")
            unpack_diag(values, "cam2")
            return values, read_ms

        def read_tags():
            values = {}
            read_ms = []
            for name, address in TAGS.items():
                try:
                    data, elapsed = read_bytes(address, 16)
                    values[name] = None if data is None else struct.unpack_from("<I", data)[0]
                except (Timeout, OSError):
                    values[name] = None
                    elapsed = 0.0
                read_ms.append(elapsed)
            return values, read_ms

        diag_before, diag_ms = read_regs()
        tags_before, _ = read_tags()
        print("diag_before=%s" % diag_before, flush=True)
        print("tags_before=%s" % tags_before, flush=True)

        duration = 6.0
        print("probe_start frame_bytes=%d duration_s=%.1f" % (FRAME_BYTES, duration), flush=True)
        previous = tags_before
        tag_changes = {name: 0 for name in TAGS}
        tag_steps = {name: 0 for name in TAGS}
        read_errors = 0
        start = time.monotonic()
        next_sample = start
        samples = 0
        while time.monotonic() - start < duration:
            now = time.monotonic()
            if now < next_sample:
                time.sleep(next_sample - now)
            next_sample += 0.020
            row, durations = read_tags()
            for name in TAGS:
                old, new = previous.get(name), row.get(name)
                if new is None:
                    read_errors += 1
                elif old is not None and new != old:
                    tag_changes[name] += 1
                    tag_steps[name] += (new - old) & 0xFFFFFFFF
            previous = row
            samples += 1
            if samples % 100 == 0:
                print("sample=%d t=%.3f tags=%s tag_dma_ms=%.3f..%.3f" %
                      (samples, time.monotonic() - start, row,
                       min(durations), max(durations)), flush=True)

        elapsed = time.monotonic() - start
        diag_after, diag_after_ms = read_regs()
        tags_after, _ = read_tags()
        print("tag_changes=%s tag_steps=%s samples=%d elapsed_s=%.3f read_errors=%d" %
              (tag_changes, tag_steps, samples, elapsed, read_errors), flush=True)
        print("diag_after=%s" % diag_after, flush=True)
        print("tags_after=%s" % tags_after, flush=True)

        for cam in ("cam1", "cam2"):
            fd_delta = delta32(diag_after.get(cam + "_frame_done_count"),
                               diag_before.get(cam + "_frame_done_count"))
            vs_delta = delta32(diag_after.get(cam + "_vsync_raw_count"),
                               diag_before.get(cam + "_vsync_raw_count"))
            aw_delta = delta16(diag_after.get(cam + "_aw_count_low16"),
                               diag_before.get(cam + "_aw_count_low16"))
            b_delta = delta16(diag_after.get(cam + "_b_count_low16"),
                              diag_before.get(cam + "_b_count_low16"))
            cmd_delta = delta16(diag_after.get(cam + "_command_count_low16"),
                                diag_before.get(cam + "_command_count_low16"))
            print("summary %s frame_done=%s fps=%.3f vsync=%s vsync_fps=%.3f "
                  "aw_delta=%s b_delta=%s cmd_delta=%s state=%s wd_low8=%s" %
                  (cam, fd_delta,
                   (fd_delta / elapsed) if fd_delta is not None else float("nan"),
                   vs_delta,
                   (vs_delta / elapsed) if vs_delta is not None else float("nan"),
                   aw_delta, b_delta, cmd_delta,
                   diag_after.get(cam + "_state"),
                   diag_after.get(cam + "_watchdog_low8")), flush=True)

        for base in ("cam1", "cam2"):
            names = [base + "_a_tag", base + "_b_tag"]
            steps = sum(tag_steps.get(n, 0) for n in names)
            print("summary %s tag_step_sum=%d tag_frame_equiv_fps=%.3f" %
                  (base, steps, steps / elapsed), flush=True)
        print("first_diag_read_ms=%.3f..%.3f last_diag_read_ms=%.3f..%.3f" %
              (min(diag_ms), max(diag_ms), min(diag_after_ms), max(diag_after_ms)), flush=True)
        for cam, base in TAG_BASES.items():
            data, elapsed_ms = read_bytes(base, FRAME_BYTES)
            print("frame_read=%s bytes=%s elapsed_ms=%.3f" %
                  (cam, None if data is None else len(data), elapsed_ms), flush=True)
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()