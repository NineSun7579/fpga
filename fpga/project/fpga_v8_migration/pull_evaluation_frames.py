"""Read-only copy of retained board evaluation frames; never alters the viewer.

Frame independence here means file-hash disjointness from development calibration.
It does not establish scene independence, annotation quality, or mAP acceptance.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import posixpath


def copy_frames(remote_dir, output_dir, calibration_dir, helper_path):
    spec = importlib.util.spec_from_file_location("migration_board_connection", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    client = helper.connect()
    calibration_hashes = {hashlib.sha256(path.read_bytes()).hexdigest(): path.name
                          for path in calibration_dir.glob("*.png")}
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    try:
        with client.open_sftp() as sftp:
            names = sorted(name for name in sftp.listdir(remote_dir)
                           if name.lower().endswith((".png", ".jpg", ".jpeg")))
            if not names:
                raise ValueError("No evaluation images found")
            for name in names:
                if Path(name).name != name:
                    raise ValueError("Unexpected frame basename")
                destination = output_dir / name
                source = posixpath.join(remote_dir, name)
                sftp.get(source, str(destination))
                digest = hashlib.sha256(destination.read_bytes()).hexdigest()
                manifest.append({"path": name, "board_path": source, "bytes": destination.stat().st_size,
                                 "sha256": digest, "calibration_same_hash": calibration_hashes.get(digest)})
    finally:
        client.close()
    result = {"status": "unlabelled_retained_evaluation_images_not_accuracy_acceptance",
              "remote_directory": remote_dir, "images": manifest,
              "calibration_hash_overlap_count": sum(bool(row["calibration_same_hash"]) for row in manifest),
              "limits": ["file-hash disjointness does not guarantee independent scenes",
                         "no annotations or class coverage assertion",
                         "retain RAW/RGB565 and model-input preprocessing provenance separately"]}
    (output_dir / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("EVALUATION_FRAMES_COPIED", len(manifest), "calibration_hash_overlap", result["calibration_hash_overlap_count"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="/userdata/model_compare_20261004/frames_eval30")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "evaluation_frames")
    parser.add_argument("--calibration", type=Path, default=Path(__file__).parent / "calibration_smoke")
    parser.add_argument("--ssh-helper", type=Path, default=Path(__file__).parents[1] / "board_ssh.py")
    args = parser.parse_args()
    copy_frames(args.remote, args.out, args.calibration, args.ssh_helper)
