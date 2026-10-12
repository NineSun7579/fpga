# Connected endpoint mapped functional simulation

## Result and scope

**PASS, 2026-10-05.** The original connected synthesis output `../endpoint_ctrl_01/synthesize/fpga_v8_endpoint_ctrl_synth_syn.vm` was compiled and simulated with official installed Pango GTP functional models. Independently, the existing RTL wrapper `../endpoint_ctrl_01/fpga_v8_endpoint_ctrl_synth.v` was compiled with the unchanged endpoint/controller RTL. Both runs used the same public-port stimulus and testbench. Mapped-versus-RTL, RTL-versus-oracle, and mapped-versus-oracle comparisons all passed: **654/654 operations, 2,208/2,208 operation/channel groups, zero failures** in each comparison. The RTL and mapped public trace files are byte-identical.

The mapped compile contains no RTL endpoint/controller replacements. There was no source modification, SSH, device access, PDS invocation, synthesis rerun, place/route, board wiring, hierarchy force, internal simulation gate, or timing/board acceptance. All new files and simulator outputs are confined to `endpoint_netlist_sim_01`.

## Tools, commands, and official cell identities

ModelSim SE-64 **10.6e, Jun 23 2018**, executables under `C:\modeltech64_10.6e\win64`. Existing netlist header: **PDS 2022.2-SP6.4, build 146967**, generated **2026-10-05 10:30:11**. Netlist top is `fpga_v8_endpoint_ctrl_synth`; mapped parameters are the frozen defaults: 7-bit AXI IDs, base `40010000`, window `00001000`, output banks `08000000`/`08200000`, output length 1,228,800 bytes.

All **19 model files** were compiled directly from the installed vendor functional simulation directory:

```text
C:\pango\PDS_2022.2-SP6.4\arch\vendor\pango\verilog\simulation
```

These are executable functional simulation models, including the vendor UDP dependencies. The synthesis `gtp_lib.v` declarations were not used. No model sources were copied or edited. [official_models.json](official_models.json) records the absolute path, exact SHA-256, and byte count for every model.

| Direct mapped primitive | Instances |
| --- | ---: |
| GTP_DFF_CE | 1,097 |
| GTP_DFF_C | 23 |
| GTP_DFF_PE | 6 |
| GTP_DFF_P | 1 |
| GTP_LUT6CARRY | 410 |
| GTP_LUT6 | 264 |
| GTP_LUT6D | 148 |
| GTP_LUT5 | 138 |
| GTP_LUT4 | 35 |
| GTP_LUT3 | 3 |
| GTP_LUT2 | 4 |
| GTP_LUT1 | 6 |
| GTP_INBUF | 318 |
| GTP_OUTBUF | 422 |
| GTP_INV | 1 |
| GTP_GRS | 1 |
| **Total** | **2,877** |

The three additional compiled dependencies are `GTP_MUX2LUT6.v`, `INT_LUTMUX2_UDP.v`, and `INT_LUTMUX4_UDP.v`. The original mapped top contains `GTP_GRS GRS_INST(.GRS_N(1'b1))`; the TB drives the public `rst_n` normally. The official FF initial/reset semantics are retained.

The eight exact tool commands, including absolute arguments and working directories, are in [commands.json](commands.json). Their sequence was:

```text
cwd = endpoint_netlist_sim_01/rtl
vlib.exe work
vlog.exe -work work <unchanged controller.v> <unchanged endpoint.v> <unchanged wrapper.v>
vlog.exe -sv -work work <new tb_endpoint_wrapper.sv>
vsim.exe -c -onfinish stop work.tb_endpoint_wrapper -do "run -all; quit -f"

cwd = endpoint_netlist_sim_01/mapped
vlib.exe work
vlog.exe -work work <19 official model paths, sorted> <existing fpga_v8_endpoint_ctrl_synth_syn.vm>
vlog.exe -sv -work work <same new tb_endpoint_wrapper.sv>
vsim.exe -c -onfinish stop work.tb_endpoint_wrapper -do "run -all; quit -f"
```

The launcher and independent evidence-audit commands are recorded verbatim in [README.md](README.md). All eight simulator tool commands returned zero. Both simulations reported `Errors: 0, Warnings: 1`. The sole warning is `vsim-8891`: the installed simulator configuration disables optimization (`-novopt` in effect). The warning concerns simulation speed; it is retained in each log. No missing-cell/binding warnings or X/Z public-output failures were observed.

## Fixture adaptation and coverage

The existing `cooperative_endpoint/run_tests.py` ownership oracle and transaction generator were imported read-only, without executing their original file-writing/simulation entry point. The original suite has 419 operations. This run retains **416 adapted regression operations** and adds **238 operations**, totaling **654**. Seeded upper 96-bit write payloads, public metadata, low-word/strobe expectations, bank ownership, descriptor keys, source tokens, response IDs, response counts, and snapshot checks are preserved.

The original TB separately instantiated endpoint and controller and inserted handshake gates between them. The new TB instantiates only the existing wrapper top and drives its public AXI128, certified descriptor, command-ready, bridge busy/done, and source-release-ready ports. The original 80-cycle internal B/R hold is adapted to public AXI B/R holds. Reset scenarios 2, 3, and 5 require internal controller B, R, or W gating and are omitted; their following read probes remain. The five reachable pending reset scenarios cover W-before-AW, stalled public B, stalled public R, a partially drained 256-beat write, and AW-before-W. There are seven common resets total, including startup and the reset before the supplemental probes.

| Coverage | Observed result in both runs |
| --- | --- |
| Device identity/version | `434F4F50` at physical `40010000`; `00010000` at `40010020`; OKAY and zero upper 96 RDATA bits |
| Valid ownership | CLAIM/ACK sequences for both output banks; exact sequence/generation keys; stale generation rejected after reset |
| Invalid ownership | Empty/wrong/duplicate CLAIM; wrong bank/generation ACK; error counters and held descriptors match oracle |
| Certified input | Four RAW claims, one non-RAW rejection; four commands and four token-preserving releases |
| Immediate outside addresses | `4000FFFF` and `40011000`: read zero/SLVERR; write SLVERR |
| Aligned lower outside address | `4000FFF0`: read zero/SLVERR; write SLVERR |
| End of window | `40010FFF` unaligned: SLVERR; `40010FF0` aligned but unimplemented local register: zero/SLVERR |
| Upper/high addresses | `40011010`, `40020000`, `50010000`, `80010000`, `FFFF0000`, `FFFFFFF0`, `FFFFFFFF`: read zero/SLVERR and write SLVERR |
| High CLAIM addresses | `400110C0`, `400200C0`, `500100C0`, `800100C0`, `FFFF00C0`: SLVERR, READY bank retained, reject counter unchanged |
| High ACK addresses | `3FFF0130`, `40011130`, `40020130`, `50010130`, `80010130`, `FFFF0130`: SLVERR, HOST_READING bank/descriptor retained, reject counter unchanged |
| Alignment | Every byte misalignment 1 through 15 tested for reads and ACK doorbell writes |
| SIZE | All disallowed sizes 0, 1, 2, 3, 5, 6, 7 rejected; size 4 used for valid accesses |
| BURST | Singleton FIXED/INCR exercised; WRAP/reserved 2/3 rejected |
| LEN/LAST | Lengths 1, 2, 15, 16, 255 rejected; promised AWLEN+1 beats drained despite normal/missing/early WLAST; singleton missing LAST rejected |
| Error read bursts | Exact ARLEN+1 zero/SLVERR beats and final-only RLAST, including 256 beats |
| Full IDs | Every ID 0 through 127 observed on both B and R; captured IDs survive changing inactive metadata |
| Write ordering | AW-first, W-first, simultaneous, persistent next AW/W during stalled B and maximum invalid drain |
| Read concurrency | Concurrent read/write, persistent next AR during 256-beat error response, stalled status snapshot across bank completion |
| Strobes | Full `FFFF`, upper-only `FFF0`, partial low-byte masks; upper write payload never aliases adjacent registers |
| Response/sideband stability | B, R, command, and source release payloads stable while stalled; no public X/Z; no early B or wrong read beat/LAST counts |

The supplemental legal CLAIM after the high-address probes transitions bank0 from READY (2) to HOST_READING (3), returning OKAY. The supplemental matching ACK transitions it to FREE (0), returning OKAY. Both transitions and every intervening descriptor/counter read match the RTL and oracle. The checks establish observable public behavior; there is no internal handshake trace in this wrapper-only run.

## Exact counts and comparisons

Counts below apply **separately to RTL and mapped**, with identical values. They are handshake/event counts, not inflated by repeated VALID cycles during stalls.

| Public channel/event | Count |
| --- | ---: |
| Accepted AW | 250 |
| Accepted W beats | 1,403 |
| Consumed B | 247 |
| Accepted AR | 398 |
| Consumed R beats | 941 |
| Descriptor claim/reject | 5 |
| Consumed command | 4 |
| Consumed source release | 4 |
| Common reset markers | 7 |
| Final per-operation public state | 654 |
| **Total public trace events** | **3,913** |

There are **247 completed writes** (160 OKAY, 87 SLVERR) and **397 completed reads** (345 OKAY beats, 596 SLVERR beats). Three accepted AWs and one accepted AR are deliberately abandoned by common reset. The accepted W count includes the staged orphan W and partial reset drain. Each simulation executes **13,430 cycles**, at a 10 ns clock period.

| Backpressure measurement | Stalled clock samples per run |
| --- | ---: |
| AXI BVALID while BREADY=0 | 1,309 |
| AXI RVALID while RREADY=0 | 2,975 |
| Command VALID while READY=0 | 52 |
| Source-release VALID while READY=0 | 74 |

All comparisons preserve event order within each operation/channel. Each compares 2,208 groups and all 654 operations, with zero mismatches. In addition, the complete RTL/mapped trace files are byte-identical, preserving their recorded cross-channel order. Trace SHA-256 for both runs:

```text
cad3eee69749116ff1907ea98f23d51a1b64bfa28a400fe2f1692e679e346e7b
```

Common stimulus SHA-256:

```text
4885b1ff089c0a832c3f1251b0abb78ba04c9d5ab8a414c239167f0dff9fc4ee
```

Detailed passing/failing summaries are in [rtl_vs_oracle.json](rtl_vs_oracle.json), [mapped_vs_oracle.json](mapped_vs_oracle.json), and [mapped_vs_rtl.json](mapped_vs_rtl.json). Per-operation labels, complete stimulus, expected public trace, both actual traces, protocol-check summaries, and simulator compile/run logs remain in this directory.

## The undriven function-local warning

The existing PDS log reports:

```text
Verilog-2021 ... fpga_v8_coop_axi128_endpoint.v(line number: 81)
Net eligible.addr_end_1 ... does not have a driver, tie it to 0
```

The RTL function assigns the 33-bit `addr_end = {1'b0, addr} + 33'd16` and compares it to the 33-bit window end. This run did not alter that function, silence the warning, or substitute a new netlist. It tested the **original connected mapped wrapper** exhibiting that warning.

For the recorded transactions, actual mapped public behavior agrees with the intended RTL: valid in-window reads/writes work; the immediate window boundaries and tested high addresses are rejected; `FFFFFFF0` does not produce an observable address-wrap alias; high-address CLAIM/ACK writes do not change bank ownership or controller reject counters. There are no observed mapped-versus-RTL failures in this run. This empirical result does **not** prove that the warning is harmless for every address, every parameter configuration, another synthesis output, or a standalone endpoint mapping. It also cannot distinguish an endpoint rejection from a downstream unimplemented-register error solely from the `40010FF0` response.

## Preservation and limitations

SHA-256 before/after manifests cover **448 existing files**, including endpoint/controller source and regression fixtures/reports, the original wrapper/netlist and synthesis logs, existing endpoint mapping-audit evidence, production `project/source` text RTL, `project/DOC` reports, and existing component-synthesis root files. [preservation.json](preservation.json) reports zero changed files. The independent evidence audit rechecks these files against the before manifest and rechecks all input and official-model hashes. It also verifies the mapped compile never includes endpoint/controller RTL and confirms both 128-ID sets.

Key unchanged input SHA-256 values:

| Input | SHA-256 |
| --- | --- |
| Original connected mapped `.vm` | `46b6cf8566d43c3047c7cb5f218db8578720c78040eea8cd0857d20d44c8cbf8` |
| Original wrapper `.v` | `d6abd0f29f1da0f732a1d6b624ae434789ba4b207c7aae43b58baf201758ab4c` |
| Endpoint RTL | `5ea714da5ed63168615f0f9162cb6a773a5ef5780f6fa5a33e2c3fce7cfafc1e` |
| Controller RTL | `fec948ff58fbc4fb7f4e70483d8182d052aaa5932c1fd53c0d40930e72a6a2ae` |
| Original regression generator | `125f04416709691b8ecc2ac480aacea41f031db805cd429b8d19761e0b4719e0` |
| Original regression TB | `93554279475f5b919322ac1e55767d71086c618ef9a5b98ea3578d48f7fdc834` |

This is a finite functional simulation of the synthesis netlist with official functional cells. No SDF is annotated. The comparison checks public transactions and selected state snapshots, and the TB checks public protocol/stall stability; it is not an exhaustive cycle-by-cycle formal equivalence proof. It provides no placed/routed delay, setup/hold, clock routing, metastability, reset recovery/removal, CDC, pin/electrical, PCIe/DDR transport, real bridge, device initialization, bitstream, board performance, or timing closure evidence. Bridge error/no-launch paths remain low in this successful-completion fixture. Three internal-gated reset scenarios are excluded as explained above. No production, board, or timing acceptance follows from this PASS.
