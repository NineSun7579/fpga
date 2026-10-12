"""Parent-invoked Linux target build/probe; no SSH, camera access or viewer control."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
MODEL_SHA = "21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31"
SDK_SHA = "c48e11a6f41b451a5fd1e4ad774ea60252d3d94f78bee9b21ea3d21b21deba9a"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, out, name, timeout=120):
    (out / (name + ".command.json")).write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
    with (out / (name + ".stdout")).open("wb") as stdout, (out / (name + ".stderr")).open("wb") as stderr:
        result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{name} failed rc={result.returncode}; see {out / (name + '.stderr')}")
    return (out / (name + ".stdout")).read_text(encoding="utf-8").strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("build", "experiment"), default="build")
    parser.add_argument("--source", type=Path, required=True, help="actual frozen candidate/src with helper and adapter")
    parser.add_argument("--fixtures", type=Path, required=True, help="suite directory containing manifest.json and fixtures/")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--lib", type=Path, default=Path("/usr/lib/librknnrt.so"))
    parser.add_argument("--out", type=Path, required=True, help="private output directory; fresh for build")
    parser.add_argument("--board-exclusive", action="store_true", help="parent has stopped the viewer and owns NPU exclusivity")
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--save-arrays", action="store_true")
    args = parser.parse_args()
    if not sys.platform.startswith("linux") or platform.machine().lower() != "aarch64":
        parser.error("invoke on the aarch64 Linux target through the parent; this script has no SSH transport")
    if args.phase == "experiment" and not args.board_exclusive:
        parser.error("--board-exclusive required; the parent must stop/restore the viewer externally")
    if not 0 <= args.warmup <= 20 or not 1 <= args.repeats <= 10:
        parser.error("warmup must be 0..20 and repeats 1..10")
    source, suite, model, library, out = (p.resolve() for p in (args.source, args.fixtures, args.model, args.lib, args.out))
    sdk = source.parent / "sdk/rknn_api.h"
    if sha(sdk) != SDK_SHA or sha(model) != MODEL_SHA:
        raise RuntimeError("retained SDK or pinned model hash differs")
    manifest_path = suite / "manifest.json"
    suite_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if suite_manifest["model_sha256"] != MODEL_SHA or len(suite_manifest["fixtures"]) != 4:
        raise RuntimeError("four-fixture pinned suite required")
    paths = {str(ROOT / name): ROOT / name for name in ("parity_probe.cpp", "run_parity_target.py")}
    for name in ("hardware_inference.h", "native_adapter.h", "inference_preprocess.h", "rgb565_convert.h"):
        paths[str(source / name)] = source / name
    for path in (sdk, model, library, manifest_path):
        paths[str(path)] = path
    for fixture in suite_manifest["fixtures"]:
        path = (suite / fixture["path"]).resolve()
        if sha(path) != fixture["sha256"]:
            raise RuntimeError("fixture hash differs: " + str(path))
        paths[str(path)] = path
    pins = {name: sha(path) for name, path in paths.items()}
    receipt_path, executable = out / "build_receipt.json", out / "viewer_helper_parity"
    if out.exists():
        if args.phase != "experiment" or not receipt_path.is_file():
            raise RuntimeError("fresh --out required for build")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["inputs_sha256"] != pins or sha(executable) != receipt["executable_sha256"]:
            raise RuntimeError("existing target build inputs or executable changed")
        for path, expected in receipt["compiler_dependencies_sha256"].items():
            if sha(Path(path)) != expected:
                raise RuntimeError("compiler dependency changed: " + path)
    else:
        out.mkdir(mode=0o700, parents=True)
        compiler = Path(shutil.which("g++") or "/missing/g++").resolve()
        version = run([str(compiler), "--version"], out, "compiler_version").splitlines()[0]
        frontend = Path(run([str(compiler), "-print-prog-name=cc1plus"], out, "frontend_path")).resolve()
        qt = shlex.split(run(["pkg-config", "--cflags", "--libs", "Qt5Core", "Qt5Gui"], out, "qt_flags"))
        dependencies = out / "probe.d"
        command = [str(compiler), "-std=c++17", "-O2", "-fPIC", "-Wall", "-Wextra", "-Werror", "-MD", "-MF", str(dependencies),
                   "-I" + str(source), "-I" + str(source.parent), "-I" + str(sdk.parent), str(ROOT / "parity_probe.cpp"),
                   str(library), "-Wl,-rpath," + str(library.parent), "-ldl", "-o", str(executable)] + qt
        run(command, out, "build")
        dep_text = dependencies.read_text(encoding="utf-8").replace("\\\n", "")
        dep_paths = [Path(p).resolve() for p in shlex.split(dep_text.split(":", 1)[1])]
        if any(sha(path) != pins[name] for name, path in paths.items()):
            raise RuntimeError("inputs changed during target build")
        receipt = dict(schema=1, status="target_built_not_executed", source_path=str(source), fixture_suite=str(suite),
                       inputs_sha256=pins, executable_sha256=sha(executable), compiler_path=str(compiler),
                       compiler_sha256=sha(compiler), compiler_version=version, frontend_path=str(frontend),
                       frontend_sha256=sha(frontend), command=command,
                       compiler_dependencies_sha256={str(path): sha(path) for path in dep_paths})
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if args.phase == "build":
        print(json.dumps(dict(status="target_built_not_executed", hardware_parity_complete=False,
                              build_receipt=str(receipt_path), executable_sha256=sha(executable))))
        return
    # No inferred board ownership: this explicit phase requires the parent's
    # exclusivity argument. Lifecycle/restoration stays in the parent's runner.
    if (out / "experiment.stdout").exists():
        raise RuntimeError("experiment already exists; do not overwrite parity evidence")
    command = [str(executable), "--source", str(source), "--model", str(model), "--fixtures", str(suite), "--receipt", str(receipt_path),
               "--runtime-sha256", sha(library), "--warmup", str(args.warmup), "--repeats", str(args.repeats)]
    if args.save_arrays:
        command += ["--save-arrays", str(out / "arrays")]
    try:
        run(command, out, "experiment", timeout=120)
        rows = [json.loads(line) for line in (out / "experiment.stdout").read_text(encoding="utf-8").splitlines() if line.startswith("{")]
        identity = next(row for row in rows if row["event"] == "identity")
        summary = next(row for row in rows if row["event"] == "summary")
        comparisons = [row for row in rows if row["event"] == "output_comparison"]
        if (not summary["passed"] or not summary["hardware_parity_complete"] or summary["compared_completions"] != 4 * args.repeats or
                len(comparisons) != 16 * args.repeats or any(not row["passed"] for row in comparisons) or
                identity["executable_sha256"] != receipt["executable_sha256"] or
                identity["build_receipt_sha256"] != sha(receipt_path)):
            raise RuntimeError("helper parity summary or build identity gate failed")
        if any(sha(path) != pins[name] for name, path in paths.items()) or sha(executable) != receipt["executable_sha256"]:
            raise RuntimeError("inputs or executable changed during target execution")
        result = dict(status="actual_helper_array_parity_passed", summary=summary, identity=identity,
                      hardware_parity_complete=True,
                      build_receipt_sha256=sha(receipt_path), log_sha256=sha(out / "experiment.stdout"),
                      stderr_sha256=sha(out / "experiment.stderr"), model_sha256=MODEL_SHA,
                      performance_claim=False, decoder_tested=False)
    except Exception as error:
        result = dict(status="actual_helper_array_parity_failed", reason=str(error),
                      hardware_parity_complete=False, build_receipt_sha256=sha(receipt_path), performance_claim=False)
        (out / "parity_receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        raise
    (out / "parity_receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps(dict(status="viewer_helper_parity_failed", hardware_parity_complete=False, reason=str(error))))
        sys.exit(1)
