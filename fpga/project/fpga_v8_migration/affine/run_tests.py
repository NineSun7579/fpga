"""Run the integer oracle and isolated Verilog-2001 ModelSim regression.

All generated vectors, libraries, logs and reports stay under this directory.
No PDS, synthesis, production files or board access is used.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys

from golden import MAX_SCALE, Q16, affine_word, pack, rounded_value

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
SEED = 0xA8816


class Scenario:
    def __init__(self, lanes):
        self.lanes = lanes
        self.pending = None
        self.lines = []
        self.tags = {}
        self.counts = dict(cycles=0, accepted=0, consumed=0, reset_pending=0,
                           stalled=0, last=0, simultaneous=0,
                           negative_operand_lanes=0, lower_saturated_lanes=0,
                           upper_saturated_lanes=0, half_tie_lanes=0,
                           unsaturated_lanes=0, high_bit_scale_words=0,
                           constants_changed_while_stalled=0)
        self.previous_constants = None

    def cycle(self, rst=1, valid=0, last=0, ready=1, a=0, b=0,
              sa=Q16, sb=Q16, za=128, zb=128, zo=128, tag=None):
        if tag:
            self.tags[tag] = self.tags.get(tag, 0) + 1
        constants = sa, sb, za, zb, zo
        input_ready = int(bool(rst and (self.pending is None or ready)))
        before = self.pending
        if not rst:
            if before is not None:
                self.counts["reset_pending"] += 1
            self.pending = None
        else:
            if before is not None and not ready:
                self.counts["stalled"] += 1
                if constants != self.previous_constants:
                    self.counts["constants_changed_while_stalled"] += 1
            if before is not None and ready:
                self.counts["consumed"] += 1
                self.counts["last"] += before[1]
                self.pending = None
            if valid and input_ready:
                self.counts["accepted"] += 1
                self.counts["simultaneous"] += int(before is not None and ready)
                self.counts["high_bit_scale_words"] += int(
                    bool((sa | sb) & (1 << 31)))
                self.pending = (affine_word(a, b, sa, sb, za, zb, zo, self.lanes),
                                last)
                for lane in range(self.lanes):
                    qa, qb = (a >> (8 * lane)) & 255, (b >> (8 * lane)) & 255
                    rounded = rounded_value(qa, qb, sa, sb, za, zb, zo)
                    numerator = (qa - za) * sa + (qb - zb) * sb + zo * Q16
                    self.counts["negative_operand_lanes"] += int(qa < za or qb < zb)
                    self.counts["lower_saturated_lanes"] += int(rounded < 0)
                    self.counts["upper_saturated_lanes"] += int(rounded > 255)
                    self.counts["half_tie_lanes"] += int(numerator % Q16 == Q16 // 2)
                    self.counts["unsaturated_lanes"] += int(0 <= rounded <= 255)
        self.previous_constants = constants
        out_valid = int(self.pending is not None)
        out_data, out_last = self.pending if out_valid else (0, 0)
        width = self.lanes * 2
        self.lines.append(
            f"{rst:b} {valid:b} {last:b} {ready:b} {a:0{width}x} {b:0{width}x} "
            f"{sa:08x} {sb:08x} {za:02x} {zb:02x} {zo:02x} "
            f"{input_ready:b} {out_valid:b} {out_data:0{width}x} {out_last:b}\n")
        self.counts["cycles"] += 1

    def repeated(self, value):
        return pack([value] * self.lanes)

    def send(self, a, b, sa=Q16, sb=Q16, za=128, zb=128, zo=128,
             last=0, tag=None):
        self.cycle(valid=1, a=a, b=b, sa=sa, sb=sb, za=za, zb=zb,
                   zo=zo, last=last, tag=tag)

    def write(self, path):
        self.cycle()
        if self.pending is not None:
            raise AssertionError("scenario did not drain")
        if self.counts["accepted"] != (self.counts["consumed"]
                                        + self.counts["reset_pending"]):
            raise AssertionError("lost or duplicated model transaction")
        for key in ("negative_operand_lanes", "lower_saturated_lanes",
                    "upper_saturated_lanes", "half_tie_lanes", "unsaturated_lanes",
                    "high_bit_scale_words", "constants_changed_while_stalled"):
            if not self.counts[key]:
                raise AssertionError(f"missing coverage: {key}")
        path.write_text("".join(self.lines), encoding="ascii")
        return dict(lanes=self.lanes, seed=SEED, coverage=self.counts, tags=self.tags)


def make_scenario(lanes, path):
    s = Scenario(lanes)
    r = s.repeated
    rng = random.Random(SEED + lanes)
    s.cycle(rst=0, valid=1, last=1, ready=1, tag="reset_blocks_acceptance")
    s.cycle(rst=0, ready=0)

    # Directed arithmetic vectors, including negative SiLU-like codes.
    for qa, qb, sa, sb, za, zb, zo, tag in (
        (127, 64, Q16, Q16, 128, 64, 100, "negative_not_clamped"),
        (80, 160, Q16, Q16, 128, 128, 128, "negative_cancellation"),
        (80, 70, 32768, 98304, 100, 40, 80, "different_domains"),
        (255, 255, MAX_SCALE, MAX_SCALE, 0, 0, 0, "maximum_positive"),
        (0, 0, MAX_SCALE, MAX_SCALE, 255, 255, 255, "maximum_negative"),
        (255, 0, MAX_SCALE, MAX_SCALE, 0, 255, 117, "large_cancellation"),
        (0, 255, MAX_SCALE, MAX_SCALE, 255, 0, 117, "reverse_cancellation"),
        (255, 0, MAX_SCALE, MAX_SCALE - Q16, 0, 255, 0, "large_small_remainder"),
        (255, 0, MAX_SCALE, MAX_SCALE - 1, 0, 255, 117, "tiny_remainder"),
        (0, 255, MAX_SCALE, MAX_SCALE - 1, 255, 0, 117, "negative_tiny_remainder"),
        (0, 255, 0, 0, 128, 128, 37, "both_weights_zero"),
        (255, 0, 0x80000000, 0x80000000, 0, 255, 109, "scale_unsigned_msb"),
    ):
        s.send(r(qa), r(qb), sa, sb, za, zb, zo, last=1, tag=tag)

    # Exercise exactly adjacent Q16 numerators on each side of +/- half ties.
    for zo in (0, 1, 128, 254, 255):
        for delta in (-3, -2, -1, 0, 1, 2, 3):
            for sa in (32767, 32768, 32769):
                s.send(r(128 + delta), r(0), sa, 0, 128, 0, zo,
                       tag="half_ties_and_neighbors")

    # Sweep all uint8 codes with signed offsets on both sides of the zero point.
    for sa, sb, za, zb, zo in ((Q16, Q16, 128, 128, 128),
                              (32768, 98304, 203, 19, 84),
                              (Q16, 0, 128, 71, 128),
                              (MAX_SCALE, MAX_SCALE, 0, 255, 117)):
        for first in range(0, 256, lanes):
            av = [(first + i) % 256 for i in range(lanes)]
            bv = [255 - v for v in av]
            s.send(pack(av), pack(bv), sa, sb, za, zb, zo,
                   last=int(first + lanes >= 256), tag="uint8_sweep")

    # Requantization: a zero-centered B works even with a nonzero B scale.
    for i in range(32):
        a = rng.getrandbits(8 * lanes)
        s.send(a, r(71), 41237, MAX_SCALE, 129, 71, 91,
               last=i % 7 == 0, tag="requant_zero_centered_b")
        s.send(a, rng.getrandbits(8 * lanes), 41237, 0, 129, 71, 91,
               tag="requant_zero_weight_b")

    # A held output must survive many changing constants and input words.
    s.send(r(127), r(64), Q16, Q16, 128, 64, 100, last=1,
           tag="snapshot_accept")
    for i in range(24):
        s.cycle(valid=1, ready=0, a=r(255), b=r(0), sa=rng.getrandbits(32),
                sb=rng.getrandbits(32), za=i, zb=255-i, zo=i * 7 % 256,
                last=0, tag="constants_change_stalled")
    s.send(r(255), r(0), 32768, 0, 0, 0, 3, last=0,
           tag="next_word_new_constants")
    for _ in range(3):
        s.cycle(ready=0, sa=MAX_SCALE, sb=MAX_SCALE, zo=255)
    s.cycle()

    # Reset an occupied output, including last, then prove fresh operation.
    for i in range(2):
        s.send(r(127), r(128), Q16, Q16, 128, 128, 128, last=1)
        s.cycle(ready=0)
        s.cycle(rst=0, valid=1, ready=i, last=1, tag="reset_pending")
        s.send(r(130), r(128), Q16, Q16, 128, 128, 128, last=0)
        s.cycle()

    # Random source/sink stalls, resets, words, domain constants and last.
    # Keep offered A/B/last stable through stalls. Constants are intentionally
    # live and may change; the DUT must use them only at acceptance.
    held = None
    for index in range(5000):
        rst = int(index % 349 != 0)
        ready = int(rng.random() < 0.57)
        if not rst:
            held = None
        if held is None and rng.random() < 0.78:
            held = (rng.getrandbits(8 * lanes), rng.getrandbits(8 * lanes),
                    int(rng.random() < 0.13))
        a, b, last = held if held is not None else (0, 0, 0)
        valid = int(held is not None)
        mode = index % 4
        if mode == 0:
            sa, sb = rng.getrandbits(32), rng.getrandbits(32)
        elif mode == 1:
            sa, sb = rng.randrange(4 * Q16), rng.randrange(4 * Q16)
        elif mode == 2:
            sa, sb = rng.choice([0, 1, 32767, 32768, 32769, Q16, MAX_SCALE]), 0
        else:
            sa = rng.choice([MAX_SCALE, 0x80000000])
            sb = sa - rng.randrange(65536)
        za, zb, zo = [rng.randrange(256) for _ in range(3)]
        can_accept = rst and (s.pending is None or ready)
        s.cycle(rst=rst, valid=valid, ready=ready, a=a, b=b, last=last,
                sa=sa, sb=sb, za=za, zb=zb, zo=zo, tag="random_cycles")
        if valid and can_accept:
            held = None
    if held is not None:
        s.send(held[0], held[1], last=held[2], tag="random_final_word")
    return s.write(path)


def command(args, cwd, log):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors="replace", timeout=120)
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {args[0]}\n"
                           f"{result.stdout[-6000:]}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin", default=os.environ.get(
        "MODELSIM_BIN", "C:/modeltech64_10.6e/win64"))
    options = parser.parse_args()
    ARTIFACTS.mkdir(exist_ok=True)
    unit_output = command([sys.executable, "-m", "unittest", "-v", "test_golden"],
                          ROOT, ARTIFACTS / "python_tests.log")
    print(unit_output.rstrip())
    sim_bin = Path(options.modelsim_bin)
    for tool in ("vlib", "vlog", "vsim"):
        if not (sim_bin / (tool + ".exe")).is_file():
            raise FileNotFoundError(f"missing ModelSim {tool} at {sim_bin}")
    scenarios = []
    for lanes in (16, 1, 4):
        case_dir = ARTIFACTS / f"lanes_{lanes}"
        case_dir.mkdir(exist_ok=True)
        vectors = case_dir / "vectors.txt"
        record = make_scenario(lanes, vectors)
        if not (case_dir / "work").exists():
            command([sim_bin / "vlib.exe", "work"], case_dir, case_dir / "vlib.log")
        compile_output = command(
            [sim_bin / "vlog.exe", "-work", "work", "-vlog01compat",
             "-pedanticerrors", "-lint",
             ROOT / "fpga_v8_affine_add.v", ROOT / "tb_fpga_v8_affine_add.v"],
            case_dir, case_dir / "compile.log")
        if "** Error" in compile_output:
            raise RuntimeError(compile_output)
        sim_output = command(
            [sim_bin / "vsim.exe", "-c", "-onfinish", "stop",
             "-gLANES=" + str(lanes), "work.tb_fpga_v8_affine_add",
             "+INPUT=vectors.txt", "-do", "onerror {quit -code 1}; run -all; quit -code 0"],
            case_dir, case_dir / "simulation.log")
        passes = [line for line in sim_output.splitlines() if "PASS lanes=" in line]
        if "FAIL" in sim_output or "** Error" in sim_output or len(passes) != 1:
            raise RuntimeError(f"simulation did not pass:\n{sim_output[-6000:]}")
        expected = record["coverage"]
        fields = dict(item.split("=", 1) for item in passes[0].split() if "=" in item)
        for key in ("cycles", "accepted", "consumed", "reset_pending",
                    "stalled", "last", "simultaneous"):
            if int(fields[key]) != expected[key]:
                raise AssertionError(f"TB/Python accounting mismatch for {key}")
        record["simulation_pass"] = passes[0].lstrip("# ")
        scenarios.append(record)
        print(record["simulation_pass"])
    for path in (ROOT / "fpga_v8_affine_add.v", ROOT / "tb_fpga_v8_affine_add.v"):
        path.read_bytes().decode("ascii")
    report = dict(status="PASS", python_tests=7, seed=SEED, scenarios=scenarios,
                  modelsim_bin=str(sim_bin),
                  source_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                 for name in ("fpga_v8_affine_add.v", "golden.py",
                                              "tb_fpga_v8_affine_add.v", "run_tests.py")},
                  scope="Isolated simulation only; not integrated, synthesized or board tested.")
    (ARTIFACTS / "results.json").write_text(json.dumps(report, indent=2) + "\n",
                                          encoding="ascii")
    print("PASS: results in affine/artifacts/results.json")


if __name__ == "__main__":
    main()
