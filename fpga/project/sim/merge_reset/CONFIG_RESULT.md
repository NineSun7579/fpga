# Simulation-only configuration reset/startup result

ModelSim 10.6e PASS on 2026-10-02 at 3269258340 ns simulation time.
Run `./run_config.ps1`; it regenerates byte-preserving candidate copies and the
reviewable `config_candidate.diff`, then compiles them with the actual unchanged
`power_on_delay.v`. All artifacts stay in this simulation directory. No
production RTL, sensor table, PDS or IP is edited.

## Exact recommended changes

`reg_config.v` (candidate copy `candidate_reg_config.v`):

```diff
-always@(posedge clk_25M)
+always@(posedge clk_25M or negedge camera_rstn)
-always@(posedge clock_20k)
+always@(posedge clock_20k or negedge camera_rstn)
```

Only gate launch in configuration step zero:

```verilog
0:begin
    if (initial_en) begin
        i2c_data <= {8'h78, reg_data};
        start <= 1;
        config_step <= 1;
    end
end
```

`i2c_com.v` (candidate copy `candidate_i2c_com.v`): add
`or negedge camera_rstn` to **both** `always@(posedge clock_i2c)` sensitivity
lists. Existing reset assignments already cover `cyc_count`, `tr_end`,
`ack1/ack2/ack3`, `sclk`, and `reg_sdat`; no new assignments are necessary.

These four asynchronous sensitivity additions plus the step-zero enable guard
are the entire functional diff. Keep the 357-command bound, all sensor table
entries, ACK handling, divider constants and transaction timing unchanged.
The sensor-table suffix beginning at `always@(reg_index)` is checked byte for
byte against production on each preparation; SHA256:
`f12fbadc47126376912b52f1aefe96502249bcc724afd96f31d9df6941878452`.

## What passed

The test uses the actual full-size power delay counters and configuration clock
divider, with 50 MHz power clock and 25 MHz configuration clock. It connects
the actual I2C core, not a transaction-completion mock. A `tri1` SDA models the
pull-up; the slave stub only pulls SDA low in the four released ACK slots.
For this core those slots are current `cyc_count` values 12, 21, 30 and 39.
The core samples the ACK on the following rising control-clock edge.

```text
CONFIG PASS run=1 START=357 STOP=357 completed=357 ACKbits=1428 index=357
CONFIG PASS run=2 START=357 STOP=357 completed=357 ACKbits=1428 index=357
TEST PASS full power startup/config rerun: 357 identical real I2C commands twice,
no pre-enable START, stopped-clock async reset, negative controls
```

- Candidate startup receives reset only through the actual power sequencer.
  No force, deposit, accelerated counters or mocked completion is used on the
  candidate. Divider counter/clock, index, FSM step, start, done, core cycle
  counter, core completion, ACK registers and bus idle outputs are known.
- Across the real interval between camera reset release and `initial_en`,
  config step/index/start/done stay zero, SDA/SCL stay idle, and zero
  transactions launch. Data holding registers may be X before the first
  launch; they are loaded with a known command before START and never used
  as valid data while reset/idle.
- Every actual START is followed by 32 decoded SDA/SCL data bits and four
  low ACK slots, then STOP and `tr_end`. The decoded word matches
  `{8'h78, reg_data}` at its index. All 357 words in the second sequence equal
  the first sequence, in order. Done rises only with index 357 and exactly
  357 STARTs, STOPs and completions. Five further divided-clock edges produce
  no additional transaction.
- After the first complete configuration, the configuration root clock is
  stopped before `rstn` is lowered. The actual power sequencer lowers
  `camera_rstn` using live sys-clock edges. Without any configuration-clock
  edge, done/index/divider/FSM/core reset to their defined values and the bus
  releases. These values remain stable while the clock is stopped. Restart
  then completes the second full 357-command sequence.

## Negative controls

Original byte-preserved RTL copies have only module names renamed:

```text
NEGATIVE PASS: actual legacy divided-clock configuration remains X during camera reset
NEGATIVE PASS: seeded legacy config launches START with initial_en tied low
NEGATIVE PASS: stopped-clock legacy core retains cyc_count=10;
seeded completed legacy config retains done=1/index=357
```

The unknown-startup negative uses no seeding. The enable negative seeds only
the legacy FSM to an idle known state so its ignored input can be tested
independently of the startup-X bug. The stale-done negative seeds only the
legacy FSM to a completed state, then asserts reset without clock edges.
The directly clocked legacy core enters a real active transaction before its
clock stops; its count remains ten and SCL control remains low after reset.

## Limits and integration implication

This resolves the earlier README's configuration-startup/rerun limitation for
the **simulation candidate**. The actual production modules retain that defect
until this reviewed diff is applied alongside the earlier top reset candidate.
The merge test and this configuration test are isolated tests; the entire FPGA
top, vendor primitives, sensor streaming and physical timing are not simulated.

The ACK-only stub proves successful writes, not a complete OV5640 behavioral
model, NACK retry, bus recovery or register readback. Existing configuration FSM
does not inspect `ack`, and the core assigns `ack1` for both of the first two
ACKs; those pre-existing behaviors are outside this minimal reset change.

Enable gates only new launches. If it falls during an active command, that
command finishes; reset still aborts and returns the controller to index zero.
In the tested top sequence `initial_en` stays high until reset. These sensitivity
changes provide asynchronous assertion; they do not introduce per-domain
reset-release synchronizers for the SCCB controllers. Production integration
still requires checking reset recovery/removal and the FPGA's implementation of
the divided control clock. No extra transaction or steady-state logic changes
are recommended from this simulation evidence.
