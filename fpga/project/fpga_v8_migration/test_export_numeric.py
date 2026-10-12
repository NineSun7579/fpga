import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from export_numeric import export, q16


class NumericExportTests(unittest.TestCase):
    def test_q16_limits_and_unsigned_half_up(self):
        np.testing.assert_array_equal(q16([0, 0.5 / 65536, 65535]), [0, 1, 4294901760])
        for value in [-1, float("nan"), 65536]:
            with self.assertRaises(ValueError):
                q16(value)

    def test_fused_head_assets_use_output_domain_without_changing_backbone(self):
        root = Path(__file__).parent
        original = json.loads((root / "numeric_layer/numeric.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            export(root / "audit/specialized.onnx", root / "audit/tasks.json",
                   root / "quantization_smoke/quantization.json", output, "per-layer", True)
            fused = json.loads((output / "numeric.json").read_text(encoding="utf-8"))
            head_count = 0
            tasks = json.loads((root / "audit/tasks.json").read_text(encoding="utf-8"))["tasks"]
            for before, after, task in zip(original["operations"], fused["operations"], tasks):
                if task["op"] != "Conv":
                    self.assertEqual(before, after)
                    continue
                if task["activation"] == "clip":
                    head_count += 1
                    self.assertEqual(after["preactivation_quantization"], fused["quantization"][task["output"]])
                    self.assertTrue(after["legacy_shared_scale_u16"])
                    self.assertTrue(after["legacy_bias_i32"])
                else:
                    self.assertEqual(before["preactivation_quantization"], after["preactivation_quantization"])
                    with np.load(root / "numeric_layer" / before["asset"]) as left, np.load(output / after["asset"]) as right:
                        self.assertEqual(set(left.files), set(right.files))
                        for field in left.files:
                            np.testing.assert_array_equal(left[field], right[field])
            self.assertEqual(head_count, 6)


if __name__ == "__main__":
    unittest.main()
