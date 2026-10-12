"""Audit existing PDS outputs without invoking any design tool or simulation."""
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import re


WORK = Path(__file__).resolve().parent
TOP = "fpga_v8_raw_frame_axi"
EXPECTED = json.loads((WORK / "expected_inputs.json").read_text(encoding="utf-8"))


def write_json(name, value):
    (WORK / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def diagnostic_key(line):
    if "The license will invalid" in line:
        return "license_expiry"
    if "Loop was found during constant probe" in line:
        return "constant_probe_loop"
    if "Public-4008" in line:
        return "Public-4008_dangling_instance"
    if "Removed GTP_DFF" in line:
        return "constant_register_removed"
    if "Unable to honor max fanout" in line:
        return "max_fanout_not_honored"
    if "prevent name conflict" in line:
        return "net_renamed"
    if "The design has" in line:
        return "io_count_exceeds_physical_package"
    if "Timing-4087" in line:
        return "Timing-4087_unconstrained_output"
    if "Timing-4086" in line:
        return "Timing-4086_unconstrained_input"
    return line


def main():
    report = {"audited": datetime.datetime.now().astimezone().isoformat(),
              "scope": "existing compile and synthesis outputs only", "diagnostics": {}}
    extracted = []
    for name in ["compile_stdout.log", "compile_stderr.log",
                 "synthesize_stdout.log", "synthesize_stderr.log"]:
        lines = (WORK / name).read_bytes().splitlines()
        warnings = []
        errors = []
        for number, raw in enumerate(lines, 1):
            if raw.startswith((b"W:", b"E:")):
                line = raw.decode("ascii", errors="backslashreplace")
                record = {"line": number, "message": line}
                (warnings if raw.startswith(b"W:") else errors).append(record)
                extracted.append(f"{name}:{number}: {line}")
        report["diagnostics"][name] = {
            "warnings": len(warnings), "errors": len(errors),
            "warning_categories": dict(Counter(diagnostic_key(w["message"]) for w in warnings)),
            "width_or_truncation_diagnostics": [w for w in warnings + errors
                if re.search(r"width|truncat|extend", w["message"], re.I)],
            "latch_diagnostics": [w for w in warnings + errors
                if re.search(r"latch", w["message"], re.I)]}
    (WORK / "diagnostics_extracted.txt").write_text("\n".join(extracted) + "\n", encoding="utf-8")
    snr = (WORK / "synthesize" / (TOP + ".snr")).read_bytes()
    cells = {}
    for line in snr.splitlines():
        match = re.match(rb"^(GTP_\w+)\s+(\d+)\s+uses?\s*$", line)
        if match:
            cells[match[1].decode("ascii")] = int(match[2])
    vm = (WORK / "synthesize" / (TOP + "_syn.vm")).read_bytes()
    netlist_cells = Counter(m.decode("ascii") for m in re.findall(
        rb"\b(GTP_\w+)\s+(?:/\*.*?\*/\s*)?(?:#\s*\(|(?:\\[^\s]+|\w+)\s*\()", vm, re.S))
    virtual_buffers = len(re.findall(
        rb'\(\*\s*PAP_IS_VIRTUAL_IO="TRUE"\s*\*\)\s*GTP_(?:INBUF|OUTBUF)', vm))
    report["cells_from_snr"] = cells
    report["cells_from_netlist"] = dict(sorted(netlist_cells.items()))
    report["cell_counts_match"] = cells == dict(netlist_cells)
    report["resource_summary"] = {}
    for key, pattern in {
        "lut": rb"Total LUTs:\s+(\d+)",
        "registers": rb"Total Registers:\s+(\d+)",
        "latches": rb"Total Latches:\s+(\d+)",
        "drm": rb"Total DRM\s*=\s*([\d.]+)",
        "apm": rb"Total APMs\s*=\s*([\d.]+)",
        "io_bits": rb"Total I/O ports\s*=\s*(\d+)"
    }.items():
        match = re.search(pattern, snr)
        if not match:
            raise RuntimeError("Missing resource summary " + key)
        report["resource_summary"][key] = float(match[1]) if key in ["drm", "apm"] else int(match[1])
    report["virtual_io_buffer_instances"] = virtual_buffers
    report["all_io_buffers_virtual"] = virtual_buffers == report["resource_summary"]["io_bits"]
    source_records = []
    for source in EXPECTED["sources"]:
        data = (WORK / source["path"]).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        source_records.append({"path": source["path"], "sha256": sha,
                               "unchanged": sha == source["sha256"]})
    report["sources_after_audit"] = source_records
    report["source_hashes_unchanged"] = all(s["unchanged"] for s in source_records)
    report["forbidden_stage_directories_present"] = [d for d in
        ["device_map", "place_route", "generate_bitstream", "generate_netlist", "report_timing", "report_power"]
        if (WORK / d).exists()]
    report["bitstream_files_present"] = [str(p.relative_to(WORK)) for p in WORK.rglob("*")
        if p.is_file() and p.suffix.lower() in [".sbit", ".bit", ".smsk"]]
    artifacts = []
    for relative in ["compile/" + TOP + "_comp.adf", "compile/" + TOP + ".cmr",
                     "synthesize/" + TOP + "_syn.adf", "synthesize/" + TOP + "_syn.vm",
                     "synthesize/" + TOP + ".snr", "compile_stdout.log", "synthesize_stdout.log"]:
        data = (WORK / relative).read_bytes()
        artifacts.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    report["artifacts"] = artifacts
    results = json.loads((WORK / "run_results.json").read_text(encoding="utf-8"))
    report["both_invocations_returned_zero"] = (len(results["stages"]) == 2 and
        all(s["returncode"] == 0 and s["expected_database_present"] for s in results["stages"]))
    report["audit_pass"] = all([
        report["cell_counts_match"], report["all_io_buffers_virtual"],
        report["source_hashes_unchanged"], report["both_invocations_returned_zero"],
        not report["forbidden_stage_directories_present"], not report["bitstream_files_present"],
        all(d["errors"] == 0 for d in report["diagnostics"].values())])
    write_json("output_audit.json", report)
    print(json.dumps({k: report[k] for k in ["audit_pass", "resource_summary", "cells_from_snr",
        "cell_counts_match", "virtual_io_buffer_instances", "diagnostics"]}, indent=2))
    if not report["audit_pass"]:
        raise RuntimeError("Output audit failed; inspect output_audit.json")


if __name__ == "__main__":
    main()
