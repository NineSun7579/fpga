"""Read-only retrieval of retained HDMI viewer build inputs and identity."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import stat


def retrieve(destination):
    destination.mkdir(parents=True, exist_ok=False)
    helper_path = Path(__file__).resolve().parents[1] / "board_ssh.py"
    spec = importlib.util.spec_from_file_location("board_connection", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    remote = "/userdata/linaro/detview-hdmifull-src"
    client = helper.connect()
    manifest = {"read_only": True, "remote_root": remote, "files": [], "status": "incomplete"}
    try:
        with client.open_sftp() as sftp:
            def pull(relative=""):
                for entry in sorted(sftp.listdir_attr(remote + ("/" + relative if relative else "")), key=lambda e: e.filename):
                    name = (relative + "/" if relative else "") + entry.filename
                    target = destination / "inputs" / name
                    if stat.S_ISDIR(entry.st_mode):
                        target.mkdir(parents=True, exist_ok=True)
                        pull(name)
                    elif stat.S_ISREG(entry.st_mode):
                        target.parent.mkdir(parents=True, exist_ok=True)
                        sftp.get(remote + "/" + name, str(target))
                        manifest["files"].append({"path": name, "bytes": target.stat().st_size,
                            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
                    else:
                        raise ValueError("Nonregular build input requires explicit handling: " + name)
            pull()
        remote_probe = "python3 - <<'PY'\nfrom pathlib import Path\nimport hashlib,json\nroot=Path(" + repr(remote) + ")\nprint(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()},sort_keys=True))\nPY"
        code, output, error = helper.run(client, remote_probe, timeout=45, sudo=True)
        if code:
            raise RuntimeError("Remote identity verification failed: " + error)
        remote_hashes = json.loads(output)
        local_hashes = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
        if local_hashes != remote_hashes:
            raise ValueError("Build inputs changed during read-only retrieval")
        code, output, error = helper.run(client, "sha256sum " + shlex.quote(remote + "/detview") +
            " /userdata/detview-hdmifull/detview-hdmifull", timeout=30, sudo=True)
        (destination / "binary_identity.txt").write_text(output + error, encoding="utf-8")
        hashes = [line.split()[0] for line in output.splitlines()]
        pinned = "0301f6901330ff161b76f1fb343edb5f0acbf93064b04794c98147da6e92a737"
        if code or hashes != [pinned, pinned] or local_hashes["detview"] != pinned:
            raise ValueError("Retained and installed viewer identities differ")
        manifest.update(status="retrieved_hash_verified", installed_binary_sha256=pinned,
                        complete_retained_directory=True, source_build_binding="requires_independent_rebuild",
                        limits=["Matching retained binary does not alone prove its current adjacent sources built it",
                                "No runtime buffer allocation or current FPGA contents inferred"])
    finally:
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        client.close()
    print("VIEWER_BUILD_RETRIEVED", len(manifest["files"]), manifest["installed_binary_sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    retrieve(parser.parse_args().destination)
