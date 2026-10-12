#!/usr/bin/env python3
"""Local Linux shared-library fixtures, no board or X server required."""
import os
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
build = root / "host_build"
build.mkdir(exist_ok=True)
cc = os.environ.get("CC", "cc")
flags = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-O2"]

def compile_(args, fallback=True):
    subprocess.run([cc, *flags, *(["-DPROBE_NO_XCB_HEADERS"] if fallback else []),
                    *args], cwd=root, check=True)

compile_(["-shared", "-fPIC", "tests/stub.c", "-Wl,-Bsymbolic-functions", "-ldl",
          "-o", str(build / "libstub.so")])
compile_(["-shared", "-fPIC", "-DPROBE_TEST_CLOCK", "xcb_reply_probe.c", "-ldl",
          "-o", str(build / "libprobe_test.so")])
for name, fallback in [("libxcb_reply_probe.so", True), ("libprobe_auto_headers.so", False)]:
    compile_(["-shared", "-fPIC", "xcb_reply_probe.c", "-ldl", "-o", str(build / name)], fallback)
compile_(["tests/host.c", "-L" + str(build), "-lstub", "-ldl", "-pthread", "-rdynamic",
          "-Wl,-rpath,$ORIGIN", "-o", str(build / "host")])

evidence = []
cases = [("forward", "1"), ("buckets", "1"), ("reentry", "1"), ("threads", "1"),
         ("windows", "1"), ("shortwrite", "1")]
cases += [(f"clock{i}", "1") for i in range(1, 9)]
cases += [("disabled", v) for v in [None, "0", "yes", "01"]]
for case, value in cases:
    env = os.environ.copy()
    env.pop("DETVIEW_XCB_REPLY_PROBE", None)
    env.pop("FIXTURE_REAL_CLOCK", None)
    env.pop("FIXTURE_SHORT_WRITE", None)
    if case == "shortwrite":
        env["FIXTURE_SHORT_WRITE"] = "1"
    env["LD_PRELOAD"] = str(build / "libprobe_test.so")
    if value is not None:
        env["DETVIEW_XCB_REPLY_PROBE"] = value
    result = subprocess.run([str(build / "host"), case], env=env, capture_output=True, text=True)
    assert result.returncode == 0, (case, result.returncode, result.stdout, result.stderr)
    reports = [dict(re.findall(r"(\w+)=([^ ]+)", line)) for line in result.stderr.splitlines()]
    if case in ["disabled", "shortwrite", "clock7"]:
        assert not reports
    else:
        assert len(reports) == (3 if case == "threads" else 2 if case == "windows" else 1), reports
        expected = 6 if case == "buckets" else 5 if case == "clock3" else 4
        for index, r in enumerate(reports):
            if case == "windows":
                expected = 4 if index == 0 else 3
            assert int(r["calls"]) == expected, r
            assert int(r["invalid_clock"]) == int(case.startswith("clock")), r
            timed = int(r["timed"])
            bins = list(map(int, r["buckets_lt1_lt5_lt10_lt20_ge20_ms"].split(",")))
            assert sum(bins) == timed == expected - int(case.startswith("clock")), r
            assert int(r["wall_ns"]) >= 5_000_000_000
            if case == "buckets":
                assert bins == [1, 1, 1, 1, 2], r
                assert int(r["sum_ns"]) == 61_500_000 and int(r["max_ns"]) == 25_000_000
            else:
                assert int(r["sum_ns"]) == timed * 500_000
                assert int(r["max_ns"]) == 500_000
        tids = set(re.findall(r"tid=(\d+)", result.stdout))
        assert {r["tid"] for r in reports} == tids
    evidence.append(f"PASS {case} env={value!r} rc={result.returncode}\n{result.stdout}{result.stderr}")
    print(f"PASS {case} env={value!r}")

for library in ["libxcb_reply_probe.so", "libprobe_auto_headers.so"]:
    for case, value in [("forward", "1"), ("disabled", "0")]:
        env = os.environ.copy()
        env.pop("FIXTURE_SHORT_WRITE", None)
        env.update(LD_PRELOAD=str(build / library), DETVIEW_XCB_REPLY_PROBE=value, FIXTURE_REAL_CLOCK="1")
        result = subprocess.run([str(build / "host"), case], env=env, capture_output=True, text=True)
        assert result.returncode == 0, (library, case, result.stderr)
        assert not result.stderr  # real calls complete well inside five seconds
        evidence.append(f"PASS production smoke {library} {case} rc=0\n{result.stdout}")
        print(f"PASS production smoke {library} {case}")

# No initial libxcb: reject at startup even when disabled, never fake success.
for value in ["0", "1"]:
    env = os.environ.copy()
    env.pop("FIXTURE_SHORT_WRITE", None)
    env.update(LD_PRELOAD=str(build / "libxcb_reply_probe.so"), DETVIEW_XCB_REPLY_PROBE=value)
    result = subprocess.run(["/bin/true"], env=env, capture_output=True, text=True)
    assert result.returncode == 127 and "startup resolution unavailable" in result.stderr
    evidence.append(f"PASS missing symbol env={value} rc=127\n{result.stderr}")
    print(f"PASS missing symbol env={value} rc=127")
symbols = subprocess.check_output(["nm", "-D", str(build / "libxcb_reply_probe.so")], text=True)
assert not any(token in symbols for token in
               [" U malloc", " U calloc", " U realloc", " U free", " U xcb_", "__tls_get_addr"])
evidence.append("PASS symbol audit: no allocation, extra XCB imports, or dynamic TLS\n" + symbols)
header_present = Path("/usr/include/xcb/xcb.h").exists()
evidence.append(f"Installed official XCB header present: {header_present}")
print(f"PASS symbol audit; installed official XCB header present: {header_present}")
(build / "test_results.txt").write_text("\n".join(evidence))
print("Host fixtures only; no hardware performance evidence.")
