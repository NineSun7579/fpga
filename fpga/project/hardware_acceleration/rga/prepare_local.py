"""Offline fixture bundle + independent RGB565 oracle. Never connects to a board."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
RAW_BYTES = 640 * 480 * 2


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fnv(data):
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
    return f"{value:016x}"


def oracle(raw):
    if len(raw) != RAW_BYTES:
        raise ValueError(f"Expected {RAW_BYTES} bytes; got {len(raw)}")
    out = bytearray()
    for (value,) in struct.iter_unpack("<H", raw):
        red, green, blue = value // 2048, (value // 32) % 64, value % 32
        # Independent arithmetic expression for the bit-replicated golden.
        out.extend((red * 8 + red // 4, green * 4 + green // 16, blue * 8 + blue // 4))
    model = bytes([114]) * (640 * 80 * 3) + out + bytes([114]) * (640 * 80 * 3)
    return bytes(out), model


def receipt(raw, name):
    rgb, model = oracle(raw)
    return {
        "name": name, "bytes": len(raw), "raw_sha256": sha(raw),
        "rgb_sha256": sha(rgb), "model_sha256": sha(model),
        "raw_fnv1a64": fnv(raw), "rgb_fnv1a64": fnv(rgb), "model_fnv1a64": fnv(model),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path,
                        default=WORKSPACE / "log" / "six_fps40_board_20261003_105717")
    parser.add_argument("--output", type=Path, default=HERE / "local_evidence")
    parser.add_argument("--selftest", type=Path,
                        help="Already locally compiled reference_selftest executable; no RGA execution")
    parser.add_argument("--bundle", action="store_true", help="Create a private source/fixture tar.gz for future parent SFTP")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fixtures = output / "fixtures"
    fixtures.mkdir(exist_ok=True)
    raw_colors = b"".join(struct.pack("<H", i & 65535) for i in range(640 * 480))
    colors = receipt(raw_colors, "tiled_all65536")
    rows = []
    for index in range(1, 7):
        source = args.fixture_dir / f"cam{index}.rgb565"
        raw = source.read_bytes()
        row = receipt(raw, source.name)
        row["original_path"] = str(source.resolve())
        destination = fixtures / source.name
        if destination.exists() and destination.read_bytes() != raw:
            raise RuntimeError(f"Refusing to replace a different staged fixture: {destination}")
        if not destination.exists():
            shutil.copyfile(source, destination)
        rows.append(row)
    result = {
        "kind": "local_reference_receipt", "hardware_executed": False,
        "source_format": "little-endian RGB565, R5top", "model": [640, 640],
        "image_roi": [0, 80, 640, 480], "padding": 114,
        "fixture_provenance_note": "Historical log fixtures, not claimed to be a current e3da capture",
        "gradient": colors, "fixtures": rows,
        "source_sha256": {path.name: sha(path.read_bytes()) for path in HERE.glob("*.hpp")},
    }
    result["source_sha256"].update({path.name: sha(path.read_bytes()) for path in HERE.glob("*.cpp")})
    if args.selftest:
        command = [str(args.selftest.resolve()), *[str(fixtures / row["name"]) for row in rows]]
        run = subprocess.run(command, text=True, capture_output=True, check=False)
        (output / "reference_selftest.jsonl").write_text(run.stdout, encoding="utf-8")
        (output / "reference_selftest.stderr").write_text(run.stderr, encoding="utf-8")
        if run.returncode:
            raise RuntimeError(f"Reference selftest failed: {run.stderr}")
        records = [json.loads(line) for line in run.stdout.splitlines()]
        if len(records) != 7 or not records[0].get("passed") or records[0].get("hardware_executed"):
            raise RuntimeError("Missing CPU-only exhaustive selftest evidence")
        for expected, actual in zip([colors, *rows], records):
            for key in ("raw_fnv1a64", "rgb_fnv1a64", "model_fnv1a64"):
                if expected[key] != actual[key]:
                    raise RuntimeError(f"Independent Python/C++ oracle mismatch: {expected['name']} {key}")
        result["cpp_python_oracle_exact"] = True
        result["reference_executable_sha256"] = sha(args.selftest.read_bytes())
        result["reference_executable_machine"] = "local; see build receipt"
    (output / "reference_receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    # A portable manifest for the deferred runner, without host absolute paths.
    (fixtures / "manifest.json").write_text(json.dumps({"fixtures": rows}, indent=2) + "\n", encoding="utf-8")
    if args.bundle:
        bundle = output / "rga_board_bundle.tar.gz"
        with tarfile.open(bundle, "w:gz") as archive:
            for name in ("reference.hpp", "reference_selftest.cpp", "native_probe.cpp", "run_board.py", "README.md"):
                archive.add(HERE / name, arcname=name, recursive=False)
            archive.add(fixtures, arcname="fixtures")
            archive.add(output / "reference_receipt.json", arcname="local_reference_receipt.json")
        (output / "bundle_sha256.json").write_text(json.dumps({"name": bundle.name,
                    "sha256": sha(bundle.read_bytes()), "hardware_executed": False}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"hardware_executed": False, "fixtures": 6,
                      "cpp_python_oracle_exact": result.get("cpp_python_oracle_exact", False),
                      "receipt": str(output / "reference_receipt.json")}))


if __name__ == "__main__":
    main()
