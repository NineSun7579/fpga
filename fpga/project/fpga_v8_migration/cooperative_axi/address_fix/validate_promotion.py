"""Validate PROMOTE.patch entirely in memory; never apply it to the originals."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
FROZEN_HASH = "235f878ac7a35134f2ce9f8b9b56fecf66d033387715c46e953fa0a907df5b40"


def proposed_files():
    lines = (ROOT / "PROMOTE.patch").read_text(encoding="ascii").splitlines()
    assert lines[0] == "*** Begin Patch" and lines[-1] == "*** End Patch"
    proposals = {}
    path = None
    hunk = []

    def flush():
        if not hunk:
            return
        old = "\n".join(line[1:] for line in hunk if not line.startswith("+")) + "\n"
        new = "\n".join(line[1:] for line in hunk if not line.startswith("-")) + "\n"
        before = proposals[path]
        if before.count(old) != 1:
            raise AssertionError(f"Patch hunk is missing or ambiguous: {path}\n{old}")
        proposals[path] = before.replace(old, new, 1)
        hunk.clear()

    for line in lines[1:]:
        if line.startswith("*** Update File: "):
            flush()
            path = Path(line.removeprefix("*** Update File: ")).resolve()
            if path.parent != BASE or path.name not in (
                    "fpga_v8_raw_frame_axi.v", "tb_fpga_v8_raw_frame_axi.v",
                    "tb_fpga_v8_raw_axi_config.v", "run_tests.py"):
                raise AssertionError(f"Unexpected promotion target: {path}")
            proposals[path] = path.read_text(encoding="ascii")
        elif line.startswith("@@") or line == "*** End Patch":
            flush()
        else:
            if not line or line[0] not in " +-":
                raise AssertionError(f"Unexpected patch line: {line}")
            hunk.append(line)
    return proposals


def main():
    frozen = BASE / "fpga_v8_raw_frame_axi.v"
    if hashlib.sha256(frozen.read_bytes()).hexdigest() != FROZEN_HASH:
        raise AssertionError("Frozen original changed; main agent must reconcile before promotion.")
    proposals = proposed_files()
    for staged, original in (
            ("fpga_v8_raw_frame_axi_physical.v", "fpga_v8_raw_frame_axi.v"),
            ("tb_fpga_v8_raw_frame_axi_physical.v", "tb_fpga_v8_raw_frame_axi.v"),
            ("tb_fpga_v8_raw_axi_physical_config.v", "tb_fpga_v8_raw_axi_config.v")):
        wanted = (ROOT / staged).read_text(encoding="ascii")
        wanted = wanted.replace("fpga_v8_raw_frame_axi_physical", "fpga_v8_raw_frame_axi")
        wanted = wanted.replace("tb_fpga_v8_raw_axi_physical_config", "tb_fpga_v8_raw_axi_config")
        wanted = wanted.replace("AXI_RAW_PHYSICAL_PASS", "AXI_RAW_PASS")
        wanted = wanted.replace("AXI_PHYSICAL_CONFIG_PASS", "AXI_CONFIG_PASS")
        if original == "fpga_v8_raw_frame_axi.v":
            wanted = wanted.replace(
                "// Staged physical-address correction. Original bridge stays frozen for PDS.\n"
                "// Reset outstanding AXI with the bus/slave. Publish only on done && !error.",
                "// Isolated candidate. Reset while a transaction is outstanding requires a\n"
                "// common reset of the AXI interconnect/slave. Publish only on done && !error.")
        if proposals[BASE / original] != wanted:
            raise AssertionError(f"Promotion does not match tested staged module: {original}")
    ast.parse(proposals[BASE / "run_tests.py"], filename="promoted_run_tests.py")
    for path, content in proposals.items():
        print(f"PROPOSED {path.name} sha256={hashlib.sha256(content.encode('ascii')).hexdigest()}")
    print("PROMOTION_VALIDATED_IN_MEMORY originals_unchanged=1 files=4")


if __name__ == "__main__":
    main()
