import json
import shlex
import sys
from pathlib import Path
from remote import HERE, call, connect, root

MODEL = "/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn"
MODEL_SHA = "be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9"

helper, client = connect()
stage = root()
try:
    if (HERE / "runtime_return_code.txt").exists():
        raise RuntimeError("refusing a second certification invocation; run guard-only checks separately")
    call(helper, client, "live_viewer_before", "python3 " + shlex.quote(stage + "/board_inventory.py"), sudo=True)
    command = "env -u DET_V8_NATIVE -u DET_INT8_IN " + shlex.quote(stage + "/runtime_probe") + " " + shlex.quote(MODEL) + " " + shlex.quote(stage + "/prepared_inputs.json") + " " + shlex.quote(stage)
    rc, _, _ = call(helper, client, "runtime_probe", "timeout 900s " + command, timeout=930, sudo=True)
    call(helper, client, "live_viewer_after", "python3 " + shlex.quote(stage + "/board_inventory.py"), sudo=True)
    guard_command = "timeout 120s " + shlex.quote(stage + "/native_guard_selftest") + " " + shlex.quote(stage + "/actual_guard_profile.txt")
    guard_rc, _, _ = call(helper, client, "native_guard_selftest", guard_command, timeout=150)
    with client.open_sftp() as sftp:
        for name in ("runtime_report.json", "actual_guard_profile.txt", "probe_runtime_maps.txt"):
            sftp.get(stage + "/" + name, str(HERE / name))
    (HERE / "runtime_return_code.txt").write_text(str(rc) + "\n")
    (HERE / "native_guard_return_code.txt").write_text(str(guard_rc) + "\n")
    if rc or guard_rc:
        raise SystemExit(rc or guard_rc)
finally:
    client.close()
