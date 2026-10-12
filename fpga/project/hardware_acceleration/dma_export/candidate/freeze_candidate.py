"""Freeze/check only this offline handoff; never build or deploy anything."""
import argparse
import hashlib
import json
from pathlib import Path
from validate_offline import PINS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MANIFEST = HERE / "frozen-manifest.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    action.add_argument("--archive-existing", action="store_true")
    args = parser.parse_args()
    if args.archive_existing:
        archive = HERE / "archive"
        archive.mkdir(exist_ok=True)
        for path in (MANIFEST, HERE / "local-validation.json"):
            target = archive / (path.stem + "-" + digest(path) + path.suffix)
            if target.exists():
                if target.read_bytes() != path.read_bytes():
                    raise SystemExit("Immutable archive conflict: " + str(target))
            else:
                with target.open("xb") as output:
                    output.write(path.read_bytes())
            print("Archived immutable prior evidence:", target.name)
        return
    if args.freeze:
        files = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p)
                 for p in sorted(HERE.iterdir()) if p.is_file() and p != MANIFEST}
        files.update({str(p.relative_to(ROOT)).replace("\\", "/"): digest(p)
                      for p in sorted((HERE / "archive").glob("*.json"))})
        files.update({"retained/" + name: pin for name, pin in PINS.items()})
        files["../DMA_COPY_DESIGN.md"] = digest(ROOT.parent / "DMA_COPY_DESIGN.md")
        report = json.loads((HERE / "local-validation.json").read_text(encoding="ascii"))
        if not (report["retained_api_audit"]["passed"] and report["model_tests"]["passed"]):
            raise SystemExit("Cannot freeze a failed validation")
        for kind in ("shared_C_policy", "extracted_driver_C_events"):
            if report.get(kind, {}).get("status") != "passed":
                raise SystemExit("Cannot freeze without executed passing evidence: " + kind)
        for name, pin in report["validated_candidate_inputs_sha256"].items():
            if digest(HERE / name) != pin:
                raise SystemExit("Validation is stale for input: " + name)
        data = {
            "format": 1,
            "scope": "Independent offline fail-closed source/report candidate; not a compiled module",
            "export_enabled": False,
            "coherent_import_backend": "absent; map/sync unsupported even if export gate changed",
            "kernel_compile": "pending",
            "hardware": "not accessed",
            "loaded_module_build_id": "1102cfd04acaeeea21ca4d03fe27ddbb32b7340a",
            "loaded_module_sha256": "0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861",
            "loaded_module_exact_source_attribution": "unavailable; no rebuild match claim",
            "files_sha256_relative_to_dma_export": files,
        }
        MANIFEST.write_text(json.dumps(data, indent=2) + "\n", encoding="ascii")
    data = json.loads(MANIFEST.read_text(encoding="ascii"))
    mismatches = [name for name, pin in data["files_sha256_relative_to_dma_export"].items()
                  if not (ROOT / name).is_file() or digest(ROOT / name) != pin]
    if mismatches:
        raise SystemExit("Freeze mismatch: " + ", ".join(mismatches))
    print("Frozen hashes verified:", len(data["files_sha256_relative_to_dma_export"]))


if __name__ == "__main__":
    main()
