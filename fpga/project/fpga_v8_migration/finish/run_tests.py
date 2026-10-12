"""Generate focused finish traffic, run ModelSim, and audit accepted-word traces."""

import argparse
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

from golden import finish_word, preactivation


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "test_results"
LUT = ROOT.parent / "activation" / "fpga_v8_activation_lut.v"
PHASES = {
    1: "initial_reset", 2: "program_table_a", 3: "idle_config_priority",
    4: "arithmetic_extrema_a", 5: "all_addresses_table_a", 6: "all_addresses_bypass_a",
    7: "rounding_a", 8: "continuous_throughput", 9: "reject_product_only",
    10: "reject_sum_only", 11: "reject_byte_only", 12: "reject_output_only",
    13: "reject_full_pipeline", 14: "config_on_output_consumption",
    15: "stall_changing_constants", 16: "reset_product", 17: "reset_sum",
    18: "reset_byte", 19: "reset_output", 20: "reset_full_pipeline",
    21: "lut_persists_after_reset", 22: "random_a", 23: "program_table_b",
    24: "all_addresses_table_b", 25: "all_addresses_bypass_b",
    26: "arithmetic_extrema_b", 27: "rounding_b", 28: "random_b", 29: "final_drain",
}


def packed(values, width):
    return sum((value & ((1 << width) - 1)) << (i * width)
               for i, value in enumerate(values))


@dataclass
class Word:
    accum: list
    bias: list
    scale: int
    zp: int
    bypass: int = 0
    last: int = 0


@dataclass
class Row:
    rst: int
    cfg_valid: int
    cfg_addr: int
    cfg_data: int
    s_valid: int
    word: Word
    m_ready: int
    phase: int

    def text(self):
        w = self.word
        return (f"{self.rst} {self.cfg_valid} {self.cfg_addr:02x} {self.cfg_data:02x} "
                f"{self.s_valid} {packed(w.accum, 32):x} {w.last} {w.scale:04x} "
                f"{packed(w.bias, 32):x} {w.zp:02x} {w.bypass} {self.m_ready} {self.phase}\n")


class Traffic:
    """Four-slot occupancy used only to schedule a legal held input producer.

    Numerical correctness is checked separately against actual handshakes, without
    modeling arithmetic stages, latency, internal data registers or Verilog widths.
    """
    def __init__(self, lanes, seed):
        self.lanes = lanes
        self.rng = random.Random(seed)
        self.rows = []
        self.slots = [False] * 4

    def noise(self):
        return Word([self.rng.randrange(-(1 << 31), 1 << 31) for _ in range(self.lanes)],
                    [self.rng.randrange(-(1 << 31), 1 << 31) for _ in range(self.lanes)],
                    self.rng.randrange(65536), self.rng.randrange(256),
                    self.rng.randrange(2), self.rng.randrange(2))

    def cycle(self, phase, word=None, valid=0, ready=1, rst=0, cfg=None):
        self.rows.append(Row(rst, int(cfg is not None), *(cfg or (0, 0)), valid,
                             word or self.noise(), ready, phase))
        if rst:
            self.slots = [False] * 4
            return False
        rooms = [False] * 4
        rooms[3] = not self.slots[3] or bool(ready)
        for i in range(2, -1, -1):
            rooms[i] = not self.slots[i] or rooms[i + 1]
        accepted = bool(valid and cfg is None and rooms[0])
        old = self.slots[:]
        for i in range(3, 0, -1):
            if rooms[i]:
                self.slots[i] = old[i - 1]
        if rooms[0]:
            self.slots[0] = accepted
        return accepted

    def send(self, phase, word):
        for _ in range(16):
            if self.cycle(phase, word, valid=1):
                return
        raise AssertionError("producer did not drain")

    def drain(self, phase):
        for _ in range(16):
            if not any(self.slots):
                self.cycle(phase)
                return
            self.cycle(phase)
        raise AssertionError("pipeline did not drain")

    def probe(self, last=0, bypass=0):
        return Word([0] * self.lanes, [0] * self.lanes, 65535, 37, bypass, last)

    def program(self, phase, table):
        self.drain(phase)
        for address, value in enumerate(table):
            self.cycle(phase, cfg=(address, value))

    def addresses(self, phase, bypass):
        for base in range(0, 256, self.lanes):
            zp = (base * 17 + 91) % 256
            codes = [(base + i) % 256 for i in range(self.lanes)]
            word = Word([0] * self.lanes, [(code - zp) * 65536 for code in codes],
                        self.rng.randrange(65536), zp, bypass, (base // self.lanes) % 2)
            self.send(phase, word)
        self.drain(phase)

    def extrema(self, phase):
        combos = [(-2147483648, -2147483648), (2147483647, 2147483647),
                  (-2147483648, 2147483647), (2147483647, -2147483648),
                  (-1, -32768), (1, 32767), (0, -2147483648), (0, 2147483647)]
        for scale in (65535, 65534, 32768, 32767, 1, 0):
            for zp in (0, 255):
                for bypass in (0, 1):
                    for base in range(0, len(combos), self.lanes):
                        pairs = [combos[(base + i) % len(combos)] for i in range(self.lanes)]
                        self.send(phase, Word([p[0] for p in pairs], [p[1] for p in pairs],
                                              scale, zp, bypass, base % 2))
        # Product and large signed bias cancel to an interior, observable code.
        for sign in (-1, 1):
            self.send(phase, Word([sign * 32767] * self.lanes,
                                 [-sign * 32767 * 65535] * self.lanes,
                                 65535, 123, 0, 1))
        self.drain(phase)

    def rounding(self, phase):
        raw = [whole * 65536 + 32768 + offset
               for whole in range(-2, 258) for offset in (-1, 0, 1)]
        for base in range(0, len(raw), self.lanes):
            zp = self.rng.randrange(256)
            values = [raw[(base + i) % len(raw)] for i in range(self.lanes)]
            self.send(phase, Word([0] * self.lanes, [v - zp * 65536 for v in values],
                                 65535, zp, (base // self.lanes) % 2, base % 2))
        self.drain(phase)

    def rejection_probes(self, table):
        poison = table[37] ^ 255
        for advance, phase in enumerate((9, 10, 11, 12)):
            self.drain(phase)
            self.send(phase, self.probe(last=advance % 2))
            for _ in range(advance):
                self.cycle(phase, ready=0)
            self.cycle(phase, ready=0, cfg=(37, poison))
            self.drain(phase)
        self.drain(13)
        for i in range(4):
            self.cycle(13, self.probe(last=i % 2, bypass=i % 2), valid=1, ready=0)
        for _ in range(3):
            self.cycle(13, ready=0, cfg=(37, poison))
        # Holding config stops the source, yet all four existing words must drain.
        for _ in range(4):
            self.cycle(13, ready=1, cfg=(37, poison))
        self.drain(13)
        self.send(13, self.probe())
        self.drain(13)
        self.send(14, self.probe(last=1))
        for _ in range(3):
            self.cycle(14, ready=0)
        # This request must be rejected on the output's consumption edge.
        self.cycle(14, ready=1, cfg=(37, poison))
        # Idle programming has priority even when the source simultaneously offers.
        offered = self.probe(last=1)
        self.cycle(14, offered, valid=1, cfg=(37, table[37]))
        self.send(14, offered)
        self.drain(14)

    def constants_stall(self):
        self.drain(15)
        for i in range(4):
            w = Word([i * 11 + j for j in range(self.lanes)],
                     [(-i * 9 + j) * 65536 for j in range(self.lanes)],
                     32768 if i % 2 else 65535, 100 + i, i % 2, i % 2)
            self.cycle(15, w, valid=1, ready=0)
        offered = self.noise()
        for _ in range(24):
            changed = self.noise()
            changed.accum = offered.accum
            changed.last = offered.last
            self.cycle(15, changed, valid=1, ready=0)
        accepted = self.noise()
        accepted.accum, accepted.last = offered.accum, offered.last
        self.send(15, accepted)
        self.drain(15)

    def reset_pending(self):
        for advance, phase in enumerate((16, 17, 18, 19)):
            self.drain(phase)
            self.send(phase, self.probe(last=1))
            for _ in range(advance):
                self.cycle(phase, ready=0)
            self.cycle(phase, rst=1, ready=0, cfg=(37, 99))
            self.cycle(phase, rst=1)
            self.cycle(phase)
            self.send(21, self.probe(last=advance % 2))
            self.drain(21)
        self.drain(20)
        for i in range(4):
            self.cycle(20, self.probe(last=i % 2), valid=1, ready=0)
        self.cycle(20, rst=1, ready=0, cfg=(37, 99))
        self.cycle(20, rst=1)
        self.cycle(20)
        self.send(21, self.probe())
        self.drain(21)

    def random_word(self):
        acc = []
        bias = []
        for _ in range(self.lanes):
            if self.rng.random() < 0.15:
                acc.append(self.rng.choice([-2147483648, 2147483647]))
                bias.append(self.rng.randrange(-(1 << 31), 1 << 31))
            else:
                acc.append(self.rng.randrange(-350, 351))
                bias.append(self.rng.randrange(-60 * 65536, 60 * 65536))
        scale = self.rng.choice([0, 1, 32767, 32768, 65534, 65535, self.rng.randrange(65536)])
        return Word(acc, bias, scale, self.rng.randrange(256),
                    self.rng.randrange(2), int(self.rng.random() < 0.2))

    def random_stream(self, phase, count):
        pending = None
        burst = 0
        for _ in range(count):
            if pending is None and self.rng.random() < 0.83:
                pending = self.random_word()
            if burst:
                ready = 0
                burst -= 1
            elif self.rng.random() < 0.05:
                burst = self.rng.randrange(3, 18)
                ready = 0
            else:
                ready = int(self.rng.random() < 0.75)
            cfg = None
            if self.rng.random() < 0.15:
                cfg = (self.rng.randrange(256), self.rng.randrange(256))
            live = self.random_word()
            if pending is not None:
                live.accum, live.last = pending.accum, pending.last
            if self.cycle(phase, live, valid=int(pending is not None), ready=ready, cfg=cfg):
                pending = None
        if pending is not None:
            self.send(phase, pending)
        self.drain(phase)


def make_traffic(lanes, seed, random_cycles):
    d = Traffic(lanes, seed)
    table_a = [(73 * x + 19) % 256 for x in range(256)]
    table_b = [((x * x + 29 * x + 157) ^ (x >> 1)) % 256 for x in range(256)]
    for _ in range(3):
        d.cycle(1, rst=1)
    d.program(2, table_a)
    offered = d.probe(last=1)
    for _ in range(3):
        d.cycle(3, offered, valid=1, cfg=(37, table_a[37]))
    d.send(3, offered)
    d.drain(3)
    d.extrema(4)
    d.addresses(5, 0)
    d.addresses(6, 1)
    d.rounding(7)
    for i in range(96):
        d.send(8, Word([i + j for j in range(lanes)], [0] * lanes,
                       32768, 25, i % 2, int(i % 13 == 0)))
    d.drain(8)
    d.rejection_probes(table_a)
    d.constants_stall()
    d.reset_pending()
    d.random_stream(22, random_cycles)
    d.program(23, table_b)
    d.addresses(24, 0)
    d.addresses(25, 1)
    d.extrema(26)
    d.rounding(27)
    d.random_stream(28, random_cycles)
    d.drain(29)
    return d.rows


def check_trace(rows, path, lanes):
    lines = path.read_text(encoding="ascii").splitlines()
    if len(lines) != len(rows):
        raise AssertionError(f"trace length {len(lines)} != stimulus {len(rows)}")
    table = [None] * 256
    expected = deque()
    counts = Counter()
    phase_counts = {phase: Counter() for phase in PHASES}
    seen_codes = {phase: set() for phase in (5, 6, 24, 25)}
    rejection_masks = set()
    reset_masks = set()
    accepted_reset_drops = 0
    old_stall = None
    occupied_previous_reset = False
    accepted_cycles = []
    output_cycles = []
    raw_min = None
    raw_max = None
    for cycle, (row, line) in enumerate(zip(rows, lines)):
        fields = line.split()
        if len(fields) != 10:
            raise AssertionError(f"bad trace cycle {cycle}: {line}")
        number, sr, cr, mv, ml = map(int, fields[:5])
        data = int(fields[5], 16)
        pv, qv, bv, gated = map(int, fields[6:])
        assert number == cycle
        mask = pv | (qv << 1) | (bv << 2) | (mv << 3)
        if occupied_previous_reset:
            assert mask == 0, f"reset failed to empty registers at cycle {cycle}"
        occupied_previous_reset = bool(row.rst)
        assert cr == int(not row.rst and mask == 0), f"config readiness cycle {cycle}"
        assert gated == (row.cfg_valid and cr), f"config gate cycle {cycle}"
        if row.rst or row.cfg_valid:
            assert not sr, f"source priority cycle {cycle}"
        if old_stall is not None and not row.rst:
            assert mv and (data, ml) == old_stall, f"stalled output changed cycle {cycle}"
        old_stall = (data, ml) if not row.rst and mv and not row.m_ready else None
        counts["cycles"] += 1
        phase_counts[row.phase]["cycles"] += 1
        if row.phase == 15 and mask == 15 and not row.m_ready:
            counts["directed_full_pipeline_stall_cycles"] += 1
            previous = rows[cycle - 1].word
            counts["scale_changes_full_pipeline_stalled"] += int(row.word.scale != previous.scale)
            counts["bias_changes_full_pipeline_stalled"] += int(row.word.bias != previous.bias)
            counts["zp_changes_full_pipeline_stalled"] += int(row.word.zp != previous.zp)
            counts["bypass_changes_full_pipeline_stalled"] += int(row.word.bypass != previous.bypass)
        if row.rst:
            if mask:
                reset_masks.add(mask)
                counts["reset_occupied_edges"] += 1
            accepted_reset_drops += len(expected)
            expected.clear()
            continue
        if row.cfg_valid:
            if cr:
                assert not expected, f"programming with pending accepted words cycle {cycle}"
                table[row.cfg_addr] = row.cfg_data
                counts["config_writes"] += 1
                phase_counts[row.phase]["config_writes"] += 1
                if row.s_valid:
                    counts["idle_config_priority"] += 1
            else:
                counts["config_rejected_busy"] += 1
                rejection_masks.add(mask)
                if not mv and (pv or qv or bv):
                    counts["config_rejected_internal_lut_empty"] += 1
                if mv and row.m_ready:
                    counts["config_rejected_output_consumption"] += 1
        if mv:
            assert expected, f"unexpected output cycle {cycle}"
            want, want_last, input_cycle = expected[0]
            assert data == packed(want, 8), (
                f"data mismatch lanes={lanes} cycle={cycle} input={input_cycle}: "
                f"got {data:x}, want {packed(want, 8):x}")
            assert ml == want_last, f"last mismatch cycle {cycle} input={input_cycle}"
            if row.m_ready:
                expected.popleft()
                counts["outputs"] += 1
                counts["output_last"] += ml
                phase_counts[row.phase]["outputs"] += 1
                output_cycles.append((row.phase, cycle))
            else:
                counts["output_stall_cycles"] += 1
        if row.s_valid and sr:
            w = row.word
            codes = [preactivation(a, w.scale, b, w.zp) for a, b in zip(w.accum, w.bias)]
            if not w.bypass:
                assert all(table[code] is not None for code in codes), "unprogrammed LUT read"
            want = finish_word(w.accum, w.scale, w.bias, w.zp, table, bool(w.bypass))
            expected.append((want, w.last, cycle))
            counts["inputs"] += 1
            counts["bypass_inputs"] += w.bypass
            counts["lut_inputs"] += int(not w.bypass)
            counts["input_last"] += w.last
            phase_counts[row.phase]["inputs"] += 1
            accepted_cycles.append((row.phase, cycle))
            if row.phase in seen_codes:
                seen_codes[row.phase].update(codes)
            for a, b, code in zip(w.accum, w.bias, codes):
                counts["lane_checks"] += 1
                counts["clamp_low_lanes"] += int(code == 0)
                counts["clamp_high_lanes"] += int(code == 255)
                if a in (-2147483648, 2147483647) and w.scale == 65535:
                    counts["fullscale_extrema_lanes"] += 1
                raw = a * w.scale + b + w.zp * 65536
                raw_min = raw if raw_min is None else min(raw_min, raw)
                raw_max = raw if raw_max is None else max(raw_max, raw)
                counts["negative_folded_bias_lanes"] += int(b < 0)
                counts["half_tie_lanes"] += int(raw % 65536 == 32768)
        elif row.s_valid:
            counts["input_stall_cycles"] += 1
    assert not expected, f"{len(expected)} expected outputs undrained"
    assert counts["inputs"] == counts["outputs"] + accepted_reset_drops
    for phase, codes in seen_codes.items():
        assert codes == set(range(256)), f"phase {phase} failed exhaustive LUT code coverage"
    assert {1, 2, 4, 8, 15} <= rejection_masks, f"missing rejected occupancy {rejection_masks}"
    assert {1, 2, 4, 8, 15} <= reset_masks, f"missing reset occupancy {reset_masks}"
    for phase in (2, 23):
        assert phase_counts[phase]["config_writes"] == 256
    assert accepted_reset_drops == 8, f"reset drop count {accepted_reset_drops}"
    assert counts["config_rejected_internal_lut_empty"] >= 3
    assert counts["config_rejected_output_consumption"] >= 1
    assert counts["idle_config_priority"] >= 4
    assert counts["fullscale_extrema_lanes"] > 0
    assert counts["half_tie_lanes"] > 0
    assert counts["output_stall_cycles"] >= 24
    assert counts["directed_full_pipeline_stall_cycles"] == 24
    for name in ("scale", "bias", "zp", "bypass"):
        assert counts[f"{name}_changes_full_pipeline_stalled"] > 0
    assert raw_min == -140737488355328
    assert raw_max == 140737505001472
    # Measured timing from the RTL, independent of the producer occupancy model.
    ins = [cycle for phase, cycle in accepted_cycles if phase == 8]
    outs = [cycle for phase, cycle in output_cycles if phase == 8]
    assert len(ins) == len(outs) == 96
    assert all(b - a == 1 for a, b in zip(ins, ins[1:]))
    assert all(b - a == 1 for a, b in zip(outs, outs[1:]))
    assert all(output - source == 4 for source, output in zip(ins, outs))
    counts["reset_discarded_words"] = accepted_reset_drops
    return {"counts": dict(counts), "rejected_occupancy_masks": sorted(rejection_masks),
            "reset_occupancy_masks": sorted(reset_masks), "address_coverage": {
                PHASES[p]: len(codes) for p, codes in seen_codes.items()},
            "observed_raw_q16_min": raw_min, "observed_raw_q16_max": raw_max,
            "throughput_words": 96, "unstalled_latency_edges": 4,
            "phases": {PHASES[p]: dict(c) for p, c in phase_counts.items()}}


def command(args, logfile):
    result = subprocess.run([str(a) for a in args], cwd=RESULTS, capture_output=True,
                            text=True, errors="replace", timeout=90)
    output = result.stdout + result.stderr
    logfile.write_text(output, encoding="ascii", errors="backslashreplace")
    if result.returncode or "** Error" in output or "FAIL" in output:
        raise RuntimeError(f"command failed ({result.returncode}): {args}\n{output}")
    return output


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin", type=Path, default=Path("C:/modeltech64_10.6e/win64"))
    parser.add_argument("--random-cycles", type=int, default=1800)
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    # Remove stale success evidence before any command that can fail.
    for name in ("TEST_REPORT.md", "results.json"):
        (RESULTS / name).unlink(missing_ok=True)
    source_files = [ROOT / "fpga_v8_conv_finish.v", ROOT / "tb_fpga_v8_conv_finish.v",
                    ROOT / "golden.py", ROOT / "test_golden.py", ROOT / "run_tests.py"]
    for path in source_files:
        path.read_bytes().decode("ascii")
    lut_before = sha256(LUT)
    scalar = command([sys.executable, ROOT / "test_golden.py"], RESULTS / "python_tests.log")
    assert "Ran 7 tests" in scalar and "OK" in scalar
    if not (RESULTS / "work").exists():
        command([args.modelsim_bin / "vlib.exe", "work"], RESULTS / "vlib.log")
    compile_args = [args.modelsim_bin / "vlog.exe", "-work", "work", "-vlog01compat",
                    LUT, ROOT / "fpga_v8_conv_finish.v", ROOT / "tb_fpga_v8_conv_finish.v"]
    compilation = command(compile_args, RESULTS / "compile.log")
    assert "Errors: 0, Warnings: 0" in compilation
    results = []
    sim_commands = []
    for lanes in (1, 3, 16):
        for seed in (56401, 20261007):
            name = f"lanes{lanes}_seed{seed}"
            rows = make_traffic(lanes, seed, args.random_cycles)
            stimulus = RESULTS / f"{name}.stimulus.txt"
            trace = RESULTS / f"{name}.trace.txt"
            stimulus.write_text("".join(row.text() for row in rows), encoding="ascii")
            trace.unlink(missing_ok=True)
            sim_args = [args.modelsim_bin / "vsim.exe", "-c", "-lib", "work",
                        "tb_fpga_v8_conv_finish", f"-gLANES={lanes}",
                        f"+STIMULUS={stimulus.as_posix()}", f"+TRACE={trace.as_posix()}",
                        "-do", "run -all; quit -f"]
            transcript = command(sim_args, RESULTS / f"{name}.log")
            assert f"PASS_FINISH_TB lanes={lanes} cycles={len(rows)}" in transcript
            warnings = [line for line in transcript.splitlines() if "** Warning:" in line]
            assert all("(vsim-8891)" in line for line in warnings), warnings
            checked = check_trace(rows, trace, lanes)
            result = {"name": name, "lanes": lanes, "seed": seed,
                      "simulation_warnings": warnings,
                      "stimulus_sha256": sha256(stimulus), "trace_sha256": sha256(trace),
                      **checked}
            results.append(result)
            sim_commands.append([str(a) for a in sim_args])
            print(f"PASS {name}: cycles={len(rows)} inputs={checked['counts']['inputs']} "
                  f"outputs={checked['counts']['outputs']} lanes_checked={checked['counts']['lane_checks']}",
                  flush=True)
    assert sha256(LUT) == lut_before, "read-only activation LUT changed"
    totals = Counter()
    for result in results:
        totals.update(result["counts"])
    payload = {"status": "PASS", "utc": datetime.now(timezone.utc).isoformat(),
               "python": sys.version, "python_executable": sys.executable,
               "random_cycles_per_table": args.random_cycles,
               "sources_sha256": {p.name: sha256(p) for p in source_files},
               "activation_lut_sha256_before": lut_before,
               "activation_lut_sha256_after": sha256(LUT),
               "compile_command": [str(a) for a in compile_args],
               "simulation_commands": sim_commands, "totals": dict(totals), "runs": results}
    (RESULTS / "results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    report = ["# Isolated convolution finish test report", "", "Result: PASS", "",
              f"UTC: {payload['utc']}", f"Python: {sys.executable} ({sys.version.split()[0]})", "",
              "Scope: standalone candidate raw-accumulator arithmetic. No production RTL, PDS,",
              "board files or activation regression were changed or run.", "",
              "Scalar golden: 7 unittest cases passed, including 12,000 exact rational cross-checks,",
              "all half-boundary neighbors, unsigned full-scale multiplication and signed bias.", "",
              "ModelSim: 10.6e, Verilog-2001 compilation (-vlog01compat). Six simulation runs:", "",
              "| Lanes | Seed | Cycles | Accepted | Checked outputs | Lane golden checks | Busy config rejected |", 
              "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in results:
        c = r["counts"]
        report.append(f"| {r['lanes']} | {r['seed']} | {c['cycles']} | {c['inputs']} | "
                      f"{c['outputs']} | {c['lane_checks']} | {c['config_rejected_busy']} |")
    report += ["", f"Totals: {totals['inputs']} inputs, {totals['outputs']} checked outputs, "
               f"{totals['lane_checks']} lane golden checks, {totals['reset_discarded_words']} "
               "intentionally discarded accepted words on reset.", "",
               "Every run verifies both different programmed 256-byte tables at all 256 addresses,",
               "and all 256 bypass codes. Tests reject configuration with product-only, sum-only,",
               "byte-only, output-only and all-four-stage occupancy (masks 1,2,4,8,15), including",
               "internal data with an empty LUT and the output consumption edge. They also verify",
               "idle config priority, draining under a held config request, changing all constants",
               "and bypass during long stalls, last alignment, signed32 extrema at scale65535,",
               "reset at every occupied stage, and LUT retention after reset.", "",
               "Each run measures 96 consecutive words at one word per clock, with four accepting",
               "edges of input-to-output latency. Output data and last are checked on every valid",
               "cycle, including stalls; only actual accepted inputs enter the scalar scoreboard.", "",
               f"Observed total stalled output cycles: {totals['output_stall_cycles']}.",
               f"Observed config rejection with internal data and empty LUT: "
               f"{totals['config_rejected_internal_lut_empty']}.",
               f"Observed full-scale extreme lane cases: {totals['fullscale_extrema_lanes']}.",
               f"Observed exact half-tie lane cases: {totals['half_tie_lanes']}.", "",
               f"Directed stalls with all four registers occupied: "
               f"{totals['directed_full_pipeline_stall_cycles']} cycles. Live input changes during",
               f"those stalls: scale={totals['scale_changes_full_pipeline_stalled']}, "
               f"bias={totals['bias_changes_full_pipeline_stalled']}, "
               f"zero point={totals['zp_changes_full_pipeline_stalled']}, "
               f"bypass={totals['bypass_changes_full_pipeline_stalled']}.", "",
               "Each run observes the exact complete supported raw Q16 bounds:",
               "-140737488355328 through 140737505001472. The maximum with rounding added is",
               "140737505034240, within signed51.", "",
               "Compilation reports Errors: 0, Warnings: 0. Simulation reports no errors; the",
               "local ModelSim settings emit vsim-8891 because optimization is disabled (-novopt).",
               "This environment warning is retained verbatim per run in results.json and logs;",
               "no other simulation warning is accepted by the runner.", "",
               "Activation source SHA256 before and after (identical):", "", f"`{lut_before}`", "",
               "Exact commands, source/stimulus/trace hashes, per-phase counts and coverage:",
               "[results.json](results.json). Compiler: [compile.log](compile.log).",
               "Scalar tests: [python_tests.log](python_tests.log). Each run has its matching",
               "`.stimulus.txt`, `.trace.txt` and `.log` retained here.", "",
               "Reproduce from finish: `python run_tests.py`.", "",
               "This demonstrates isolated simulation behavior. Synthesis, timing closure and",
               "board integration remain outside this candidate's scope.", ""]
    (RESULTS / "TEST_REPORT.md").write_text("\n".join(report), encoding="ascii")
    print(f"PASS_ALL: runs={len(results)} lane_checks={totals['lane_checks']}")


if __name__ == "__main__":
    main()
