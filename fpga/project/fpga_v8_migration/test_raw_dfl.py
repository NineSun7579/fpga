import unittest

import numpy as np

from raw_dfl import SCALES, decode, sigmoid


def empty_outputs():
    result = {}
    for name, side, _ in SCALES:
        result[f"box_{name}"] = np.full((1, 64, side, side), -10, np.float32)
        result[f"cls_{name}"] = np.full((1, 3, side, side), -10, np.float32)
    return result


class RawDflTests(unittest.TestCase):
    def test_logits_use_sigmoid_even_when_all_scores_are_between_zero_and_one(self):
        outputs = empty_outputs()
        outputs["cls_p3"][0, 2, 10, 10] = 0.25
        boxes = decode(outputs, confidence=0.55)
        self.assertEqual(len(boxes), 1)
        self.assertEqual(int(boxes[0, 5]), 2)
        self.assertAlmostEqual(boxes[0, 4], 1 / (1 + np.exp(-0.25)))

    def test_uniform_distribution_has_analytic_distance_and_grid_center(self):
        outputs = empty_outputs()
        outputs["cls_p4"][0, 0, 10, 12] = 10
        boxes = decode(outputs)
        # Uniform bins 0..15 have mean 7.5; P4 stride=16 and center=(grid+0.5)*16.
        np.testing.assert_allclose(boxes[0, :4], [80, 48, 320, 288], atol=1e-9)

    def test_class_aware_nms_keeps_different_classes(self):
        outputs = empty_outputs()
        outputs["cls_p3"][0, 0, 10, 10] = 10
        outputs["cls_p3"][0, 0, 10, 11] = 9
        outputs["cls_p3"][0, 1, 10, 12] = 8
        boxes = decode(outputs)
        self.assertEqual(len(boxes), 2)
        self.assertEqual(set(boxes[:, 5].astype(int)), {0, 1})

    def test_nonfinite_and_wrong_contract_rejected(self):
        outputs = empty_outputs()
        outputs["cls_p5"][0, 0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            decode(outputs)
        outputs = empty_outputs()
        outputs["box_p3"] = outputs["box_p3"][:, :32]
        with self.assertRaises(ValueError):
            decode(outputs)

    def test_extreme_sigmoid_is_finite(self):
        np.testing.assert_array_equal(sigmoid(np.array([-1000, 0, 1000])), [0, 0.5, 1])


if __name__ == "__main__":
    unittest.main()
