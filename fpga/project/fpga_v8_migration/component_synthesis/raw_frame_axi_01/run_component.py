"""Run an isolated two-stage PDS component build and retain machine evidence."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


WORK = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else Path(__file__).resolve().parent
PDS = Path("C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe")
EXPECTED = json.loads((WORK / "expected_inputs.json").read_text(encoding="utf-8"))


def stamp():
    return datetime.datetime.now().astimezone().isoformat()


def save(name, value):
    (WORK / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def inputs():
    records = []
    for source in EXPECTED["sources"]:
        path = (WORK / source["path"]).resolve()
        data = path.read_bytes()
        record = dict(source)
        record.update(absolute_path=str(path), actual_bytes=len(data),
                      actual_sha256=hashlib.sha256(data).hexdigest())
        record["unchanged"] = (record["actual_bytes"] == source["bytes"] and
                               record["actual_sha256"] == source["sha256"])
        records.append(record)
    return {"timestamp": stamp(), "sources": records,
            "all_unchanged": all(r["unchanged"] for r in records)}


def check_processes(stage):
    command = ["powershell.exe", "-NoProfile", "-Command",
               "$items=@(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | "
               "Select-Object Id,ProcessName,Path); ConvertTo-Json -InputObject $items -Compress"]
    result = subprocess.run(command, cwd=WORK, capture_output=True, text=True, check=True)
    processes = json.loads(result.stdout.strip() or "[]")
    save("process_check_" + stage + ".json", {"timestamp": stamp(),
         "command": command, "processes": processes, "stderr": result.stderr})
    if processes:
        raise RuntimeError("BLOCKED: another PDS GUI/shell exists; no process was modified")


def verify_registration():
    data = (WORK / "project.pds").read_bytes()
    registered = re.findall(rb'\(_file\s+"([^"]+\.v)"', data)
    if [p.decode("ascii") for p in registered] != [s["path"] for s in EXPECTED["sources"]]:
        raise RuntimeError("PDS source registration differs from exact three-source manifest")
    modules = {}
    for source in EXPECTED["sources"]:
        raw = (WORK / source["path"]).read_bytes()
        raw = re.sub(rb"//[^\r\n]*|/\*.*?\*/", b"", raw, flags=re.S)
        names = re.findall(rb"\bmodule\s+(\w+)", raw)
        for name in names:
            if name in modules:
                raise RuntimeError("Duplicate module " + name.decode("ascii"))
            modules[name] = raw
    roots = []
    for name in modules:
        pattern = rb"\b" + name + rb"\s+(?:#\s*\(.*?\)\s*)?\w+\s*\("
        if not any(re.search(pattern, raw, re.S) for owner, raw in modules.items() if owner != name):
            roots.append(name.decode("ascii"))
    if roots != [EXPECTED["top"]]:
        raise RuntimeError("Not exactly one expected uninstantiated root: " + repr(roots))
    save("registration_check.json", {"timestamp": stamp(), "registered_sources":
         [p.decode("ascii") for p in registered], "modules":
         [p.decode("ascii") for p in modules], "uninstantiated_roots": roots,
         "top_selection": "PDS autodetect of the sole uninstantiated root",
         "project_sha256_before": hashlib.sha256(data).hexdigest(),
         "constraint_sha256": hashlib.sha256((WORK / "component.fdc").read_bytes()).hexdigest()})


def main():
    results = {"started": stamp(), "stages": [], "scope": "compile and synthesize only"}
    save("run_results.json", results)
    try:
        check_processes("initial")
        for directory in ["compile", "synthesize", "device_map", "place_route", "generate_bitstream"]:
            if (WORK / directory).exists():
                raise RuntimeError("Use a fresh isolated project; outputs already exist: " + directory)
        before = inputs()
        save("source_inputs_before.json", before)
        if not before["all_unchanged"]:
            raise RuntimeError("Input source hashes differ from the stable candidate manifest")
        verify_registration()
        for stage in EXPECTED["allowed_stages"]:
            check_processes(stage)
            command = [str(PDS), "-project", str(WORK / "project.pds"),
                       "-run", stage, "-work_dir", str(WORK)]
            record = {"stage": stage, "command": command, "cwd": str(WORK), "started": stamp()}
            results["stages"].append(record)
            save("run_results.json", results)
            print("Running", stage, "in", WORK, flush=True)
            with (WORK / (stage + "_stdout.log")).open("wb") as out, \
                 (WORK / (stage + "_stderr.log")).open("wb") as err:
                process = subprocess.run(command, cwd=WORK, stdout=out, stderr=err)
            record.update(returncode=process.returncode, finished=stamp())
            after = inputs()
            save("source_inputs_after_" + stage + ".json", after)
            record["source_hashes_unchanged"] = after["all_unchanged"]
            folder = "compile" if stage == "compile" else "synthesize"
            suffix = "_comp.adf" if stage == "compile" else "_syn.adf"
            record["expected_database_present"] = (WORK / folder / (EXPECTED["top"] + suffix)).is_file()
            save("run_results.json", results)
            print(json.dumps(record, indent=2), flush=True)
            if process.returncode != 0 or not after["all_unchanged"] or not record["expected_database_present"]:
                raise RuntimeError("Stage failed or lacked expected database: " + stage)
        results["status"] = "two stages returned zero with expected databases and unchanged source hashes"
        check_processes("final")
    except Exception as exc:
        results["status"] = "blocked_or_failed"
        results["blocker"] = str(exc)
        print(str(exc), file=sys.stderr, flush=True)
    finally:
        results["finished"] = stamp()
        save("source_inputs_final.json", inputs())
        save("run_results.json", results)
    return 0 if "blocker" not in results else 1


if __name__ == "__main__":
    sys.exit(main())
