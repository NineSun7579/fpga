"""Audit inherited worker/protocol files against the isolated short-hold source."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent
source = root.parent / "candidate_short_hold_viewer"
changed = sorted(
    str(p.relative_to(source))
    for p in source.rglob("*")
    if p.is_file() and "local_build" not in p.relative_to(source).parts
    and p.read_bytes() != (root / p.relative_to(source)).read_bytes()
)
assert changed == ["vision_pipeline.cpp"], changed
receipt = {
    "changed_copied_files": changed,
    "main_cpp_sha256": hashlib.sha256((root / "main.cpp").read_bytes()).hexdigest(),
    "main_cpp_matches_short_hold": True,
}
(root / "local_build").mkdir(exist_ok=True)
(root / "local_build" / "source_preservation.json").write_text(
    json.dumps(receipt, indent=2), encoding="utf-8"
)
print(json.dumps(receipt))
