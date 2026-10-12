"""Read pins, audit retained API declarations, run offline model/C predicates.

Never invokes SSH, Kbuild, insmod/rmmod, viewers, or board interfaces. Full driver
compilation must be done later against the complete frozen generated headers.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from extract_event_harness import generate, extract_braced

HERE = Path(__file__).resolve().parent
RETAINED = HERE.parent / "retained"
PINS = {
    "pango_pci_driver.c": "b7f61d8f628e4db7e7d520742b1a195dea4f2b18292203ff9ef5104c16460b72",
    "pango_pci_driver.h": "7bb7ee3a4cdb0ad1f7254a8ac40e39aff3a28f4ec96f8f97672e8488115b7ec1",
    "kernel-reference/include/linux/dma-buf.h": "ffd2ffec76ff3e97cb562fa933f32958c54e9adab73a32000a24f250ecef7115",
    "kernel-reference/include/linux/dma-mapping.h": "068d8bdb38e34b6014244cb429850568570d83564d2ecb6bdcdc52cb46b000af",
    "kernel-reference/include/linux/scatterlist.h": "3f5c8a11a0bfe36eebd772b30a3e0d15ac5182a4b911ed4e248eb0ac46ea466c",
    "kernel-reference/include/linux/dma-map-ops.h": "8d9b6e86bd55da341aadbb98e4da69ef445a8b8076c616f5fdfcdbf6274ecb81",
    "kernel-reference/Makefile": "3d9cd3c81e4b311fb7a892817539a6fa750d286695faf28b920ffa69ea73d673",
}


def normalized(data):
    return re.sub(rb"\s+", b" ", data).strip()


def audit():
    checks = {}
    hashes = {}
    for name, pin in PINS.items():
        digest = hashlib.sha256((RETAINED / name).read_bytes()).hexdigest()
        hashes[name] = digest
        checks["pin:" + name] = digest == pin
    buf = normalized((RETAINED / "kernel-reference/include/linux/dma-buf.h").read_bytes())
    dma = normalized((RETAINED / "kernel-reference/include/linux/dma-mapping.h").read_bytes())
    sg = normalized((RETAINED / "kernel-reference/include/linux/scatterlist.h").read_bytes())
    declarations = {
        "attach": b"int (*attach)(struct dma_buf *, struct dma_buf_attachment *);",
        "detach": b"void (*detach)(struct dma_buf *, struct dma_buf_attachment *);",
        "map_dma_buf": b"struct sg_table * (*map_dma_buf)(struct dma_buf_attachment *, enum dma_data_direction);",
        "unmap_dma_buf": b"void (*unmap_dma_buf)(struct dma_buf_attachment *, struct sg_table *, enum dma_data_direction);",
        "release": b"void (*release)(struct dma_buf *);",
        "begin_cpu_access": b"int (*begin_cpu_access)(struct dma_buf *, enum dma_data_direction);",
        "end_cpu_access": b"int (*end_cpu_access)(struct dma_buf *, enum dma_data_direction);",
        "mmap": b"int (*mmap)(struct dma_buf *, struct vm_area_struct *vma);",
        "owner_pin": b".owner = THIS_MODULE",
    }
    for name, declaration in declarations.items():
        checks["dma_buf_ops:" + name] = declaration in buf
    for name, declaration in {
        "dma_get_sgtable": b"#define dma_get_sgtable(d, t, v, h, s) dma_get_sgtable_attrs(d, t, v, h, s, 0)",
        "dma_map_sgtable": b"int dma_map_sgtable(struct device *dev, struct sg_table *sgt, enum dma_data_direction dir, unsigned long attrs);",
        "dma_mmap_coherent": b"#define dma_mmap_coherent(d, v, c, h, s) dma_mmap_attrs(d, v, c, h, s, 0)",
        "unmap_orig_nents": b"dma_unmap_sg_attrs(dev, sgt->sgl, sgt->orig_nents, dir, attrs);",
        "cpu_sync_orig_nents": b"dma_sync_sg_for_cpu(dev, sgt->sgl, sgt->orig_nents, dir);",
        "device_sync_orig_nents": b"dma_sync_sg_for_device(dev, sgt->sgl, sgt->orig_nents, dir);",
    }.items():
        checks["dma_api:" + name] = declaration in dma
    checks["sg:orig_nents"] = b"unsigned int orig_nents;" in sg
    source = (HERE / "pango_dma_candidate.c").read_bytes()
    checks["candidate:ASCII"] = source.isascii()
    checks["candidate:export_disabled"] = b"#define PANGO_EXPORT_PROVEN 0" in source
    checks["candidate:actual_attachment_backend_boundary"] = b"pango_backend_map(a->dev, &map->sgt, dir)" in source
    checks["candidate:no_streaming_alias_calls"] = all(x not in source for x in (
        b"dma_map_sgtable(", b"dma_unmap_sgtable(", b"dma_sync_sgtable_for_cpu(",
        b"dma_sync_sgtable_for_device(", b"DMA_ATTR_SKIP_CPU_SYNC"))
    checks["candidate:backend_hard_unsupported"] = b"return false;" in extract_braced(source, "pango_import_backend_ready")
    checks["candidate:source_direction_only"] = b"if (dir != DMA_TO_DEVICE)" in extract_braced(source, "pango_buf_map")
    checks["candidate:dma_mask32_only"] = b"DMA_BIT_MASK(64)" not in source and b"DMA_BIT_MASK(32)" in source
    checks["candidate:complete_dma32_guards"] = b"pango_dma32_valid((u64)b->dma, size)" in source and b"pango_dma32_valid((u64)addr, op->total_length)" in source
    dispatch = extract_braced(source, "pango_ioctl")
    checks["candidate:input_usercopy_before_lock"] = dispatch.index(b"copy_from_user(") < dispatch.index(b"mutex_lock_interruptible(")
    checks["candidate:single_input_snapshot"] = source.count(b"copy_from_user(") == 1 and b"get_user(" not in source
    checks["candidate:no_dma_address_page_cast"] = all(x not in source for x in (
        b"virt_to_page", b"phys_to_page", b"pfn_to_page", b"dma_to_phys"))
    checks["candidate:no_irq_launch_helpers"] = b"void read_img(" not in source and b"void read_npu(" not in source
    checks["candidate:shared_range_policy"] = b"pango_rx_hits_lease(g->lease_mask" in source
    checks["candidate:shared_unmap_policy"] = b"pango_unmap_busy(g->exports" in source
    return {"checks": checks, "sha256": hashes, "passed": all(checks.values())}


def wsl_path(path):
    path = Path(path).resolve()
    return "/mnt/" + path.drive[0].lower() + str(path)[2:].replace("\\", "/")


def run_policy_harness(clang, wsl=None, source=None, extra_include=None):
    source = Path(source or HERE / "policy_harness.c")
    if wsl:
        with tempfile.TemporaryDirectory(prefix="pango-C-") as tmp:
            exe = Path(tmp) / "harness"
            commands = [["wsl.exe", "--distribution", wsl, "--exec", "gcc", "-std=c11", "-O1",
                         "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                         "-I", wsl_path(HERE)]]
            if extra_include:
                commands[0].extend(["-I", wsl_path(extra_include)])
            commands[0].extend([wsl_path(source), "-o", wsl_path(exe)])
            commands.append(["wsl.exe", "--distribution", wsl, "--exec", wsl_path(exe)])
            runs = []
            for command in commands:
                proc = subprocess.run(command, capture_output=True, text=True, timeout=30)
                runs.append({"command": command, "returncode": proc.returncode,
                             "stdout": proc.stdout, "stderr": proc.stderr})
                if proc.returncode:
                    return {"status": "failed", "runs": runs}
            return {"status": "passed", "runs": runs, "environment": "local WSL userspace; no Kbuild"}
    if not clang:
        return {"status": "pending", "reason": "No host C compiler available"}
    with tempfile.TemporaryDirectory(prefix="pango-policy-") as tmp:
        tmp = Path(tmp)
        if os.name == "nt":
            # Explicit Windows target: installed clang may default to embedded.
            obj = tmp / "policy.obj"
            exe = tmp / "policy.exe"
            lld = Path(clang).parent / "lld.exe"
            if not lld.exists():
                return {"status": "pending", "reason": "Freestanding Windows lld unavailable"}
            commands = [
                [clang, "--target=x86_64-pc-windows-msvc", "-std=c11", "-O1",
                 "-Wall", "-Wextra", "-Werror", "-ffreestanding", "-fno-stack-protector",
                 "-c", str(source), "-o", str(obj)],
                [str(lld), "-flavor", "link", "/nodefaultlib", "/entry:main",
                 "/subsystem:console", "/out:" + str(exe), str(obj)],
                [str(exe)],
            ]
        else:
            exe = tmp / "policy"
            commands = [[clang, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
                         str(source), "-o", str(exe)], [str(exe)]]
        if extra_include:
            commands[0][1:1] = ["-I", str(extra_include)]
        runs = []
        for command in commands:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=30)
            runs.append({"command": command, "returncode": proc.returncode,
                         "stdout": proc.stdout, "stderr": proc.stderr})
            if proc.returncode:
                if "No available targets are compatible" in proc.stderr:
                    syntax_command = [clang, "--target=x86_64-pc-windows-msvc",
                                      "-std=c11", "-Wall", "-Wextra", "-Werror",
                                      "-fsyntax-only", str(source)]
                    if extra_include:
                        syntax_command[1:1] = ["-I", str(extra_include)]
                    syntax = subprocess.run(syntax_command, capture_output=True,
                                            text=True, timeout=30)
                    runs.append({"command": syntax_command, "returncode": syntax.returncode,
                                 "stdout": syntax.stdout, "stderr": syntax.stderr})
                    return {"status": "syntax_checked_execution_pending" if not syntax.returncode else "failed",
                            "reason": "Installed embedded clang lacks a host code-generation backend",
                            "runs": runs}
                return {"status": "failed", "runs": runs}
        return {"status": "passed", "runs": runs}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=HERE / "local-validation.json")
    parser.add_argument("--clang", default=shutil.which("clang") or shutil.which("cc"))
    parser.add_argument("--wsl", help="Local WSL distribution for userspace GCC harnesses only")
    args = parser.parse_args()
    api = audit()
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_lifecycle.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    policy = run_policy_harness(args.clang, wsl=args.wsl)
    with tempfile.TemporaryDirectory(prefix="pango-extracted-") as tmp:
        provenance = generate(tmp)
        events = run_policy_harness(args.clang, wsl=args.wsl,
                                    source=HERE / "driver_event_harness.c", extra_include=tmp)
        events["provenance"] = provenance
    report = {
        "scope": "offline model and shared C policy only; no driver build or hardware",
        "retained_api_audit": api,
        "model_tests": {"run": result.testsRun, "failures": len(result.failures),
                        "errors": len(result.errors), "passed": result.wasSuccessful()},
        "shared_C_policy": policy,
        "extracted_driver_C_events": events,
        "driver_compile": {"status": "pending_for_revised_bytes", "reason": "Parent reported the earlier candidate compiled privately against 6.1.99/GCC12.2; that result does not cover this revision. Only selected target headers are retained locally"},
        "hardware_validation": "not performed",
        "export_gate": "disabled; EOPNOTSUPP",
        "original_loaded_module_rebuild_match": "not established",
        "validated_candidate_inputs_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(HERE.iterdir()) if p.is_file() and
            (p.suffix in (".c", ".h", ".py") or p.name in ("Makefile", "README.md"))
        },
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print("API audit:", api["passed"], "Model:", result.wasSuccessful(),
          "Shared C policy:", policy["status"], "Extracted C events:", events["status"])
    print("Report:", args.report)
    return 0 if api["passed"] and result.wasSuccessful() and policy["status"] != "failed" and events["status"] != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
