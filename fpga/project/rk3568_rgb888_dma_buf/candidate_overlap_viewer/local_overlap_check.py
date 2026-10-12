"""Host-only actual-code overlap regressions, negative cases and mutations."""
from pathlib import Path
import os
import subprocess
import shlex

root = Path(__file__).resolve().parent
os.chdir(root)
env = dict(os.environ, DETVIEW_FPGA_INFER_RGB="1")
build = root / "local_build"
faults = ["initial-tag", "old-tag", "raw-tag", "source", "camera", "sequence",
          "epoch", "destination", "mode", "stale", "generation", "early-release",
          "error", "raw-dma", "raw-timeout", "timeout"]
for fault in faults:
    result = subprocess.run([str(build / "protocol_test"), fault], env=env,
                            capture_output=True, text=True, timeout=12)
    (build / f"overlap_{fault}.log").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (fault, result.stdout, result.stderr)
    print(f"OVERLAP_{fault.upper().replace('-', '_')}_PASS")

source = (build / "protocol.cpp").read_text()
trigger = "const uint32_t jobs = reg(0x90);\n        write(0x20, 3);"
assert source.count(trigger) == 1
late = source.replace(trigger, "")
late = late.replace("poll(true, jobs); validate();", trigger + "\n        poll(true, jobs); validate();")
early = source.replace(trigger, "")
early = early.replace("        validate();\n        if (timing) timing->holdValidated", "        " + trigger + "\n        validate();\n        if (timing) timing->holdValidated")
criterion = "reg(0x90) == uint32_t(jobs + 1)"
assert source.count(criterion) == 1
mutations = [("raw-before-trigger", late, []), ("trigger-before-validation", early, ["initial-tag"]),
             ("inexact-generation", source.replace(criterion, "reg(0x90) >= uint32_t(jobs + 1)"), ["generation"])]
qt = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs", "Qt5Core", "Qt5Gui"], text=True))
for name, text, args in mutations:
    unit = build / f"overlap_mutant_{name}.cpp"
    unit.write_text(text)
    binary = unit.with_suffix("")
    subprocess.run(["g++", "-std=c++17", "-O2", "-fPIC", "-pthread", "-I.", str(unit),
                    "-o", str(binary), *qt,
                    "-Wl,--wrap=open,--wrap=close,--wrap=raise,--wrap=mmap,--wrap=munmap,--wrap=ioctl"], check=True)
    result = subprocess.run([str(binary), *args], env=env, capture_output=True, text=True, timeout=12)
    (build / f"overlap_mutant_{name}.log").write_text(result.stdout + result.stderr)
    assert result.returncode != 0, name
    assert "Assertion" in result.stderr, (name, result.stderr)
    print(f"OVERLAP_MUTATION_REJECTED {name}")

excluded = {"local_build", "local_builds", "build", "__pycache__"}
def files(base):
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()
            and not any(part in excluded or part.startswith("build-") for part in p.relative_to(base).parts)}
original = files(root.parent / "candidate_prefetch_lead_viewer")
candidate = files(root)
changed = sorted(name for name in original.keys() & candidate.keys() if original[name] != candidate[name])
assert changed == ["main.cpp", "scheme2_protocol_test_body.h"], changed
assert not original.keys() - candidate.keys()
assert sorted(candidate.keys() - original.keys()) == ["OVERLAP_REVIEW.md", "local_overlap_check.py", "local_overlap_check.sh"]
print("OVERLAP_PRESERVATION_PASS: only acquisition and asynchronous fixture changed")
