# Isolated six-camera register snapshot candidate

Candidates are `integrated_six_batch` and `six_camera_batch_viewer_src`. No PDS
process, board/device access, programming, commits, or modifications to baseline
sources/build products were performed. The generator copies source and the
project input only; it does not copy build outputs. External IP/project input
references remain references and were checked to exist.

## Independently verified cause and minimal fix

Byte-level inspection of the actual converter (`source/ov5640/axi_to_axi_lite.v`)
confirmed that it forwards one AR address, returns `{96'b0, m_axil_rdata}`, and
always asserts RLAST. It neither expands ARLEN nor produces a full AXI burst.
The real PCIe read engine subtracts ARLEN+1 and advances the address by that
number of 16-byte beats on RLAST. A 19-beat register request would therefore
skip intermediate register addresses with ordinary burst selection.

The candidate changes only two RTL files: `pcie_fifo.v` selects ARLEN=0 when
the current address is inclusively 0x40020000..0x40020120, and `delivery_regs.v`
advertises caps=15 (new bit3). DDR burst calculation is unchanged. Project
paths are rebased by the generator; no other RTL logic changes are present.

## Viewer behavior

The Reader first probes signature and caps with the original scalar transport.
Caps bit3 enables a 304-byte snapshot containing 19 16-byte register slots; the
32-bit value is at the start of each slot. Without bit3 the original scalar
path runs, with no snapshot ioctl. Snapshot failure quarantines rather than
silently falling back after admission.

Every original validation stage remains: capabilities, idle/default ownership,
selector/size readback, inactive selector status, admission/freeze, source bank
and identity, RAW tag, completion/jobs, identity and byte count before copy,
identity and RAW tag after copy, release acknowledgement and RGB restoration.
Status and configuration stages obtain fresh snapshots. Writes invalidate the
snapshot, and it is explicitly invalidated across tag/payload DMA. The healthy
mock transaction takes 14 snapshots plus two scalar capability probes; no
snapshot survives into a new Reader transaction. This is a serialized register
transport optimization, not a hardware-atomic metadata capture.

Production transport copies 304 bytes from the existing Metadata scratch slot
into owned Reader storage, validates returned offset/address/count, and uses the
existing fd and mutex. RAW/payload addresses, reserved RKNN input layout, copy
routines, analytics/inference/display code, and corrected SIGTERM code are
byte-identical to the current six-camera viewer. `main.cpp` differs only by
the inserted `ThumbnailTransport::readSnapshot` method.

## Actual tests

`sim_six_batch/six_batch_modelsim.log`: ModelSim 10.6e, zero errors, final marker
`SIX_BATCH_ENGINE_PASS ar_stalls=5104 r_stalls=54445 capacity_stalls=47636`.
The complete real `pcie_fifo` read logic connects to the real delivery adapter,
AXI-to-Lite converter and delivery registers. It checks every accepted address,
burst length, response word, FIFO write word/count and final engine retirement.

| Request | Accepted responses/FIFO writes | Accepted ARs |
| --- | ---: | ---: |
| register snapshot, 304 bytes | 19 | 19 |
| final register 0x40020120, 16 bytes | 1 | 1 |
| outside window 0x40020130, 304 bytes | 19 | 2 |
| DDR, 16 / 17 / 32 bytes | 1 / 2 / 2 | 1 / 1 / 1 |
| DDR, 255 / 256 / 257 / 304 bytes | 16 / 16 / 17 / 19 | 1 / 1 / 2 / 2 |
| thumbnail DDR, 153600 bytes | 9600 | 600 |
| RAW DDR, 614400 bytes | 38400 | 2400 |
| RAW plus tag DDR, 614416 bytes | 38401 | 2401 |
| RGB DDR, 1228800 bytes | 76800 | 4800 |

`sim_six_batch/six_batch_baseline_negative.log`: the same test with the baseline
read engine fails at `register burst not single beat`, as expected. It uses a
separate simulation library and never changes the baseline.

`six_camera_batch_viewer_src/six_batch_thumbnail_selftest.log`:
`SIX_THUMBNAIL_SELFTEST_PASS cases=530 failures=0`. Runs the entire pre-existing
camera/bank/fault/timeout/guard suite in both scalar and batch modes, every
snapshot failure, and mutations at idle, selector, held, completion, pre-copy,
post-copy, release and restoration validation stages.

`six_camera_batch_viewer_src/six_batch_transport_selftest.log`:
`SIX_BATCH_TRANSPORT_PASS cases=1545 failures=0`. Compiles the exact extracted
production snapshot method against a local fake ioctl. Covers invalid
arguments, ioctl failure, returned offset/address/length corruption, destination
guards, owned snapshot survival after scratch reuse, and RAW/RKNN canaries.

`six_batch_preservation_report.json` verifies 361 recorded baseline hashes,
the allowed changes, identical reserved layout, preserved validation call
counts, and exact main.cpp insertion removal equality. Full byte hashes are
authoritative; `six_batch_changes.diff` uses reversible Latin-1 byte rendering
because sources contain mixed GBK and UTF-8.

## Reproduction and limitations

On fresh absent candidate directories: run `python make_six_batch.py`,
`python optimize_six_batch_host.py`, then `python extend_six_batch_selftest.py`.
The generator refuses to overwrite existing candidates.

Run `python generate_six_batch_sim.py`; from `sim_six_batch` run
`vsim -c -do run.do -l six_batch_modelsim.log`. For the expected negative
control, generate with `--baseline` and run `run_baseline.do`.

Host tests compile with C++17 and `-O2 -Wall -Wextra`. Define
`THUMBNAIL_STANDALONE_SELFTEST` for `thumbnail_delivery_selftest.cpp`.
Run `python generate_six_batch_transport_test.py` before compiling
`six_batch_transport_selftest.cpp`. Run `python verify_six_batch.py` for audit.
The copied baseline helper `verify_source_preservation.py` is historical;
use the root `verify_six_batch.py` for this candidate.

Vendor PCIe link and FIFO IP are endpoint stubs; command inputs and FIFO
capacity are driven at the endpoint wires. Tests verify enqueue data, not
vendor FIFO CDC, physical PCIe packet delivery, host DMA completion, or the
crossbar. DDR responses come from a backpressured behavioral slave. Real RGB
and thumbnail converter cores compile and instantiate through the adapter but
remain idle in this read-transport test. The read engine simulation copy only
normalizes pre-existing forward/implicit declaration placement for ModelSim;
the candidate synthesis source retains its original declaration layout.
ModelSim reports expected unconnected-stub/unused-port warnings and existing
adapter lock/protection width warnings (62 warnings, zero errors).

Full Qt/aarch64 viewer build, PDS synthesis/timing/bitstream, live register and
payload parity, and display performance measurement remain for the parent.
No hardware or performance result is claimed.
