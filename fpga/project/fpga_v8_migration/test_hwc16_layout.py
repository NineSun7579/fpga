import struct
import unittest

import numpy as np

from hwc16_layout import pack_biases, pack_hwc16, pack_weights, select_channel_groups, unpack_hwc16


class Hwc16LayoutTests(unittest.TestCase):
    def test_pixel_and_group_address_order(self):
        feature = np.arange(32 * 2 * 3, dtype=np.uint8).reshape(1, 32, 2, 3)
        packed = pack_hwc16(feature, 128)
        self.assertEqual(list(packed[:32]), [c * 6 for c in range(32)])
        self.assertEqual(list(packed[32:64]), [c * 6 + 1 for c in range(32)])
        np.testing.assert_array_equal(unpack_hwc16(packed, feature.shape), feature)

    def test_channel_copy_gathers_every_pixel(self):
        feature = np.arange(64 * 3 * 5, dtype=np.uint8).reshape(1, 64, 3, 5)
        source = pack_hwc16(feature, 0)
        selected = select_channel_groups(source, 15, 4, 2, 2)
        np.testing.assert_array_equal(unpack_hwc16(selected, (1, 32, 3, 5)), feature[:, 32:64])
        self.assertNotEqual(selected, source[32 * 3 * 5:])

    def test_nonzero_padding_for_three_classes(self):
        feature = np.array([[[[7, 8]], [[9, 10]], [[11, 12]]]], np.uint8)
        packed = pack_hwc16(feature, 149)
        self.assertEqual(list(packed[:16]), [7, 9, 11] + [149] * 13)

    def test_weight_kernel_and_output_lane_order_with_padding(self):
        weights = np.arange(3 * 17 * 3 * 3, dtype=np.int16).astype(np.int8).reshape(3, 17, 3, 3)
        packed = pack_weights(weights)
        self.assertEqual(len(packed), 16 * 32 * 9)
        expected = []
        for ob in range(0, 16, 2):
            for ib in range(0, 32, 16):
                for y in range(3):
                    for x in range(3):
                        for ol in range(2):
                            for il in range(16):
                                v = int(weights[ob + ol, ib + il, y, x]) if ob + ol < 3 and ib + il < 17 else 0
                                expected.append(v & 255)
        self.assertEqual(packed, bytes(expected))

    def test_signed_biases_in_low32_of64_slots(self):
        data = pack_biases(np.array([-1, 2147483647, -2147483648], np.int64), 16)
        self.assertEqual(struct.unpack("<4Q", data[:32]), (0xffffffff, 0x7fffffff, 0x80000000, 0))
        self.assertEqual(len(data), 128)
        with self.assertRaises(ValueError):
            pack_biases(np.array([2147483648]), 16)


if __name__ == "__main__":
    unittest.main()
