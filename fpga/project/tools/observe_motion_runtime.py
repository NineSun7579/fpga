"""Save a bounded runtime observation of the existing RK3568 viewer."""
import argparse
import json
from pathlib import Path
import re
import shlex
import time

from board_host import ssh_connect


VIEWER_PGREP = "{ pgrep -x camview || test $? -eq 1; } && { pgrep -x camview_motion_ || test $? -eq 1; }"
EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "log" / "100h_motion"


def _manifest(name, directory):
    return json.loads((directory / name).read_text(encoding="utf-8-sig"))


def _proc_identity(run, pid):
    stat = run("cat /proc/" + pid + "/stat").strip()
    # comm can contain spaces and parentheses; starttime is field 22.
    end = stat.rfind(")")
    fields = stat[end + 2:].split()
    if end < 0 or stat.split(" (", 1)[0] != pid or len(fields) < 20:
        raise RuntimeError("Invalid viewer process stat")
    starttime = fields[19]
    exe = run("readlink /proc/" + pid + "/exe").strip()
    if not starttime.isdecimal() or not exe.startswith("/") or exe.endswith(" (deleted)"):
        raise RuntimeError("Invalid viewer process identity")
    return {"pid": pid, "starttime": starttime, "exe": exe}


def viewer_identity(run, directory=EVIDENCE_DIR, expected=None):
    pids = run(VIEWER_PGREP + " || test $? -eq 1").split()
    if len(pids) != 1 or not pids[0].isdecimal():
        raise RuntimeError("Expected exactly one running camview or camview_motion_")
    identity = _proc_identity(run, pids[0])
    if expected is not None and any(identity[key] != expected[key]
                                    for key in ("pid", "starttime", "exe")):
        raise RuntimeError("Viewer restarted or executable changed during observation")
    baseline = _manifest("viewer_launch_baseline.json", directory)
    if identity["exe"] == baseline["exe"]:
        identity["kind"] = "baseline"
    else:
        build = _manifest("viewer_build.json", directory)
        installed = build["remote_directory"] + "/camview"
        if identity["exe"] not in (build["binary"], installed):
            raise RuntimeError("Unrecognized viewer executable")
        digest = build["binary_sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError("Invalid candidate manifest hash")
        actual = run("sha256sum /proc/" + pids[0] + "/exe").split()
        if not actual or actual[0] != digest:
            raise RuntimeError("Running candidate hash mismatch")
        identity.update(kind="candidate", binary_sha256=digest)
    if _proc_identity(run, pids[0]) != {key: identity[key] for key in ("pid", "starttime", "exe")}:
        raise RuntimeError("Viewer changed while checking identity")
    if run(VIEWER_PGREP + " || test $? -eq 1").split() != pids:
        raise RuntimeError("Viewer selection changed while checking identity")
    if expected is not None and identity != expected:
        raise RuntimeError("Viewer identity changed during observation")
    return identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--seconds", type=int, default=120)
    args = parser.parse_args()
    if not args.label.replace("_", "").isalnum() or args.seconds < 10:
        parser.error("invalid label or observation duration")
    directory = EVIDENCE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    client = ssh_connect(timeout=8)
    try:
        def run(command):
            stdin, stdout, stderr = client.exec_command(
                "sudo -S sh -c " + shlex.quote(command), timeout=20)
            stdin.write("123456\n")
            stdin.flush()
            output, error = stdout.read(), stderr.read()
            if stdout.channel.recv_exit_status():
                raise RuntimeError(error.decode(errors="replace"))
            return output.decode(errors="replace")

        checkpoint = (
            "cat /proc/uptime; " + VIEWER_PGREP + "; "
            "grep -c 'flip timeout' /var/log/Xorg.0.log || true")
        identity = viewer_identity(run, directory)
        before = run(checkpoint)
        logfile = run("readlink /proc/" + identity["pid"] + "/fd/2").strip()
        if not logfile.startswith("/") or logfile.endswith(" (deleted)"):
            raise RuntimeError("Viewer stderr is not an accessible log file")
        quoted_log = shlex.quote(logfile)
        offset = int(run("stat -c %s " + quoted_log).strip())
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            time.sleep(min(20, max(0, deadline - time.monotonic())))
            viewer_identity(run, directory, identity)
            print(run(checkpoint).strip(), flush=True)
        after = run(checkpoint)
        viewer_identity(run, directory, identity)
        log = run("tail -c +" + str(offset + 1) + " " + quoted_log)
        viewer_identity(run, directory, identity)
        if not log:
            raise RuntimeError("No new viewer log data during observation")
        metrics = {}
        for key in ("swap_fps", "uploaded_fps", "paint_ms", "camera_upload_ms"):
            values = [float(value) for value in re.findall(
                r"^" + key + r"=(\d+(?:\.\d+)?)$", log, re.MULTILINE)]
            if values:
                metrics[key] = {"count": len(values), "min": min(values),
                                "max": max(values), "mean": sum(values) / len(values)}
        evidence = {"before": before, "after": after, "metrics": metrics, "logfile": logfile,
                    "unstable_nonzero": re.findall(r"unstable=([1-9]\d*)", log),
                    "log": log, "viewer_identity": identity}
        path = directory / (args.label + "_observation.json")
        path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(metrics, indent=2))
        print(path)
    finally:
        client.close()


if __name__ == "__main__":
    main()
