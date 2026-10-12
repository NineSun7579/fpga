"""Scalar model-asset golden, independent of RTL widths and stage logic."""


def lane(accumulator, scale, bias, zero_point, table, bypass=False):
    raw = int(accumulator) * int(scale) + int(bias) + int(zero_point) * 65536
    code = max(0, min(255, (raw + 32768) // 65536))
    return code, code if bypass else int(table[code])


def pack(values, bits):
    mask = (1 << bits) - 1
    return sum((int(value) & mask) << (index * bits) for index, value in enumerate(values))
