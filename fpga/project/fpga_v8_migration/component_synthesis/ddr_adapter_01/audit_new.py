"""Audit the two new isolated synthesis projects; never invoke or edit PDS/RTL.

Usage: audit_new.py before|after ddr_adapter_01|endpoint_ctrl_01
       audit_new.py module-scan
       audit_new.py final
All generated evidence stays in the two new directories.
"""
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
NEW = {"ddr_adapter_01", "endpoint_ctrl_01"}


def stamp():
    return datetime.datetime.now().astimezone().isoformat()


def save(work, name, value):
    (work / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def record(path, relative):
    data = path.read_bytes()
    return {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def historical_files():
    # Root REPORT.md is the one authorized mutable historical file.
    return [record(p, p.relative_to(ROOT).as_posix()) for p in sorted(ROOT.rglob("*"))
        if p.is_file() and p.relative_to(ROOT).parts[0] not in NEW
        and p.relative_to(ROOT).as_posix() != "REPORT.md"]


def inputs(work, expected):
    result = []
    for source in expected["sources"]:
        data = (work / source["path"]).read_bytes()
        item = record(work / source["path"], source["path"])
        item.update(ascii=data.isascii(), unchanged=(item["sha256"] == source["sha256"]
            and item["bytes"] == source["bytes"]))
        result.append(item)
    return result


def process_check(work, label):
    command = ["powershell.exe", "-NoProfile", "-Command",
        "$auditPdsItems=@(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | "
        "Select-Object Id,ProcessName,Path); ConvertTo-Json -InputObject $auditPdsItems -Compress"]
    check = subprocess.run(command, cwd=work, capture_output=True, text=True, check=True)
    processes = json.loads(check.stdout.strip() or "[]")
    result = {"timestamp": stamp(), "command": command, "processes": processes, "stderr": check.stderr}
    save(work, "process_check_" + label + ".json", result)
    if processes:
        raise RuntimeError("BLOCKED: another PDS GUI/shell exists; no process was modified")
    return result


def group(data, start):
    if data[start:start+1] != b"(":
        raise RuntimeError("Expected opening parenthesis")
    depth = 0
    for index in range(start, len(data)):
        if data[index:index+1] == b"(":
            depth += 1
        elif data[index:index+1] == b")":
            depth -= 1
            if depth == 0:
                return data[start+1:index], index+1
    raise RuntimeError("Unbalanced source group")


def bindings(work, expected):
    definitions = {}
    for source in expected["sources"]:
        data = (work / source["path"]).read_bytes()
        data = re.sub(rb"//[^\r\n]*|/\*.*?\*/", b"", data, flags=re.S)
        match = re.search(rb"\bmodule\s+(\w+)\s*", data)
        name = match[1].decode("ascii")
        position = match.end()
        params = b""
        if data[position:position+1] == b"#":
            params, position = group(data, data.index(b"(", position))
        ports, end = group(data, data.index(b"(", position))
        names = [re.search(rb"(\w+)\s*$", field)[1].decode("ascii") for field in ports.split(b",")]
        if name in definitions or len(names) != len(set(names)):
            raise RuntimeError("Duplicate declaration")
        definitions[name] = {"source": source["path"], "data": data, "ports": names,
            "parameter_declarations": params.decode("ascii"), "port_declarations": ports.decode("ascii")}
    instances = []
    for owner, definition in definitions.items():
        data = definition["data"]
        for kind, child in definitions.items():
            if kind == owner:
                continue
            for match in re.finditer(rb"\b" + kind.encode("ascii") + rb"\s*", data):
                position = match.end()
                overrides = b""
                if data[position:position+1] == b"#":
                    overrides, position = group(data, data.index(b"(", position))
                tail = re.match(rb"\s*(\w+)\s*\(", data[position:])
                if not tail:
                    continue
                port_group, _ = group(data, position + tail.end()-1)
                port_bindings = {}
                duplicates = []
                for bind in re.finditer(rb"\.(\w+)\s*\(", port_group):
                    port = bind[1].decode("ascii")
                    value, _ = group(port_group, bind.end()-1)
                    if port in port_bindings:
                        duplicates.append(port)
                    port_bindings[port] = value.decode("ascii").strip()
                instances.append({"owner": owner, "module_type": kind,
                    "instance": tail[1].decode("ascii"), "bindings": port_bindings,
                    "expected_ports": len(child["ports"]),
                    "omitted_ports": sorted(set(child["ports"]) - set(port_bindings)),
                    "unknown_ports": sorted(set(port_bindings) - set(child["ports"])),
                    "duplicate_ports": duplicates,
                    "explicitly_open_ports": [p for p, value in port_bindings.items() if not value],
                    "parameter_overrides": overrides.decode("ascii")})
    top = expected["top"]
    roots = sorted(set(definitions) - {i["module_type"] for i in instances})
    result = {"top": top, "uninstantiated_roots": roots, "modules": list(definitions),
        "top_ports": definitions[top]["ports"],
        "top_parameter_declarations": definitions[top]["parameter_declarations"],
        "top_port_declarations": definitions[top]["port_declarations"], "instances": instances}
    result["binding_names_valid"] = roots == [top] and all(
        not i["unknown_ports"] and not i["duplicate_ports"] for i in instances)
    if top == "fpga_v8_endpoint_ctrl_synth":
        endpoint, control = (next(i for i in instances if i["instance"] == name) for name in ["endpoint", "control"])
        local = {port.removeprefix("m_axil_"): value for port, value in endpoint["bindings"].items()
            if port.startswith("m_axil_")}
        same = len(local) == 19 and all(control["bindings"]["s_axil_" + port] == value
            for port, value in local.items())
        passthrough = all(value == ("clk" if port == "core_clk" else port)
            for instance in [endpoint, control] for port, value in instance["bindings"].items()
            if not port.startswith(("m_axil_", "s_axil_")))
        result["direct_19_signal_axil_link"] = same
        result["all_other_ports_directly_exposed"] = passthrough
        result["wrapper_wiring_only"] = not re.search(rb"\b(?:always|initial|assign|force)\b", definitions[top]["data"])
        result["binding_names_valid"] &= all([same, passthrough, result["wrapper_wiring_only"],
            len(instances) == 2, all(not i["omitted_ports"] and not i["explicitly_open_ports"] for i in instances)])
    else:
        # Generated wrappers deliberately omit disabled FIFO water-level outputs.
        result["binding_names_valid"] &= len(instances) == 8 and all(
            set(i["omitted_ports"]) <= {"rd_water_level", "wr_water_level"} for i in instances)
        fifo_metadata = {}
        for name in ["ddr_fifo16_w", "ddr_fifo16_r"]:
            metadata = {}
            for match in re.finditer(rb"\blocalparam\s+(\w+)\s*=\s*(\d+|\"[^\"]*\")\s*;", definitions[name]["data"]):
                value = match[2].decode("ascii")
                metadata[match[1].decode("ascii")] = value.strip('"') if value.startswith('"') else int(value)
            fifo_metadata[name] = metadata
        result["generated_fifo_metadata"] = fifo_metadata
        adapter = definitions[top]["data"]
        result["fixed_limits_in_source"] = all(re.search(pattern, adapter) for pattern in [
            rb"s_awlen\s*<=\s*15", rb"s_arlen\s*<=\s*15",
            rb"input\s+wire\s*\[3:0\]\s*s_awid", rb"input\s+wire\s*\[6:0\]\s*s_arid"])
        result["binding_names_valid"] &= result["fixed_limits_in_source"]
    if not result["binding_names_valid"]:
        raise RuntimeError("Source binding or interface audit failed")
    return result


def before(work, expected):
    if (work / "historical_files_before.json").exists():
        raise RuntimeError("Refusing to overwrite initial evidence")
    process_check(work, "before_audit")
    records = inputs(work, expected)
    if not all(s["unchanged"] and s["ascii"] for s in records):
        raise RuntimeError("Pinned source hash/ASCII check failed")
    signature = bindings(work, expected)
    if work.name == "ddr_adapter_01":
        sim = json.loads((work / expected["fifo_simulation_hash_evidence_read_only"]).read_text(encoding="utf-8"))
        project = ROOT.parent.parent
        signature["all_fifo_hashes_match_simulation_compile_list"] = all(
            sim["source_sha256"][(work / s["path"]).resolve().relative_to(project).as_posix()] == s["sha256"]
            for s in expected["sources"][1:])
        assert signature["all_fifo_hashes_match_simulation_compile_list"]
    save(work, "source_signature_before.json", {"timestamp": stamp(), "sources": records, "binding_audit": signature})
    history = historical_files()
    save(work, "historical_files_before.json", {"timestamp": stamp(), "files": history})
    print(f"{work.name}: {len(records)} pinned ASCII sources, {len(signature['instances'])} dependency instances, "
        f"{len(history)} immutable historical files verified; PDS clear.")


def category(line):
    for fragment, name in [
        ("The license will invalid", "license_expiry"),
        ("Loop was found during constant probe", "constant_probe_loop"),
        ("does not have a driver, tie it to 0", "undriven_net_tied_zero"),
        ("Public-4008", "dangling_instance_cleaned"),
        ("stuck at constant", "constant_register_removed"),
        ("Unable to honor max fanout", "max_fanout_not_honored"),
        ("syn_maxfan", "max_fanout_cell_not_replicated"),
        ("prevent name conflict", "net_renamed"),
        ("The design has", "io_count_exceeds_physical_package"),
        ("Timing-4087", "unconstrained_output"),
        ("Timing-4086", "unconstrained_input"),
        ("not connected", "unconnected_port")]:
        if fragment in line:
            return name
    return line


def after(work, expected):
    top = expected["top"]
    result = {"timestamp": stamp(), "top": top, "diagnostics": {}}
    extracted = []
    elaborated = {}
    for name in ["compile_stdout.log", "compile_stderr.log", "synthesize_stdout.log", "synthesize_stderr.log"]:
        data = (work / name).read_bytes()
        warnings, errors = [], []
        for number, raw in enumerate(data.splitlines(), 1):
            if raw.startswith((b"W:", b"E:")):
                message = raw.decode("ascii", errors="backslashreplace")
                item = {"line": number, "message": message}
                (warnings if raw.startswith(b"W:") else errors).append(item)
                extracted.append(f"{name}:{number}: {message}")
        result["diagnostics"][name] = {"warnings": len(warnings), "errors": len(errors),
            "warning_categories": dict(Counter(category(w["message"]) for w in warnings)),
            "width_or_truncation_diagnostics": [w for w in warnings + errors if re.search(r"width|truncat|extend", w["message"], re.I)],
            "latch_diagnostics": [w for w in warnings + errors if "latch" in w["message"].lower()],
            "undriven_net_diagnostics": [w for w in warnings + errors if "does not have a driver" in w["message"]],
            "missing_module_or_blackbox_diagnostics": [w for w in warnings + errors if re.search(
                r"black.?box|missing.*module|module.*not found|unresolved.*module", w["message"], re.I)]}
        if name != "synthesize_stdout.log":
            continue
        result["analyzed_modules"] = sorted(set(m.decode("ascii") for m in re.findall(rb"Analyzing module (\w+) \(library work\)", data)))
        result["elaborated_modules"] = sorted(set(m.decode("ascii") for m in re.findall(rb"Elaborating module (\w+)\s", data)))
        result["selected_tops"] = [m.decode("ascii") for m in re.findall(rb'Module "([^"]+)" is set as top module', data)]
        for match in re.finditer(rb"Module instance \{([^}]+)\} parameter value:\s*", data):
            values = {}
            for raw in data[match.end():].splitlines():
                if not raw.strip():
                    continue
                assignment = re.match(rb"\s*(\w+)\s*=\s*(\d+)'b([01]+)\s*$", raw)
                if not assignment:
                    text_assignment = re.match(rb"\s*(\w+)\s*=\s*([A-Z_]+)\s*$", raw)
                    if text_assignment:
                        values[text_assignment[1].decode("ascii")] = text_assignment[2].decode("ascii")
                        continue
                    break
                key = assignment[1].decode("ascii")
                value = int(assignment[3], 2)
                if key in ["RST_TYPE", "FIFO_TYPE", "INIT_FILE", "FILE_FORMAT"]:
                    value = value.to_bytes((int(assignment[2])+7)//8, "big").lstrip(b"\0").decode("ascii")
                values[key] = value
            elaborated[match[1].decode("ascii")] = values
    (work / "diagnostics_extracted.txt").write_text("\n".join(extracted) + "\n", encoding="utf-8")
    result["elaborated_parameters"] = elaborated
    result["top_parameters_match"] = elaborated.get(top) == expected["parameters"]
    result["child_parameters_match"] = all(elaborated.get(top + "/" + child) == params
        for child, params in expected.get("expected_child_parameters", {}).items())
    if work.name == "ddr_adapter_01":
        matched = []
        for side, width in [("w", 144), ("r", 133)]:
            path = f"{top}/{'write' if side == 'w' else 'read'}_fifo/u_ipm_distributed_fifo_ddr_fifo16_{side}"
            matched.append(elaborated.get(path) == {"ADDR_WIDTH": 4, "DATA_WIDTH": width,
                "RST_TYPE": "SYNC", "OUT_REG": 0, "FIFO_TYPE": "SYNC_FIFO",
                "ALMOST_FULL_NUM": 11, "ALMOST_EMPTY_NUM": 4})
            matched.append(elaborated.get(path + f"/ipm_distributed_sdpram_ddr_fifo16_{side}") == {
                "ADDR_WIDTH": 4, "DATA_WIDTH": width, "RST_TYPE": "SYNC", "OUT_REG": 0,
                "INIT_FILE": "NONE", "FILE_FORMAT": "BIN"})
            matched.append(elaborated.get(path + f"/u_ipm_distributed_fifo_ctr_ddr_fifo16_{side}") == {
                "DEPTH": 4, "FIFO_TYPE": "SYNC_FIFO", "ALMOST_FULL_NUM": 11, "ALMOST_EMPTY_NUM": 4})
        result["actual_fifo_parameters_match"] = all(matched)
    snr = (work / "synthesize" / (top + ".snr")).read_bytes()
    cells = {}
    for line in snr.splitlines():
        match = re.match(rb"^(GTP_\w+)\s+(\d+)\s+uses?\s*$", line)
        if match:
            cells[match[1].decode("ascii")] = int(match[2])
    vm = (work / "synthesize" / (top + "_syn.vm")).read_bytes()
    counts = Counter(m.decode("ascii") for m in re.findall(
        rb"\b(GTP_\w+)\s+(?:/\*.*?\*/\s*)?(?:#\s*\(|(?:\\[^\s]+|\w+)\s*\()", vm, re.S))
    result["cells_from_snr"] = cells
    result["cells_from_netlist"] = dict(sorted(counts.items()))
    result["cell_counts_match"] = cells == dict(counts)
    resources = {}
    for key, pattern in {"lut": rb"Total LUTs:\s+(\d+)", "registers": rb"Total Registers:\s+(\d+)",
        "distributed_ram_luts": rb"LUTs as dram:\s+(\d+)", "logic_luts": rb"LUTs as logic:\s+(\d+)",
        "latches": rb"Total Latches:\s+(\d+)", "drm": rb"Total DRM\s*=\s*([\d.]+)",
        "apm": rb"Total APMs\s*=\s*([\d.]+)", "io_bits": rb"Total I/O ports\s*=\s*(\d+)"}.items():
        match = re.search(pattern, snr)
        resources[key] = float(match[1]) if key in ["drm", "apm"] else int(match[1])
    result["resource_summary"] = resources
    result["lut_usage_components_match"] = resources["lut"] == resources["logic_luts"] + resources["distributed_ram_luts"]
    result["distributed_ram_summary_lines"] = [line.decode("ascii") for line in snr.splitlines() if b"Distributed" in line or b"distributed" in line]
    virtual = len(re.findall(rb'\(\*\s*PAP_IS_VIRTUAL_IO="TRUE"\s*\*\)\s*GTP_(?:INBUF|OUTBUF)', vm))
    result["virtual_io_buffer_instances"] = virtual
    result["all_io_buffers_virtual"] = virtual == resources["io_bits"]
    result["sources_after_all_runs"] = inputs(work, expected)
    result["all_sources_unchanged_ascii"] = all(s["unchanged"] and s["ascii"] for s in result["sources_after_all_runs"])
    result["binding_audit"] = bindings(work, expected)
    history = historical_files()
    prior = json.loads((work / "historical_files_before.json").read_text(encoding="utf-8"))["files"]
    result["all_historical_files_unchanged"] = history == prior
    result["historical_file_count"] = len(history)
    result["forbidden_stage_directories_present"] = [d for d in ["device_map", "place_route", "generate_bitstream",
        "generate_netlist", "report_timing", "report_power"] if (work / d).exists()]
    result["bitstream_files_present"] = [p.relative_to(work).as_posix() for p in work.rglob("*") if p.is_file()
        and p.suffix.lower() in [".sbit", ".bit", ".smsk"]]
    run = json.loads((work / "run_results.json").read_text(encoding="utf-8"))
    result["both_stages_returned_zero"] = run.get("status") == "success" and [s["stage"] for s in run["stages"]] == ["compile", "synthesize"] and all(
        s["returncode"] == 0 and s["source_hashes_unchanged"] and s["expected_database_present"] for s in run["stages"])
    result["artifacts"] = [record(work / path, path) for path in ["compile/" + top + "_comp.adf", "compile/" + top + ".cmr",
        "synthesize/" + top + "_syn.adf", "synthesize/" + top + "_syn.vm", "synthesize/" + top + ".snr",
        "compile_stdout.log", "synthesize_stdout.log"]]
    process_check(work, "after_audit")
    modules = sorted(result["binding_audit"]["modules"])
    result["all_registered_modules_analyzed_and_elaborated"] = result["analyzed_modules"] == modules and result["elaborated_modules"] == modules
    result["audit_scope"] = "compile/synthesis artifacts, binding, parameters, mapped resources, virtual IO and integrity"
    result["synthesized_functional_equivalence_proven"] = False
    result["audit_pass"] = all([result["top_parameters_match"], result["child_parameters_match"],
        result.get("actual_fifo_parameters_match", True), result["cell_counts_match"], result["all_io_buffers_virtual"],
        result["lut_usage_components_match"],
        result["all_sources_unchanged_ascii"], result["all_historical_files_unchanged"], result["binding_audit"]["binding_names_valid"],
        result["all_registered_modules_analyzed_and_elaborated"], result["selected_tops"] == [top],
        result["both_stages_returned_zero"], not result["forbidden_stage_directories_present"], not result["bitstream_files_present"],
        all(d["errors"] == 0 and not d["missing_module_or_blackbox_diagnostics"] for d in result["diagnostics"].values())])
    previous_path = work / "output_audit.json"
    if previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        if not previous["audit_pass"] and not (work / "output_audit_initial_parser.json").exists():
            save(work, "output_audit_initial_parser.json", previous)
    save(work, "output_audit.json", result)
    print(json.dumps({key: result[key] for key in ["audit_pass", "resource_summary", "cells_from_snr",
        "elaborated_parameters", "all_historical_files_unchanged", "historical_file_count", "diagnostics"]}, indent=2))
    if not result["audit_pass"]:
        raise RuntimeError("Output audit failed; raw evidence retained")


def module_scan():
    work = ROOT / "endpoint_ctrl_01"
    name = b"fpga_v8_endpoint_ctrl_synth"
    declarations = []
    scanned = 0
    project = ROOT.parent.parent
    for path in project.rglob("*"):
        if path.suffix.lower() not in [".v", ".sv"] or not path.is_file():
            continue
        scanned += 1
        data = path.read_bytes()
        data = re.sub(rb"//[^\r\n]*|/\*.*?\*/", b"", data, flags=re.S)
        for match in re.finditer(rb"\bmodule\s+" + name + rb"\b", data):
            declarations.append(path.relative_to(project).as_posix())
    result = {"timestamp": stamp(), "module": name.decode("ascii"), "rtl_files_scanned_as_bytes": scanned,
        "declarations": declarations, "unique": len(declarations) == 1}
    save(work, "wrapper_module_scan.json", result)
    print(json.dumps(result, indent=2))
    if not result["unique"]:
        raise RuntimeError("Synthesis wrapper module name is not unique")


def final():
    work = ROOT / "endpoint_ctrl_01"
    save(work, "final_verification.json", {"timestamp": stamp(), "status": "in_progress"})
    result = {"timestamp": stamp(), "projects": {}}
    for name in sorted(NEW):
        folder = ROOT / name
        expected = json.loads((folder / "expected_inputs.json").read_text(encoding="utf-8"))
        audited = json.loads((folder / "output_audit.json").read_text(encoding="utf-8"))
        sources = inputs(folder, expected)
        result["projects"][name] = {"top": expected["top"], "resources": audited["resource_summary"],
            "audit_pass": audited["audit_pass"], "sources": sources,
            "warning_review": json.loads((folder / "warning_review.json").read_text(encoding="utf-8")),
            "all_sources_unchanged_ascii": all(s["unchanged"] and s["ascii"] for s in sources),
            "artifacts_unchanged": all(record(folder / a["path"], a["path"]) == a for a in audited["artifacts"])}
    prior = json.loads((ROOT / "ddr_adapter_01/historical_files_before.json").read_text(encoding="utf-8"))["files"]
    result["all_historical_files_unchanged"] = historical_files() == prior
    result["historical_file_count"] = len(prior)
    runs = [json.loads((ROOT / name / "run_results.json").read_text(encoding="utf-8")) for name in ["ddr_adapter_01", "endpoint_ctrl_01"]]
    stages = [stage for run in runs for stage in run["stages"]]
    result["sequential_stage_intervals"] = [{k: s[k] for k in ["stage", "started", "finished", "returncode", "cwd"]} for s in stages]
    result["all_four_stages_sequential"] = all(a["finished"] <= b["started"] for a, b in zip(stages, stages[1:]))
    process_check(work, "final_audit")
    report = ROOT / "REPORT.md"
    result["report"] = record(report, "REPORT.md")
    result["report_links_exist"] = all((ROOT / target).is_file() for target in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")))
    result["wrapper_module_unique"] = json.loads((work / "wrapper_module_scan.json").read_text(encoding="utf-8"))["unique"]
    result["verification_pass"] = all([result["all_historical_files_unchanged"], result["all_four_stages_sequential"],
        result["report_links_exist"], result["wrapper_module_unique"], all(p["audit_pass"] and p["all_sources_unchanged_ascii"] and p["artifacts_unchanged"]
            for p in result["projects"].values())])
    save(work, "final_verification.json", result)
    print(json.dumps(result, indent=2))
    if not result["verification_pass"]:
        raise RuntimeError("Final verification failed")


if __name__ == "__main__":
    if sys.argv[1:] == ["module-scan"]:
        module_scan()
    elif sys.argv[1:] == ["final"]:
        final()
    elif len(sys.argv) == 3 and sys.argv[1] in ["before", "after"] and sys.argv[2] in NEW:
        folder = ROOT / sys.argv[2]
        expected = json.loads((folder / "expected_inputs.json").read_text(encoding="utf-8"))
        (before if sys.argv[1] == "before" else after)(folder, expected)
    else:
        raise RuntimeError("Usage: audit_new.py before|after project_name, or final")
