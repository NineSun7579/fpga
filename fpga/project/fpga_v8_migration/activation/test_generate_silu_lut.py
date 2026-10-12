"""Independent scalar checks for affine quantization and generator artifacts."""

import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from generate_silu_lut import build_silu_lut


CASES = ((0.0625, 128, 0.03125, 16), (0.125, 80, 0.05, 120))


class GeneratorTests(unittest.TestCase):
    def test_all_codes_against_independent_scalar_reference(self):
        tables = []
        for in_scale, in_zp, out_scale, out_zp in CASES:
            table, manifest = build_silu_lut(in_scale, in_zp, out_scale, out_zp)
            errors = []
            unclipped_errors = []
            low = high = 0
            for code in range(256):
                x = (code - in_zp) * in_scale
                y = x / (1.0 + math.exp(-x))
                rounded = round(y / out_scale + out_zp)
                expected = max(0, min(255, rounded))
                self.assertEqual(int(table[code]), expected, (code, x, y))
                error = (expected - out_zp) * out_scale - y
                errors.append(error)
                if 0 <= rounded <= 255:
                    unclipped_errors.append(error)
                low += rounded < 0
                high += rounded > 255
            self.assertEqual(int(table[in_zp]), out_zp)
            self.assertTrue(np.any(table[:in_zp] < out_zp))
            self.assertEqual(manifest["clipped_low_count"], low)
            self.assertEqual(manifest["clipped_high_count"], high)
            self.assertEqual(manifest["table_sha256"], hashlib.sha256(table.tobytes()).hexdigest())
            for name, values in (("all_codes_error", errors),
                                 ("unclipped_codes_error", unclipped_errors)):
                self.assertAlmostEqual(manifest[name]["max_abs"], max(map(abs, values)))
                self.assertAlmostEqual(manifest[name]["mean_abs"], sum(map(abs, values)) / len(values))
                self.assertAlmostEqual(manifest[name]["rmse"], math.sqrt(sum(v*v for v in values) / len(values)))
            self.assertLessEqual(manifest["unclipped_codes_error"]["max_abs"], out_scale / 2 + 1e-12)
            self.assertIn("not_calibrated", manifest["calibration_status"])
            tables.append(table)
        self.assertGreaterEqual(int(np.count_nonzero(tables[0] != tables[1])), 200)

    def test_ties_to_even_and_stable_large_negative_domain(self):
        table, _ = build_silu_lut(100.0, 128, 200.0, 0)
        self.assertEqual(int(table[127]), 0)
        self.assertEqual(int(table[129]), 0)  # SiLU(100) / 200 rounds 0.5 to 0.
        self.assertEqual(int(table[131]), 2)  # 1.5 rounds to 2.

    def test_invalid_parameters(self):
        for args in ((0, 128, 0.1, 16), (float("inf"), 128, 0.1, 16),
                     (float("nan"), 128, 0.1, 16), (0.1, -1, 0.1, 16),
                     (0.1, 128, -0.1, 16), (0.1, 128, 0.1, 256),
                     (1e308, 128, 0.1, 16), (1.0, 128, 1e-320, 16)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                build_silu_lut(*args)

    def test_cli_files_and_error_exit(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=root, prefix="generator_test_") as tmp:
            hex_path = Path(tmp) / "silu.hex"
            manifest_path = Path(tmp) / "silu.json"
            command = [sys.executable, str(root / "generate_silu_lut.py"),
                       "--input-scale", "0.0625", "--input-zero-point", "128",
                       "--output-scale", "0.03125", "--output-zero-point", "16",
                       "--hex", str(hex_path), "--manifest", str(manifest_path)]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertIn("UNCALIBRATED", result.stdout)
            raw = hex_path.read_bytes()
            self.assertEqual(len(raw.splitlines()), 256)
            table = bytes(int(line, 16) for line in raw.splitlines())
            manifest = json.loads(manifest_path.read_text(encoding="ascii"))
            self.assertEqual(manifest["table_sha256"], hashlib.sha256(table).hexdigest())
            self.assertEqual(table, build_silu_lut(*CASES[0])[0].tobytes())
            command[command.index("--input-scale") + 1] = "0"
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be finite and positive", result.stderr)


if __name__ == "__main__":
    unittest.main()
