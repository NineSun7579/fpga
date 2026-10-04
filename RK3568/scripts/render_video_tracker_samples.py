#!/usr/bin/env python3
"""Render sampled tracker outputs on their exact input video frames."""
import argparse
import json
from pathlib import Path

import cv2


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('video', type=Path)
    cli.add_argument('log', type=Path)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    rows = [json.loads(line.split('] ', 1)[1]) for line in args.log.read_text(encoding='utf-8', errors='replace').splitlines()
            if line.startswith('[tracker-debug]')]
    if not rows:
        raise ValueError('No tracking records')
    cap = cv2.VideoCapture(str(args.video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    panels = []
    for seconds in [10, 20, 30, 40, 50, 60]:
        target = int(seconds * fps) + 1
        row = min(rows, key=lambda r: abs(int(r['source_frame']) - target))
        index = (int(row['source_frame']) - 1) % frames
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = cap.read()
        if not ok:
            raise ValueError('Cannot decode frame ' + str(index))
        for box in row['boxes']:
            if box['id'] == '0':
                continue
            color = (0, 165, 255) if box['predicted'] else (0, 255, 0)
            xy = (round(box['x']), round(box['y']))
            br = (round(box['x'] + box['w']), round(box['y'] + box['h']))
            cv2.rectangle(image, xy, br, color, 1)
            cv2.putText(image, f"#{box['id']} ncc={box['ncc']:.2f}" + (' P' if box['predicted'] else ''),
                        (xy[0], max(60, xy[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, .35, color, 1)
        cv2.rectangle(image, (0, 0), (640, 40), (30, 30, 30), -1)
        cv2.putText(image, f"video {index / fps:.2f}s | source #{row['source_frame']} | tracks {row['tracked_vehicles']}",
                    (8, 26), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
        panels.append(image)
    cap.release()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), cv2.vconcat([cv2.hconcat(panels[:3]), cv2.hconcat(panels[3:])])):
        raise ValueError('Failed writing samples')
    print(args.output)


if __name__ == '__main__':
    main()
