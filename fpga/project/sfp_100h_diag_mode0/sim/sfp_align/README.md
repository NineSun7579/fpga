This isolated test compiles the production `source/sfp/sfp_rx_link.v` and
`source/sfp/sfp_video_rx.v` directly. `hsst_sfp_stub.v` implements every port
connected by the production wrapper. Stimulus enters through the stub's
`o_rxd_2/o_rxk_2` outputs, not through a forced internal aligned bus.
Only the power-on counter is accelerated. The authorized production repair
changes only the alignment case selector in `sfp_rx_link.v`. PDS, IP files,
and other simulation directories are untouched.

Run from this directory in PowerShell:

```powershell
C:\Users\NineSun\anaconda3\python.exe run_tests.py --full
```

Requires ModelSim at `C:/modeltech64_10.6e/win64`. `results/` contains the
replay of the modified actual production wrapper; `results_before_fix/`
preserves the original production replay and byte-exact original source.
`results_probe/` preserves the initial isolated experiment.
Each has compile logs, input byte/K vectors, decoded pixels, realignment
traces, per-case ModelSim logs, and `summary.json`. The probe fixture is
generated from the production source with exactly one replacement:

```verilog
case (rot)
// becomes
case (hit0 ? 2'd0 : hit1 ? 2'd1 : hit2 ? 2'd2 : hit3 ? 2'd3 : rot)
```

The initial probe selected the matching control candidate in the same clock
edge that records the new rotation. That exact single selector replacement
has now been applied to production with all other bytes preserved. The
historical probe is retained as evidence; rerunning `--probe` requires an
unmodified source containing `case (rot)` and is not part of the repair run.

Stimulus uses byte0 first: video control is `BC,28,st,BC`, K bits `1,0,0,1`;
payload is two little-endian RGB565 pixels with all K bits clear.
All four initial byte offsets are covered. One actual `BC(K),28(D)` pair
is removed or duplicated before repacking the continuous byte/K stream
into 32-bit words. No payload byte is deleted, and no discontinuous word
rotation is used to approximate a two-byte CTC event.

The production HSST file sets CH2 CTC to GE, derives 2SKIP mode, and enables
GE automatic behavior. The requested BC/28 mutation coincides with the
first two bytes of each video control. However, inspection of actual
`ipcore/hsst_sfp/hsst_sfp.v` exposes a configuration discrepancy:
`SKIP_REG0=10'b110111100` is `0x1BC`, while
`SKIP_REG1=10'b001010000` is `0x050`, not `0x028`. The vendor example source
also feeds that second literal into its GE skip-byte stream. The production
wrapper comments describing BC/28 are therefore not evidence that the
physical core deletes BC/28. No interpretation of GE automatic behavior
has been proved here. This test models the requested post-CTC symbol result
of an isolated pair event; it does not
model the analog link, vendor FIFO occupancy, GE automatic substitutions,
or the frequency/timing of CTC events on the board.

Cases distinguish deletion in the preceding blank control from deletion
inside the SOF control itself. A single SOF-high control is a deliberate
boundary test. A separate eight-control VS-high case checks redundancy;
one pair deletion in its first high control still permits SOF recovery.
Payloads are paced with two controls per two-pixel word and a blanking tail
to prevent FIFO overflow from obscuring alignment behavior.

`pixels` counts every decoded DE pulse; `frame_pixels` counts DE pulses
after the first observed VS rising edge. It is not a splitter/DDRx frame
commit counter. Pixel identity and order are compared against the original
payload, in addition to counts. All baseline cases assert exact pixels,
one SOF, the expected frame count, and zero overflow. Mutation cases retain
their diagnostic outcomes without asserting that a known defect is correct.

Confirmed defect in the original production wrapper: when a two-byte deletion changes phase, an
intact SOF can be present in a hit candidate while `case (rot)` emits the
old phase. Nonblocking `rot <= ...` takes effect too late for that candidate;
the next clock advances the window, so the SOF is never emitted. With a
single SOF-high control, all four offsets reproduce zero SOF while all
64 pixels remain exact. At 1280x480, all 614400 pixels remain exact but
the count after a detected SOF is zero. Same-cycle hit selection restores
one SOF and all 614400 frame pixels for this exact full-size replay.

Deleting the pair inside a single SOF control instead destroys the
four-byte signature itself (`BC,28,20,BC` becomes `20,BC`). Both production
and the same-cycle probe miss SOF. Rotation selection alone cannot restore
that case.

Deleting the pair from the last control immediately before a data word
also loses exactly that word's two pixels: `1008` and `1009` disappear from
the 64-pixel replay at all four offsets. Both production and probe emit
62 pixels. The corresponding 1280x480 replay emits 614398 pixels with one
SOF and zero FIFO overflows. Deletion from the earlier of two preceding
controls, and all tested insertions, retain exact payload order and counts.

See `DIAGNOSTICS.md` for the final matrix and exact evidence locations.
No complete protocol repair or board-freeze diagnosis is claimed.
