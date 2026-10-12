# Actual capture/core DDR contract

This directory supplies a simulation-only integration regression. It connects
the finalized capture lease manager (HOST_REQUIRED=1), actual capture wrapper,
unchanged camera w_en/w/w_ctrl, and unchanged axi_dma_write into camera slot 4
of the actual cooperative core. Five independent competing writers use slots
0,1,2,3,5 and disjoint 16-word regions at 0x00800000 + slot*0x00100000. They are
AXI traffic generators, not five additional sensor models.

RAW source regions remain 0x01800000 / 0x01A00000 and prepared output regions
0x08000000 / 0x08200000. Source descriptors and real bridge source releases are
wired directly to the immutable capture manager. Native host RAW claim/release
wires independently hold source leases. Output CLAIM, bound descriptor reads,
staged bank/sequence/generation ACK and doorbell go through the actual control
AXI-Lite interface with 32-bit local addresses/data. PCIe endpoint binding is a
separate parent regression.

The production axi_crossbar_rd routes host reads on slot 0 and core reads on
slot 2. Full IDs at the adapter are 0x06 for host and 0x21 for core (010 route
prefix plus AXI ID 1). The actual DDR adapter and generated ddr_fifo16_w/r IP
are used. The production top read-route snapshot runs on the same accepted
ARs and vendor responses as a shadow; all returned IDs/data/last are compared
while responses are held, including complete unthrottleable 16-word bursts.

The existing fpga_v8_vendor_ddr_stub is unchanged and supplies randomized
AW/AR/W/R scheduling, WID derived from accepted AW and vendor last-consumed
retirement. fpga_v8_capture_contract_memory adds a sparse, exact 256 MiB byte
address space around that scheduler. All memory writes come from actual vendor
W consumption. Reads return those written bytes; there is no preloaded RAW
shortcut and no forced lease/camera/core register. The physical DDR3 IP is not
simulated.

The sensor driver supplies continuous RGB565 pixels within each row and fixed
blanking between rows. It never samples ready. Full geometry is 640x480 into
640x640 RGB888, with 80 rows above/below filled with byte 114. Two smaller
cases exercise retained leases/output backpressure and common reset recovery.

Run `python run_tests.py`; use `--case small_leases`, `--case small_reset`, or
`--case full_640x480` to select a case. The runner writes only below this
directory and hashes the entire finalized capture_lease tree, all 42 production
pins, original read crossbar, actual core/bridge/control/arbiter/adapter and
official Pango primitives before/after.

Each published frame uses prefix `g<generation>_s<sequence>`:

- `*_completed_raw.bin`: physical memory snapshot after actual tag B publication.
- `*_rawbankcopy.bin`: host DDR read copy under the native RAW claim. File format
  is exactly width*height*2 little-endian RGB565 bytes, then a 16-byte tag word:
  little-endian sequence32 followed by twelve zero bytes.
- `*_preparedinput.bin`: host DDR read copy under actual output CLAIM, before
  successful exact ACK. Format is row-major NHWC uint8 RGB, RGB565 components
  expanded by bit replication, with the configured 114-valued letterbox rows.
- `*_source_pixels_fixture.bin`: independent expected sensor RGB565 payload,
  excluding the tag, retained to identify the exact input fixture.
- `*_software_preparedinput.bin`: software result prepared directly from the
  captured RAW copy. Compare this file byte-for-byte with preparedinput.bin.

`checker.json` pairs those files by camera/source bank/sequence/generation/token
and records input/output SHA-256, exact byte counts, source fixture and status.
Python prepares RGB888 from the **captured RAW copy itself**, then also checks
the exact sensor fixture independently. It never repacks PNGs. Reset-cancelled
operations are explicitly marked and do not claim completed prepared output.
`contract_trace.txt` and `memory_trace.txt` permit independent ownership,
memory, all-128-bit FIFO-stream and read-route reconstruction.

This is evidence for the camera/core/adapter/generated-FIFO boundary. It does
not establish a full production-top integration, sensor CDC correctness,
physical DDR timing, host PCIe transport, synthesis, board operation or durable
generation allocation. Production and all finalized dependencies are read-only.
