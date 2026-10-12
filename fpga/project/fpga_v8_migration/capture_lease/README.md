# Capture lease candidate

This directory is an isolated candidate. `fpga_v8_capture_lease` reserves a
camera DDR bank on the **actual admitted `m_vsync`**, before the original
controller's delayed SOF synchronizer presents a DMA command. The bank becomes
HELD only after the actual tag command completes successfully:
`dma_done && ctrl.dbg_state[2:0] == 6 && frame_good && !dma_abort`.
No local timer, legacy `xdma_ack`, or early SOF releases ownership.

`fpga_v8_capture_ov5640_ddr` is an ASCII candidate copy of the production
wrapper. It instantiates the unmodified production `ov5640_ddr_w_en`,
`ov5640_ddr_w`, and `ov5640_ddr_w_ctrl`. Its only admission extension is
`lease_block` in `w_en.engine_busy`; packing and the controller SOF synchronizer
are unchanged. It exports actual admission, bank selection, successful tag B,
and retired-error events. Its source validity/overflow/flush machinery matches
the production wrapper. Connect **the original `axi_dma_write`** using
`WAIT_FOR_DATA=1`, `BURST_LEN=16`, and full 16-byte input keep. Connect its
`data_in_last` to wrapper `dma_done` and `data_in_abort` to `dma_abort`. The latter
means accepted AXI AW/W/B obligations have retired; it is not an abort request.

The bank state outputs encode FREE=0, WRITING=1, HELD=2. Offered descriptors
already hold the bank indefinitely. Sensor pixels are never backpressured;
new whole frames are dropped at SOF when the original controller-selected bank
is unavailable. The original controller alternates banks only on publication,
so a free other bank cannot bypass a held selected bank. This is conservative
but does not modify original bank-selection logic.

## Source and fixed layout

Use the unfiltered **cam5 SFP RGB565 stream** (`cam5_pix/de/hs/vs`) feeding
production `top.v:1782`; cam1–4 go through FIR processing. Production cam5 is
already DATA_WIDTH=16, CAM_DATA_LEN=38400, bank0=0x01800000,
bank1=0x01A00000. The cooperative controller checks camera ID `<6`, so CAM_ID=4
denotes physical cam5 using zero-based indices. No production top is edited.

All manager/wrapper parameters must agree. Defaults are 640x480 RGB565,
RAW_LENGTH=614400 bytes, plus a separate full 16-byte tag word, and DDR_LIMIT=
256 MiB (exclusive end). Manager elaboration guards check nonzero geometry,
exact `2*width*height == 16*CAM_DATA_LEN == RAW_LENGTH`, even/nonzero beat count,
16-byte base alignment, no bank overlap including tags, and widened end bounds.
Only DATA_WIDTH=16 is certified. The wrapper fixes its length and addresses as
parameters; there is no unverified software address/length configuration.
RAW descriptors exclude the tag from their length. Parameter rejection blocks
capture and rejects every attempted arm.

## Independent consumers

HOST_REQUIRED defaults to **1**. Each successfully published bank has two
independent obligations: cooperative RAW conversion and host RAW reads. Each
consumer gets a separate valid/ready descriptor and must first accept it. Fields
are `{src_addr,length,seq,generation,camera,bank,token64}`; the cooperative port
also asserts `input_raw_valid=1` only for successfully completed good RAW frames.
Descriptors stay stable under backpressure. Each consumer selects bank0 first
when both banks are eligible at startup, then uses its own round-robin pointer;
an already offered descriptor remains selected until accepted.

Wire the cooperative manager ports to `cooperative_control` on a common clock:

Connect manager `clk`, wrapper/DMA `axi_clk/clk`, and controller `core_clk` to
that same clock. Manager/wrapper/DMA reset is active high; controller `rst_n`
is the inverse of the common reset, with coordinated deassertion.

| Capture manager | Cooperative controller |
| --- | --- |
| `input_valid/ready`, `input_raw_valid` | same-named ports |
| `input_src_addr/generation/camera` | same-named ports |
| `input_seq` | `input_source_seq` |
| `input_bank`, `input_token` | `input_camera_bank`, `input_lease_token` |
| `release_valid/ready` | `src_release_valid/ready` |
| `release_camera/seq/generation/token` | same suffix on `src_release_*` |
| `release_bank` | `src_release_camera_bank` |

The controller's `src_release_addr` is redundant with the fixed bank addresses
and can be checked by the integration adapter. The token is opaque to that
controller. No extra claim signal is needed: descriptor
valid/ready is the claim. The controller passes the release identity back after
its actual bridge drain.

The host adapter must implement `host_valid/ready` as an explicit RAW lease
claim, bind the accepted immutable descriptor, finish **all** reads/DMA work,
then supply `host_release_*`. Both release interfaces consume each valid/ready
request and pulse exactly one of accept/reject. Ready permits rejected requests;
ready alone never means a release succeeded. A release before the corresponding
claim, wrong camera/bank/sequence/generation/token, duplicate release, and stale
release are rejected. Same-edge claim plus release is premature and rejected.
Only both successful releases free the bank, including simultaneous releases.
The original `xdma_req/ack` interface remains available for cosmetic legacy
notifications, and has **no connection** to manager ownership.

HOST_REQUIRED=0 is an explicit isolated cooperative-only mode. It is safe only
when there are no host RAW readers or other consumers; host descriptors are
disabled and all host releases rejected. There is no boolean ACK shortcut.

## Epoch, sequence and reset

After common reset, capture is disarmed. Supply `config_valid` and a fresh
nonzero `config_generation`; hold until `config_ready`. The handshake is ready
only with both banks FREE and the actual wrapper idle/flush complete. On valid
configuration it pulses `config_accept` and `epoch_start`. Connect `epoch_start`
back to the wrapper: it synchronously restarts the **idle** camera datapath and
its tag counter, while DMA has no remaining obligations. Configuration requests
block SOF admission to avoid a same-edge race. Zero and current generations
are rejected. Configuration during leases is backpressured.

Successful publication uses the actual tag counter+1. Sequence is global for
this single camera stream, starts at 1 per configured generation, and token64=
`{generation,seq}`. Publication of 0xffffffff disarms before sequence can wrap;
all leases must finish before arming with a fresh generation. Identity mismatch
between manager and tag counter latches `protocol_fault` and stops admission.

**The manager cannot establish a fresh epoch across power cycles or resets.**
Reset erases its generation history. The host must allocate a never-reused
generation and must also avoid reusing older generations after ordinary rearm:
hardware only detects zero and the current generation. Generation exhaustion,
host persistence, and rollover allocation are external protocol responsibilities.
Multiple camera streams must use an integration policy that also prevents the
cooperative output controller's bank/sequence/generation ACK key from colliding.

Reset must be coordinated across capture manager, wrapper/FIFOs, DMA,
cooperative core, DDR adapter/interconnect, and host transaction models. Reset
cancels all leases without synthetic releases; resetting only the manager
while DMA can still write is unsafe. Test reset cancels an accepted AW using a
common DMA/memory-model reset, then proves fresh-generation admission and
old-token rejection. Independent clock domains require a real descriptor and
release CDC bridge, synchronized reset release, and an epoch barrier. These
bindings are not supplied here.

## Verification

Run `python run_tests.py` in this directory. ModelSim defaults to
`C:/modeltech64_10.6e/win64`; override MODELSIM_BIN if needed. Production and
candidate RTL compile without `-sv` (testbench alone uses SystemVerilog).
The tests use the official Pango DRM/FIFO models and original camera/DMA RTL;
there are no behavioral FIFO substitutes. Every consumed WDATA bit, WSTRB and
WLAST is checked for X/Z, including zero-strobe abort padding. Python independently
checks full 128-bit pixel words, tag padding/counter, AW/W/B retirement, every
published DDR image, deterministic descriptors, claims/releases, public state
snapshots and frozen held-bank contents.

The suite covers full 640x480 and small geometry; default dual readers;
cooperative-only mode; both banks held; each consumer released first; premature,
wrong and stale releases; legacy ACK; descriptor backpressure; malformed short
and natural official-FIFO overflow; early SOF while AW/B blocked; successful tag
B held through another complete sensor frame; payload/tag B errors; recovery;
reset mid accepted AW; rearm and sequence rollover. Rollover uses a documented
testbench deposit into near-limit counters, not a production shortcut.

`artifacts/production_hashes_before.json` and `production_hashes_after.json`
retain the initial 22-file dependency baseline. The additional
`production_scope_hashes_before.json` / `production_scope_hashes_after.json`
cover all 42 active camera/DMA/top/FIFO/vendor Verilog files, including FIFO
templates and the included DRM reset-value file. The
runner scans module names with a Python bytes regex across production source
and active candidates, excluding generated artifacts. `artifacts/results.json`
records exact commands, trace hashes and oracle counts. No PDS, synthesis,
board, DDR adapter or host protocol binding is changed or run by this candidate.
