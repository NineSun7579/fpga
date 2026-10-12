# Current-run mapped register ABI review

Run: `project/motion_100h/run_20261003_212303`. Result: **scoped mapped data-path pass; full AXI protocol pass not claimed**. Detailed evidence and counts: that run's `register_scope_mapped_review.json`.

Actual mapped snapshot capture cones select CAM1–4 corresponding record bits for camera indices 0–3 and zero for reserved CAM5/6 indices 4–5. All 266 retained snapshot bits passed 51,072 Boolean checks: six cameras, all 16 independent active-camera input patterns, both selector-byte strobe states. Record leaves never borrow another bit position. Each active camera retains 266 AXI-clock record registers.

The other 54 packet bits, positions 35–63, 87–95 and 112–127 inclusive, are optimized away. Their mapped AXI read cones return zero with all other snapshot state arbitrary. All six valid camera indices and ten words passed 3,516 selected-bit/zero read-cone checks. Together these cover **all 320 packet bits**, beyond source zero declarations. An enabled CAM5/6 capture freezes an all-zero ten-word packet. Changing the selector alone intentionally retains the previous snapshot.

Merged camera selection passed 384 bit checks over all old/write selectors and byte-1 strobes. Capture enable passed 64 checks and resolves to `N9 && w_data[31] && w_strb[3] && next_camera < 6`, allowing CAM5/6 capture and rejecting indices 6/7. `N9` remains an upstream qualification cut.

At registered read addresses `0x20000830`, `0x20000840`, and `0x20000850`, all 32 mapped output bits resolve respectively to **0x4d4f5431**, **0x01e00280**, and **0x0c102804**, with unrelated state unknown. All 68 invalid camera/word combinations return zero: 2,176 output-bit checks.

Mapped structure retains 266 snapshot, 32 generation, three camera-selector, four word-selector, 32 AXI read-data and 28 read-address registers, all on `axi_clk` with local reset net `ddr_init_done`. Snapshot/generation share `N544`; read data/address use `prep_regs_u/N290` and `prep_regs_u/N228`. Optimized address bits are not independently certified by sequential equivalence.

Exact quotes from current `mapped_dump.v`, with instance start-line anchors:

```text
// N27_6[0]_1/LUT6_inst, line 926889 onward
.INIT(64'b0000110000000000000011001100110000001010000000000000101010101010)
// snapshot[0]/opit_0_inv_L6Q, line 932664 onward
.INIT(64'b1100101011111111110010100000000011001010111111111100101000000000)
.L6Q (\prep_regs_u/u_motion_register_bank/snapshot [0] ),
.CE (\prep_regs_u/u_motion_register_bank/N544 ),
            .CLK (axi_clk),
// N544_7/gateop, line 931491 onward
.INIT(64'b0000000010000000100000001000000000000000100000001000000010000000)
// s_axi_rdata[0]/opit_0_inv_L8Q, line 925491 onward
.L8Q (prep_axil_rdata[0]),
```

The first LUT takes CAM1/2 same-bit data, write camera high bit, byte-1 strobe, stored camera high bit and merged camera low bit. The snapshot LUT takes CAM3/4 same-bit data, merged bits 0/1 and first LUT output. Every retained bit's actual pin connections and INIT tables were evaluated, including special bit cones. The read proof follows full combinational cones into registered `prep_axil_rdata`, including LUT7 `M` and LUT8 `M0/M1/M2` selectors.

SHA-256 of original current-run bytes:

| File relative to run | SHA-256 |
| --- | --- |
| mapped_dump.v | eaf0974fc723227dfa0f71717f3f2fc1c26d50689193ee816f0aba351b07b7f0 |
| mapped_dump.txt | 8c291ebb8843cd956d84218e302f7243abae431ee56eae903ff4344177958524 |
| inputs/source/top.v | ba90f96605423210f9563990a470e0d9585529c4f7edcda1c086bf3fae3c45b2 |
| inputs/source/motion/motion_register_bank.v | 4f59383a67efa94e396d1e4f39aba105aa3e747ce129cf52b7c9deaea9f12cba |
| inputs/source/preprocess/prep_regs.v | 73c830859b81c5f9065c2e17631231165b497e5a0e6aa2ab948e81a4e33f1c0b |

Limits: conservative Boolean evaluation of mapped LUT INIT/pin semantics via read-only in-memory Python parser. Unknown leaves propagate as `{0,1}`; register Q leaves represent held state. No vendor primitive simulation or sequential formal equivalence was run. ADIF was hashed but not independently connectivity-crosschecked. Upstream `N9` qualification, ready/valid timing, reset transitions and generation carry arithmetic remain unverified. Full interface acceptance needs those checks against this exact export; no reserved-camera packet mux gap remains under stated primitive semantics. RAM pipeline/control and physical timing are outside ownership.
