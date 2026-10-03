# Verified ModelSim results

The shared-SOF timing mechanism reproduces CAM6's half-rate publication in
the actual production receiver and full camera wrappers. Delaying shared SOF
by 100 us eliminates it with the modeled completion latency. All eight
experiments passed; production module and external FIFO-stub hashes matched
before and after. No source, sensor configuration, merge, PDS or flash changes
were made by this experiment.

| Case | Height | Final-pixel-to-SOF blank | Payload DMA tail* | CAM5 published | CAM6 published |
|---|---:|---:|---:|---:|---:|
| baseline_full | 480 | 0.064 us | 1.28 us | 6/6 | 3/6 |
| delayed_100us_full | 480 | 100 us | 1.28 us | 6/6 | 6/6 |
| short_fast_dma | 2 | 0.512 us | 0 us | 6/6 | 6/6 |
| short_256 | 2 | 0.064 us | 1.28 us | 6/6 | 3/6 |
| short_1024 | 2 | 0.064 us | 5.12 us | 3/6 | 3/6 |
| short_1100 | 2 | 0.064 us | 5.50 us | 3/6 | 3/6 |
| delayed_tail_19000 | 2 | 100 us | 95 us | 6/6 | 6/6 |
| delayed_tail_21000 | 2 | 100 us | 105 us | 3/6 | 3/6 |

*Tail parameter starts after the final accepted AXI payload beat. In these
runs the actual payload completion pulse is generated `TAIL+5` AXI cycles
after the last accepted source pixel. The tag completion pulse follows
20 cycles later. The production FSM then consumes completion and flushes.
AXI cycles are 5 ns. Height-2 cases are timing controls; their synthetic
offered frame rates are not sensor frame-rate claims.

The six full 640x480 frames per camera were checked pixel by pixel after
the production packer, including every final pixel. Each successful tag
contained the next sequence value; no source faults or FIFO overflow occurred.
At the modeled baseline offered rate of 50.158098 fps, CAM5's publication
rate was 50.158098 fps and CAM6's 25.079049 fps. With 100 us blank the offered
rate was 49.907930 fps and both published at 49.907930 fps.

The decisive baseline trace at the second shared SOF is:

```text
SOF CAM5 frame=2 cycle=3987463 admitted=2 dropped=0 state=1 flush=0 complete=0 last_pixel_age=1040
SOF CAM6 frame=2 cycle=3987463 admitted=1 dropped=1 state=4 flush=0 complete=1 last_pixel_age=16
DONE CAM6 frame=2 tag=0 cycle=3987708 last_pixel_age=261 last_beat_age=257
DONE CAM6 frame=2 tag=1 cycle=3987728 last_pixel_age=281 last_beat_age=17
```

The same SOF reaches both engines on the same AXI cycle. CAM5 is idle;
CAM6 is still in DATA despite having captured every pixel. Its payload
and tag complete later, but the SOF has already been discarded. It does
not restart mid-frame; it admits frame 3, then drops frame 4, and so on.
The 1040-versus-16-cycle ages demonstrate the 1024-AXI-cycle / 640-RX-cycle
last-pixel lead for CAM5.

The corresponding delayed trace is:

```text
SOF CAM5 frame=2 cycle=4007450 admitted=2 dropped=0 state=1 flush=0 complete=0 last_pixel_age=21027
SOF CAM6 frame=2 cycle=4007450 admitted=2 dropped=0 state=1 flush=0 complete=0 last_pixel_age=20003
```

Both engines have retired the payload, tag, and local flush before shared
SOF, and every subsequent frame is admitted. The 1024-cycle tail control
also exposes the tag requirement: CAM5 has completed payload but remains
in WAIT_TAG_DONE (`state=6`) when its SOF arrives, so it too loses that frame.

This establishes a receiver mechanism, not the measured board root cause
or a hardware >=40-fps result. The 64-ns baseline blank and DMA tails are
controlled test inputs, not hardware measurements. Actual source blank
and DDR retirement latency must be confirmed on the board. In particular,
100 us is sufficient only when payload, tag, and flush finish before SOF;
the 105-us negative control disproves any unconditional guarantee.

Reproduction: `python run.py` in this directory. `python run.py --resume`
can retain already-passing case logs. See `results.log`, individual case
logs, `compile.log`, `source_audit.log`, and the paired SHA-256 JSON files.
The log message's `frame` field is the latest incoming SOF index; a completion
logged as frame 2 after a drop can belong to the still-retiring frame 1.
