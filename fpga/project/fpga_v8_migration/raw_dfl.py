"""Float reference decoding for the verified V8 six-output contract.

Class outputs are logits, not probabilities. All box outputs have 16 bins.
Use this reference for FPGA tensor comparisons before feeding the camera UI.
"""

import numpy as np


CLASSES = ("zebra", "vehicle", "person")
SCALES = (("p3", 80, 8), ("p4", 40, 16), ("p5", 20, 32))


def sigmoid(values):
    values = np.asarray(values, dtype=np.float64)
    exp_negative_abs = np.exp(-np.abs(values))
    return np.where(values >= 0, 1 / (1 + exp_negative_abs),
                    exp_negative_abs / (1 + exp_negative_abs))


def decode(outputs, confidence=0.25, iou_threshold=0.45, max_detections=300):
    if not 0 <= confidence <= 1 or not 0 <= iou_threshold <= 1 or max_detections < 1:
        raise ValueError("Invalid detection thresholds/limit")
    required = {f"{kind}_{scale}" for scale, _, _ in SCALES for kind in ("box", "cls")}
    if set(outputs) != required:
        raise ValueError(f"Expected exactly {sorted(required)}")
    all_boxes, all_scores, all_classes = [], [], []
    for scale, side, stride in SCALES:
        box = np.asarray(outputs[f"box_{scale}"])
        cls = np.asarray(outputs[f"cls_{scale}"])
        if box.shape != (1, 64, side, side) or cls.shape != (1, 3, side, side):
            raise ValueError(f"Incorrect tensor shape at {scale}: {box.shape}, {cls.shape}")
        if not np.isfinite(box).all() or not np.isfinite(cls).all():
            raise ValueError(f"Nonfinite output at {scale}")
        scores = sigmoid(cls[0])
        classes = scores.argmax(axis=0)
        best = scores.max(axis=0)
        y, x = np.nonzero(best >= confidence)
        if not len(x):
            continue
        logits = box[0].reshape(4, 16, side, side)[:, :, y, x].astype(np.float64)
        exps = np.exp(logits - logits.max(axis=1, keepdims=True))
        probabilities = exps / exps.sum(axis=1, keepdims=True)
        distances = (probabilities * np.arange(16)[None, :, None]).sum(axis=1) * stride
        cx, cy = (x + 0.5) * stride, (y + 0.5) * stride
        boxes = np.column_stack((cx - distances[0], cy - distances[1],
                                 cx + distances[2], cy + distances[3]))
        all_boxes.append(boxes)
        all_scores.append(best[y, x])
        all_classes.append(classes[y, x])
    if not all_boxes:
        return np.empty((0, 6), dtype=np.float64)
    boxes, scores, classes = map(np.concatenate, (all_boxes, all_scores, all_classes))
    order = np.argsort(-scores, kind="stable")
    keep = []
    while len(order) and len(keep) < max_detections:
        i = order[0]
        keep.append(i)
        peers = order[1:]
        if not len(peers):
            break
        top_left = np.maximum(boxes[i, :2], boxes[peers, :2])
        bottom_right = np.minimum(boxes[i, 2:], boxes[peers, 2:])
        intersection = np.prod(np.maximum(bottom_right - top_left, 0), axis=1)
        area_i = np.prod(np.maximum(boxes[i, 2:] - boxes[i, :2], 0))
        area_peers = np.prod(np.maximum(boxes[peers, 2:] - boxes[peers, :2], 0), axis=1)
        overlap = intersection / np.maximum(area_i + area_peers - intersection, 1e-12)
        # YOLO NMS is class-aware; overlapping different classes remain visible.
        order = peers[(classes[peers] != classes[i]) | (overlap <= iou_threshold)]
    return np.column_stack((boxes[keep], scores[keep], classes[keep]))
