"""Independent two-bank ownership scoreboard and cycle-level ModelSim test.

Only this directory is written. RTL is compiled as Verilog-2001 (no -sv).
The Python model uses a ready FIFO and lease records, not RTL internals.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parent
MODELSIM = Path(os.environ.get("MODELSIM_BIN", r"C:\modeltech64_10.6e\win64"))
IN_LAYOUT = [
    ("rst_n", 1), ("input_valid", 1), ("input_raw_valid", 1),
    ("input_src_addr", 32), ("input_source_seq", 32), ("input_generation", 32),
    ("input_camera", 3), ("input_camera_bank", 1), ("input_lease_token", 64),
    ("cmd_ready", 1), ("bridge_busy", 1), ("bridge_done", 1),
    ("bridge_error", 1), ("bridge_cmd_error", 1), ("src_release_ready", 1),
    ("s_axil_awaddr", 32), ("s_axil_awvalid", 1), ("s_axil_wdata", 32),
    ("s_axil_wstrb", 4), ("s_axil_wvalid", 1), ("s_axil_bready", 1),
    ("s_axil_araddr", 32), ("s_axil_arvalid", 1), ("s_axil_rready", 1),
]
OUT_LAYOUT = [
    ("input_ready", 1), ("input_claim", 1), ("input_reject", 1),
    ("cmd_valid", 1), ("cmd_src_addr", 32), ("cmd_dst_addr", 32), ("cmd_frame_id", 32),
    ("src_release_valid", 1), ("src_release_addr", 32), ("src_release_seq", 32),
    ("src_release_generation", 32), ("src_release_camera", 3),
    ("src_release_camera_bank", 1), ("src_release_token", 64),
    ("busy", 1), ("bank0_state", 2), ("bank1_state", 2),
    ("s_axil_awready", 1), ("s_axil_wready", 1), ("s_axil_bvalid", 1),
    ("s_axil_bresp", 2), ("s_axil_arready", 1), ("s_axil_rvalid", 1),
    ("s_axil_rdata", 32), ("s_axil_rresp", 2),
]
FREE, WRITING, READY, HOST = range(4)
OKAY, SLVERR = 0, 2


def pack(layout, fields):
    result = 0
    for key, bits in layout:
        value = fields[key]
        assert 0 <= value < 1 << bits, (key, value)
        result = (result << bits) | value
    return result


def unpack(layout, value):
    result = {}
    for key, bits in reversed(layout):
        result[key] = value & ((1 << bits) - 1)
        value >>= bits
    assert not value
    return result


@dataclass(frozen=True)
class Lease:
    address: int = 0
    seq: int = 0
    generation: int = 0
    camera: int = 0
    camera_bank: int = 0
    token: int = 0


class Scoreboard:
    def __init__(self, addresses=(0x08000000, 0x08200000), length=1228800):
        self.addresses = addresses
        self.length = length
        self.reset()

    def reset(self):
        self.states = [FREE, FREE]
        self.leases = [Lease(), Lease()]
        self.ready_queue = deque()
        self.host = None
        self.operation = None
        self.launched = False
        self.failed = False
        self.rejected = False
        self.command = None
        self.last_command = (0, 0, 0)
        self.release = None
        self.last_release = Lease()
        self.ack = [0, 0, 0]
        self.counters = dict(ack=0, claim=0, raw=0, failure=0, done=0, release=0, accept=0)
        self.last_error = 0
        self.aw_slot = None
        self.w_slot = None
        self.b = None
        self.last_b = OKAY
        self.r = None
        self.last_r = (0, OKAY)

    def outputs(self, s):
        ready = int(bool(s["rst_n"] and self.operation is None and self.command is None
                         and not s["bridge_busy"] and self.release is None
                         and FREE in self.states))
        claim = ready & s["input_valid"] & s["input_raw_valid"]
        reject = ready & s["input_valid"] & (not s["input_raw_valid"])
        cmd = self.last_command
        lease = self.last_release
        data, resp = self.last_r
        return dict(input_ready=ready, input_claim=int(claim), input_reject=int(reject),
                    cmd_valid=int(self.command is not None), cmd_src_addr=cmd[0],
                    cmd_dst_addr=cmd[1], cmd_frame_id=cmd[2],
                    src_release_valid=int(self.release is not None),
                    src_release_addr=lease.address, src_release_seq=lease.seq,
                    src_release_generation=lease.generation, src_release_camera=lease.camera,
                    src_release_camera_bank=lease.camera_bank, src_release_token=lease.token,
                    busy=int(self.operation is not None), bank0_state=self.states[0],
                    bank1_state=self.states[1],
                    s_axil_awready=int(bool(s["rst_n"] and self.aw_slot is None and self.b is None)),
                    s_axil_wready=int(bool(s["rst_n"] and self.w_slot is None and self.b is None)),
                    s_axil_bvalid=int(self.b is not None), s_axil_bresp=self.last_b,
                    s_axil_arready=int(bool(s["rst_n"] and (self.r is None or s["s_axil_rready"]))),
                    s_axil_rvalid=int(self.r is not None), s_axil_rdata=data, s_axil_rresp=resp)

    def read(self, addr, s):
        lease = self.leases[self.host] if self.host is not None else Lease()
        valid = self.host is not None
        desc = {0x10: self.host if valid else 0xffffffff,
                0x14: lease.seq, 0x18: lease.generation, 0x1c: self.length if valid else 0,
                0x20: self.addresses[self.host] if valid else 0, 0x24: lease.camera,
                0x28: lease.camera_bank, 0x2c: lease.address,
                0x30: self.host if valid else 0xffffffff,
                0x34: lease.token & 0xffffffff, 0x38: lease.token >> 32}
        status = (int(self.operation is not None) | (int(self.command is not None) << 1)
                  | (int(bool(self.ready_queue)) << 2) | (int(valid) << 3)
                  | (int(self.release is not None) << 4) | (s["bridge_busy"] << 5)
                  | (int(self.last_error != 0) << 6)
                  | (self.states[0] << 10) | (self.states[1] << 12))
        table = {0: 0x434f4f50, 4: status, 8: 0x10000,
                 0x0c: self.ready_queue[0] if self.ready_queue else 0xffffffff,
                 **desc, 0x40: self.ack[0], 0x44: self.ack[1], 0x48: self.ack[2], 0x4c: 0,
                 0x50: self.counters["ack"], 0x54: self.counters["claim"],
                 0x58: self.counters["raw"], 0x5c: self.counters["failure"],
                 0x60: self.counters["done"], 0x64: self.counters["release"],
                 0x68: self.counters["accept"], 0x6c: self.last_error}
        return (table[addr], OKAY) if addr in table else (0, SLVERR)

    def write(self, addr, data, strobes):
        if addr in (0x40, 0x44, 0x48):
            idx = (addr - 0x40) // 4
            original = bytearray(self.ack[idx].to_bytes(4, "little"))
            for byte in range(4):
                if strobes & (1 << byte):
                    original[byte] = (data >> (byte * 8)) & 255
            self.ack[idx] = int.from_bytes(original, "little")
            return OKAY
        if addr == 0x30:
            if not strobes & 1:
                return OKAY
            selected = data & 1
            if self.host is None and self.ready_queue and self.ready_queue[0] == selected:
                self.host = self.ready_queue.popleft()
                self.states[self.host] = HOST
                return OKAY
            self.counters["claim"] += 1
            self.last_error = 3
            return SLVERR
        if addr == 0x4c:
            if not (strobes & 1 and data & 1):
                return OKAY
            if self.host is not None:
                lease = self.leases[self.host]
                if self.ack == [self.host, lease.seq, lease.generation] and self.states[self.host] == HOST:
                    self.states[self.host] = FREE
                    self.host = None
                    return OKAY
            self.counters["ack"] += 1
            self.last_error = 4
            return SLVERR
        return SLVERR

    def tick(self, s, out):
        if not s["rst_n"]:
            self.reset()
            return
        # Reads snapshot state at AR acceptance, before same-edge transitions.
        next_r = self.read(s["s_axil_araddr"], s) if out["s_axil_arready"] and s["s_axil_arvalid"] else None
        pending_write = (self.aw_slot, self.w_slot) if (
            self.aw_slot is not None and self.w_slot is not None and self.b is None) else None
        old_ready = list(self.ready_queue)
        finished = (self.operation is not None and self.launched and
                    (s["bridge_done"] or ((self.rejected or s["bridge_cmd_error"]) and not s["bridge_busy"])))
        terminal_error = self.failed or s["bridge_error"] or self.rejected or s["bridge_cmd_error"]
        if self.release is not None and s["src_release_ready"]:
            self.release = None
            self.counters["release"] += 1
        if out["input_reject"]:
            self.counters["raw"] += 1
            self.last_error = 1
        if out["input_claim"]:
            bank = self.states.index(FREE)
            lease = Lease(s["input_src_addr"], s["input_source_seq"], s["input_generation"],
                          s["input_camera"], s["input_camera_bank"], s["input_lease_token"])
            self.states[bank] = WRITING
            self.leases[bank] = lease
            self.operation = bank
            self.launched = self.failed = self.rejected = False
            self.command = (lease.address, self.addresses[bank], lease.seq)
            self.last_command = self.command
            self.last_release = lease
            self.counters["accept"] += 1
        if self.operation is not None and self.launched:
            self.failed |= bool(s["bridge_error"] or s["bridge_cmd_error"])
            self.rejected |= bool(s["bridge_cmd_error"])
        if out["cmd_valid"] and s["cmd_ready"]:
            self.command = None
            self.launched = True
        if finished:
            bank = self.operation
            self.release = self.leases[bank]
            self.states[bank] = FREE if terminal_error else READY
            if terminal_error:
                self.counters["failure"] += 1
                self.last_error = 2
            else:
                self.ready_queue.append(bank)
                self.counters["done"] += 1
            self.operation = None
            self.launched = False
        if self.b is not None and s["s_axil_bready"]:
            self.b = None
        if pending_write is not None:
            addr, (data, strobes) = pending_write
            # A newly completed output is visible to CLAIM next cycle. Older
            # ready records may still be claimed on the completion edge.
            self.ready_queue = deque(old_ready)
            self.b = self.write(addr, data, strobes)
            if finished and not terminal_error:
                self.ready_queue.append(bank)
            self.last_b = self.b
            self.aw_slot = self.w_slot = None
        if out["s_axil_awready"] and s["s_axil_awvalid"]:
            self.aw_slot = s["s_axil_awaddr"]
        if out["s_axil_wready"] and s["s_axil_wvalid"]:
            self.w_slot = (s["s_axil_wdata"], s["s_axil_wstrb"])
        if next_r is not None:
            self.r = next_r
            self.last_r = next_r
        elif self.r is not None and s["s_axil_rready"]:
            self.r = None
        assert len(self.ready_queue) == len(set(self.ready_queue))
        assert all(self.states[b] == READY for b in self.ready_queue)
        assert (self.host is None) or self.states[self.host] == HOST
        assert (self.operation is None) or self.states[self.operation] == WRITING


class Scenario:
    def __init__(self, addresses=(0x08000000, 0x08200000), length=1228800):
        self.model = Scoreboard(addresses, length)
        self.inputs, self.expected, self.labels = [], [], []
        self.levels = dict(rst_n=1, bridge_busy=0, bridge_error=0,
                           cmd_ready=0, src_release_ready=0)
        self.markers = []

    def cycle(self, label="", **signals):
        s = {key: 0 for key, _ in IN_LAYOUT}
        s.update(self.levels)
        s.update(signals)
        if not s["rst_n"]:
            self.model.reset()
        out = self.model.outputs(s)
        self.inputs.append(s)
        self.expected.append(out)
        self.labels.append(label)
        self.model.tick(s, out)
        return out

    def wait(self, cycles=1, label="", **signals):
        for _ in range(cycles):
            self.cycle(label, **signals)

    def reset(self):
        self.levels.update(bridge_busy=0, bridge_error=0, cmd_ready=0, src_release_ready=0)
        self.wait(3, "common reset", rst_n=0)
        self.wait(2, "reset deasserted")

    def mark(self, label):
        self.markers.append(dict(label=label, cycle=len(self.inputs)))

    def write(self, addr, data, strobes=15, order=0, gap=0, bstall=0, expect=OKAY):
        # order=-1: W before AW; +1: AW before W; 0: simultaneous.
        aw_done = w_done = False
        cycles = 0
        while not (aw_done and w_done):
            aw_valid = not aw_done and (order != -1 or cycles > gap)
            w_valid = not w_done and (order != 1 or cycles > gap)
            out = self.cycle("AXIL AW/W", s_axil_awaddr=addr, s_axil_awvalid=int(aw_valid),
                             s_axil_wdata=data, s_axil_wstrb=strobes, s_axil_wvalid=int(w_valid))
            aw_done |= bool(aw_valid and out["s_axil_awready"])
            w_done |= bool(w_valid and out["s_axil_wready"])
            cycles += 1
            assert cycles < 100
        while not self.model.b is not None:
            self.cycle("wait B")
        self.wait(bstall, "B backpressure")
        assert self.model.b == expect, (hex(addr), hex(data), self.model.b, expect)
        self.cycle("consume B", s_axil_bready=1)

    def read(self, addr, rstall=0, expect=None, resp=OKAY):
        while True:
            out = self.cycle("AR accepted", s_axil_araddr=addr, s_axil_arvalid=1)
            if out["s_axil_arready"]:
                break
        assert self.model.r is not None
        data, actual_resp = self.model.r
        assert actual_resp == resp, (addr, actual_resp, resp)
        if expect is not None:
            assert data == expect, (hex(addr), hex(data), hex(expect))
        self.wait(rstall, "R backpressure")
        self.cycle("consume R", s_axil_rready=1)
        return data

    def offer(self, lease, raw=True, stalls=0):
        out = self.cycle("input descriptor", input_valid=1, input_raw_valid=int(raw),
                         input_src_addr=lease.address, input_source_seq=lease.seq,
                         input_generation=lease.generation, input_camera=lease.camera,
                         input_camera_bank=lease.camera_bank, input_lease_token=lease.token)
        assert out["input_ready"]
        assert bool(out["input_claim"]) == raw
        assert bool(out["input_reject"]) != raw
        if raw:
            self.wait(stalls, "buffered bridge command")

    def launch(self):
        assert self.model.command is not None
        self.cycle("bridge command acceptance", cmd_ready=1)
        self.levels["bridge_busy"] = 1
        self.wait(2, "bridge active")

    def finish(self, error=False, delay=4, release_stall=3):
        assert self.model.operation is not None
        self.levels["bridge_error"] = int(error)
        self.wait(delay, "final B/drain delayed")
        assert self.model.release is None
        assert self.model.states[self.model.operation] == WRITING
        self.levels["bridge_busy"] = 0
        self.cycle("bridge drained completion", bridge_done=1)
        assert self.model.release is not None
        self.wait(release_stall, "source release stalled", input_valid=1, input_raw_valid=1)
        self.cycle("source release acceptance", src_release_ready=1)
        self.levels["bridge_error"] = 0

    def ack(self, bank, seq, gen, expect=OKAY, order=0):
        self.write(0x40, bank, order=order)
        self.write(0x44, seq, order=-order)
        self.write(0x48, gen, order=order)
        self.write(0x4c, 1, expect=expect)

    def descriptor(self, bank, lease):
        wanted = {0x10: bank, 0x14: lease.seq, 0x18: lease.generation,
                  0x1c: self.model.length, 0x20: self.model.addresses[bank],
                  0x24: lease.camera, 0x28: lease.camera_bank, 0x2c: lease.address,
                  0x34: lease.token & 0xffffffff, 0x38: lease.token >> 32}
        for addr, value in wanted.items():
            self.read(addr, rstall=2, expect=value)


def directed(sc):
    sc.reset()
    sc.read(0, expect=0x434f4f50)
    sc.read(8, expect=0x10000)
    sc.read(0x10, expect=0xffffffff)
    sc.read(0x14, expect=0)
    sc.read(0x10000, resp=SLVERR)
    sc.read(3, resp=SLVERR)
    sc.write(0, 0xffffffff, expect=SLVERR)
    sc.write(0x41, 0, expect=SLVERR)
    # Every byte strobe combination and independent ordering; mask merges
    # are verified through public reads, not internal model values alone.
    value = 0
    for strobe in range(16):
        data = (0x91827364 ^ (strobe * 0x0f070301)) & 0xffffffff
        sc.write(0x44, data, strobes=strobe, order=(strobe % 3) - 1, gap=strobe % 4, bstall=strobe % 5)
        mask = sum(255 << (8 * b) for b in range(4) if strobe & (1 << b))
        value = (value & ~mask) | (data & mask)
        sc.read(0x44, expect=value)
    for addr in (0x40, 0x48):
        sc.write(addr, 0xaabbccdd)
        sc.write(addr, 0x12345678, strobes=5, order=-1, gap=6)
        sc.read(addr, expect=0xaa34cc78)
    sc.mark("all strobes, AW/W orders, B stalls, exact register decode")

    raw_bad = Lease(0x00400000, 1, 17, 3, 1, 0x123456789abcdef0)
    sc.offer(raw_bad, raw=False)
    sc.wait(4)
    assert sc.model.command is None and sc.model.release is None
    sc.read(0x58, expect=1)
    sc.write(0x30, 0, expect=SLVERR)
    sc.ack(0, 1, 17, expect=SLVERR)
    sc.mark("uncertified RAW rejected without lease claim or bridge start")

    first = Lease(0x00400000, 0xfffffff0, 17, 3, 1, 0x123456789abcdef0)
    sc.offer(first, stalls=12)
    for _ in range(5):
        out = sc.cycle("blocked duplicate input", input_valid=1, input_raw_valid=1,
                       input_src_addr=0x00600000, input_source_seq=123)
        assert not out["input_ready"]
    sc.launch()
    sc.levels["bridge_error"] = 0
    sc.wait(15, "last write B not retired")
    sc.write(0x30, 0, expect=SLVERR)
    sc.finish(delay=7, release_stall=9)
    sc.read(0x0c, expect=0)
    # ACK must never free READY, even with correct seq/generation.
    sc.ack(0, first.seq, first.generation, expect=SLVERR, order=-1)
    assert sc.model.states == [READY, FREE]
    sc.write(0x30, 0, strobes=0)
    assert sc.model.host is None
    sc.write(0x30, 0)
    sc.descriptor(0, first)
    sc.write(0x30, 1, expect=SLVERR)
    sc.ack(1, first.seq, first.generation, expect=SLVERR)
    sc.ack(0, first.seq ^ 1, first.generation, expect=SLVERR)
    sc.ack(0, first.seq, first.generation - 1, expect=SLVERR)
    sc.descriptor(0, first)
    sc.mark("WRITING waits for drain; exact HOST_READING ACK and coherent claim")

    second = Lease(0x00600000, 7, 18, 2, 0, 0xffeeddcc11223344)
    sc.offer(second, stalls=3)
    sc.launch()
    # Capture a descriptor R, then complete the other bank while R is blocked.
    sc.cycle("capture stalled descriptor R", s_axil_arvalid=1, s_axil_araddr=0x14)
    sc.finish(delay=9, release_stall=7)
    sc.wait(8, "new AR held while old R blocked", s_axil_arvalid=1, s_axil_araddr=0x20)
    sc.cycle("R/AR same cycle", s_axil_rready=1, s_axil_arvalid=1, s_axil_araddr=0x20)
    assert sc.model.r == (sc.model.addresses[0], OKAY)
    sc.cycle("next consecutive AR", s_axil_rready=1, s_axil_arvalid=1, s_axil_araddr=0x18)
    assert sc.model.r == (first.generation, OKAY)
    sc.cycle("drain R", s_axil_rready=1)
    assert sc.model.states == [HOST, READY]
    for _ in range(20):
        out = sc.cycle("both outputs owned: backpressure", input_valid=1, input_raw_valid=1)
        assert not out["input_ready"]
    sc.descriptor(0, first)
    sc.ack(0, first.seq, first.generation)
    # Delayed duplicate ACK cannot free another bank in READY.
    sc.write(0x4c, 1, expect=SLVERR)
    assert sc.model.states == [FREE, READY]
    sc.write(0x30, 0, expect=SLVERR)
    sc.write(0x30, 1)
    sc.descriptor(1, second)
    sc.mark("second READY during host read; output-full stalls; AR/R hold and replacement")

    failed = Lease(0x00400000, 8, 18, 1, 1, 0xa0b0c0d000000001)
    sc.offer(failed, stalls=5)
    sc.launch()
    sc.levels["bridge_error"] = 1
    sc.wait(10, "in-flight error cannot release or abort")
    sc.levels["bridge_error"] = 0  # even a transient error stays latched
    sc.finish(error=False, delay=10, release_stall=15)
    assert sc.model.states == [FREE, HOST]
    sc.read(0x5c, expect=1)
    sc.descriptor(1, second)
    sc.ack(1, second.seq, second.generation)
    sc.mark("transient bridge error drains then frees output; release backpressure")

    # Existing bridge rejects misalignment without ever pulsing done.
    rejected = Lease(0x00400001, 9, 18, 0, 0, 0x1234)
    sc.offer(rejected)
    sc.cycle("invalid command accepted by bridge", cmd_ready=1)
    sc.cycle("no-launch bridge command rejection", bridge_cmd_error=1, bridge_error=1)
    assert sc.model.release == rejected and sc.model.operation is None
    sc.wait(5, "rejected input release stalled")
    sc.cycle("rejected input release acceptance", src_release_ready=1)
    sc.read(0x5c, expect=2)
    sc.mark("cmd_error handles real bridge no-done rejection")

    # Both READY: FIFO age uses completion order, independent of seq/gen.
    older = Lease(0x00400000, 0xffffffff, 0xffffffff, 0, 1, 0x5555)
    newer = Lease(0x00600000, 0, 0, 3, 0, 0x6666)
    for lease in (older, newer):
        sc.offer(lease)
        sc.launch()
        sc.finish()
    for _ in range(8):
        out = sc.cycle("both banks READY: descriptor remains caller owned",
                       input_valid=1, input_raw_valid=1)
        assert not out["input_ready"]
    sc.write(0x30, 1, expect=SLVERR)
    sc.write(0x30, 0)
    sc.descriptor(0, older)
    sc.ack(0, older.seq, older.generation)
    sc.write(0x30, 1)
    sc.descriptor(1, newer)
    sc.ack(1, newer.seq, newer.generation)
    sc.mark("oldest-ready claim independent of numeric sequence/generation wrap")

    # Keep AWVALID/WVALID asserted through a stalled B to the next handshake.
    sc.cycle("continuous write 1", s_axil_awvalid=1, s_axil_awaddr=0x44,
             s_axil_wvalid=1, s_axil_wstrb=15, s_axil_wdata=0x11223344)
    sc.cycle("commit write 1")
    for _ in range(6):
        sc.cycle("second write blocked behind B", s_axil_awvalid=1, s_axil_awaddr=0x48,
                 s_axil_wvalid=1, s_axil_wstrb=15, s_axil_wdata=0x99887766)
    sc.cycle("consume B with next AW/W held", s_axil_bready=1,
             s_axil_awvalid=1, s_axil_awaddr=0x48,
             s_axil_wvalid=1, s_axil_wstrb=15, s_axil_wdata=0x99887766)
    sc.cycle("next AW/W accepted", s_axil_awvalid=1, s_axil_awaddr=0x48,
             s_axil_wvalid=1, s_axil_wstrb=15, s_axil_wdata=0x99887766)
    sc.cycle("commit write 2")
    sc.cycle("consume B 2", s_axil_bready=1)
    sc.read(0x44, expect=0x11223344)
    sc.read(0x48, expect=0x99887766)
    sc.mark("back-to-back AW/W sustained through B response stalls")

    # Reset with a claim, partial write and stalled R. External manager changes
    # generation, even when source seq is reused. Stale ACK must fail.
    previous = Lease(0x00400000, 55, 100, 3, 1, 0x7777)
    sc.offer(previous)
    sc.launch()
    sc.finish()
    sc.write(0x30, 0)
    sc.cycle("half write before reset", s_axil_awvalid=1, s_axil_awaddr=0x4c,
             s_axil_arvalid=1, s_axil_araddr=0x14)
    sc.reset()
    current = Lease(previous.address, previous.seq, previous.generation + 1, 3, 1, 0x8888)
    sc.offer(current, stalls=7)
    sc.launch()
    sc.finish()
    sc.write(0x30, 0)
    sc.ack(0, previous.seq, previous.generation, expect=SLVERR)
    sc.descriptor(0, current)
    sc.ack(0, current.seq, current.generation)
    sc.read(0x50, expect=1)
    sc.read(0x60, expect=1)
    sc.read(0x64, expect=1)
    sc.read(0x68, expect=1)
    sc.mark("common reset clears AXIL slots/claims; changed generation rejects stale ACK")

    # Completion and host write commit on the same edge: a previously READY
    # record can be claimed, while a just-completed record requires a new CLAIM.
    sc.reset()
    lease0 = Lease(0x00400000, 1, 202, 0, 0, 0x1001)
    lease1 = Lease(0x00600000, 2, 202, 1, 1, 0x1002)
    sc.offer(lease0)
    sc.launch()
    sc.finish()
    sc.offer(lease1)
    sc.launch()
    sc.cycle("capture claim for already READY bank during operation",
             s_axil_awvalid=1, s_axil_awaddr=0x30,
             s_axil_wvalid=1, s_axil_wstrb=15, s_axil_wdata=0)
    sc.levels["bridge_busy"] = 0
    sc.cycle("complete other bank and commit claim simultaneously", bridge_done=1)
    assert sc.model.states == [HOST, READY]
    sc.cycle("retire B and source release", s_axil_bready=1, src_release_ready=1)
    sc.descriptor(0, lease0)
    sc.ack(0, lease0.seq, lease0.generation)
    sc.write(0x30, 1)
    # ACK bank 1 and complete bank 0 on the same edge.
    lease2 = Lease(0x00400000, 3, 202, 3, 0, 0x1003)
    sc.offer(lease2)
    sc.launch()
    sc.write(0x40, 1)
    sc.write(0x44, lease1.seq)
    sc.write(0x48, lease1.generation)
    sc.cycle("capture ACK of host bank during operation",
             s_axil_awvalid=1, s_axil_awaddr=0x4c,
             s_axil_wvalid=1, s_axil_wstrb=1, s_axil_wdata=1)
    sc.levels["bridge_busy"] = 0
    sc.cycle("ACK host bank and complete other bank simultaneously", bridge_done=1)
    assert sc.model.states == [READY, FREE]
    sc.cycle("retire concurrent B and release", s_axil_bready=1, src_release_ready=1)
    sc.write(0x30, 0)
    sc.ack(0, lease2.seq, lease2.generation)

    lease3 = Lease(0x00400000, 4, 202, 2, 0, 0x1004)
    sc.offer(lease3)
    sc.launch()
    sc.cycle("capture premature claim", s_axil_awvalid=1, s_axil_awaddr=0x30,
             s_axil_wvalid=1, s_axil_wstrb=1, s_axil_wdata=0)
    sc.levels["bridge_busy"] = 0
    sc.cycle("premature claim commits at completion edge", bridge_done=1)
    assert sc.model.b == SLVERR and sc.model.host is None
    sc.cycle("consume premature B and release", s_axil_bready=1, src_release_ready=1)
    sc.write(0x30, 0)
    sc.ack(0, lease3.seq, lease3.generation)
    sc.mark("simultaneous completion/CLAIM and completion/ACK; edge snapshot semantics")

    # A spurious done before command acceptance cannot retire the lease.
    sc.offer(lease0, stalls=2)
    sc.cycle("done before command acceptance ignored", bridge_done=1)
    assert sc.model.release is None and sc.model.operation == 0
    sc.launch()
    # Command rejection while busy is retained, but must wait for idle/drain.
    sc.cycle("command error while bridge still busy", bridge_cmd_error=1)
    sc.wait(8, "rejection waits until bridge idle")
    assert sc.model.operation == 0 and sc.model.release is None
    sc.levels["bridge_busy"] = 0
    sc.cycle("rejected command reaches idle")
    assert sc.model.states[0] == FREE and sc.model.release == lease0
    sc.cycle("release rejected command", src_release_ready=1)
    sc.mark("pre-command done ignored; cmd_error held until bridge idle")

    # Common reset invalidates pending controller/AXIL work. Tests model the
    # bridge and bus receiving that same reset, never standalone cancellation.
    sc.offer(lease0, stalls=4)
    sc.cycle("W-only partial write and queued command", s_axil_wvalid=1,
             s_axil_wstrb=15, s_axil_wdata=0xdeadbeef)
    sc.reset()
    sc.wait(3, "partial W and queued command flushed", bridge_done=1)
    assert sc.model.command is None and sc.model.release is None
    sc.offer(lease1)
    sc.launch()
    sc.cycle("capture write while bridge active", s_axil_awvalid=1, s_axil_awaddr=0x44,
             s_axil_wvalid=1, s_axil_wstrb=15, s_axil_wdata=0x12345678)
    sc.cycle("pending B during bridge operation")
    sc.reset()
    sc.read(0x44, expect=0)
    sc.offer(lease2)
    sc.launch()
    sc.levels["bridge_busy"] = 0
    sc.cycle("complete with pending release before reset", bridge_done=1)
    assert sc.model.release is not None
    sc.reset()
    sc.wait(4, "pending source release invalidated by coordinated reset")
    assert sc.model.release is None and sc.model.states == [FREE, FREE]
    sc.mark("common reset during queued command, active operation, pending B and source release")


def random_ownership(sc, seed, frames=180):
    rng = random.Random(seed)
    sc.reset()
    for frame in range(frames):
        # Retain banks at random; retire only through the host transaction.
        if sc.model.ready_queue and (FREE not in sc.model.states or rng.randrange(3) == 0):
            bank = sc.model.ready_queue[0]
            lease = sc.model.leases[bank]
            sc.write(0x30, bank, order=rng.choice((-1, 0, 1)), gap=rng.randrange(5))
            sc.descriptor(bank, lease)
            if rng.randrange(2):
                sc.ack(bank, lease.seq, lease.generation ^ 0x80000000, expect=SLVERR)
            sc.ack(bank, lease.seq, lease.generation)
        lease = Lease(0x00400000 + (frame % 2) * 0x00200000,
                      (seed * 65537 + frame * 97) & 0xffffffff,
                      0x20000000 + seed, rng.randrange(4), rng.randrange(2), rng.getrandbits(64))
        sc.offer(lease, stalls=rng.randrange(10))
        sc.launch()
        sc.finish(error=rng.randrange(7) == 0, delay=rng.randrange(2, 15), release_stall=rng.randrange(10))
        sc.read(4, rstall=rng.randrange(5))
        if rng.randrange(4) == 0:
            sc.read(0x5c)
    while sc.model.ready_queue:
        bank = sc.model.ready_queue[0]
        lease = sc.model.leases[bank]
        sc.write(0x30, bank)
        sc.ack(bank, lease.seq, lease.generation)
    assert sc.model.states == [FREE, FREE]
    assert sc.model.counters["accept"] == frames
    assert sc.model.counters["release"] == frames
    sc.mark(f"random ownership seed={seed} frames={frames}")


def command(args, cwd):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    (cwd / (Path(args[0]).stem + "_console.log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Command failed: {args}\n{result.stdout[-10000:]}\n{result.stderr[-2000:]}")


def run_case(name, sc, parameters=()):
    case = ROOT / "artifacts" / name
    case.mkdir(parents=True, exist_ok=True)
    in_bits, out_bits = sum(w for _, w in IN_LAYOUT), sum(w for _, w in OUT_LAYOUT)
    tb = (ROOT / "tb_fpga_v8_coop_control_axil.v").read_text(encoding="ascii")
    assert f"IN_BITS = {in_bits};" in tb, in_bits
    assert f"OUT_BITS = {out_bits};" in tb, out_bits
    vectors, trace = case / "vectors.hex", case / "trace.hex"
    vectors.write_text("".join(f"{pack(IN_LAYOUT, s):0{(in_bits+3)//4}x}\n" for s in sc.inputs), encoding="ascii")
    trace.unlink(missing_ok=True)
    if not (case / "work").exists():
        command([str(MODELSIM / "vlib.exe"), "work"], case)
    compile_args = [str(MODELSIM / "vlog.exe"), "-work", "work",
                    str(ROOT / "fpga_v8_coop_control_axil.v"),
                    str(ROOT / "tb_fpga_v8_coop_control_axil.v")]
    command(compile_args, case)
    do = case / "run.do"
    do.write_text("onerror {quit -code 1}\nonbreak {quit -code 0}\nrun -all\nquit -code 0\n", encoding="ascii")
    sim_args = [str(MODELSIM / "vsim.exe"), "-c", "-onfinish", "stop",
                "-l", str(case / "transcript.log"), "-do", str(do),
                "work.tb_fpga_v8_coop_control_axil", *parameters,
                f"+VECTORS={vectors.as_posix()}", f"+TRACE={trace.as_posix()}"]
    command(sim_args, case)
    transcript = (case / "transcript.log").read_text(encoding="utf-8", errors="replace")
    assert "CONTROL_TRACE_PASS" in transcript and "** Error" not in transcript and "** Fatal" not in transcript
    actual = trace.read_text(encoding="ascii").splitlines()
    assert len(actual) == len(sc.expected), (len(actual), len(sc.expected))
    for cycle, (line, expected) in enumerate(zip(actual, sc.expected)):
        if "x" in line.lower() or "z" in line.lower():
            raise AssertionError(f"Unknown output at {name} cycle={cycle}: {line}")
        observed = unpack(OUT_LAYOUT, int(line, 16))
        differences = {k: (expected[k], observed[k]) for k in expected if expected[k] != observed[k]}
        if differences:
            raise AssertionError(f"{name} cycle={cycle} label={sc.labels[cycle]}\n"
                                 f"expected/observed: {differences}\nstimulus: {sc.inputs[cycle]}")
    expected_path = case / "expected.hex"
    expected_path.write_text("".join(f"{pack(OUT_LAYOUT, out):0{(out_bits+3)//4}x}\n" for out in sc.expected), encoding="ascii")
    result = dict(name=name, cycles=len(actual), compared_output_bits=out_bits,
                  markers=sc.markers, final_counters=sc.model.counters,
                  compile_command=compile_args, simulation_command=sim_args,
                  vectors_sha256=hashlib.sha256(vectors.read_bytes()).hexdigest(),
                  trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest())
    print(f"PASS {name}: {len(actual)} cycles, {out_bits} outputs bits/cycle", flush=True)
    return result


def main():
    directed_case = Scenario()
    directed(directed_case)
    cases = [run_case("directed", directed_case)]
    for seed in (11, 29, 83):
        random_case = Scenario()
        random_ownership(random_case, seed)
        cases.append(run_case(f"random_{seed}", random_case))
    custom = Scenario((0x08400000, 0x08800000), 4096)
    directed(custom)
    cases.append(run_case("parameterized", custom,
                          ("-gOUTPUT_BANK0_ADDR=138412032", "-gOUTPUT_BANK1_ADDR=142606336", "-gOUTPUT_LENGTH=4096")))
    report = dict(status="PASS", modelsim_bin=str(MODELSIM), rtl_language="Verilog-2001",
                  total_cycles=sum(case["cycles"] for case in cases), randomized_frames=540,
                  cases=cases, rtl_sha256=hashlib.sha256((ROOT / "fpga_v8_coop_control_axil.v").read_bytes()).hexdigest())
    (ROOT / "artifacts" / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(f"PASS report: {ROOT / 'artifacts' / 'results.json'}")


if __name__ == "__main__":
    main()
