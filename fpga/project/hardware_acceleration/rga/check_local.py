"""Compile-only checks; optional public SDK header download is never board access."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent


def download(url):
    with urlopen(Request(url, headers={"User-Agent": "rga-local-syntax-check"}), timeout=30) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headers-root", type=Path,
                        help="Local root containing rga/im2d.h; preferably a future parent SFTP header capture")
    parser.add_argument("--fetch-upstream-headers", action="store_true",
                        help="Fetch public aiRockchip headers solely for non-board syntax evidence")
    args = parser.parse_args()
    output = HERE / "local_evidence"
    output.mkdir(exist_ok=True)
    receipt = {"hardware_executed": False, "platform": platform.uname()._asdict(), "checks": []}
    headers = args.headers_root
    if args.fetch_upstream_headers:
        if headers:
            parser.error("Specify either captured headers or public syntax-only headers")
        commit = json.loads(download("https://api.github.com/repos/airockchip/librga/commits/main"))["sha"]
        listing = json.loads(download(f"https://api.github.com/repos/airockchip/librga/contents/include?ref={commit}"))
        headers = output / "upstream_headers"
        rga = headers / "rga"
        rga.mkdir(parents=True, exist_ok=True)
        entries = [entry for entry in listing if entry["name"].endswith(".h") and entry["type"] == "file"]
        def capture(entry):
            blob = json.loads(download(entry["git_url"]))
            if blob.get("encoding") != "base64":
                raise RuntimeError("Unexpected GitHub blob encoding")
            data = base64.b64decode(blob["content"])
            (rga / entry["name"]).write_bytes(data)
            return entry["name"], hashlib.sha256(data).hexdigest()
        with ThreadPoolExecutor(max_workers=4) as pool:
            hashes = dict(pool.map(capture, entries))
        receipt["header_source"] = {
            "repository": "https://github.com/airockchip/librga", "commit": commit,
            "board_headers": False, "sha256": hashes,
            "limitation": "Public SDK syntax check does not prove the board SDK, driver, imports or execution",
        }
        (output / "upstream_header_source.json").write_text(json.dumps(receipt["header_source"], indent=2) + "\n", encoding="utf-8")
    elif headers:
        hashes = {str(path.relative_to(headers)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in (headers / "rga").rglob("*.h")}
        receipt["header_source"] = {"kind": "local_header_root", "path": str(headers.resolve()), "sha256": hashes,
                                    "board_headers": "not established by a local syntax check"}
        earlier = output / "local_checks.json"
        upstream = output / "upstream_header_source.json"
        if upstream.exists():
            receipt["upstream_header_provenance"] = json.loads(upstream.read_text())
        elif earlier.exists() and headers.resolve() == (output / "upstream_headers").resolve():
            previous = json.loads(earlier.read_text()).get("header_source")
            if previous and previous.get("repository"):
                upstream.write_text(json.dumps(previous, indent=2) + "\n", encoding="utf-8")
                receipt["upstream_header_provenance"] = previous
    if headers:
        command = ["g++", "-std=gnu++14", "-Wall", "-Wextra", "-fsyntax-only",
                   "-I" + str(headers.resolve()), str(HERE / "native_probe.cpp")]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        receipt["checks"].append({"command": command, "returncode": result.returncode,
                                   "stdout": result.stdout, "stderr": result.stderr})
    for name in ("prepare_local.py", "run_board.py", "check_local.py"):
        compile((HERE / name).read_text(encoding="utf-8"), name, "exec")
    receipt["python_syntax"] = True
    receipt["source_sha256"] = {
        name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
        for name in ("reference.hpp", "reference_selftest.cpp", "native_probe.cpp", "run_board.py")
    }
    receipt["passed"] = all(row["returncode"] == 0 for row in receipt["checks"])
    (output / "local_checks.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": receipt["passed"], "hardware_executed": False,
                      "native_syntax_checked": bool(receipt["checks"])}))
    if not receipt["passed"]:
        for row in receipt["checks"]:
            print(row["stderr"])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
