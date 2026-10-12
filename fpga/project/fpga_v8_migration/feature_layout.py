"""Proposed C16 feature-memory serialization, independent of host endianness.

This codec establishes a testable transfer contract. Legacy RTL compatibility
remains an integration check, not an assumption made by this module.
"""

import numpy as np


def pack_c16(tensor, zero_point):
    tensor = np.asarray(tensor)
    if tensor.dtype != np.uint8 or tensor.ndim != 4 or tensor.shape[0] != 1:
        raise ValueError("Expected batch-1 NCHW uint8 tensor")
    if not 0 <= zero_point <= 255 or any(dim <= 0 for dim in tensor.shape):
        raise ValueError("Invalid tensor dimensions or padding zero-point")
    _, channels, height, width = tensor.shape
    groups = (channels + 15) // 16
    padded = np.full((groups * 16, height, width), zero_point, np.uint8)
    padded[:channels] = tensor[0]
    return padded.reshape(groups, 16, height, width).transpose(0, 2, 3, 1).copy().tobytes()


def unpack_c16(data, shape):
    if len(shape) != 4 or shape[0] != 1 or any(dim <= 0 for dim in shape):
        raise ValueError("Expected positive batch-1 NCHW dimensions")
    _, channels, height, width = shape
    groups = (channels + 15) // 16
    codes = np.frombuffer(data, dtype=np.uint8)
    if codes.size != groups * height * width * 16:
        raise ValueError("Packed byte count does not match tensor dimensions")
    return codes.reshape(groups, height, width, 16).transpose(0, 3, 1, 2).reshape(
        groups * 16, height, width)[:channels][None].copy()
