"""Verify the isolated lead candidate against its checked parent."""
from pathlib import Path
import json
root = Path(__file__).resolve().parent
source = root.parent / "candidate_prefetch_checked_viewer"
excluded = {"local_build", "local_builds", "build", "__pycache__"}
def files(base):
    return {str(p.relative_to(base)): p for p in base.rglob("*") if p.is_file()
            and not any(part in excluded or part.startswith("build-") for part in p.relative_to(base).parts)}
old, new = files(source), files(root)
changed = sorted(name for name in old.keys() & new.keys() if old[name].read_bytes() != new[name].read_bytes())
expected = sorted(["fpga_infer_input.h", "inference_cadence.h", "local_fair_check.sh", "local_prefetch_check.sh",
    "local_prefetch_preservation.py", "local_short_hold_negative_check.py", "main.cpp", "prefetch_selftest.cpp",
    "scheme2_protocol_test_body.h", "vision_pipeline.cpp"])
assert changed == expected, changed
assert not old.keys() - new.keys()
assert sorted(new.keys() - old.keys()) == ["LEAD_PREFETCH_REVIEW.md", "prefetch_config.h"]
main = (root / "main.cpp").read_text(encoding="utf-8-sig")
pipeline = (root / "vision_pipeline.cpp").read_text(encoding="utf-8-sig")
assert "scheme2::enabled() && scheme2::prefetchTimingEnabled()" in main
assert "scheme2::prefetchLeadMs()" in pipeline
assert "lastRequestMs = now; ++requests;" in pipeline
assert "if (timing) timing->holdCommand = monotonicMs();" in main
assert "if (timing) input->timing = *timing;" in main
print(json.dumps({"changed_files": changed, "added_files": sorted(new.keys() - old.keys()),
    "result": "LEAD_PREFETCH_PRESERVATION_PASS"}, indent=2))
