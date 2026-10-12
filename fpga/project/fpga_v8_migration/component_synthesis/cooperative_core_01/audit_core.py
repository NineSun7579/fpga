"""Capture before/after evidence for the integrated core without changing RTL."""
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

WORK = Path(__file__).resolve().parent
EXPECTED = json.loads((WORK / "expected_inputs.json").read_text(encoding="utf-8"))
TOP = EXPECTED["top"]


def stamp():
    return datetime.datetime.now().astimezone().isoformat()


def save(name, value):
    (WORK / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def historical_files():
    records = []
    for folder in EXPECTED["historical_projects_immutable"]:
        for path in sorted((WORK / folder).rglob("*")):
            if path.is_file():
                data = path.read_bytes()
                records.append({"path": path.relative_to(WORK.parent).as_posix(),
                    "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return records


def sources():
    records = []
    for source in EXPECTED["sources"]:
        data = (WORK / source["path"]).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        records.append({"path": source["path"], "bytes": len(data), "sha256": sha,
            "ascii": data.isascii(), "unchanged": sha == source["sha256"] and len(data) == source["bytes"]})
    return records


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


def binding_audit():
    definitions = {}
    for source in EXPECTED["sources"]:
        data = (WORK / source["path"]).read_bytes()
        data = re.sub(rb"//[^\r\n]*|/\*.*?\*/", b"", data, flags=re.S)
        match = re.search(rb"\bmodule\s+(\w+)\s*", data)
        if not match:
            raise RuntimeError("No module definition in " + source["path"])
        name = match[1].decode("ascii")
        position = match.end()
        parameters = b""
        if data[position:position+1] == b"#":
            parameters, position = group(data, data.index(b"(", position))
        ports, end = group(data, data.index(b"(", position))
        port_names = [re.search(rb"(\w+)\s*$", field)[1].decode("ascii") for field in ports.split(b",")]
        if name in definitions or len(port_names) != len(set(port_names)):
            raise RuntimeError("Duplicate declaration")
        definitions[name] = {"source": source["path"], "data": data,
            "port_names": port_names, "parameter_declarations": parameters.decode("ascii"),
            "port_declarations": ports.decode("ascii")}
    instances = []
    for owner, definition in definitions.items():
        data = definition["data"]
        for module_type, child in definitions.items():
            if module_type == owner:
                continue
            for match in re.finditer(rb"\b" + module_type.encode("ascii") + rb"\s*", data):
                position = match.end()
                overrides = b""
                if data[position:position+1] == b"#":
                    overrides, position = group(data, data.index(b"(", position))
                tail = re.match(rb"\s*(\w+)\s*\(", data[position:])
                if not tail:
                    continue
                instance = tail[1].decode("ascii")
                bindings, end = group(data, position + tail.end()-1)
                names = []
                opens = []
                for bind in re.finditer(rb"\.(\w+)\s*\(", bindings):
                    name = bind[1].decode("ascii")
                    value, _ = group(bindings, bind.end()-1)
                    names.append(name)
                    if not value.strip():
                        opens.append(name)
                missing = sorted(set(child["port_names"]) - set(names))
                unknown = sorted(set(names) - set(child["port_names"]))
                duplicate = sorted(n for n, count in Counter(names).items() if count > 1)
                instances.append({"owner": owner, "instance": instance, "module_type": module_type,
                    "bindings": len(names), "expected_ports": len(child["port_names"]),
                    "missing": missing, "unknown": unknown, "duplicate": duplicate,
                    "explicitly_open": opens, "parameter_overrides": overrides.decode("ascii")})
    expected_instances = {"control", "bridge", "write_arbiter", "raw_pipeline", "output_packer"}
    complete = set(i["instance"] for i in instances) == expected_instances and all(
        not i["missing"] and not i["unknown"] and not i["duplicate"] for i in instances)
    signature = {"top": TOP, "top_parameter_declarations": definitions[TOP]["parameter_declarations"],
        "top_port_declarations": definitions[TOP]["port_declarations"],
        "top_ports": definitions[TOP]["port_names"], "modules": list(definitions),
        "instances": instances, "complete_named_bindings": complete,
        "OUTPUT_LENGTH_expression": EXPECTED["output_length_expression"],
        "OUTPUT_LENGTH_at_defaults": 3 * EXPECTED["parameters"]["WIDTH"] * EXPECTED["parameters"]["OUT_HEIGHT"]}
    if not complete:
        raise RuntimeError("Incomplete source module binding")
    return signature


def category(line):
    for fragment, name in [
        ("The license will invalid", "license_expiry"),
        ("Loop was found during constant probe", "constant_probe_loop"),
        ("Public-4008", "dangling_instance_cleaned"),
        ("stuck at constant", "constant_register_removed"),
        ("Unable to honor max fanout", "max_fanout_not_honored"),
        ("prevent name conflict", "net_renamed"),
        ("The design has", "io_count_exceeds_physical_package"),
        ("Timing-4087", "unconstrained_output"),
        ("Timing-4086", "unconstrained_input")]:
        if fragment in line:
            return name
    return line


def before():
    if (WORK / "historical_projects_before.json").exists():
        raise RuntimeError("Refusing to overwrite initial evidence")
    records = sources()
    if not all(s["unchanged"] and s["ascii"] for s in records):
        raise RuntimeError("Six-source hash/ASCII check failed")
    save("source_signature_before.json", {"timestamp": stamp(), "sources": records,
        "binding_audit": binding_audit()})
    save("historical_projects_before.json", {"timestamp": stamp(), "files": historical_files()})
    print("Six pinned ASCII sources and all five dependency bindings verified; historical projects snapshotted.")


def after():
    result = {"timestamp": stamp(), "top": TOP, "diagnostics": {}}
    extracted = []
    elaborated = {}
    for name in ["compile_stdout.log", "compile_stderr.log", "synthesize_stdout.log", "synthesize_stderr.log"]:
        data = (WORK / name).read_bytes()
        warnings = []
        errors = []
        for number, raw in enumerate(data.splitlines(), 1):
            if raw.startswith((b"W:", b"E:")):
                message = raw.decode("ascii", errors="backslashreplace")
                record = {"line": number, "message": message}
                (warnings if raw.startswith(b"W:") else errors).append(record)
                extracted.append(f"{name}:{number}: {message}")
        result["diagnostics"][name] = {"warnings": len(warnings), "errors": len(errors),
            "warning_categories": dict(Counter(category(w["message"]) for w in warnings)),
            "width_or_truncation_diagnostics": [w for w in warnings + errors if re.search(
                r"width|truncat|extend", w["message"], re.I)],
            "latch_diagnostics": [w for w in warnings + errors if "latch" in w["message"].lower()],
            "missing_module_or_blackbox_diagnostics": [w for w in warnings + errors if re.search(
                r"black.?box|missing.*module|module.*not found|unresolved.*module", w["message"], re.I)]}
        if name == "synthesize_stdout.log":
            for match in re.finditer(rb"Module instance \{([^}]+)\} parameter value:\s*", data):
                values = {}
                for raw in data[match.end():].splitlines():
                    if not raw.strip():
                        continue
                    assignment = re.match(rb"\s*(\w+)\s*=\s*\d+'b([01]+)\s*$", raw)
                    if not assignment:
                        break
                    values[assignment[1].decode("ascii")] = int(assignment[2], 2)
                elaborated[match[1].decode("ascii")] = values
            result["analyzed_modules"] = sorted(set(m.decode("ascii") for m in re.findall(
                rb"Analyzing module (\w+) \(library work\)", data)))
            result["elaborated_modules"] = sorted(set(m.decode("ascii") for m in re.findall(
                rb"Elaborating module (\w+)\s", data)))
            result["selected_tops"] = [m.decode("ascii") for m in re.findall(
                rb'Module "([^"]+)" is set as top module', data)]
    (WORK / "diagnostics_extracted.txt").write_text("\n".join(extracted) + "\n", encoding="utf-8")
    result["elaborated_parameters"] = elaborated
    result["top_parameters_match"] = elaborated.get(TOP) == EXPECTED["parameters"]
    result["derived_output_length_matches"] = (
        elaborated.get(TOP + "/control", {}).get("OUTPUT_LENGTH") == EXPECTED["derived_output_length"])
    result["fixed_bridge_id_width_matches"] = elaborated.get(TOP + "/bridge", {}).get("ID_WIDTH") == 4
    result["fixed_arbiter_parameters_match"] = elaborated.get(TOP + "/write_arbiter") == {
        "MASTER_COUNT": 7, "ID_WIDTH": 4, "ADDR_WIDTH": 32, "DATA_WIDTH": 128, "OWNER_WIDTH": 3}
    snr = (WORK / "synthesize" / (TOP + ".snr")).read_bytes()
    cells = {}
    for line in snr.splitlines():
        match = re.match(rb"^(GTP_\w+)\s+(\d+)\s+uses?\s*$", line)
        if match:
            cells[match[1].decode("ascii")] = int(match[2])
    vm = (WORK / "synthesize" / (TOP + "_syn.vm")).read_bytes()
    vm_counts = Counter(m.decode("ascii") for m in re.findall(
        rb"\b(GTP_\w+)\s+(?:/\*.*?\*/\s*)?(?:#\s*\(|(?:\\[^\s]+|\w+)\s*\()", vm, re.S))
    result["cells_from_snr"] = cells
    result["cells_from_netlist"] = dict(sorted(vm_counts.items()))
    result["cell_counts_match"] = cells == dict(vm_counts)
    resources = {}
    for key, pattern in {
        "lut": rb"Total LUTs:\s+(\d+)", "registers": rb"Total Registers:\s+(\d+)",
        "latches": rb"Total Latches:\s+(\d+)", "drm": rb"Total DRM\s*=\s*([\d.]+)",
        "apm": rb"Total APMs\s*=\s*([\d.]+)", "io_bits": rb"Total I/O ports\s*=\s*(\d+)"}.items():
        match = re.search(pattern, snr)
        resources[key] = float(match[1]) if key in ["drm", "apm"] else int(match[1])
    result["resource_summary"] = resources
    virtual_buffers = len(re.findall(
        rb'\(\*\s*PAP_IS_VIRTUAL_IO="TRUE"\s*\*\)\s*GTP_(?:INBUF|OUTBUF)', vm))
    result["virtual_io_buffer_instances"] = virtual_buffers
    result["all_io_buffers_virtual"] = virtual_buffers == resources["io_bits"]
    result["sources_after_all_runs"] = sources()
    result["all_six_sources_unchanged_ascii"] = all(
        s["unchanged"] and s["ascii"] for s in result["sources_after_all_runs"])
    result["binding_audit"] = binding_audit()
    prior = json.loads((WORK / "historical_projects_before.json").read_text(encoding="utf-8"))
    historical = historical_files()
    result["historical_projects_unchanged"] = historical == prior["files"]
    result["historical_file_count"] = len(historical)
    result["forbidden_stage_directories_present"] = [d for d in
        ["device_map", "place_route", "generate_bitstream", "generate_netlist", "report_timing", "report_power"]
        if (WORK / d).exists()]
    result["bitstream_files_present"] = [p.relative_to(WORK).as_posix() for p in WORK.rglob("*")
        if p.is_file() and p.suffix.lower() in [".sbit", ".bit", ".smsk"]]
    run = json.loads((WORK / "run_results.json").read_text(encoding="utf-8"))
    result["both_stages_returned_zero"] = len(run["stages"]) == 2 and all(
        s["returncode"] == 0 and s["expected_database_present"] for s in run["stages"])
    result["artifacts"] = []
    for relative in ["compile/" + TOP + "_comp.adf", "compile/" + TOP + ".cmr",
        "synthesize/" + TOP + "_syn.adf", "synthesize/" + TOP + "_syn.vm",
        "synthesize/" + TOP + ".snr", "compile_stdout.log", "synthesize_stdout.log"]:
        data = (WORK / relative).read_bytes()
        result["artifacts"].append({"path": relative, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()})
    command = ["powershell.exe", "-NoProfile", "-Command",
        "$items=@(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Path); "
        "ConvertTo-Json -InputObject $items -Compress"]
    check = subprocess.run(command, cwd=WORK, capture_output=True, text=True, check=True)
    processes = json.loads(check.stdout.strip() or "[]")
    save("process_check_after_audit.json", {"timestamp": stamp(), "command": command,
        "processes": processes, "stderr": check.stderr})
    result["pds_processes_clear"] = not processes
    expected_modules = sorted(result["binding_audit"]["modules"])
    result["all_six_modules_analyzed_and_elaborated"] = (
        result["analyzed_modules"] == expected_modules and result["elaborated_modules"] == expected_modules)
    result["audit_pass"] = all([
        result["top_parameters_match"], result["derived_output_length_matches"],
        result["fixed_bridge_id_width_matches"], result["fixed_arbiter_parameters_match"],
        result["selected_tops"] == [TOP], result["all_six_modules_analyzed_and_elaborated"],
        result["cell_counts_match"], result["all_io_buffers_virtual"],
        result["all_six_sources_unchanged_ascii"], result["historical_projects_unchanged"],
        result["binding_audit"]["complete_named_bindings"], result["both_stages_returned_zero"],
        not result["forbidden_stage_directories_present"], not result["bitstream_files_present"],
        all(d["errors"] == 0 and not d["missing_module_or_blackbox_diagnostics"]
            for d in result["diagnostics"].values())])
    save("output_audit.json", result)
    print(json.dumps({k: result[k] for k in ["audit_pass", "resource_summary", "cells_from_snr",
        "elaborated_parameters", "historical_projects_unchanged", "historical_file_count", "diagnostics"]}, indent=2))
    if not result["audit_pass"]:
        raise RuntimeError("Integrated core output audit failed")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["before", "after"]:
        raise RuntimeError("Usage: audit_core.py before|after")
    before() if sys.argv[1] == "before" else after()
