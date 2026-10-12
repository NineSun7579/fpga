# Physical address-limit regression

Result: PASS, ModelSim SE-64 10.6e, 2026-10-05. The tested top is
`fpga_v8_raw_frame_axi_physical`; the original bridge remains unchanged.
Exact simulator argument lists, protected hashes, pass markers, cycle counts,
and byte SHA-256 values are in `artifacts/results.json`.

Diagnostic verified read-only: `project/source/top.v:626` assigns
`ddr3_aw_addr <= ddr_axi_awaddr[27:0]`; line 647 assigns
`ddr3_ar_addr <= ddr_axi_araddr[27:0]`. Thus the original 512 MiB decode-based
contract admits aliased physical addresses. The corrected default and maximum
`DDR_ADDRESS_LIMIT` are `0x10000000`, 256 MiB. Zero, unaligned, larger limits,
and footprints exceeding the configured limit reject commands before AXI.

| Case | Geometry W/H/OUT_H/TOP | Limit | Retired frames | Compared bytes | Simulation time |
| --- | --- | --- | ---: | ---: | ---: |
| small_4x3 | 4/3/5/1 | 0x10000000 | 16 | 960 | 1.599 s |
| overflow_1x1 | 1/1/6/2 | 0x10000000 | 16 | 288 | 1.578 s |
| smaller_limit_4x3 | 4/3/5/1 | 0x02000000 | 16 | 960 | 1.618 s |
| full_640x480 | 640/480/640/80 | 0x10000000 | 1 | 1,228,800 | 3.175 s |
| invalid_config | Eight rejected parameter sets | Mixed invalid | 0 | 0 | 1.627 s |

Total: 49 retired frames, 1,231,008 bytes compared by the AXI testbench and
again by independent Python, 45 rejected address commands, eight rejected
configuration instances. Fifteen frames intentionally retire with sticky
RID/RRESP/RLAST/BID/BRESP error; others retire without error. The complete
prior stall, partial-word, snapshot, error-drain, final-B, and common-reset
coverage runs on the corrected module, including the full default baseline.
Each of the five compilations has zero warnings/errors; simulation has zero
errors and only ModelSim's existing disabled-optimization warning.

Each small suite explicitly rejects source and destination bases at the
configured limit, footprints ending 16 bytes beyond it, the old `0x20000000`
boundary, and the high-alias address `0x10001000`. Alignment, overlap, and
32-bit wrap cases also reject. No rejected command issues AR/AW/W or reports
`done`. The testbench asserts that every accepted AR/AW 16-byte footprint is
within the configured physical limit.

Exact-default-boundary clean transfers pass for both source and destination:

| Geometry | Source base ending at 0x10000000 | Destination base ending at 0x10000000 |
| --- | --- | --- |
| 4x3 -> 4x5 | 0x0fffffe0 (32 bus bytes) | 0x0fffffc0 (64 bus bytes) |
| 1x1 -> 1x6 | 0x0ffffff0 (16 bus bytes) | 0x0fffffe0 (32 bus bytes) |

The aligned smaller limit 0x02000000 also passes end-equals-limit reads and
writes, while rejecting addresses beyond the smaller bound. Invalid-limit
instances test `0`, `0x08000001`, `0x20000000`, and a valid aligned `0x10`
limit too small for the frame. The other four instances exercise the prior
invalid geometry cases. `CONFIG_OK` is checked directly as well as rejection
signals, so limit failures cannot hide behind an unrelated invalid address.

Full baseline: 38,400 AR/R and 76,800 AW/W/B, 950,492 active cycles,
1,228,800 bytes, SHA-256:

```text
a5bffe15ad024e7311ac19ec729420dc83db3d37df7fccd509cedab092811074
```

The final B is delayed by 80 cycles (81 observed slave scheduling cycles).
`done`/`cmd_ready` remain blocked until its acceptance and full drain.
No board throughput or timing-closure claim follows from these cycles.

Staged RTL SHA-256:

```text
cd4824105e0aea6e08ee0ed24a47de3efc1ad437ea39c2da67f71472eee8fc55
```

Frozen original SHA-256, unchanged before/after the regression:

```text
235f878ac7a35134f2ce9f8b9b56fecf66d033387715c46e953fa0a907df5b40
```

Shared RTL and original testbench/runner hashes are also unchanged. All three
new Verilog modules have unique names and ASCII content. `PROMOTE.patch` was
validated entirely in memory: its proposed RTL and testbenches equal the
tested copies after restoring original names/markers; the proposed Python
runner parses successfully. It has not been applied.

Pending handoff: the parent must confirm the concurrent synthesis is finished,
apply `PROMOTE.patch`, run the promoted regression, and rerun PDS for the new
bridge hash `c2bdc1a3622fa0c84fc487a9859ba27220ddad4c5d304bc4221157906c47bc6f`.
The old PDS result does not validate this fix. Publish only on `done && !error`;
outstanding AXI still requires common bridge/interconnect/slave reset.
