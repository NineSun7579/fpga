"""Audit the live candidate against its isolated prefetch source."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent
source = root.parent / "candidate_prefetch_viewer"
changed = sorted(
    str(p.relative_to(source))
    for p in source.rglob("*")
    if p.is_file() and "local_build" not in p.relative_to(source).parts
    and p.read_bytes() != (root / p.relative_to(source)).read_bytes()
)
assert changed == ["fpga_infer_input.h", "local_prefetch_preservation.py", "main.cpp",
                   "vision_pipeline.cpp", "vision_pipeline_selftest.cpp"], changed
receipt = {
    "changed_copied_files": changed,
    "main_cpp_sha256": hashlib.sha256((root / "main.cpp").read_bytes()).hexdigest(),
    "main_cpp_matches_short_hold": False,
    "added_files": ["infer_age.h", "LIVE_PREFETCH_REVIEW.md"],
}
(root / "local_build").mkdir(exist_ok=True)
(root / "local_build" / "source_preservation.json").write_text(
    json.dumps(receipt, indent=2), encoding="utf-8"
)
print(json.dumps(receipt))
