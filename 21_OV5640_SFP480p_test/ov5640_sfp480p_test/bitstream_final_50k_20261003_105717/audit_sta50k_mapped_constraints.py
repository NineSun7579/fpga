"""Audit native PDS get_pins enumeration before emitting a post-map-only FDC.

No PDS execution or production mutation. Run this against a fresh TA enumeration
log for the exact mapped ADF that will be used by the next implementation step.
The caller must record the ADF hash before/after collecting that log.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

PATTERNS = {
    "wclk": ("u_sfp_video_tx/u_fifo/mem_*/ram32x1dp/WCLK", 288),
    "rd": ("u_sfp_video_tx/u_fifo/mem_*/ram32x1dp/RD", 288),
    "head": ("u_sfp_video_tx/head_q*/I*", 288),
    "head_s": ("u_sfp_video_tx/head_q*/S*", 198),
    "wr_gray_d": ("u_sfp_video_tx/u_fifo/wptr_rd1*/D", 10),
    "rd_gray_d": ("u_sfp_video_tx/u_fifo/rptr_wr1*/D", 10),
    "sys_rs": ("sys_rst_sync*/RS", 2),
    "diag_rs": ("diag_rst_sync*/RS", 2),
}


def enumerations(text):
    result = {}
    active = None
    for line in text.splitlines():
        match = re.match(r"I: The pattern '([^']+)' .* match (\d+) objects below:", line)
        if match:
            active = match[1]
            if active in result:
                raise ValueError("Duplicate query enumeration: " + active)
            result[active] = {"reported": int(match[2]), "pins": []}
        elif active and line.startswith("I: pin "):
            result[active]["pins"].append(line[len("I: pin "):].strip())
        elif line.startswith("Executing : "):
            active = None
    return result


def audit(text, fifo_only=False):
    if re.search(r"^E:", text, re.M):
        raise ValueError("PDS enumeration log contains an error")
    found = enumerations(text)
    selected = {}
    for key, (pattern, expected) in PATTERNS.items():
        if fifo_only and key.endswith("_rs"):
            continue
        entry = found.get(pattern)
        if not entry:
            raise ValueError("Missing query: " + pattern)
        pins = entry["pins"]
        if entry["reported"] != expected or len(pins) != expected or len(set(pins)) != expected:
            raise ValueError(f"{key}: expected {expected}, reported {entry['reported']}, identities {len(pins)}")
        selected[key] = sorted(pins)
    for key in ("wr_gray_d", "rd_gray_d"):
        bits = sorted(int(re.search(r"\[(\d+)\]", p)[1]) for p in selected[key])
        if bits != list(range(10)) or any(not p.endswith("/D") for p in selected[key]):
            raise ValueError("Gray destinations are not exactly D bits 0..9")
    wram = {p.rsplit("/", 1)[0] for p in selected["wclk"]}
    rram = {p.rsplit("/", 1)[0] for p in selected["rd"]}
    if wram != rram:
        raise ValueError("WCLK and RD collections do not identify the same RAMs")
    if not fifo_only:
        for key, root in (("sys_rs", "sys_rst_sync"), ("diag_rs", "diag_rst_sync")):
            for bit in range(2):
                matches = [p for p in selected[key] if p.startswith(f"{root}[{bit}]/") and p.endswith("/RS")]
                if len(matches) != 1:
                    raise ValueError("Reset collection is not the dedicated two-bit chain: " + key)
    return selected


def pin_list(pins):
    if any("{" in p or "}" in p or any(c.isspace() for c in p) for p in pins):
        raise ValueError("Unexpected characters in mapped object name")
    return "[get_pins -hierarchical {" + " ".join(pins) + "}]"


def candidate(objects):
    return "\n".join([
        "# STA50K_POSTMAP_ONLY_BEGIN -- never register this file for compile/synthesize",
        "# Exact objects audited externally; source/map hash must remain unchanged.",
        "set_false_path -from " + pin_list(objects["wclk"]) + " -through " + pin_list(objects["rd"]) + " -to " + pin_list(objects["head"]),
        "# Mapped head-mux S aliases: same WCLK origin and mandatory RD throughpoint.",
        "set_false_path -from " + pin_list(objects["wclk"]) + " -through " + pin_list(objects["rd"]) + " -to " + pin_list(objects["head_s"]),
        "set_max_delay 16.000 -datapath_only -from [get_clocks mrg_clk] -to " + pin_list(objects["wr_gray_d"]),
        "set_max_delay 8.000 -datapath_only -from [get_clocks p_clk2core_tx_2] -to " + pin_list(objects["rd_gray_d"]),
        "set_false_path -from [get_clocks cfg_clk] -to " + pin_list(objects["sys_rs"] + objects["diag_rs"]),
        "# STA50K_POSTMAP_ONLY_END",
        "",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--expected-db-sha256", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fifo-only", action="store_true", help="Baseline parser verification only; cannot emit FDC")
    args = parser.parse_args()
    actual = hashlib.sha256(args.db.read_bytes()).hexdigest()
    if actual.lower() != args.expected_db_sha256.lower():
        raise SystemExit("Mapped ADF hash changed; refusing candidate")
    objects = audit(args.log.read_bytes().decode("gb18030", errors="replace"), args.fifo_only)
    evidence = {"db": str(args.db.resolve()), "db_sha256": actual,
                "log_sha256": hashlib.sha256(args.log.read_bytes()).hexdigest(),
                "counts": {key: len(pins) for key, pins in objects.items()}, "objects": objects}
    if args.output:
        if args.fifo_only:
            raise SystemExit("FIFO-only baseline verification cannot emit a production candidate")
        args.output.write_bytes(candidate(objects).encode("ascii"))
        evidence["fdc_sha256"] = hashlib.sha256(args.output.read_bytes()).hexdigest()
        args.output.with_suffix(args.output.suffix + ".audit.json").write_text(json.dumps(evidence, indent=2), encoding="utf8")
    print(json.dumps({key: value for key, value in evidence.items() if key != "objects"}, indent=2))


if __name__ == "__main__":
    main()
