# Streaming B snapshot alternative (simulation only)

## Actual production rerun after parent applied the change

`run_production.ps1` directly compiled actual production `cam2_merge.v` for all
nine preserved corner-bench cases. All nine passed in ModelSim 10.6e on
2026-10-02, 17:58:15 through 17:59:28. Production is identical to the candidate
after removing comments/whitespace; the sole visible difference is omission of
the added explanatory snapshot comment. Unreachable COPY/cpy logic is retained.

Verified production SHA256:
`462ae7a978678d6440cdc2bdfb05015d8caa3a18db8b904f2dba92548cae0a7c`.
No further production edits were made. Exact extracted frame counts, service
cycles, snapshot counters and PASS lines are preserved in `production_results.txt`;
raw transcripts are `production_<case>.log`. `audit_production.py` verifies the
equivalence, direct production compilation and results.

Every case measured 1285 service clocks/pair, both output frames were
A=307200 + B=307200 =614400, 480 rows, zero pixel/snapshot errors, zero FIFO full.
Partial/mixed cases correctly rejected four/two incomplete B rows respectively.
Late/slow cases exercised 5625/5408 blocked B FIFO-read cycles. Entirely absent B
gave 960 black rows; second-frame missing B repeated the first frame's final
completed B row 480 times. All preserved fallback checks passed.

The top-level read-only check confirms `mrg_clk` still toggles on falling edges
of `clk2core_tx`, consistent with parent restoration to 62.5 MHz. Top-level clock
STA/audit and rebuild remain with parent.

No production/top/PDS/IP files are changed by this experiment. `prepare.py` reads
production, archives its exact bytes in `cam2_merge_reference.v`, and creates
`cam2_merge_stream_snapshot.v`. Run `run_all.ps1` using ModelSim 10.6e.

## Exact minimal change suggested

In `S_RD_B`, immediately after the `b_rcnt` increment, add:

```verilog
if (!b_rep) begin
    if (b_cur) b_memL[b_rcnt[9:0]] <= `UD b_mem1[b_rcnt[9:0]];
    else       b_memL[b_rcnt[9:0]] <= `UD b_mem0[b_rcnt[9:0]];
end
```

In the `if (!b_rep)` branch at the last B pixel, replace the transition to
`S_COPY` with:

```verilog
snap_valid <= `UD 1'b1;
if (pair_cnt == LINES - 13'd1)
    state <= `UD S_VSYNC;
else begin
    pair_cnt <= `UD pair_cnt + 13'd1;
    state <= `UD S_GAP_BA;
end
```

Keep the existing `b_cur <= ~b_cur`, page consumption, `gap_cnt` reset and fallback
branch. The tested minimal candidate leaves unreachable `S_COPY`, `cpy_src`
and `cpy_cnt` logic in place to minimize the diff. Those can be removed later,
but removal is not part of this tested candidate.

## Snapshot semantics and page safety

Only complete accepted B FIFO rows seal a page. While outputting a real B row,
the same page/address used by `c_data` supplies the snapshot write. The page is
held ready until the last pixel, so refill cannot replace an unread pixel.
Consumption releases it on the same edge that reads/writes its last pixel;
the following edge can begin refilling, after the snapshot no longer uses it.

`snap_valid` commits with the final pixel write. During a real row, `b_memL`
temporarily contains a mix of old/new pixels, but no snapshot read occurs:
the FSM cannot preempt a real row or select fallback mid-row. On fallback,
there are no snapshot writes. Thus fallback sees the last completed real row,
and black is used before the first completed real row. Partial input rows never
change the snapshot, because they never become output-ready pages.

Snapshot persists across output VS exactly as in the original. Output frame
boundary is still 480 A/B pairs; delayed B rows can remain queued into the next
output frame. This experiment preserves that existing behavior rather than
adding camera-frame correspondence or flushing.

## Test coverage

All nine cases passed. All output frames had A=307200, B=307200,
merged=614400; all pixel/snapshot checks passed and FIFO full counts were zero.
`service62.log` additionally measured minimum pair service as 1285 clocks.
`suggested_patch.diff` is the exact byte-preserving unified diff against the
captured production reference.

Observed fallback counts: missing=6 rows, partial=4, mixed=6, late=1 initial
black, slow=2. Late/slow cases had respectively 5625/5408 blocked B FIFO-read
cycles, without write drops. Fully absent B produced 960 black rows. B missing
in frame 2 produced 480 real rows then 480 repeats of frame 1's last completed
B row; all 960 completed snapshots were checked.

All tests use actual camera byte capture, vendor IO clock primitives, production
async FIFOs and the candidate merge. A/B byte periods 11.9045/11.900 ns, output
16 ns (62.5 MHz), HTS2000, VTS705, 640 pixels and two frames; EXTRA=1 adds a
481st row. The original startup-zero assumption for unreset capture registers
is retained from the parent simulation.

The scoreboard checks A pixels in order and real B pixels against the queue of
complete captured B rows. Fallback checks every pixel against the last completed
real output row (or zero before one exists). Snapshot contents are checked after
each output row. Real/black/repeat transitions, malformed input rows and stalled
FIFO reads are counted. Every output frame must have 307200 A, 307200 B,
614400 merged pixels and 480 uninterrupted 1280-pixel DE runs.

| Case | B stimulus |
|---|---|
| full62 | Two full 640x480 frames |
| extra62 | 481 input rows each frame; extra row must be capped |
| missing62 | No DE row at source rows 0, 7, 479 each frame |
| partial62 | 320-pixel source rows 11 and 479 each frame |
| mixed62 | Missing rows 0,7; partial row 11 |
| late62 | B starts 20 us late; initial black, then real rows; FIFO backpressure |
| slow62 | B period 11.920 ns (~1302 ppm slower than A); repeat and recovery, backpressure |
| absent62 | No B DE during either frame; all B output must be black |
| frame_missing62 | Full first B frame, no second B frame; last-good row persists across VS |

## Service comparison

For a ready next A page, row service is 640 A + 640 B + four GAP clocks + one
WAIT/entry clock = **1285 clocks**, versus **1925 clocks** with COPY. The earlier
1286/1926 figures were conservative estimates with an extra entry clock.
The candidate scoreboard records `MIN_PAIR_SERVICE_CLOCKS` to verify the count.

| Design | Clocks/pair | Time at 62.5 MHz | Required clock at 84 MHz byte PCLK/HTS2000 |
|---|---:|---:|---:|
| Original COPY | 1925 | 30.800 us | 80.850 MHz |
| Streaming snapshot | 1285 | 20.560 us | 53.970 MHz |

Input row interval is 23.810 us. Streaming snapshot has ~3.25 us service margin
at62.5, avoiding a clock change for the modeled burst rate. Frame-end VS adds
blanking overhead, easily covered by VTS705's blank interval.

## Limitations / parent decision

This proves functional service and fallback semantics in the tested scenarios;
no synthesis or STA was run on the candidate. Snapshot write now shares the
real B read datapath and can change RAM inference or routing. Review inferred
RAM resources and routed timing before choosing it over direct125.

Finite line FIFOs cannot absorb arbitrary camera phase skew or unbounded frame
rate mismatch. No camera backpressure exists; sufficiently delayed/fast B can
still overflow. The late/slow tests cover a bounded skew over two frames, not
long-term lock or arbitrary phase. There is no external output-ready handshake.
Mid-row reset aborts a frame, as in production; snapshot survival across reset
is not provided. Optical CTC and receiver behavior are outside these tests.
