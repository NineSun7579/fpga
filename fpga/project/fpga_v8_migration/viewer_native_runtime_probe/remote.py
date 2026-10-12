"""Bounded calls through the existing board helper; secrets are never printed."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import uuid

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True


def connect():
    spec = importlib.util.spec_from_file_location("probe_board_connection", BASE.parent / "board_ssh.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper, helper.connect()


def call(helper, client, label, command, timeout=60, sudo=False):
    rc, stdout, stderr = helper.run(client, command, timeout=timeout, sudo=sudo)
    (HERE / (label + ".stdout.txt")).write_text(stdout, encoding="utf-8")
    (HERE / (label + ".stderr.txt")).write_text(stderr, encoding="utf-8")
    (HERE / (label + ".command.json")).write_text(json.dumps({"command": command, "timeout_seconds": timeout,
             "sudo": sudo, "return_code": rc}, indent=2) + "\n", encoding="utf-8")
    print(label, "return_code", rc, flush=True)
    return rc, stdout, stderr


def root():
    return json.loads((HERE / "remote_stage.json").read_text())["remote_root"]


def initialize():
    stage = "/userdata/linaro/viewer_native_runtime_probe_" + uuid.uuid4().hex
    helper, client = connect()
    try:
        rc, _, _ = call(helper, client, "create_stage", "mkdir -m 700 " + shlex.quote(stage))
        if rc:
            raise RuntimeError("unique staging directory creation failed")
        previous = None
        if (HERE / "remote_stage.json").exists():
            previous = json.loads((HERE / "remote_stage.json").read_text())
            (HERE / "remote_stage_unavailable.json").write_text(json.dumps(previous, indent=2) + "\n")
        (HERE / "remote_stage.json").write_text(json.dumps({"remote_root": stage}, indent=2) + "\n")
        with client.open_sftp() as sftp:
            sftp.put(str(HERE / "board_inventory.py"), stage + "/board_inventory.py")
        call(helper, client, "input_inventory" if previous is None else "input_inventory_persistent", "python3 " + shlex.quote(stage + "/board_inventory.py") + " inputs", sudo=True)
        call(helper, client, "live_viewer_initial" if previous is None else "live_viewer_stage_recreated", "python3 " + shlex.quote(stage + "/board_inventory.py"), sudo=True)
        call(helper, client, "toolchain", "g++ --version\npkg-config --modversion Qt5Core\npkg-config --cflags --libs Qt5Core\nsha256sum /usr/lib/librknnrt.so")
    finally:
        client.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["initialize"]:
        initialize()
    else:
        raise ValueError("usage: remote.py initialize")
