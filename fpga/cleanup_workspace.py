"""Remove verified FPGA intermediates; retain RTL, IP, snapshots and reports.

Requires cleanup_inventory.json. Preview by default; --apply deletes the preview.
"""
import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FLOW = {"compile", "synthesize", "device_map", "place_route", "report_timing",
        "report_power", "generate_netlist", "constraint_check"}
BINARY = {".adf", ".db", ".cmr", ".snr", ".dmr", ".prr", ".rtr",
          ".ppr", ".pps", ".ppf", ".gnr"}
SIM_BINARY = {".wlf", ".vcd", ".qdb", ".qpg", ".qtl"}
PROTECTED = {"source", "ipcore", "_attic", "_rollback_backup_20260925"}


def reason_for(rel):
    path = Path(rel)
    parts = {p.lower() for p in path.parts[:-1]}
    if parts & PROTECTED or any(p.startswith(".bak") for p in parts):
        return None
    if "__pycache__" in parts and path.suffix.lower() == ".pyc":
        return "Python cache"
    flow = any(p in FLOW or p.removeprefix("previous_") in FLOW for p in parts)
    if flow and path.suffix.lower() in BINARY:
        return "PDS intermediate database"
    if flow and (path.name.endswith("_syn.vm") or path.name.endswith("_pnr.netlist")
                 or path.name.endswith("_sim.v") or path.name.endswith("_sta.sdf")):
        return "PDS generated netlist"
    if path.suffix.lower() in SIM_BINARY and ("sim" in parts or
            any(p == "work" or p.startswith("work_") for p in parts)):
        return "Simulation cache or waveform"
    if any(p == "work" or p.startswith("work_") for p in parts) and path.name in {"_info", "_vmake"}:
        return "ModelSim library metadata"
    return None


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    inventory = json.loads((ROOT / "cleanup_inventory.json").read_text(encoding="utf-8"))
    selected = [{"path": p, "bytes": size, "reason": reason_for(p)}
                for p, size in inventory["files"] if reason_for(p)]
    # Protected directories are excluded by the deletion rules. Hash current
    # RTL plus configurations and bitstreams, avoiding tens of thousands of
    # historical source/IP copies before any space can be released.
    protected = [p for p, _ in inventory["files"] if
                 p.startswith("project\\source\\") or
                 Path(p).suffix.lower() in {".pds", ".fdc", ".pcf", ".sbit", ".bit", ".smsk"}]
    plan = {"before_bytes": inventory["total_bytes"], "selected_bytes": sum(x["bytes"] for x in selected),
            "selected_count": len(selected), "selected": selected}
    (ROOT / "cleanup_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    totals = collections.Counter()
    for item in selected:
        totals[item["reason"]] += item["bytes"]
    print(json.dumps({"count": len(selected), "MiB": round(plan["selected_bytes"] / 2**20, 2),
                      "categories_MiB": {k: round(v / 2**20, 2) for k, v in totals.items()}}, indent=2), flush=True)
    if not args.apply:
        return
    print("Checking current RTL, configurations and bitstreams...", flush=True)
    baseline_path = ROOT / "cleanup_preservation_baseline.json"
    if baseline_path.exists():
        before = json.loads(baseline_path.read_text(encoding="utf-8"))
    else:
        before = {p: digest(ROOT / p) for p in protected}
        baseline_path.write_text(json.dumps(before, ensure_ascii=False), encoding="utf-8")
    print("Preservation baseline ready; deleting largest intermediates first...", flush=True)
    deleted, errors = [], []

    def remove_one(item):
        target = ROOT / item["path"]
        try:
            if not target.exists():
                return {**item, "removed_in_previous_pass": True}, None
            if not target.resolve().is_relative_to(ROOT) or target.is_symlink():
                raise ValueError("Path escapes workspace or is a symlink")
            if target.stat().st_size != item["bytes"]:
                raise ValueError("File changed since inventory")
            target.unlink()
            return item, None
        except (OSError, ValueError) as exc:
            return None, {"path": item["path"], "error": str(exc)}

    with ThreadPoolExecutor(max_workers=8) as pool:
        for item, error in pool.map(remove_one, sorted(selected, key=lambda row: row["bytes"], reverse=True)):
            if error:
                errors.append(error)
            else:
                deleted.append(item)
                if len(deleted) % 500 == 0:
                    print(f"Deleted {len(deleted)}/{len(selected)} files", flush=True)
    changed = [p for p, expected in before.items() if not (ROOT / p).is_file()
               or digest(ROOT / p) != expected]
    result = {"before_bytes": inventory["total_bytes"], "deleted_bytes": sum(x["bytes"] for x in deleted),
              "deleted_count": len(deleted), "protected_files_checked": len(before),
              "protected_files_changed": changed, "errors": errors, "deleted": deleted}
    (ROOT / "cleanup_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "deleted"}, ensure_ascii=False, indent=2), flush=True)
    if changed or errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
