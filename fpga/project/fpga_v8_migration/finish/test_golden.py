import math
import random
import unittest
from fractions import Fraction

from golden import finish_word, preactivation


class ScalarGoldenTests(unittest.TestCase):
    def test_all_half_boundaries(self):
        for whole in range(-2, 258):
            for offset in (-1, 0, 1):
                bias = whole * 65536 + 32768 + offset
                expected = max(0, min(255, whole + (offset >= 0)))
                self.assertEqual(preactivation(0, 65535, bias, 0), expected)

    def test_fullscale_extrema(self):
        self.assertEqual(preactivation(2147483647, 65535, 2147483647, 255), 255)
        self.assertEqual(preactivation(-2147483648, 65535, -2147483648, 0), 0)
        self.assertEqual(preactivation(-2147483648, 65535, 2147483647, 255), 0)
        self.assertEqual(preactivation(2147483647, 65535, -2147483648, 0), 255)

    def test_unsigned_scale_and_signed_bias(self):
        self.assertEqual(preactivation(1, 65535, -32768, 0), 0)
        self.assertEqual(preactivation(1, 65535, -32767, 0), 1)
        self.assertEqual(preactivation(-1, 65535, 32767, 1), 1)
        self.assertEqual(preactivation(-1, 65535, 32766, 1), 0)
        self.assertEqual(preactivation(1, 32768, 0, 0), 1)

    def test_zero_scale_and_zero_point(self):
        for zp in range(256):
            for acc in (-2147483648, -1, 0, 1, 2147483647):
                self.assertEqual(preactivation(acc, 0, 0, zp), zp)
        self.assertEqual(preactivation(0, 0, -2147483648, 255), 0)
        self.assertEqual(preactivation(0, 0, 2147483647, 0), 255)

    def test_random_against_rational_rounding(self):
        rng = random.Random(20261007)
        for _ in range(12000):
            acc = rng.randrange(-(1 << 31), 1 << 31)
            scale = rng.randrange(65536)
            bias = rng.randrange(-(1 << 31), 1 << 31)
            zp = rng.randrange(256)
            rational = Fraction(acc * scale + bias, 65536) + zp
            expected = max(0, min(255, math.floor(rational + Fraction(1, 2))))
            self.assertEqual(preactivation(acc, scale, bias, zp), expected)

    def test_word_lane_order_lut_and_bypass(self):
        table = [(x * 73 + 19) % 256 for x in range(256)]
        acc = [0, 1, -1, 2147483647, -2147483648]
        bias = [10 * 65536, 0, 0, 0, 0]
        codes = [10, 1, 0, 255, 0]
        self.assertEqual(finish_word(acc, 65535, bias, 0, table, True), codes)
        self.assertEqual(finish_word(acc, 65535, bias, 0, table, False),
                         [table[x] for x in codes])

    def test_out_of_range_inputs(self):
        for args in ((1 << 31, 0, 0, 0), (-(1 << 31) - 1, 0, 0, 0),
                     (0, 65536, 0, 0), (0, -1, 0, 0),
                     (0, 0, 1 << 31, 0), (0, 0, -(1 << 31) - 1, 0),
                     (0, 0, 0, 256), (0, 0, 0, -1)):
            with self.assertRaises(ValueError):
                preactivation(*args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
