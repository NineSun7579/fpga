"""Audit finished component evidence; never invokes PDS or alters historical 02."""
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parent
CURRENT = ["raw_frame_axi_03", "coop_control_01", "ddr_write_arbiter_01"]


def stamp():
    return datetime.datetime.now().astimezone().isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def diagnostic_key(line):
    for fragment, category in [
        ("The license will invalid", "license_expiry"),
        ("Loop was found during constant probe", "constant_probe_loop"),
        ("Public-4008", "Public-4008_dangling_instance"),
        ("stuck at constant", "constant_register_removed"),
        ("Unable to honor max fanout", "max_fanout_not_honored"),
        ("prevent name conflict", "net_renamed"),
        ("The design has", "io_count_exceeds_physical_package"),
        ("Timing-4087", "Timing-4087_unconstrained_output"),
        ("Timing-4086", "Timing-4086_unconstrained_input")]:
        if fragment in line:
            return category
    return line


def resource_summary(snr):
    values = {}
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
        values[key] = float(match[1]) if key in ["drm", "apm"] else int(match[1])
    return values


def audit(folder):
    work = ROOT / folder
    expected = json.loads((work / "expected_inputs.json").read_text(encoding="utf-8"))
    top = expected["top"]
    report = {"audited": stamp(), "top": top, "diagnostics": {}}
    extracted = []
    parameters = []
    selected_tops = []
    for stage in expected["allowed_stages"]:
        for name in [stage + "_stdout.log", stage + "_stderr.log"]:
            data = (work / name).read_bytes()
            lines = data.splitlines()
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
            selected_tops.extend(m.decode("ascii") for m in re.findall(
                rb'Module "([^"]+)" is set as top module', data))
            pattern = rb"Module instance \{" + top.encode("ascii") + rb"\} parameter value:\s*"
            match = re.search(pattern, data)
            if match:
                values = {}
                for raw in data[match.end():].splitlines():
                    if not raw.strip():
                        continue
                    assignment = re.match(rb"\s*(\w+)\s*=\s*\d+'b([01]+)\s*$", raw)
                    if not assignment:
                        break
                    values[assignment[1].decode("ascii")] = int(assignment[2], 2)
                parameters.append({"log": name, "values": values})
    (work / "diagnostics_extracted.txt").write_text("\n".join(extracted) + "\n", encoding="utf-8")
    report["elaborated_parameters"] = parameters
    report["parameters_match_manifest"] = bool(parameters) and all(
        p["values"] == expected["parameters"] for p in parameters)
    report["selected_tops"] = selected_tops
    report["top_matches_manifest"] = bool(selected_tops) and all(t == top for t in selected_tops)
    snr = (work / "synthesize" / (top + ".snr")).read_bytes()
    cells = {}
    for line in snr.splitlines():
        match = re.match(rb"^(GTP_\w+)\s+(\d+)\s+uses?\s*$", line)
        if match:
            cells[match[1].decode("ascii")] = int(match[2])
    vm = (work / "synthesize" / (top + "_syn.vm")).read_bytes()
    netlist_cells = Counter(m.decode("ascii") for m in re.findall(
        rb"\b(GTP_\w+)\s+(?:/\*.*?\*/\s*)?(?:#\s*\(|(?:\\[^\s]+|\w+)\s*\()", vm, re.S))
    virtual_buffers = len(re.findall(
        rb'\(\*\s*PAP_IS_VIRTUAL_IO="TRUE"\s*\*\)\s*GTP_(?:INBUF|OUTBUF)', vm))
    report["cells_from_snr"] = cells
    report["cells_from_netlist"] = dict(sorted(netlist_cells.items()))
    report["cell_counts_match"] = cells == dict(netlist_cells)
    report["resource_summary"] = resource_summary(snr)
    report["virtual_io_buffer_instances"] = virtual_buffers
    report["all_io_buffers_virtual"] = virtual_buffers == report["resource_summary"]["io_bits"]
    source_records = []
    for source in expected["sources"]:
        data = (work / source["path"]).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        source_records.append({"path": source["path"], "sha256": sha, "bytes": len(data),
            "unchanged": sha == source["sha256"] and len(data) == source["bytes"]})
    report["sources_after_all_pds_runs"] = source_records
    report["source_hashes_unchanged"] = all(s["unchanged"] for s in source_records)
    report["forbidden_stage_directories_present"] = [d for d in
        ["device_map", "place_route", "generate_bitstream", "generate_netlist", "report_timing", "report_power"]
        if (work / d).exists()]
    report["bitstream_files_present"] = [str(p.relative_to(work)) for p in work.rglob("*")
        if p.is_file() and p.suffix.lower() in [".sbit", ".bit", ".smsk"]]
    artifacts = []
    for relative in ["compile/" + top + "_comp.adf", "compile/" + top + ".cmr",
                     "synthesize/" + top + "_syn.adf", "synthesize/" + top + "_syn.vm",
                     "synthesize/" + top + ".snr"] + [s + "_stdout.log" for s in expected["allowed_stages"]]:
        data = (work / relative).read_bytes()
        artifacts.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    report["artifacts"] = artifacts
    results = json.loads((work / "run_results.json").read_text(encoding="utf-8"))
    report["all_invocations_returned_zero"] = (
        [s["stage"] for s in results["stages"]] == expected["allowed_stages"] and
        all(s["returncode"] == 0 and s["expected_database_present"] for s in results["stages"]))
    report["audit_pass"] = all([
        report["parameters_match_manifest"], report["top_matches_manifest"],
        report["cell_counts_match"], report["all_io_buffers_virtual"],
        report["source_hashes_unchanged"], report["all_invocations_returned_zero"],
        not report["forbidden_stage_directories_present"], not report["bitstream_files_present"],
        all(d["errors"] == 0 for d in report["diagnostics"].values())])
    write_json(work / "output_audit.json", report)
    print(folder, "audit_pass=" + str(report["audit_pass"]), report["resource_summary"])
    if not report["audit_pass"]:
        raise RuntimeError("Output audit failed: " + folder)
    return report


def main():
    reports = {folder: audit(folder) for folder in CURRENT}
    baseline = json.loads((ROOT / "historical_02_before_03.json").read_text(encoding="utf-8"))
    previous = {f["path"]: f for f in baseline["files"]}
    current = {}
    for path in sorted((ROOT / "raw_frame_axi_02").rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            rel = path.relative_to(ROOT).as_posix()
            current[rel] = {"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    history = {"checked": stamp(), "files_before": len(previous), "files_after": len(current),
               "all_historical_02_files_unchanged": previous == current}
    write_json(ROOT / "historical_02_after_03.json", history)
    if previous != current:
        raise RuntimeError("Historical 02 files changed")
    old = resource_summary((ROOT / "raw_frame_axi_02/synthesize/fpga_v8_raw_frame_axi.snr").read_bytes())
    new = reports["raw_frame_axi_03"]["resource_summary"]
    command = ["powershell.exe", "-NoProfile", "-Command",
        "$items=@(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Path); "
        "ConvertTo-Json -InputObject $items -Compress"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    processes = json.loads(result.stdout.strip() or "[]")
    write_json(ROOT / "final_process_check.json", {"timestamp": stamp(), "command": command,
        "processes": processes, "stderr": result.stderr})
    summary = {"audited": stamp(), "components": {f: r["resource_summary"] for f, r in reports.items()},
        "all_component_audits_pass": all(r["audit_pass"] for r in reports.values()),
        "all_five_source_hashes_unchanged": all(r["source_hashes_unchanged"] for r in reports.values()),
        "historical_02_unchanged": previous == current,
        "bridge_03_minus_historical_02": {k: new[k] - old[k] for k in new},
        "separate_component_arithmetic_sum": {k: sum(r["resource_summary"][k] for r in reports.values())
            for k in ["lut", "registers", "latches", "drm", "apm"]},
        "integrated_core_synthesized": False, "board_acceptance": False,
        "pds_processes_clear": not processes}
    write_json(ROOT / "subset_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
