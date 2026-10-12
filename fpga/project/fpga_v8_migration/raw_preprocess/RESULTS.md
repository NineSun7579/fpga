# ModelSim validation results

Command: `python run_tests.py`

Simulator: ModelSim SE-64 10.6e, `C:/modeltech64_10.6e/win64`.
Compilation: `vlog -vlog01compat`, ASCII sources, **0 errors, 0 warnings**.
Result: **23 cases passed**. Independent Python comparison checked
**4,917,738 RGB bytes** in **307,381 128-bit words**, including four complete
640x480 source frames transformed to 640x640 NHWC RGB output frames.

Each full output frame contains 409,600 pixels / 1,228,800 valid bytes /
76,800 full 128-bit words. Top and bottom each contain 80 rows of RGB
`[114,114,114]`. Each full source frame covers all 65,536 RGB565 codes,
including primary colors and the unfiltered literal word `0x464b`.

Cycle counts below measure clock edges from accepted `start` to the final
accepted RGB pixel or final accepted packed word. The simulation clock is a
testbench convention; these are observed cycle counts, not an FPS claim.

| Case | Frame | Final RGB consumed | Final packed word consumed | Packed stall cycles |
| --- | ---: | ---: | ---: | ---: |
| Full ready | 0 | 409,601 | 409,602 | 0 |
| Full ready | 1 | 409,601 | 409,602 | 0 |
| Random source/output stalls | 0 | 537,646 | 537,655 | 35,049 |
| Random source/output stalls | 1 | 538,781 | 538,791 | 34,836 |

With full ready, each frame accepted all 307,200 source pixels on consecutive
clocks and all 409,600 output pixels on consecutive clocks. The packer emits
76,800 words over that continuous pixel stream, retaining bytes across word
boundaries. Stalled runs produced identical frame hashes to full-ready runs.

Other passing checks:

- Three sequential odd 4x3 source / 4x5 output frames: exactly 60 RGB bytes
  per frame, three full words and a final word with `keep=0fff`.
- Three 2x2 frames without padding: exactly 12 bytes and `keep=0fff`.
- Single-pixel frames, top-only padding, bottom-only padding, and zero fill
  on both sides; all per-frame data changes compared exactly.
- Early and late/missing source `last`: sticky errors, geometry-driven
  counts, surplus source rejected, and error cleared by the next command.
- Direct packer test with 33 sequential frames of 1..33 pixels: every final
  byte count and both final overflow cases checked; 1,683 bytes in 121 words.
- Nine-clock stall of the final 24-bit bottom-padding pixel: stable output,
  busy retained, source blocked, done only on final acceptance.
- Reset while integrated outputs are pending; reset with buffered partial
  bytes; reset with a full word plus pending final flush; reset with a final
  partial word; all followed by clean restarts with no ghost output.
- Idle source rejection, busy command rejection, and ten invalid geometry/
  fill combinations rejected through `config_error` with no frame activity.

Machine-readable evidence is in `artifacts/report.json`. Every case has a
`simulation.log`; frame cases also preserve source/golden hex files,
`actual_words.txt`, and `cycles.txt`. `artifacts/compile.log` preserves the
compiler result. See `README.md` for interfaces and reproduction commands.

Both DUT modules remain standalone. No production, PDS, board, or DDR wiring
was changed. Letterbox `done` is completion of its 24-bit stream; a future
DDR writer must separately track the packer's final-word handshake and
memory-write completion. FPGA synthesis, timing closure, and board throughput
were outside this validation.
