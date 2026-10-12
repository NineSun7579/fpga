# Fourth whole candidate: local bitstream delivery

Current requested endpoint: compile a usable bitstream, without programming it.
No board deployment or cooperative FPS is required to finish this revised task.
Board performance and physical transport acceptance must not be claimed from it.

Implemented changes:

* PCIe receive byte-count metadata is registered with synchronous RAM requests,
  removing the 32-bit length subtraction from the mask/merge data path. Existing
  50 transport scenarios pass. This is RTL function evidence, not routed timing.
* AXI write beat count uses `32-AXI_BURST_SIZE+1` bits. For 128-bit data, the
  maximum is ceil((2^32-1)/16) = 2^28, requiring 29 bits. Eighty differential
  scenarios per mode (160 total across WAIT_FOR_DATA=0/1) match original public outputs and internal beat counts with command
  boundaries, random lengths, stalls and aborts. All seven top instances use
  the unique replacement module; cycle behavior is preserved in those tests.
* Guard 02 removes the original competing asynchronous set/clear behavior.
  Component PDS confirms zero latches, loops and unclocked sequential cells.
  Nine pulse/clock-stop scenarios pass. Runtime fault requires reconfiguration.

`run_whole.py` owns fresh `../whole_candidate_v4_route_01/`. It checks PDS is
idle before each phase, runs compile and synthesis, requires zero loops/latches/
no_clock, then runs physical implementation with inherited physical options.
No IP or FDC is changed. `audit_binding.py` confirms all 694 original inputs
unchanged and the exact top delta consists solely of three instance-type
replacements. External ports and camera/motion wiring are byte-identical.

After the completion notification, run `export_whole.py`. It independently
exports the actual routed DB with the installed report limit of 200000, checks
the corrected modules actually elaborate, counts every returned negative path
against all ten slow/fast summary sections, and reuses physical audits for all
32 motion history DRM36K cells, read-before-write modes, HSST and PCB pins.
Unscored IO paths are explicitly retained; passing scored paths does not prove
physical camera input/output timing or board-level operation.

Only after those checks pass, `generate_bitstream.py` executes the historical
PDS `gen_bit_stream` command against that exact ADF in a new local work folder.
It records bit sizes/SHA256, unchanged ADF/source hashes and generation exit
status. It has no programming command. Deliver the bit file together with
`parent_handoff.json`, `bitstream_result.json` and the final reports, including
any remaining unscored IO/physical validation limits.

Not yet established: fourth-candidate routed timing and generated bitstream.
Final acceptance must be updated from the actual results, not this plan.
