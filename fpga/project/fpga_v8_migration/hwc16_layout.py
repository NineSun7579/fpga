"""Legacy pixel-major [row,column,channel_group,lane] feature codec.

Byte lane0 is at the lowest address. Actual DMA loaders must uphold this
contract; historical text/host block reversal must not be silently reused.
"""

import numpy as np


def pack_hwc16(tensor, zero_point):
    tensor = np.asarray(tensor)
    if tensor.dtype != np.uint8 or tensor.ndim != 4 or tensor.shape[0] != 1:
        raise ValueError("Expected batch-1 NCHW uint8")
    if any(dim <= 0 for dim in tensor.shape) or not 0 <= zero_point <= 255:
        raise ValueError("Invalid dimensions or zero-point")
    _, channels, height, width = tensor.shape
    padded_channels = (channels + 15) // 16 * 16
    storage = np.full((height, width, padded_channels), zero_point, np.uint8)
    storage[:, :, :channels] = tensor[0].transpose(1, 2, 0)
    return storage.tobytes()


def unpack_hwc16(data, shape):
    if len(shape) != 4 or shape[0] != 1 or any(dim <= 0 for dim in shape):
        raise ValueError("Expected positive batch-1 NCHW dimensions")
    _, channels, height, width = shape
    padded_channels = (channels + 15) // 16 * 16
    codes = np.frombuffer(data, np.uint8)
    if codes.size != height * width * padded_channels:
        raise ValueError("Packed feature size disagrees with shape")
    return codes.reshape(height, width, padded_channels)[:, :, :channels].transpose(2, 0, 1)[None].copy()


def select_channel_groups(data, pixels, source_groups, first_group, group_count):
    if pixels <= 0 or source_groups <= 0 or first_group < 0 or group_count <= 0 or first_group + group_count > source_groups:
        raise ValueError("Invalid channel-copy contract")
    source = np.frombuffer(data, np.uint8)
    if source.size != pixels * source_groups * 16:
        raise ValueError("Source frame byte count disagrees with command")
    return source.reshape(pixels, source_groups, 16)[:, first_group:first_group + group_count].copy().tobytes()


def pack_weights(weights, input_lanes=16, output_lanes=2, output_align=16):
    weights = np.asarray(weights)
    if weights.dtype != np.int8 or weights.ndim != 4 or weights.shape[2:] not in {(1, 1), (3, 3)}:
        raise ValueError("Expected signed int8 OIHW kernel1 or3")
    if input_lanes != 16 or output_lanes <= 0 or output_align % output_lanes:
        raise ValueError("Expected C16 inputs and output alignment divisible by lane count")
    co, ci, kh, kw = weights.shape
    padded_out = (co + output_align - 1) // output_align * output_align
    padded_in = (ci + input_lanes - 1) // input_lanes * input_lanes
    padded = np.zeros((padded_out, padded_in, kh, kw), np.int8)
    padded[:co, :ci] = weights
    return padded.reshape(padded_out // output_lanes, output_lanes,
                          padded_in // input_lanes, input_lanes, kh, kw).transpose(
                              0, 2, 4, 5, 1, 3).copy().tobytes()


def pack_biases(bias_q16, padded_channels):
    biases = np.asarray(bias_q16, np.int64)
    if biases.ndim != 1 or padded_channels < len(biases) or padded_channels % 2:
        raise ValueError("Invalid bias padding contract")
    if (biases < -2147483648).any() or (biases > 2147483647).any():
        raise ValueError("Bias does not fit legacy signed32 field")
    # Each bias occupies the low32 of a64bit slot; two slots per128bit word.
    storage = np.zeros(padded_channels, dtype="<u8")
    storage[:len(biases)] = (biases & 0xffffffff).astype(np.uint64)
    return storage.tobytes()
