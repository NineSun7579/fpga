# Additional directed six-background verification

Result: PASS, real ModelSim SE-64 10.6e (`C:/modeltech64_10.6e/win64`). No production RTL bug was established by these cases. Run from the delivery root:

```powershell
python verify_six_background_extra.py
```

The independent runner writes only `sim_six_background_extra/`. Its test sources are `background_extra_fault_tb.sv` and `background_extra_memory_tb.sv`; the RAW tests are generated into its own simulation directory from a read-only existing frame-recovery test. Existing runners and suites are not regenerated or edited. No PDS invocation, board operation, host deployment, or git commit occurs. SHA-256 checks before and after the final run matched all 130 protected source/project/constraint files and original runner/test files. Full hashes, normalized PCIe simulation-copy hash, and PASS lines are in `sim_six_background_extra/receipt.json`.

## Exact coverage and evidence

There are 12 simulation executions and 45 scenario results: 18 reduced RAW frame outcomes, five full-resolution RAW frame outcomes, eight fault/stall cases, two FIFO events, and 12 camera/bank transport reads.

| Test | Directed cases | Final evidence/log |
| --- | --- | --- |
| Real RAW chain, 32×16 | 11 successful frames, seven aborts | `raw_chain.log`: background AW=B=23, 11 tags, 11 successful flush exports; RAW AW=B=66 after the extra wrap frame |
| Real RAW chain, 640×480 | Four successful frames, one failed RAW tag B | `full_raw_chain.log`: background AW=B=3004, four tags, four successful flush exports; RAW AW=B=12005 |
| Background source fault | Four locations: stalled AW, stalled middle W, stalled final W, delayed tag B | `fault_0.log` through `fault_3.log`: AW=B respectively 1,1,1,2 |
| Background deadline | The same four locations | `fault_4.log` through `fault_7.log`: AW=B respectively 1,1,1,2 |
| Full FIFO | Push+pop at capacity, then push without pop at capacity | `fifo.log`: both events PASS, preserved count/data on simultaneous event; overflow remains busy until retirement, then invalid and empty |
| Shared HMIC memory → production PCIe read engine | All six cameras × both banks; 153616 bytes per read | `memory.log`: 12 reads, each 9601 accepted R beats, 601 AR transactions, 9601 checked TX FIFO writes |

### Real publication chain

Both RAW tests instantiate candidate `ov5640_ddr`, its admitted pixel tap and capture controller/packer, actual `axi_dma_write` and `stream_pipe`, and the actual `background_six` writer with a serviced AXI sink. Background SOF/pixels/fault/publication/sequence connect directly to the real camera exports and hardware counter; no background publication pulse is injected. The full-resolution run connects stored-beat availability and sets `WAIT_FOR_DATA=1`. The reduced inherited recovery run retains its original non-credit-gated DMA setting for its existing fault cases.

At admission, the producer predicts the sequence as **the current hardware RAW publication counter plus one**. It accepts completion only when the exported hardware counter-change pulse carries that sequence. This is distinct from predicting a source frame number: rejected/failed source attempts do not advance the successful RAW counter. The tests check every published thumbnail against independently calculated even x/even y source pixels and the real RAW counter, including memory tag and record sequence.

The reduced cases include short frame at next SOF, missing-data watchdog, source abort during RAW AW stall, RAW overflow with W/B backpressure, payload BRESP error, tag BRESP error, and dirty-bank invalidation while another bank remains published. The delayed RAW tag B case explicitly checks that thumbnail publication has not occurred before B. Failed tag B explicitly checks that no successful thumbnail publication occurred and that the attempted record is invalid.

The full-resolution sequence is successful 1, successful 2, failed tag B retaining counter 2 and invalid guard `00000008`, successful retry 3, then wrap to 0. Four complete 307200-pixel RAW payloads and four complete 76800-pixel thumbnails are checked. The wrap is reached by a simulation-only initial-state deposit of `ffffffff` into the actual controller success/tag counters and passive pulse-history register; no counter/publication output is forced. The next real frame/tag B drives the increment and exported pulse to zero. Each successful pulse is asserted to occur while local capture flush is active and the passive fault export is clear. Both the reduced and full runs enforce the successful flush-export count.

### Fault drain and FIFO boundary

The fault matrix uses real background producer/writer RTL with 32×16 input so all boundary combinations run quickly. Each source-fault or naturally expiring deadline occurs with an announced transaction outstanding. The bus monitor checks AW address/AWLEN stability, W data/strobe/WLAST stability under backpressure, payload pixel golden, tag data, exact W beat count, and one B per AW. Busy remains set and quiescence remains false until that transaction's real B handshake. After B, the failed record is invalid, quiescence is true, and quarantine is clear for these source/deadline faults. A delayed tag B is tested for both causes. This matrix totals ten AW and ten B retirements.

The independent depth-16 producer reaches a full FIFO naturally with 640-wide input. A complete packed beat is pushed on the same edge as a pop; count remains 16 and old/new FIFO contents are checked. The next complete packed beat arrives with no pop, causing overflow. The attempt retains its announced transaction until a retirement pulse, then clears FIFO state and validity. This FIFO-only test supplies grant/take/retire directly to control the exact boundary; actual writer/B draining is separately covered by the fault matrix and RAW-chain tests.

### Production address and pixel parity

The shared-memory test instantiates six actual 640×480 background producers and their actual writer. It writes both banks for all six cameras into one HMIC-addressed memory, then the actual PCIe AXI read engine reads those same locations. Within a burst, each 128-bit beat advances **eight HMIC units**, each unit storing one RGB565 pixel. Burst starts advance 256 units. Camera slots are C5,C1,C2,C3,C4,C6, slot stride `80000`, bank stride `40000`, and final tag offset 153600. Metadata destination, dimensions `00f00140`, payload length, sequence, tag address, and valid generation guard are checked against the expected bank mapping.

The independent CPU golden is `(camera*1000 + bank*20000 + source_y*640 + source_x) mod 65536`, with source x and y even. It checks every actual AXI R beat and every PCIe TX FIFO input beat: 921600 payload pixels and 12 full 128-bit final tags, totaling 115212 beats at each checkpoint. Gaps start as `dead`; all 921600 inter-burst gap units remain poison after the writes. Total background writes are AW=B=7212, with 12 tags and 921696 written HMIC units. Backpressure evidence: 3614 AR stall cycles, 38390 R gating cycles, and 33600 capacity-stall cycles in the final run.

## Limits

- The full real RAW/controller/DMA publication chain covers one physical camera instance and both background banks. The six-camera shared-memory test supplies admitted streams and RAW publication inputs directly; it does not claim six simultaneous real capture controllers in one full-top simulation. Those are separate complementary tests.
- The shared-memory/PCIe test uses the existing normalized `sim_six_background/pcie_fifo_modelsim.v` and vendor endpoint stubs without modifying them. It verifies the production AXI read state machine and TX FIFO enqueue data; it does not model a physical PCIe link, host DMA completion, or the board DDR controller. RAW FIFO IP is represented by the existing behavioral FIFO contracts, with reduced capacity in the inherited replay.
- The reduced RAW test's pre-wrap `PASS FRAME RECOVERY` line reports its original ten successes and seven aborts; the later `EXTRA_RAW_CHAIN_PASS` line is the authoritative final eleven-success ledger. Raw and full logs retain harmless unconnected-output/endpoint and ModelSim optimization warnings; final logs have no Error/Fatal entries.
- **Odd HEIGHT is unsupported by this producer's present geometry.** `OUT_PIXELS=WIDTH*HEIGHT/4` and `last_selected=PIXELS-WIDTH-2` assume an even height for even-row selection and tail completion. This is a structural observation, not a newly demonstrated production-640×480 defect or an odd-height simulation result. No odd-height RTL change was made.
- These simulations establish functional directed coverage, not timing closure, PDS success, board behavior, or viewer validation. The parent session owns those activities.
