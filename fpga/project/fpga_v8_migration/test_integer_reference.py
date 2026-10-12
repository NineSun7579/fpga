import unittest

import numpy as np

from integer_reference import convolution, detection_matches, integer_matmul_session, maxpool5, requantize, saturate_q16


class IntegerReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = integer_matmul_session()

    def test_convolution_against_independent_scalar_mac_with_padding_and_stride(self):
        codes = np.array([[[[8, 11, 2, 200], [7, 6, 19, 128], [9, 3, 255, 4]],
                           [[255, 1, 2, 3], [16, 17, 18, 19], [0, 128, 64, 32]]]], np.uint8)
        weights = np.array([[[[1, -2, 3], [4, 0, -5], [6, 7, 8]],
                             [[-127, 2, 3], [4, 5, 6], [7, 8, 127]]]], np.int8)
        actual = convolution(codes, weights, [2, 2], [1, 1, 1, 1], 19, self.session)
        expected = np.zeros((1, 1, 2, 2), np.int64)
        for y in range(2):
            for x in range(2):
                for c in range(2):
                    for ky in range(3):
                        for kx in range(3):
                            iy, ix = y * 2 + ky - 1, x * 2 + kx - 1
                            code = int(codes[0, c, iy, ix]) if 0 <= iy < 3 and 0 <= ix < 4 else 19
                            expected[0, 0, y, x] += code * int(weights[0, c, ky, kx])
        np.testing.assert_array_equal(actual, expected)

    def test_folded_bias_cancelled_zero_input_uses_encoded_multiplier(self):
        codes = np.full((1, 2, 3, 3), 137, np.uint8)
        weights = np.arange(-9, 9, dtype=np.int8).reshape(1, 2, 3, 3)
        accum = convolution(codes, weights, [1, 1], [1, 1, 1, 1], 137, self.session)
        multiplier = 1237
        folded_bias = -137 * int(weights.astype(np.int64).sum()) * multiplier
        np.testing.assert_array_equal(saturate_q16(accum * multiplier + folded_bias + 128 * 65536),
                                      np.full((1, 1, 3, 3), 128, np.uint8))

    def test_rounding_at_signed_half_ties_and_saturation(self):
        inputs = np.array([-65537, -32769, -32768, 32767, 32768, 65536,
                           254 * 65536 + 32768, 255 * 65536 + 32768], np.int64)
        np.testing.assert_array_equal(saturate_q16(inputs), [0, 0, 0, 0, 1, 1, 255, 255])

    def test_requantization_preserves_negative_real_features(self):
        source = {"zero_point": 128}
        destination = {"zero_point": 64}
        np.testing.assert_array_equal(requantize(np.array([124, 127, 128, 130], np.uint8), source,
                                                destination, 32768), [62, 64, 64, 65])

    def test_maxpool_padding_cannot_replace_negative_values_with_affine_zero(self):
        # Every code here represents a negative value with zero-point 100.
        codes = np.full((1, 1, 3, 3), 20, np.uint8)
        np.testing.assert_array_equal(maxpool5(codes), codes)

    def test_detection_matching_rejects_disjoint_boxes_and_wrong_classes(self):
        reference = np.array([[0, 0, 10, 10, 0.8, 1], [30, 30, 40, 40, 0.9, 2]])
        candidate = np.array([[0, 0, 10, 10, 0.8, 2], [30, 30, 40, 40, 0.9, 2],
                              [50, 50, 60, 60, 0.7, 1]])
        result = detection_matches(reference, candidate)
        self.assertEqual(result["matches"][0]["float_index"], 1)
        self.assertEqual(result["matches"][0]["integer_index"], 1)
        self.assertEqual(result["unmatched_float"], [0])
        self.assertEqual(result["unmatched_integer"], [0, 2])


if __name__ == "__main__":
    unittest.main()
