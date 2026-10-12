"""Audit CAM1–4 motion metadata and all six video capture channels."""
import argparse
import json
from pathlib import Path
import re


def audit(text):
    expression = re.compile(
        r"motion camera=(\d+) seq=(\d+) valid=([01]) blocks=(\d+) samples=(\d+) "
        r"bbox=(none|\d+,\d+-\d+,\d+) error=([01]) generation=(\d+) "
        r"latest=1 bitmap=([0-9a-fA-F]{48})$")
    channels = {camera: [] for camera in range(1, 5)}
    errors = []
    matches = []
    for line in text.splitlines():
        if line.startswith("motion camera="):
            match = expression.fullmatch(line)
            if match is None:
                errors.append("Malformed motion record: " + line[:160])
            else:
                matches.append(match)
    for match in matches:
        camera, seq, valid, blocks, samples, box, fault, generation, bitmap = match.groups()
        camera, seq, valid, blocks, samples = map(int, (camera, seq, valid, blocks, samples))
        bits = int(bitmap, 16)
        if seq > 0xffffffff or int(generation) > 0xffffffff:
            errors.append("Motion sequence or generation exceeds 32-bit range")
        if camera not in channels:
            errors.append("Invalid camera index " + str(camera))
            continue
        if blocks != bits.bit_count() or blocks > 192 or samples > 19200:
            errors.append("Camera %d sequence %d has inconsistent counts" % (camera, seq))
        if samples < blocks * 8:
            errors.append("Camera %d sequence %d violates block threshold" % (camera, seq))
        if bits:
            coordinates = [(index % 16, index // 16) for index in range(192) if bits >> index & 1]
            expected = "%d,%d-%d,%d" % (
                min(x for x, y in coordinates), min(y for x, y in coordinates),
                max(x for x, y in coordinates), max(y for x, y in coordinates))
            if box != expected:
                errors.append("Camera %d sequence %d bbox differs from bitmap" % (camera, seq))
        elif box != "none":
            errors.append("Empty bitmap has a bounding box")
        if not valid and (samples or bits):
            errors.append("Reference seed contains motion")
        if int(fault):
            errors.append("Camera %d sequence %d reports frame error" % (camera, seq))
        channels[camera].append({"sequence": seq, "valid": valid, "blocks": blocks,
                                 "samples": samples, "generation": int(generation)})
    summary = {}
    for camera, rows in channels.items():
        sequences = [row["sequence"] for row in rows]
        if len(set(sequences)) < 3 or not any(row["valid"] for row in rows):
            errors.append("Camera %d lacks three advancing valid motion snapshots" % camera)
        for before, after in zip(sequences, sequences[1:]):
            delta = (after - before) & 0xffffffff
            if delta >= 0x80000000:
                errors.append("Camera %d motion sequence regressed" % camera)
        generations = [row["generation"] for row in rows]
        for before, after in zip(generations, generations[1:]):
            delta = (after - before) & 0xffffffff
            if delta == 0 or delta >= 0x80000000:
                errors.append("Camera %d snapshot generation failed to advance" % camera)
        capture = [float(value) for value in re.findall(
            r"capture camera=" + str(camera) + r" .*?delivered_fps=([\d.]+)", text)]
        if not capture or min(capture) <= 0:
            errors.append("Camera %d has no live capture evidence" % camera)
        summary[camera] = {"snapshots": len(rows), "distinct_sequences": len(set(sequences)),
                           "valid_snapshots": sum(row["valid"] for row in rows),
                           "max_changed_blocks": max((row["blocks"] for row in rows), default=0),
                           "capture_mean_fps": sum(capture) / len(capture) if capture else None}
    if "motion disabled:" in text:
        errors.append("Motion register polling disabled during observation")
    video_summary = {}
    for camera in range(1, 7):
        capture = [float(value) for value in re.findall(
            r"capture camera=" + str(camera) + r" .*?delivered_fps=([\d.]+)", text)]
        if not capture or min(capture) <= 0:
            errors.append("Video camera %d has no live capture evidence" % camera)
        video_summary[camera] = {"capture_windows": len(capture),
                                "capture_mean_fps": sum(capture) / len(capture) if capture else None}
    if re.search(r"unstable=[1-9]\d*", text):
        errors.append("Unstable camera read reported")
    movement = any(row["blocks"] > 0 and row["valid"] for rows in channels.values() for row in rows)
    if not movement:
        errors.append("No valid changed region observed; live movement remains unverified")
    return {"accepted": not errors, "movement_observed": movement,
            "errors": errors, "cameras": summary, "video_cameras": video_summary}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = args.input.read_text(encoding="utf-8")
    if args.input.suffix == ".json":
        text = json.loads(text)["log"]
    result = audit(text)
    output = args.output or args.input.with_name(args.input.stem + "_audit.json")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
