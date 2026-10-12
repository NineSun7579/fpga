#!/usr/bin/env python3
"""Linux host ABI/aggregation tests; all output stays under egl_swap_probe."""
import os
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
build = root / "host_build"
build.mkdir(exist_ok=True)
cc = os.environ.get("CC", "cc")
flags = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-DPROBE_NO_EGL_HEADERS"]
def compile_(args):
    subprocess.run([cc, *flags, *args], check=True, cwd=root)

compile_(["-shared", "-fPIC", "tests/stub.c", "-Wl,-Bsymbolic-functions", "-o", str(build / "libstub.so")])
compile_(["-shared", "-fPIC", "-DPROBE_TEST_CLOCK", "egl_swap_probe.c", "-ldl", "-pthread",
          "-o", str(build / "libprobe_test.so")])
compile_(["-shared", "-fPIC", "egl_swap_probe.c", "-ldl", "-pthread",
          "-o", str(build / "libegl_swap_probe.so")])
# Also compile against installed official declarations (auto detection).
subprocess.run([cc, *[f for f in flags if f != "-DPROBE_NO_EGL_HEADERS"],
                "-shared", "-fPIC", "egl_swap_probe.c", "-ldl", "-pthread",
                "-o", str(build / "libegl_swap_probe_auto_headers.so")], check=True, cwd=root)
compile_(["tests/host.c", "-L" + str(build), "-lstub", "-ldl", "-pthread", "-rdynamic",
          "-Wl,-rpath,$ORIGIN", "-o", str(build / "host")])

evidence = []
for case, enabled in [("forward", "1"), ("disabled", None), ("disabled", "0"),
                      ("disabled", "yes"), ("clockfail1", "1"), ("clockfail2", "1"),
                      ("reentry", "1"), ("buckets", "1"), ("swapfailure", "1"), ("threads", "1")]:
    env = os.environ.copy()
    env["LD_PRELOAD"] = str(build / "libprobe_test.so")
    env.pop("DETVIEW_EGL_SWAP_PROBE", None)
    if enabled is not None:
        env["DETVIEW_EGL_SWAP_PROBE"] = enabled
    result = subprocess.run([str(build / "host"), case], env=env, capture_output=True, text=True)
    assert result.returncode == 0, (case, result.stdout, result.stderr)
    lines = result.stderr.splitlines()
    reports = [dict(re.findall(r"(\w+)=([^ ]+)", line)) for line in lines if "wall_s=" in line]
    if case == "disabled":
        assert not lines, lines
    else:
        expected = {"forward": 3, "clockfail1": 2, "clockfail2": 2, "reentry": 2, "buckets": 6,
                    "swapfailure": 2, "threads": 401}[case]
        assert sum(int(r["calls"]) for r in reports) == expected, reports
        invalid = int(case.startswith("clockfail"))
        assert sum(int(r["invalid_clock"]) for r in reports) == invalid
        assert sum(int(r["timed"]) for r in reports) == expected - invalid
        for r in reports:
            calls, timed = int(r["calls"]), int(r["timed"])
            wall, total = float(r["wall_s"]), float(r["sum_ms"])
            bins = list(map(int, r["buckets_lt1_lt5_lt10_lt20_ge20"].split(",")))
            assert sum(bins) == timed
            assert int(r["longswap_ge20ms"]) == bins[4]
            assert int(r["success"]) == calls - int(case == "swapfailure")
            assert wall >= 5
            assert abs(float(r["calls_per_wall_s"]) - calls / wall) < 0.0001
            assert abs(float(r["swap_time_per_wall"]) - total / 1000 / wall) < 0.0001
            assert abs(float(r["mean_ms"]) - total / timed) < 0.0001
        if case == "forward":
            intervals = [dict(re.findall(r"(\w+)=([^ ]+)", l)) for l in lines if "interval_request=" in l]
            assert [int(r["interval_request"]) for r in intervals] == [-3, 0, 1, 42, -3]
            assert [int(r["return"]) for r in intervals] == [0, 9, 9, 9, 0]
            assert [int(r["success"]) for r in intervals] == [0, 1, 1, 1, 0]
        if case == "buckets":
            assert reports[0]["buckets_lt1_lt5_lt10_lt20_ge20"] == "1,1,1,1,2"
    evidence.append(f"PASS {case} env={enabled!r}\n{result.stdout}{result.stderr}")
    print(f"PASS {case} env={enabled!r}")
for library in ["libegl_swap_probe.so", "libegl_swap_probe_auto_headers.so"]:
    for case, value in [("forward", "1"), ("disabled", "0")]:
        env = os.environ.copy()
        env.update(LD_PRELOAD=str(build / library), DETVIEW_EGL_SWAP_PROBE=value)
        result = subprocess.run([str(build / "host"), case], env=env, capture_output=True, text=True)
        assert result.returncode == 0, (library, case, result.stderr)
        if case == "disabled":
            assert not result.stderr
        else:
            assert result.stderr.count("interval_request=") == 5
        evidence.append(f"PASS production smoke {library} {case}\n{result.stdout}{result.stderr}")
        print(f"PASS production smoke {library} {case}")
(build / "test_results.txt").write_text("\n".join(evidence))
print("Host stubs only: no hardware performance evidence.")
