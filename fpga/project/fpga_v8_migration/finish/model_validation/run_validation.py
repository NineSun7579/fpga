"""Verify actual exported model constants on read-only finish RTL, LANES=2."""

import argparse
import ast
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import subprocess
import sys

import numpy as np

from golden import lane, pack


HERE = Path(__file__).resolve().parent
MIGRATION = HERE.parent.parent
OUT = HERE / "test_results"
NUMERIC = MIGRATION / "numeric_layer/numeric.json"
TASKS = MIGRATION / "audit/tasks.json"
FRAME = MIGRATION / "integer_layer/frame_01/report.json"
MODEL = MIGRATION / "audit/specialized.onnx"
CALIBRATION = MIGRATION / "quantization_smoke/quantization.json"
RTL = HERE.parent / "fpga_v8_conv_finish.v"
LUT = MIGRATION / "activation/fpga_v8_activation_lut.v"
CONFIG = MIGRATION.parent / "source/npu/npu_top/config.v"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="ascii")


def integer_reference_functions():
    """Extract the current expression and saturation function without running a graph."""
    path = MIGRATION / "integer_reference.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    saturation = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == "saturate_q16")
    module = ast.Module(body=[saturation], type_ignores=[])
    environment = {"np": np}
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), environment)
    expressions = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "raw_q16" for t in node.targets)]
    assert len(expressions) == 1, "reference raw_q16 expression ambiguous"
    expression = compile(ast.Expression(body=expressions[0]), str(path), "eval")

    def check(vector, table):
        accum = np.array(vector["accum"], dtype=np.int64).reshape(1, 2, 1, 1)
        asset = {"multiplier_q16": np.full(2, vector["scale"], dtype=np.int64),
                 "folded_bias_q16": np.array(vector["bias"], dtype=np.int64)}
        operation = {"preactivation_quantization": {"zero_point": vector["zp"]}}
        raw = eval(expression, {"accum": accum, "asset": asset, "operation": operation})
        codes = environment["saturate_q16"](raw).reshape(2).tolist()
        outputs = codes if vector["bypass"] else [table[c] for c in codes]
        assert codes == vector["codes"] and outputs == vector["outputs"], vector
    return check


def load_assets():
    numeric = json.loads(NUMERIC.read_text())
    tasks = json.loads(TASKS.read_text())
    frame = json.loads(FRAME.read_text())
    calibration = json.loads(CALIBRATION.read_text())
    assert digest(MODEL) == numeric["model_sha256"] == tasks["source_sha256"]
    assert digest(TASKS) == numeric["tasks_sha256"]
    assert digest(CALIBRATION) == numeric["calibration_sha256"]
    assert calibration["model_sha256"] == numeric["model_sha256"]
    assert digest(NUMERIC) == frame["numeric_sha256"]
    release = json.loads((MIGRATION / "artifacts/manifest.json").read_text())
    release_model = next(a for a in release if a["name"].endswith('.onnx'))
    assert digest(MIGRATION / "artifacts" / release_model["name"]) == release_model["sha256"]
    assert numeric["weight_domain"] == frame["weight_domain"] == "per-layer"
    # Read bytes because production RTL comments use GBK. No production mutation.
    assert re.search(rb'`define\s+CONV_CHA_PAR_OUT\s+2\b', CONFIG.read_bytes())
    task_map = {t["id"]: t for t in tasks["tasks"]}
    traces = {t["task_id"]: t for t in frame["trace"] if t["op"] == "Conv"}
    ops = [op for op in numeric["operations"] if op["op"] == "Conv"]
    assert len(ops) == len(traces) == 55
    assert Counter(o["activation"] for o in ops) == {"silu": 49, "clip": 6}
    layers = []
    for op in ops:
        task = task_map[op["task_id"]]
        path = MIGRATION / "numeric_layer" / op["asset"]
        assert digest(path) == op["asset_sha256"], path
        with np.load(path, allow_pickle=False) as archive:
            weight = archive["weight"].copy()
            scale = archive["multiplier_q16"].copy()
            bias = archive["folded_bias_q16"].copy()
            unfolded = archive["bias_q16"].copy()
            table = archive["activation_lut"].copy()
        co = weight.shape[0]
        assert weight.dtype == np.int8 and list(weight.shape) == task["weight_shape"]
        assert task["output_shape"][1] == co
        assert scale.shape == bias.shape == unfolded.shape == (co,)
        assert scale.dtype.kind == bias.dtype.kind == unfolded.dtype.kind == "i"
        assert 0 < int(scale[0]) <= 65535 and np.all(scale == scale[0])
        assert scale.tolist() == op["multiplier_q16"]
        assert np.all(bias >= -(1 << 31)) and np.all(bias < (1 << 31))
        assert table.dtype == np.uint8 and table.shape == (256,)
        assert task["activation"] == op["activation"]
        input_zp = int(numeric["quantization"][task["inputs"][0]]["zero_point"])
        pre_zp = int(op["preactivation_quantization"]["zero_point"])
        output_zp = int(numeric["quantization"][task["output"]]["zero_point"])
        weight64 = weight.astype(np.int64)
        weight_sum = weight64.sum(axis=(1, 2, 3))
        bounds = 255 * np.abs(weight64).sum(axis=(1, 2, 3))
        achievable_min = 255 * np.minimum(weight64, 0).sum(axis=(1, 2, 3))
        achievable_max = 255 * np.maximum(weight64, 0).sum(axis=(1, 2, 3))
        assert np.all(bounds < (1 << 31)), "model raw accumulator int32 overflow"
        assert int(bounds.max()) == op["raw_accumulator_abs_bound_max"]
        postscale = bounds * scale + np.abs(bias) + pre_zp * 65536
        assert int(postscale.max()) == op["postscale_q16_abs_bound_max"]
        assert np.array_equal(bias, unfolded - input_zp * weight_sum * scale)
        assert np.array_equal(input_zp * weight_sum * scale + bias, unfolded)
        trace = traces[op["task_id"]]
        assert trace["name"] == task["name"]
        assert -int(bounds.max()) <= trace["raw_accumulator_min"] <= trace["raw_accumulator_max"] <= int(bounds.max())
        layer = {"task_id": op["task_id"], "name": task["name"],
                 "activation": op["activation"], "asset": op["asset"],
                 "asset_sha256": digest(path), "table_sha256": hashlib.sha256(table.tobytes()).hexdigest(),
                 "co": co, "padded_co": ((co + 15) // 16) * 16,
                 "scale": int(scale[0]), "bias": bias.tolist(), "bias_q16": unfolded.tolist(),
                 "weight_sum": weight_sum.tolist(), "raw_abs_bounds": bounds.tolist(),
                 "achievable_min": achievable_min.tolist(), "achievable_max": achievable_max.tolist(),
                 "input_zp": input_zp, "pre_zp": pre_zp, "output_zp": output_zp,
                 "trace_min": trace["raw_accumulator_min"], "trace_max": trace["raw_accumulator_max"],
                 "table": table.tolist(), "raw_bound_max": int(bounds.max()),
                 "folded_bias_signed32": True, "shared_scale_unsigned16": True,
                 "raw_bounds_strictly_below_int32_limit": True,
                 "input_zp_cancellation_verified_channels": co,
                 "bias_le_i32_sha256": hashlib.sha256(bias.astype('<i4').tobytes()).hexdigest(),
                 "scale_le_u16_sha256": hashlib.sha256(int(scale[0]).to_bytes(2, 'little')).hexdigest(),
                 "output_shape": task["output_shape"]}
        layers.append(layer)
    provenance_files = [NUMERIC, TASKS, FRAME, MODEL, CALIBRATION,
                        MIGRATION / "artifacts/manifest.json",
                        MIGRATION / "artifacts/wb_v8_w25_nop2c2f_raw_dfl6_clip10.onnx",
                        MIGRATION / "integer_reference.py", MIGRATION / "feature_layout.py",
                        MIGRATION / "export_numeric.py", CONFIG, RTL, LUT]
    provenance_files += [MIGRATION / "numeric_layer" / l["asset"] for l in layers]
    provenance_files += [p for p in HERE.parent.iterdir() if p.is_file() and p not in provenance_files]
    provenance = {str(p.resolve()): digest(p) for p in provenance_files}
    return layers, numeric, provenance


def residue_search(scale, bias, zp, bound):
    """Solve the reachable Q16 residues nearest the half point for fixed constants."""
    gcd = math.gcd(scale, 65536)
    residue_class = bias % gcd
    below = 32767 - ((32767 - residue_class) % gcd)
    above = 32769 + ((residue_class - 32769) % gcd)
    nearest = 32768 if 32768 % gcd == residue_class else min((below, above), key=lambda r: abs(r - 32768))
    period = 65536 // gcd
    inverse = pow(scale // gcd, -1, period)
    target_accum = (128 * 65536 + 32768 - bias - zp * 65536) // scale
    found = {}
    for name, residue in (("below", below), ("nearest", nearest), ("above", above)):
        a0 = (((residue - bias) // gcd) * inverse) % period
        k = (target_accum - a0 + period // 2) // period
        low = -((bound + a0) // period)
        high = (bound - a0) // period
        if low <= high:
            k = max(low, min(high, k))
        accumulator = a0 + k * period
        assert -(1 << 31) <= accumulator < (1 << 31)
        raw = accumulator * scale + bias + zp * 65536
        assert raw % 65536 == residue
        found[name] = {"accumulator": accumulator, "residue": residue,
                       "distance_from_half": abs(residue - 32768),
                       "within_model_abs_bound": abs(accumulator) <= bound,
                       "unclamped_round": (raw + 32768) // 65536}
    return {"gcd": gcd, "exact_half_reachable": nearest == 32768, **found}


def layer_vectors(layer, rng, random_words):
    co, padded = layer["co"], layer["padded_co"]
    scale, zp = layer["scale"], layer["pre_zp"]
    search = [residue_search(scale, b, zp, bound)
              for b, bound in zip(layer["bias"], layer["raw_abs_bounds"])]
    layer["half_search_by_channel"] = search
    layer["exact_half_reachable_channels"] = sum(s['exact_half_reachable'] for s in search)
    layer["interior_exact_half_channels"] = sum(s['exact_half_reachable'] and
                0 <= s['nearest']['unclamped_round'] <= 255 for s in search)
    assert all(s[side]['within_model_abs_bound'] for s in search for side in ('below', 'nearest', 'above'))
    fixture = [
        ("model_bound_negative", [-x for x in layer["raw_abs_bounds"]]),
        ("model_bound_positive", layer["raw_abs_bounds"]),
        ("achievable_weight_min", layer["achievable_min"]),
        ("achievable_weight_max", layer["achievable_max"]),
        ("trace_min", [layer["trace_min"]] * co),
        ("trace_max", [layer["trace_max"]] * co),
        ("all_code_zero_interior", [0] * co),
        ("all_input_zp_interior_and_padding", [layer["input_zp"] * s for s in layer["weight_sum"]]),
        ("signed32_min", [-(1 << 31)] * co),
        ("signed32_max", [(1 << 31) - 1] * co),
    ]
    for key in ("below", "nearest", "above"):
        fixture.append(("half_residue_" + key, [s[key]["accumulator"] for s in search]))
    for n, name in ((0, "zero_one_round_transition"), (254, "254_255_round_transition")):
        threshold = n * 65536 + 32768
        values = [(threshold - b - zp * 65536) // scale for b in layer["bias"]]
        fixture.append((name + "_below", values))
        fixture.append((name + "_above", [x + 1 for x in values]))
    layer["layout_fixture_names"] = [name for name, _ in fixture]
    layer["layout_fixture_count"] = len(fixture)
    vectors = []

    def word(base, accum, kind, fixture_index=None, bypass=0, last=0):
        channels = [base, base + 1]
        real_mask = sum(1 << i for i, c in enumerate(channels) if c < co)
        bias = [layer["bias"][c] if c < co else 0 for c in channels]
        accum = [int(a) if c < co else 0 for c, a in zip(channels, accum)]
        codes, outputs = zip(*(lane(a, scale, b, zp, layer["table"], bypass)
                               for a, b in zip(accum, bias)))
        vectors.append({"task_id": layer["task_id"], "pair_base": base, "channels": channels,
                        "valid_lane_mask": real_mask, "kind": kind,
                        "fixture_index": fixture_index, "accum": accum, "bias": bias,
                        "scale": scale, "zp": zp, "bypass": bypass, "last": last,
                        "codes": list(codes), "outputs": list(outputs)})

    # C16 order: channel group, fixture pixel, pair within the group.
    for group in range(padded // 16):
        for index, (name, values) in enumerate(fixture):
            for pair in range(8):
                base = group * 16 + pair * 2
                accum = [values[c] if c < co else 0 for c in (base, base + 1)]
                word(base, accum, name, index, last=int(pair == 7))
    # Model tables can merge adjacent codes. Bypass exposes searched rounding codes.
    for name, values in fixture:
        if name.startswith('half_residue_') or 'round_transition' in name:
            for base in range(0, padded, 2):
                accum = [values[c] if c < co else 0 for c in (base, base + 1)]
                word(base, accum, 'bypass_' + name, bypass=1, last=int((base % 16) == 14))
    # Sweep every preactivation code using real constants, not synthetic biases.
    base = 0
    for code in range(256):
        accum = []
        for c in (0, 1):
            a = (code * 65536 - layer["bias"][c] - zp * 65536 + scale // 2) // scale
            assert lane(a, scale, layer["bias"][c], zp, layer["table"])[0] == code
            accum.append(a)
        word(base, accum, "all_256_table_codes", last=int(code == 255))
    for i in range(random_words):
        base = rng.randrange((co + 1) // 2) * 2
        accum = [rng.randint(layer["trace_min"], layer["trace_max"]) for _ in range(2)]
        word(base, accum, "trace_range_random", last=int(i % 19 == 18))
    for base in range(0, padded, 2):
        accum = [layer["input_zp"] * layer["weight_sum"][c] if c < co else 0
                 for c in (base, base + 1)]
        word(base, accum, "bypass_model_constants", bypass=1, last=int(base + 2 == padded))
    for i in range(5):
        base = (i % ((co + 1) // 2)) * 2
        accum = [layer["input_zp"] * layer["weight_sum"][c] if c < co else 0
                 for c in (base, base + 1)]
        word(base, accum, "directed_stall", bypass=i % 2, last=i % 2)
    return vectors


class Producer:
    """Occupancy only schedules legal input holds; scoreboard uses actual handshakes."""
    def __init__(self, rng):
        self.rng = rng
        self.slots = [False] * 4
        self.rows = []
        self.burst = 0

    def ready(self):
        if self.burst:
            self.burst -= 1
            return 0
        if self.rng.random() < 0.04:
            self.burst = self.rng.randrange(5, 17)
            return 0
        return int(self.rng.random() < 0.78)

    def cycle(self, task, vector=None, cfg=None, rst=0, ready=None, poison=False):
        ready = self.ready() if ready is None else ready
        row = {"task_id": task, "vector_id": -1 if vector is None else vector["id"],
               "rst": rst, "cfg_valid": int(cfg is not None),
               "cfg_addr": 0 if cfg is None else cfg[0], "cfg_data": 0 if cfg is None else cfg[1],
               "valid": int(vector is not None), "m_ready": ready,
               "accum": [0, 0] if vector is None else vector["accum"],
               "last": 0 if vector is None else vector["last"]}
        if vector is None or poison:
            row.update(scale=self.rng.randrange(65536), zp=self.rng.randrange(256),
                       bias=[self.rng.randrange(-(1 << 31), 1 << 31) for _ in range(2)],
                       bypass=self.rng.randrange(2))
        else:
            row.update({key: vector[key] for key in ("scale", "zp", "bias", "bypass")})
        self.rows.append(row)
        if rst:
            self.slots = [False] * 4
            return False
        old = self.slots[:]
        room = [False] * 4
        room[3] = not old[3] or ready
        for i in range(2, -1, -1):
            room[i] = not old[i] or room[i + 1]
        accepted = bool(vector is not None and cfg is None and room[0])
        for i in range(3, 0, -1):
            if room[i]:
                self.slots[i] = old[i - 1]
        if room[0]:
            self.slots[0] = accepted
        assert not (poison and accepted), "poisoned constants must never be accepted"
        return accepted

    def drain(self, task):
        for _ in range(8):
            self.cycle(task, ready=1)
        assert not any(self.slots)

    def send(self, vector):
        for _ in range(1000):
            if self.cycle(vector["task_id"], vector):
                return
        raise AssertionError("traffic timeout")


def row_text(r):
    return (f"{r['rst']} {r['cfg_valid']} {r['cfg_addr']:02x} {r['cfg_data']:02x} "
            f"{r['valid']} {pack(r['accum'],32):016x} {r['last']} {r['scale']:04x} "
            f"{pack(r['bias'],32):016x} {r['zp']:02x} {r['bypass']} {r['m_ready']} "
            f"{r['task_id']} {r['vector_id']}\n")


def fixtures_and_traffic(layers, seed, random_words):
    rng = random.Random(seed)
    producer = Producer(rng)
    reference_check = integer_reference_functions()
    vectors = []
    for _ in range(3):
        producer.cycle(-1, rst=1, ready=0)
    for layer in layers:
        task = layer["task_id"]
        producer.drain(task)
        for address, value in enumerate(layer["table"]):
            producer.cycle(task, cfg=(address, value), ready=1)
        per_layer = layer_vectors(layer, rng, random_words)
        for vector in per_layer:
            vector["id"] = len(vectors)
            vectors.append(vector)
            reference_check(vector, layer["table"])
        # Random gaps poison live constants immediately after accepted words.
        for vector in per_layer[:-5]:
            for _ in range(rng.randrange(3)):
                producer.cycle(task)
            producer.send(vector)
        producer.drain(task)
        # Fill all slots, then change live constants while a fifth offer waits.
        for vector in per_layer[-5:-1]:
            assert producer.cycle(task, vector, ready=0)
        assert all(producer.slots)
        for _ in range(16):
            producer.cycle(task, per_layer[-1], ready=0, poison=True)
        assert producer.cycle(task, per_layer[-1], ready=1)
        producer.drain(task)
        layer["vector_count"] = len(per_layer)
        layer["random_word_count"] = random_words
        layer["python_reference_expression_checks"] = len(per_layer) * 2
        layer["vector_id_first"] = per_layer[0]["id"]
        layer["vector_id_last"] = per_layer[-1]["id"]
        json_write(OUT / f"task_{task:03d}.vectors.json", per_layer)
    producer.drain(layers[-1]["task_id"])
    return vectors, producer.rows


def command(args, log):
    result = subprocess.run([str(a) for a in args], cwd=OUT, capture_output=True,
                            text=True, errors="replace", timeout=120)
    text = result.stdout + result.stderr
    log.write_text(text, encoding="ascii", errors="backslashreplace")
    if result.returncode or "** Error" in text or "FAIL" in text:
        raise RuntimeError(f"command failed: {args}\n{text}")
    return text


def codec_functions():
    env = {"np": np}
    # Direct execution avoids importing/writing any cache outside this directory.
    path = MIGRATION / "feature_layout.py"
    exec(compile(path.read_text(), str(path), "exec"), env)
    return env["pack_c16"]


def verify(rows, vectors, layers, trace):
    lines = trace.read_text(encoding="ascii").splitlines()
    assert len(lines) == len(rows), f"trace length mismatch: {len(lines)} != {len(rows)}"
    layer_map = {l["task_id"]: l for l in layers}
    counts = Counter()
    per_task = {l["task_id"]: Counter() for l in layers}
    cfg_seen = {l["task_id"]: [] for l in layers}
    queue = deque()
    accepted = []
    consumed = []
    old_stall = None
    actual_layout = {l["task_id"]: bytearray([l["output_zp"]] *
                     (l["padded_co"] * l["layout_fixture_count"])) for l in layers}
    layout_positions = {l["task_id"]: set() for l in layers}
    codes_seen = {l["task_id"]: set() for l in layers}
    for cycle in range(len(rows)):
        row, line = rows[cycle], lines[cycle]
        f = line.split()
        assert len(f) == 11, f"bad trace row: {cycle} {line}"
        assert int(f[0]) == cycle and int(f[1]) == row["task_id"] and int(f[2]) == row["vector_id"]
        for i in (3, 4, 5, 6, 8, 9, 10):
            assert f[i] in ("0", "1"), f"unknown control at cycle {cycle}: {line}"
        sr, cr, mv, ml = map(int, f[3:7])
        pv, sv, bv = map(int, f[8:11])
        if mv:
            assert re.fullmatch(r"[0-9a-fA-F]{4}", f[7]), f"unknown output cycle {cycle}: {line}"
        data = int(f[7], 16) if re.fullmatch(r"[0-9a-fA-F]{4}", f[7]) else None
        mask = pv | (sv << 1) | (bv << 2) | (mv << 3)
        assert cr == int(not row["rst"] and mask == 0)
        room3 = not mv or row["m_ready"]
        room2 = not bv or room3
        room1 = not sv or room2
        room0 = not pv or room1
        assert sr == int(not row["rst"] and not row["cfg_valid"] and room0)
        counts["cycles"] += 1
        if row["rst"]:
            assert not queue, "model regression must not reset away comparisons"
            old_stall = None
            continue
        task = row["task_id"]
        c = per_task[task]
        if mask and cycle and not rows[cycle - 1]["rst"]:
            old = rows[cycle - 1]
            for name in ("scale", "bias", "zp", "bypass"):
                c[name + "_live_changes_occupied"] += int(row[name] != old[name])
        if row["cfg_valid"]:
            assert cr and not mask and not queue and not sr
            cfg_seen[task].append((row["cfg_addr"], row["cfg_data"]))
            c["idle_table_writes"] += 1
        if old_stall is not None:
            assert mv and (data, ml) == old_stall, f"output changed under stall at cycle {cycle}"
        old_stall = (data, ml) if mv and not row["m_ready"] else None
        if mask == 15 and not row["m_ready"] and row["vector_id"] >= 0:
            offered = vectors[row["vector_id"]]
            if offered["kind"] == "directed_stall":
                c["directed_full_pipeline_stall_cycles"] += 1
                assert not sr
        if mv:
            assert queue, f"unexpected output cycle {cycle}"
            vector, accepted_cycle = queue[0]
            assert data == pack(vector["outputs"], 8), (
                f"task {vector['task_id']} vector {vector['id']} cycle {cycle}: "
                f"RTL {data:04x} != golden {pack(vector['outputs'],8):04x}")
            assert ml == vector["last"], f"last mismatch vector {vector['id']}"
            c["valid_cycle_lane_checks"] += 2
            if row["m_ready"]:
                queue.popleft()
                assert task == vector["task_id"], "output crossed task programming boundary"
                consumed.append(vector["id"])
                c["compared_words"] += 1
                c["physical_lane_compares"] += 2
                c["real_lane_compares"] += vector["valid_lane_mask"].bit_count()
                c["dummy_lane_compares"] += 2 - vector["valid_lane_mask"].bit_count()
                c["last_compares"] += 1
                c["last_high_words"] += ml
                c["kind_" + vector["kind"]] += 1
                if vector["fixture_index"] is not None:
                    layer = layer_map[task]
                    index = vector["fixture_index"]
                    for lane_index, channel in enumerate(vector["channels"]):
                        position = ((channel // 16) * layer["layout_fixture_count"] + index) * 16 + channel % 16
                        assert position not in layout_positions[task], "duplicate C16 byte position"
                        layout_positions[task].add(position)
                        if channel < layer["co"]:
                            actual_layout[task][position] = (data >> (lane_index * 8)) & 255
                if vector["kind"] == "all_256_table_codes":
                    codes_seen[task].update(vector["codes"])
            else:
                c["output_stall_cycles"] += 1
        if row["valid"] and sr:
            vector = vectors[row["vector_id"]]
            assert vector["task_id"] == task
            for name in ("accum", "bias", "scale", "zp", "bypass", "last"):
                assert row[name] == vector[name], f"wrong constants accepted vector {vector['id']} {name}"
            assert cfg_seen[task] == list(enumerate(layer_map[task]["table"]))
            accepted.append(vector["id"])
            queue.append((vector, cycle))
            c["accepted_words"] += 1
            if vector["kind"] == "trace_range_random":
                c["random_words"] += 1
        elif row["valid"]:
            c["source_stall_cycles"] += 1
    assert not queue, "pending words left at end"
    assert accepted == consumed == list(range(len(vectors))), "exact accepted/output vector sequence mismatch"
    pack_c16 = codec_functions()
    for layer in layers:
        task = layer["task_id"]
        c = per_task[task]
        assert c["accepted_words"] == c["compared_words"] == layer["vector_count"]
        assert c["random_words"] >= 100
        assert c["idle_table_writes"] == 256
        assert codes_seen[task] == set(range(256))
        assert c["directed_full_pipeline_stall_cycles"] == 16
        real_kind_coverage = {}
        for vector in vectors[layer['vector_id_first']:layer['vector_id_last'] + 1]:
            if vector['kind'] != 'trace_range_random' and vector['kind'] not in ('all_256_table_codes', 'directed_stall'):
                real_kind_coverage.setdefault(vector['kind'], set()).update(
                    channel for channel in vector['channels'] if channel < layer['co'])
        assert all(channels == set(range(layer['co'])) for channels in real_kind_coverage.values())
        layer['real_channel_coverage_by_kind'] = {kind: len(channels) for kind, channels in real_kind_coverage.items()}
        for name in ("scale", "bias", "zp", "bypass"):
            assert c[name + "_live_changes_occupied"] > 0
        assert len(layout_positions[task]) == len(actual_layout[task])
        golden_tensor = np.empty((1, layer["co"], 1, layer["layout_fixture_count"]), np.uint8)
        per_layer_vectors = vectors[layer["vector_id_first"]:layer["vector_id_last"] + 1]
        real_layout_channels = set()
        for v in per_layer_vectors:
            if v["fixture_index"] is not None:
                for i, channel in enumerate(v["channels"]):
                    if channel < layer["co"]:
                        golden_tensor[0, channel, 0, v["fixture_index"]] = v["outputs"][i]
                        real_layout_channels.add(channel)
        assert real_layout_channels == set(range(layer["co"]))
        expected_bytes = pack_c16(golden_tensor, layer["output_zp"])
        actual_bytes = bytes(actual_layout[task])
        assert len(actual_bytes) == len(expected_bytes) and actual_bytes == expected_bytes
        (OUT / f"task_{task:03d}.golden.c16.bin").write_bytes(expected_bytes)
        (OUT / f"task_{task:03d}.rtl.c16.bin").write_bytes(actual_bytes)
        layer["c16_fixture_sha256"] = hashlib.sha256(actual_bytes).hexdigest()
        layer["c16_compared_bytes"] = len(actual_bytes)
        layer["all_real_bias_channels_checked"] = len(real_layout_channels)
        layer["table_codes_checked"] = len(codes_seen[task])
        layer["counts"] = dict(c)
        counts.update(c)
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin", type=Path, default=Path("C:/modeltech64_10.6e/win64"))
    parser.add_argument("--seed", type=int, default=564012)
    parser.add_argument("--random-words", type=int, default=128)
    args = parser.parse_args()
    assert args.random_words >= 100
    OUT.mkdir(exist_ok=True)
    for name in ("TEST_REPORT.md", "manifest.json"):
        (OUT / name).unlink(missing_ok=True)
    for source in HERE.glob('*'):
        if source.is_file():
            source.read_bytes().decode('ascii')
    layers, numeric, before = load_assets()
    print("ASSET_AUDIT PASS: 55 Conv, 49 SiLU, 6 Clip; hash chain and model constant ranges", flush=True)
    vectors, rows = fixtures_and_traffic(layers, args.seed, args.random_words)
    stimulus, trace = OUT / "model.stimulus.txt", OUT / "model.trace.txt"
    stimulus.write_text("".join(row_text(r) for r in rows), encoding="ascii")
    trace.unlink(missing_ok=True)
    print(f"GOLDEN_EXPRESSION PASS: words={len(vectors)} lane_checks={2*len(vectors)}", flush=True)
    if not (OUT / "work").exists():
        command([args.modelsim_bin / "vlib.exe", "work"], OUT / "vlib.log")
    compile_cmd = [args.modelsim_bin / "vlog.exe", "-work", "work", "-vlog01compat",
                   LUT, RTL, HERE / "tb_fpga_v8_finish_model.v"]
    text = command(compile_cmd, OUT / "compile.log")
    assert "Errors: 0, Warnings: 0" in text
    sim_cmd = [args.modelsim_bin / "vsim.exe", "-c", "-lib", "work", "tb_fpga_v8_finish_model",
               f"+STIMULUS={stimulus.as_posix()}", f"+TRACE={trace.as_posix()}",
               "-do", "run -all; quit -f"]
    text = command(sim_cmd, OUT / "simulation.log")
    assert f"PASS_FINISH_MODEL_TB cycles={len(rows)} lanes=2" in text
    warnings = [line for line in text.splitlines() if "** Warning:" in line]
    assert all("(vsim-8891)" in line for line in warnings), warnings
    counts = verify(rows, vectors, layers, trace)
    constant_ranges = {
        'shared_scale_unsigned16_min': min(l['scale'] for l in layers),
        'shared_scale_unsigned16_max': max(l['scale'] for l in layers),
        'folded_bias_signed32_min': min(min(l['bias']) for l in layers),
        'folded_bias_signed32_max': max(max(l['bias']) for l in layers),
        'model_raw_abs_bound_max': max(l['raw_bound_max'] for l in layers),
        'total_real_bias_channels': sum(l['co'] for l in layers),
        'exact_half_reachable_channels': sum(l['exact_half_reachable_channels'] for l in layers),
        'interior_exact_half_channels': sum(l['interior_exact_half_channels'] for l in layers),
    }
    after = {path: digest(Path(path)) for path in before}
    assert before == after, "read-only source or input changed during validation"
    source_hashes = {str(p.resolve()): digest(p) for p in HERE.glob('*') if p.is_file()}
    for layer in layers:
        json_write(OUT / f"task_{layer['task_id']:03d}.audit.json", layer)
    manifest = {"status": "PASS", "utc": datetime.now(timezone.utc).isoformat(),
                "scope": "model-specific isolated finish RTL constant integration, not full graph or legacy RAM wrapping",
                "lanes": 2, "seed": args.seed, "random_words_per_layer": args.random_words,
                "convolutions": 55, "activation_counts": {"silu": 49, "clip": 6},
                "numeric_sha256": digest(NUMERIC), "model_sha256": numeric["model_sha256"],
                "read_only_inputs_sha256_before": before, "read_only_inputs_sha256_after": after,
                "validation_sources_sha256": source_hashes,
                "stimulus_sha256": digest(stimulus), "trace_sha256": digest(trace),
                "compile_command": [str(a) for a in compile_cmd],
                "simulation_command": [str(a) for a in sim_cmd], "simulation_warnings": warnings,
                "python": sys.version, "python_executable": sys.executable,
                "python_current_reference_expression_lane_checks": 2 * len(vectors),
                "constant_ranges_and_half_coverage": constant_ranges,
                "words_compared_by_activation": {kind: sum(l['counts']['compared_words'] for l in layers
                     if l['activation'] == kind) for kind in ('silu', 'clip')},
                "counts": counts, "layers": layers}
    manifest["artifacts_sha256"] = {p.name: digest(p) for p in OUT.iterdir()
                                    if p.is_file() and p.name not in ('manifest.json', 'TEST_REPORT.md')}
    json_write(OUT / "manifest.json", manifest)
    report = ["# Model-specific convolution finish validation", "", "Result: PASS", "",
              f"UTC: {manifest['utc']}", f"Python: {sys.executable} ({sys.version.split()[0]})", "",
              "ModelSim 10.6e, LANES=2, existing finish RTL and activation LUT unchanged.",
              "55 actual exported tasks: 49 SiLU and 6 Clip. No prior tests, PDS synthesis,",
              "production change or full-graph inference was run.", "",
              f"Compared {counts['compared_words']} words, {counts['physical_lane_compares']} physical lane bytes,",
              f"{counts['real_lane_compares']} real output lane bytes and {counts['dummy_lane_compares']} masked dummy lane bytes.",
              f"Checked {counts['valid_cycle_lane_checks']} lane values on valid cycles, including stalls;",
              f"all {counts['last_compares']} output last flags match. Every expected word was accepted",
              "and consumed exactly once in order. No X output or minimum-length comparison skip.", "",
              f"Current integer_reference.py expression/saturate_q16 cross-checks: {2*len(vectors)} lanes.",
              f"All {sum(l['co'] for l in layers)} real channel biases tested with model/achievable bounds, trace extrema,",
              "zero raw input, all-input-zp cancellation, signed32 extrema, half-residue searches",
              "and zero/255 rounding transition neighbors. Raw model bounds are all strictly",
              f"below 2^31; largest is {max(l['raw_bound_max'] for l in layers)}.", "",
              f"Verified hardware constants: shared scale {constant_ranges['shared_scale_unsigned16_min']}.."
              f"{constant_ranges['shared_scale_unsigned16_max']}; signed folded bias "
              f"{constant_ranges['folded_bias_signed32_min']}..{constant_ranges['folded_bias_signed32_max']}.",
              f"Exact half ties are reachable for {constant_ranges['exact_half_reachable_channels']} channels,",
              f"with {constant_ranges['interior_exact_half_channels']} selected ties in the unclamped 0..255 range.",
              "All below/nearest/above residue selections stay within each channel's model raw bound.",
              "Every rounding-search and 0/255 transition fixture also passes with bypass, directly",
              "comparing requantized codes even when neighboring LUT outputs are identical.", "",
              f"All task tables programmed through {counts['idle_table_writes']} idle accepted configuration writes.",
              "Every task tests all 256 table codes using its actual coefficients and biases.",
              f"Trace-range random words: {counts['random_words']} ({args.random_words} per layer).",
              f"Output stall cycles: {counts['output_stall_cycles']}; directed occupied-all-stage stalls: "
              f"{counts['directed_full_pipeline_stall_cycles']}.", "",
              f"Valid words by activation: SiLU={manifest['words_compared_by_activation']['silu']}, "
              f"Clip={manifest['words_compared_by_activation']['clip']}.",
              "Live input changes while words were pending are measured and verified per task:",
              f"scale={counts['scale_live_changes_occupied']}, bias={counts['bias_live_changes_occupied']}, "
              f"zero point={counts['zp_live_changes_occupied']}, bypass={counts['bypass_live_changes_occupied']}.", "",
              "All-input-zp accumulators are input_zp * signed_weight_sum, including the synthetic",
              "zp-padded window. Accumulator*encoded_scale + folded_bias equals exported bias_q16",
              "exactly for every real channel; no input-zp correction is applied twice.", "",
              "Odd CO=3 heads use mask=1 for channels [2,3], bias=0 and accumulator=0 for the",
              "dummy lane. The physical dummy LUT result is compared. C16 padding is explicitly",
              "replaced with output-zp after masking; per-word bypass cannot act only on a dummy lane.", "",
              f"C16 fixture bytes compared: {sum(l['c16_compared_bytes'] for l in layers)} across 55 matching SHA256 pairs.",
              "Pairs follow low-lane/even-channel order and every padded16 byte position is covered.",
              "These hashes describe synthetic model-constant fixtures, not full-frame model outputs.", "",
              "Compilation: Errors: 0, Warnings: 0. Simulation has no errors; inherited local",
              "-novopt emits vsim-8891 only (recorded verbatim in manifest and simulation.log).", "",
              "Numeric export SHA256:", "", f"`{digest(NUMERIC)}`", "",
              "Specialized export model SHA256:", "", f"`{numeric['model_sha256']}`", "",
              "| Task | Activation | CO | Scale | Words | Real bytes | C16 bytes |", 
              "| ---: | --- | ---: | ---: | ---: | ---: | ---: |"]
    for l in layers:
        report.append(f"| {l['task_id']} | {l['activation']} | {l['co']} | {l['scale']} | "
                      f"{l['counts']['compared_words']} | {l['counts']['real_lane_compares']} | {l['c16_compared_bytes']} |")
    report += ["", "Exact commands, provenance, constant hashes, vector/trace hashes and counts:",
               "[manifest.json](manifest.json). Per-task audit files include every bias, raw bound,",
               "weight sum, searched residue, mask and synthetic C16 hash. Original source",
               "model and specialized export hashes are recorded separately.", "",
               "Reproduce: `python run_validation.py` from finish/model_validation.", "",
               "Acceptance is limited to model-asset integration with the isolated finish primitive.",
               "Convolution MACs, legacy wrapping, graph execution, DMA, accuracy, timing closure",
               "and board performance remain outside this evidence.", ""]
    (OUT / "TEST_REPORT.md").write_text("\n".join(report), encoding="ascii")
    print(f"PASS_MODEL_FINISH: tasks=55 SiLU=49 Clip=6 words={counts['compared_words']} "
          f"physical_bytes={counts['physical_lane_compares']} real_bytes={counts['real_lane_compares']}", flush=True)


if __name__ == '__main__':
    main()
