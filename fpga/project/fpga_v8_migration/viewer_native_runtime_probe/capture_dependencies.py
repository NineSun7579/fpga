import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

stage = Path(sys.argv[1]).resolve()
rows = {}
for depfile in stage.glob("*.d"):
    text = depfile.read_text().replace("\\\n", " ").split(":", 1)[1]
    for path in shlex.split(text):
        file = Path(path)
        if file.exists():
            rows[str(file)] = {"canonical_path": str(file.resolve()), "bytes": file.stat().st_size,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "kind": "compiler_dependency"}
ldd = subprocess.check_output(["ldd", str(stage / "runtime_probe")], text=True)
for line in ldd.splitlines():
    match = re.search(r"(/\S+)\s+\(", line)
    if match:
        file = Path(match.group(1))
        rows[str(file)] = {"canonical_path": str(file.resolve()), "bytes": file.stat().st_size,
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "kind": "loaded_link_dependency"}
(stage / "compiled_dependency_hashes.json").write_text(json.dumps(rows, indent=2) + "\n")
print("DEPENDENCIES_HASHED", len(rows))
