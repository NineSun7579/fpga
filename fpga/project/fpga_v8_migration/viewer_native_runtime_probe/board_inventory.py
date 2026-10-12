"""Read-only board inventory. Never opens device nodes or changes processes."""
import hashlib
import json
from pathlib import Path
import os
import time


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for data in iter(lambda: stream.read(1048576), b""):
            h.update(data)
    return h.hexdigest()


def identity():
    result = {"observed_unix": time.time(), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
              "viewers": [], "errors": []}
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            comm = (directory / "comm").read_text().strip()
            if "detview" not in comm and "camview" not in comm:
                continue
            raw = (directory / "stat").read_text()
            fields = raw[raw.rfind(")") + 2:].split()
            if fields[0] == "Z":
                continue
            result["viewers"].append({"pid": int(directory.name), "comm": comm, "starttime": fields[19],
                "exe": os.readlink(directory / "exe"), "exe_sha256": digest(directory / "exe"),
                "cwd": os.readlink(directory / "cwd"),
                "argv": [os.fsdecode(v) for v in (directory / "cmdline").read_bytes().split(b"\0") if v],
                "runtime_maps": [line for line in (directory / "maps").read_text().splitlines() if "librknnrt.so" in line]})
        except FileNotFoundError:
            continue
        except Exception as error:
            result["errors"].append({"pid": directory.name, "error": str(error)})
    result["viewers"].sort(key=lambda row: row["pid"])
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "inputs":
        roots = [Path("/tmp/fpga_v8_pipeline_1791156966"), Path("/userdata/model_compare_20261004")]
        files = []
        for root in roots:
            if root.exists():
                for item in root.rglob("*"):
                    if item.is_file() and (item.suffix in (".rgb", ".bin", ".json") or "inventory" in item.name):
                        files.append({"path": str(item), "bytes": item.stat().st_size})
        print(json.dumps({"files": files}, indent=2))
    else:
        print(json.dumps(identity(), indent=2))
