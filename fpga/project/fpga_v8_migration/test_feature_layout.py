import unittest

import numpy as np

from feature_layout import pack_c16, unpack_c16
from plan_buffers import plan


class FeatureLayoutTests(unittest.TestCase):
    def test_known_lane_and_channel_group_addresses(self):
        tensor = np.arange(32 * 2 * 3, dtype=np.uint8).reshape(1, 32, 2, 3)
        packed = pack_c16(tensor, 19)
        # The first word contains channels 0..15 at spatial coordinate (0,0).
        self.assertEqual(list(packed[:16]), [channel * 6 for channel in range(16)])
        self.assertEqual(list(packed[16:32]), [channel * 6 + 1 for channel in range(16)])
        self.assertEqual(packed[2 * 3 * 16], tensor[0, 16, 0, 0])
        np.testing.assert_array_equal(unpack_c16(packed, tensor.shape), tensor)

    def test_channel_view_is_a_contiguous_parent_byte_range(self):
        tensor = np.arange(64 * 3 * 5, dtype=np.uint8).reshape(1, 64, 3, 5)
        packed = pack_c16(tensor, 17)
        offset = 32 * 3 * 5
        view = unpack_c16(packed[offset:offset + 32 * 3 * 5], (1, 32, 3, 5))
        np.testing.assert_array_equal(view, tensor[:, 32:64])

    def test_rgb_and_final_three_class_padding_use_zero_point(self):
        tensor = np.array([[[[1, 2]], [[3, 4]], [[5, 6]]]], np.uint8)
        packed = pack_c16(tensor, 128)
        self.assertEqual(list(packed[:16]), [1, 3, 5] + [128] * 13)
        self.assertEqual(list(packed[16:]), [2, 4, 6] + [128] * 13)
        np.testing.assert_array_equal(unpack_c16(packed, tensor.shape), tensor)

    def test_wrong_byte_count_is_rejected(self):
        with self.assertRaises(ValueError):
            unpack_c16(bytes(15), (1, 3, 1, 1))

    def test_parent_survives_late_view_consumer_and_inputs_are_not_overwritten(self):
        tensors = {name: {"shape": [1, channels, 1, 1],
                          "bytes_u8_padded": channels, "padded_channels": channels}
                   for name, channels in [("input", 32), ("parent", 32), ("view", 16),
                                           ("work", 32), ("result", 16)]}
        tasks = [
            {"id": 0, "op": "Conv", "inputs": ["input"], "output": "parent"},
            {"id": 1, "op": "ChannelView", "inputs": ["parent"], "output": "view",
             "input_shapes": [[1, 32, 1, 1]], "channel_start": 16},
            {"id": 2, "op": "Conv", "inputs": ["input"], "output": "work"},
            {"id": 3, "op": "Conv", "inputs": ["view"], "output": "result"},
        ]
        result = plan({"tasks": tasks, "tensors": tensors, "outputs": ["result"]})
        alloc = result["allocations"]
        self.assertEqual(alloc["parent"]["last_consumer_task"], 3)
        self.assertEqual(alloc["view"]["offset"], alloc["parent"]["offset"] + 16)
        self.assertNotEqual(alloc["work"]["offset"], alloc["parent"]["offset"])
        self.assertNotEqual(alloc["work"]["offset"], alloc["input"]["offset"])


if __name__ == "__main__":
    unittest.main()
