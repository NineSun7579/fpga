"""Build an isolated motion viewer on RK3568 without stopping its DMA owner."""
import hashlib
import json
from pathlib import Path
import shlex
import re
import argparse

from board_host import ssh_connect


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    root = Path(__file__).resolve().parents[2]
    source = root / "project" / "motion_100h" / "host" / "camview"
    names = ("main.cpp", "dma_copy.h", "motion_abi.h", "camview.pro", "test_motion_abi.cpp")
    contents = {name: (source / name).read_bytes() for name in names}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    version = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:12]
    remote = "/userdata/linaro/100h_motion/viewer_" + version
    output = root / "log" / "100h_motion"
    output.mkdir(exist_ok=True)
    client = ssh_connect(timeout=8)
    try:
        def run(command, timeout=30):
            stdin, stdout, stderr = client.exec_command(
                "sudo -S sh -c " + shlex.quote(command), timeout=timeout)
            stdin.write("123456\n")
            stdin.flush()
            data, error = stdout.read(), stderr.read()
            code = stdout.channel.recv_exit_status()
            if code:
                (output / ("viewer_build_" + version + "_failed.log")).write_bytes(data + error)
                raise RuntimeError(data.decode(errors="replace") + error.decode(errors="replace"))
            return data

        # Root owns the actual build directory; uploads are first staged in the
        # authenticated user's writable /userdata tree, then copied by sudo.
        upload = "/userdata/linaro/100h_motion_upload_" + version
        stdin, stdout, stderr = client.exec_command("mkdir -p " + shlex.quote(upload), timeout=20)
        if stdout.channel.recv_exit_status():
            raise RuntimeError(stderr.read().decode(errors="replace"))
        with client.open_sftp() as transfer:
            for name, data in contents.items():
                with transfer.file(upload + "/" + name, "wb") as stream:
                    stream.write(data)
        command = ("mkdir -p " + shlex.quote(remote) + " && cp " +
                   " ".join(shlex.quote(upload + "/" + name) for name in names) +
                   " " + shlex.quote(remote) + " && cd " + shlex.quote(remote) +
                   " && qmake camview.pro && make -j2 && "
                   "c++ -std=c++17 -Wall -Wextra -pedantic test_motion_abi.cpp -o test_motion_abi && "
                   "./test_motion_abi && sha256sum camview_motion_private")
        log = run(command, timeout=120)
        (output / ("viewer_build_" + version + ".log")).write_bytes(log)
        for name in names:
            if (source / name).read_bytes() != contents[name]:
                raise RuntimeError("Local input changed during host build: " + name)
        receipt = {"remote_directory": remote, "binary": remote + "/camview_motion_private",
                   "input_sha256": hashes, "build_log": log.decode(errors="replace")}
        digest = re.search(r"^([0-9a-f]{64})\s+camview_motion_private$", receipt["build_log"], re.MULTILINE)
        if not digest:
            raise RuntimeError("Built binary hash missing")
        receipt["binary_sha256"] = digest.group(1)
        (output / "viewer_build.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(log.decode(errors="replace"))
        print(remote)
    finally:
        client.close()


if __name__ == "__main__":
    main()
