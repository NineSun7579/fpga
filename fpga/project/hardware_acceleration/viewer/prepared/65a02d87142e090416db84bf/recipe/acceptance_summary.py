"""Compute bounded cumulative deltas from one viewer's acceptance log; no board access."""
import argparse
import json
from pathlib import Path

ARRAYS = ("per_camera_paints", "delivered", "dma_frame_requests", "dma_request_bytes",
          "dma_payload_request_bytes", "dma_tag_request_bytes")
SCALARS = ("completed", "failed", "paint_new_frames")


def observed_window(first, last, minimum_seconds=120):
    if first["epoch"] != last["epoch"] or first["started_ns"] != last["started_ns"]:
        raise ValueError("counter epochs differ; never combine restarted viewers")
    a0, a1 = int(first["sample_begin_ns"]), int(first["sample_end_ns"])
    b0, b1 = int(last["sample_begin_ns"]), int(last["sample_end_ns"])
    if a1 < a0 or b1 < b0 or b0 <= a1:
        raise ValueError("invalid or overlapping endpoint sample bounds")
    elapsed_min, elapsed_max = b0 - a1, b1 - a0
    if elapsed_min < minimum_seconds * 1e9:
        raise ValueError(f"observed interval is shorter than {minimum_seconds:g}s after snapshot uncertainty")

    def delta(x, y):
        x, y = int(x), int(y)
        if x < 0 or y < x:
            raise ValueError("cumulative counter decreased")
        return y - x

    totals = {key: delta(first[key], last[key]) for key in SCALARS}
    for key in ARRAYS:
        if len(first[key]) != 6 or len(last[key]) != 6:
            raise ValueError("six-camera arrays required")
        totals[key] = [delta(x, y) for x, y in zip(first[key], last[key])]

    def rates(n):
        return {"minimum_fps": n * 1e9 / elapsed_max, "maximum_fps": n * 1e9 / elapsed_min}

    return dict(status="observed_cumulative_window_not_parity_certification", epoch=first["epoch"],
                first_snapshot=first["snapshot"], last_snapshot=last["snapshot"],
                first_sample_bounds_ns=[a0, a1], last_sample_bounds_ns=[b0, b1],
                seconds_bounds=[elapsed_min / 1e9, elapsed_max / 1e9], delta=totals,
                completed_fps_bounds=rates(totals["completed"]),
                per_camera_paint_fps_bounds=[rates(n) for n in totals["per_camera_paints"]],
                per_camera_delivered_fps_bounds=[rates(n) for n in totals["delivered"]],
                all_six_cameras_painted=all(n > 0 for n in totals["per_camera_paints"]),
                scanout_verified=False,
                limitation="Each counter is exact at its independent atomic read within the recorded endpoint bounds; no common instantaneous cut is claimed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--epoch", help="required when log contains more than one viewer epoch")
    parser.add_argument("--first", type=int, help="first snapshot serial after warmup; default earliest")
    parser.add_argument("--last", type=int, help="last snapshot serial; default latest")
    parser.add_argument("--minimum-seconds", type=float, default=120)
    args = parser.parse_args()
    if args.minimum_seconds < 0:
        parser.error("minimum seconds must be nonnegative")
    rows = [json.loads(line.split("[acceptance] ", 1)[1])
            for line in args.log.read_text(encoding="utf-8").splitlines() if "[acceptance] " in line]
    if args.epoch:
        rows = [row for row in rows if row["epoch"] == args.epoch]
    if len(rows) < 2 or len({row["epoch"] for row in rows}) != 1:
        parser.error("need at least two snapshots from exactly one epoch; select --epoch if needed")
    snapshots = {int(row["snapshot"]): row for row in rows}
    if len(snapshots) != len(rows):
        parser.error("duplicate snapshot serials")
    try:
        first = snapshots[args.first if args.first is not None else min(snapshots)]
        last = snapshots[args.last if args.last is not None else max(snapshots)]
        result = observed_window(first, last, args.minimum_seconds)
    except (KeyError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
