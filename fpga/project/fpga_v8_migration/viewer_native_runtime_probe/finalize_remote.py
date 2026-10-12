"""Read-only final hashes, process identity and retained build artifacts. No inference."""
import hashlib
import json
from pathlib import Path
import shlex
from remote import BASE, HERE, call, connect, root

stage = root()
helper, client = connect()
try:
    call(helper, client, "live_viewer_final", "python3 " + shlex.quote(stage + "/board_inventory.py"), sudo=True)
    remote_files = [row["remote_relative"] for row in json.loads((HERE / "source_dependencies.json").read_text())]
    remote_files += ["runtime_probe.cpp", "prepare_inputs.cpp", "input_expectations.json", "runtime_probe", "native_guard_selftest"]
    rc, _, _ = call(helper, client, "remote_source_and_binary_hashes", "sha256sum " + " ".join(shlex.quote(stage + "/" + name) for name in remote_files))
    if rc:
        raise RuntimeError("final source hashes failed")
    call(helper, client, "model_runtime_final_hashes", "sha256sum /usr/lib/librknnrt.so /root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn", sudo=True)
    call(helper, client, "dependency_identity_final", "python3 " + shlex.quote(stage + "/capture_dependencies.py") + " " + shlex.quote(stage), timeout=60)
    with client.open_sftp() as sftp:
        for name in ("runtime_probe", "native_guard_selftest", "prepare_inputs", "runtime_probe.o", "native_guard_selftest.o", "prepare_inputs.o", "prepare_inputs.d"):
            target = HERE / "artifacts" / name
            target.parent.mkdir(exist_ok=True)
            sftp.get(stage + "/" + name, str(target))
        sftp.get(stage + "/compiled_dependency_hashes.json", str(HERE / "compiled_dependency_hashes_after.json"))
finally:
    client.close()

before = json.loads((HERE / "candidate_public_hashes_before.json").read_text())
after = {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest() for name in before}
(HERE / "candidate_public_hashes_after.json").write_text(json.dumps(after, indent=2) + "\n")
if before != after:
    raise RuntimeError("candidate public source/header hashes changed")
print("PUBLIC_CANDIDATE_HASHES_UNCHANGED", len(before))
