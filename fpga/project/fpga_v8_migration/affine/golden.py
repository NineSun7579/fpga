"""Exact integer oracle for unsigned-byte affine add and requantization."""

Q16 = 1 << 16
MAX_SCALE = (1 << 32) - 1


def rounded_value(qa, qb, scale_a, scale_b, zp_a, zp_b, zp_out):
    """Return the signed, unsaturated result; ties round toward positive infinity."""
    for name, value in (("qa", qa), ("qb", qb), ("zp_a", zp_a),
                        ("zp_b", zp_b), ("zp_out", zp_out)):
        if not isinstance(value, int) or not 0 <= value <= 255:
            raise ValueError(f"{name} must be an unsigned byte")
    for name, value in (("scale_a", scale_a), ("scale_b", scale_b)):
        if not isinstance(value, int) or not 0 <= value <= MAX_SCALE:
            raise ValueError(f"{name} must be unsigned 32-bit Q16")
    numerator = ((qa - zp_a) * scale_a + (qb - zp_b) * scale_b
                 + zp_out * Q16)
    return (numerator + Q16 // 2) // Q16


def affine_lane(qa, qb, scale_a, scale_b, zp_a, zp_b, zp_out):
    return min(255, max(0, rounded_value(
        qa, qb, scale_a, scale_b, zp_a, zp_b, zp_out)))


def affine_word(a, b, scale_a, scale_b, zp_a, zp_b, zp_out, lanes=16):
    """Pack lane zero in the least significant byte, as in the RTL."""
    if not isinstance(lanes, int) or lanes < 1:
        raise ValueError("lanes must be a positive integer")
    if not 0 <= a < (1 << (8 * lanes)) or not 0 <= b < (1 << (8 * lanes)):
        raise ValueError("input words must fit the configured lane count")
    return sum(affine_lane((a >> (8 * i)) & 255, (b >> (8 * i)) & 255,
                           scale_a, scale_b, zp_a, zp_b, zp_out) << (8 * i)
               for i in range(lanes))


def pack(values):
    if any(not 0 <= value <= 255 for value in values):
        raise ValueError("pack requires unsigned bytes")
    return sum(value << (8 * i) for i, value in enumerate(values))
