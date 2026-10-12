"""Independent scalar candidate convolution arithmetic (Python integers only)."""


def preactivation(accumulator, scale_q16, folded_bias_q16, zero_point):
    if not -(1 << 31) <= accumulator < (1 << 31):
        raise ValueError("accumulator must be signed32")
    if not 0 <= scale_q16 < (1 << 16):
        raise ValueError("scale_q16 must be unsigned16")
    if not -(1 << 31) <= folded_bias_q16 < (1 << 31):
        raise ValueError("folded_bias_q16 must be signed32")
    if not 0 <= zero_point <= 255:
        raise ValueError("zero_point must be unsigned8")
    raw = accumulator * scale_q16 + folded_bias_q16 + zero_point * 65536
    # Euclidean division is independent of RTL bit widths and arithmetic shifts.
    whole, fraction = divmod(raw, 65536)
    nearest = whole + int(fraction >= 32768)
    return max(0, min(255, nearest))


def finish_word(accumulators, scale_q16, biases, zero_point, table, bypass):
    if len(accumulators) != len(biases):
        raise ValueError("lane counts disagree")
    codes = [preactivation(a, scale_q16, b, zero_point)
             for a, b in zip(accumulators, biases)]
    return codes if bypass else [table[code] for code in codes]
