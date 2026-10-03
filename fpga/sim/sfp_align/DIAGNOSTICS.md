The authorized repair was validated by rerunning the unchanged full matrix
with ModelSim SE-64 10.6e against the actual modified production wrapper:
41 cases completed, compile errors/warnings 0/0, and FIFO overflow zero.
Every input `.vec` is byte-identical to the original investigation input.
All 41 result records match the historical isolated probe records.

All four baseline offsets retain one SOF and exact pixels. The deletion in
blank control before an intact singleton SOF now gives one SOF and all
64 exact pixels at every offset; its full-size replay gives one SOF and
614400 exact pixels after SOF (previously zero SOF and zero after-SOF count).
The remaining deletion-before-data limitation is unchanged: 62/64 at every
offset and 614398/614400 in the full-size replay, with the same two pixels
lost. Deletion inside a singleton SOF still destroys its signature and
misses SOF. Physical root cause remains unproved.

Repair evidence is in `results/summary.json`, `results/compile.log`, and
`results/repair_audit.json`, with individual vectors, traces, and pixels.
The audit verifies actual production compilation, unchanged inputs,
the exact single ASCII production replacement, preserved baselines,
restored intact-SOF cases, and unchanged remaining deletion limitations.

The initial investigation with ModelSim SE-64 10.6e completed 41 original production replays and 41 isolated probe
replays. The production run compiled the actual wrapper and video decoder;
no physical HSST implementation was compiled. All runs had zero decoder
FIFO overflow. All four initial byte offsets passed the unchanged stream
with exact payload identity/order and one VS rising edge.

Original investigation full-frame results (1280x480 = 614400 pixels; offset 0):

| Event | Production SOF | Production pixels / after SOF | Probe SOF | Probe pixels / after SOF |
| --- | ---: | ---: | ---: | ---: |
| None | 1 | 614400 / 614400 | 1 | 614400 / 614400 |
| Delete BC/28 in blank control immediately before single SOF-high control | 0 | 614400 / 0 | 1 | 614400 / 614400 |
| Delete BC/28 in first of two controls before data | 1 | 614400 / 614400 | 1 | 614400 / 614400 |
| Delete BC/28 in last control immediately before data | 1 | 614398 / 614398 | 1 | 614398 / 614398 |
| Insert BC/28 in last control immediately before data | 1 | 614400 / 614400 | 1 | 614400 / 614400 |

The 64-pixel matrix reproduces each deletion loss at all four offsets.
Deleting the pair within a single SOF-high control misses SOF in both
versions; all 64 payload pixels remain exact. When VS high is repeated in
eight consecutive controls, deletion within its first high control still
gives one SOF and all 64 exact pixels in both versions. All tested pair
insertions pass with one SOF and exact pixels.

Concrete rotation defect at production `sfp_rx_link.v:222` and `:226`:
`rot <= new_offset` and `case (rot)` execute together, so the output selects
the old offset. In `results_before_fix/delete_before_sof_off0_n64.trace`, at 300 ns,
`old_rot=0`, `hit=0100`, and candidate 2 is intact `bc2028bc/9`.
The old aligned output remains `bc0028bc/9`. The next window advances,
discarding the only intact VS-high control. The decoder reports zero SOF,
despite recovering every payload pixel exactly.

Minimal proved correction for this specific defect: select the hit
candidate in the same edge that updates the saved rotation, using the
same hit0/1/2/3 priority and falling back to saved `rot` without a hit.
The generated local probe changes only the `case` selector. It restores
SOF in all four short replays and restores the full 614400 pixels after
SOF in the full-size replay. It also preserves every passing baseline.

This correction is insufficient for general two-byte deletion tolerance.
Deleting a pair inside SOF destroys its recognized signature. Deleting
the pair immediately before data changes phase before another intact
control is available; the two pixels `1008/1009` are lost in both versions.
No complete corrective approach for those cases was proved, and none is
proposed here.

Hardware applicability has a concrete unresolved configuration issue:
the actual IP source uses `CH2_RXPCS_SKIP_REG0=10'b110111100` (`0x1BC`) and
`CH2_RXPCS_SKIP_REG1=10'b001010000` (`0x050`), at lines 155 and 159.
The wrapper's BC/28 comment conflicts with the second literal. GE derives
2SKIP and enables GE automatic behavior, but this stub cannot prove that
the physical core removes BC/28. The tests establish receiver defects for
the explicitly requested BC/28 symbol mutations, not a cause of the current
CAM5/CAM6 freeze. Single-SOF tests deliberately expose event loss; repeated
VS-high controls demonstrate that one pair removal need not erase SOF on
a longer pulse.

Initial evidence: `results_before_fix/summary.json`, `results_probe/summary.json`, their
per-case `.log` and `.trace` files, and decoded `.pixels` files. The `.vec`
inputs contain actual raw HSST output bus words and K flags after byte
mutation/repacking. `frame_pixels` is the decoder DE count after a detected
VS rising edge, not a DDR commit or splitter counter.

The initial investigation changed only files under `project/sim/sfp_align`.
The subsequent authorized production repair changes exactly one ASCII
substring at `source/sfp/sfp_rx_link.v:226`:

```verilog
case (hit0 ? 2'd0 : hit1 ? 2'd1 : hit2 ? 2'd2 : hit3 ? 2'd3 : rot)
```

Hit priority remains hit0, hit1, hit2, hit3, with saved `rot` as fallback.
The saved rotation update and all other production source bytes, including
encoding and line endings, are preserved. The byte-exact source before the
repair is saved in `results_before_fix/sfp_rx_link_before_fix.v`.
PDS, IP, and other simulation directories were not edited. The parent's
already-running build164731 uses its old snapshot; this repair does not
update that build or claim its bitstream contains the fix.
