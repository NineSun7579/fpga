# Channel-copy test report

PASS on 2026-10-05 using Python 3 from
`C:/Users/NineSun/anaconda3/python.exe` and ModelSim SE-64 10.6e from
`C:/modeltech64_10.6e/win64`. Command:

```powershell
python -B run_tests.py
```

Working directory:
`C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/channel_copy`.
The runner invokes `vlib work`,
`vlog -vlog01compat -work work fpga_v8_channel_copy.v tb_fpga_v8_channel_copy.v`,
and `vsim -c -onfinish stop work.tb_fpga_v8_channel_copy +VECTORS=... -do run.do`
from its local `artifacts` directory with absolute RTL paths. Full argument
arrays, source hashes, audit hash, Python version, and output hashes are in
`artifacts/test_results.json`.

Compilation: 0 errors, 0 warnings. Simulation: 0 errors, one tool warning
about the environment's existing `-novopt` setting. All 69 cases completed;
the simulation ran 445,892 clock edges and emitted `PASS_SIM`.

The Verilog scoreboard checked every one of 103,860 accepted output words,
including each `m_last`. Python then checked exact word counts, the entire
word/last lists, and all 1,661,760 output bytes against its independently
generated per-pixel channel slices. All 274,702 declared input words were
consumed. The checks watch eight cycles after each completion for extra
output, duplicate completion, and error persistence. No comparison truncates
either stream or accepts matching prefixes.

The 69 cases are:

- 20 selection/geometry cases: source groups 1, 2, 4, 8 and uneven groups
  3, 5, 7, 9; first, second, middle, last, and full selections; uneven pixel
  and selected-group counts; asymmetric 2x3 and 3x3 layouts.
- 5 directed protocol cases: final output accepted before trailing skipped
  words, source end before a stalled final output, selected-output stall and
  replacement, a waiting valid command throughout an old transaction, and
  a stalled selection spanning trailing skips and the next pixel's skips.
- 5 malformed-last cases: early first marker, early middle marker, missing
  final marker, late marker offered beyond the declared source length, and
  multiple early markers. Each sets sticky `frame_error` while preserving
  the complete configured output and source count.
- 1 maximum-width case: 65,535 source groups and selection of group 65,534.
- 24 deterministic random geometry cases, each with source bubbles, output
  stalls, and changes to every live command field after acceptance.
- All 14 exact model ChannelViews below, also with random source bubbles,
  output stalls, and changed live command fields after acceptance.

Nine additional invalid-command handshakes pass: zero pixels, zero groups,
zero selected count, first group equal to groups, selection crossing the
end, selected count exceeding groups, first group 65,535 with four groups,
65,534 plus two with 65,535 groups, and 65,535 plus 65,535. Each produces a
one-cycle `cmd_error` without starting a transaction or consuming input.

Four reset scenarios pass with selected output pending: a one-word completed
source, a completed source with trailing skips, a maximum 32-bit pixel command
with an early marker, and a source with a missing final marker. Reset is
asserted between clock edges while valid inputs are present. Pending output,
busy, done, error, and ready are cleared; no discarded output or completion
appears after reset. Later commands and golden comparisons pass.

The exact model scenarios read from `audit/tasks.json` are:

| Task | Model operation | Pixels | Source groups | First group | Count | Source words | Output words |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | /model.3/Slice | 80x80 | 4 | 0 | 2 | 25,600 | 12,800 |
| 5 | /model.3/Slice_1 | 80x80 | 4 | 2 | 2 | 25,600 | 12,800 |
| 13 | /model.5/Slice | 40x40 | 8 | 0 | 4 | 12,800 | 6,400 |
| 14 | /model.5/Slice_1 | 40x40 | 8 | 4 | 4 | 12,800 | 6,400 |
| 22 | /model.7/Slice | 20x20 | 16 | 0 | 8 | 6,400 | 3,200 |
| 23 | /model.7/Slice_1 | 20x20 | 16 | 8 | 8 | 6,400 | 3,200 |
| 38 | /model.11/Slice | 40x40 | 8 | 0 | 4 | 12,800 | 6,400 |
| 39 | /model.11/Slice_1 | 40x40 | 8 | 4 | 4 | 12,800 | 6,400 |
| 47 | /model.14/Slice | 80x80 | 4 | 0 | 2 | 25,600 | 12,800 |
| 48 | /model.14/Slice_1 | 80x80 | 4 | 2 | 2 | 25,600 | 12,800 |
| 56 | /model.17/Slice | 40x40 | 8 | 0 | 4 | 12,800 | 6,400 |
| 57 | /model.17/Slice_1 | 40x40 | 8 | 4 | 4 | 12,800 | 6,400 |
| 65 | /model.20/Slice | 20x20 | 16 | 0 | 8 | 6,400 | 3,200 |
| 66 | /model.20/Slice_1 | 20x20 | 16 | 8 | 8 | 6,400 | 3,200 |

The full model scenarios alone compare 102,400 output words and 1,638,400
bytes. Serialization is exactly `[row,column,channel_group,lane]`, with 16
uint8 lanes per 128-bit word and lane zero in the low byte. Expected output
is constructed by slicing channels separately inside each pixel. It does
not reuse the migration feature codec or assume source address aliasing.

Observed protocol coverage:

| Event | Count |
| --- | ---: |
| Skipped source words consumed while output stalled | 14,472 |
| Selected source cycles blocked by pending output | 85,393 |
| Source bubble cycles | 91,905 |
| Output stall cycles while source incomplete | 104,875 |
| Simultaneous source/output handshakes | 83,106 |
| Directed waits for remaining source or output completion | 30 |
| Waiting command cycles during old busy transaction | 28 |

Implementation and generated writes are confined to `channel_copy`. This
report covers isolated RTL simulation and the HWC16 byte contract. No
production RTL, PDS, board, synthesis, or other agents' files were changed.
