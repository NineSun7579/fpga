# Live convolution packing and arithmetic audit

Packing is correct for the live 16-input, 2-output engines. The unmodified MAC cores **fail strict official-vendor simulation because the live multiplier wrapper is one register shorter than its declared timing contract**. This audit did not alter production RTL, PDS projects, IP, existing simulation tools, or board state.

## Packing and DMA contract

Live `source/npu/npu_top/config.v:60-61,87-88` selects input16/output2. `npu_top.v:453-458,891-896` passes those macros into `conv11_para_top` and `conv_top`; module defaults of output8 are not the live configuration.

Let `CiP=ceil(Ci/16)*16`, `CoP=ceil(Co/16)*16`, `IB=CiP/16`, `OB=CoP/2`. A complete layer parameter image starts with **CoP*8 bias bytes**, followed by **CoP*CiP*Kh*Kw weight bytes**. The preparation assets are separate files; a future command builder must concatenate them or otherwise provide this single-address DMA image. They are not yet an executable instruction image.

`hwc16_layout.pack_weights` byte order is:

```
output_block2 -> input_block16 -> ky -> kx -> output_lane2 -> input_lane16
offset = (((((ob*IB + ib)*Kh + ky)*Kw + kx)*2 + ol)*16 + il)
byte = int8 W[ob*2+ol, ib*16+il, ky, kx] (two's complement)
```

Invalid input/output channels are weight0. Increasing byte address maps to increasing input lane: byte0 is bus `[7:0]`, byte15 is `[127:120]`. All **55** prepared weight files match an independent scalar-loop reconstruction, and all bias files match an independent slot reconstruction; see `asset_bounds.json`. No packer change is required.

In `conv_weight.v:335-367`, accepted DMA words fill each tap FIFO with exactly two words before moving to the next FIFO; 3x3 uses FIFO0..8 in row-major tap order. The 18 accepted words per `(ob,ib)` frame are tap0 lane0, tap0 lane1, ..., tap8 lane0, tap8 lane1. The loader broadcasts two consecutive valid beats with all nine tap ports in parallel, lane0 then lane1, and `m_last` on beat1. For 1x1 it stores pairs round-robin among FIFOs, then selects the active FIFO onto `m_data_4`; the dedicated `conv11_weight` does the same with its two FIFOs. The exact round-trip loader simulations pass for 3x3, general 1x1, and dedicated 1x1.

Loader DMA input accepts only `s_valid && s_ready`; bubbles are allowed. `s_last` ends the DMA transaction, which may contain multiple weight frames. It is **not** the per-frame MAC weight last. The loader's per-frame `m_valid` contains two contiguous beats and `m_last` marks the second. At the MAC input, low `weight_valid` resets `kernel_cnt`, so there must be no bubble between those two beats. `weight_last` toggles the write bank without valid qualification: assert it only on the second valid beat. `start` resets read/write bank controls but does not clear stored weights. Read bank switching happens on `mul_last=data_last_d[0]`, one cycle after `s_last` enters the core. A bank must not be overwritten until its data row has released it. Control tracks capacity for two resident weight frames. Bias banks are released separately at `calculate_last && s_last` after the add/multiply delay.

Configured geometry must use `calculate_cin_num=IB`, `calculate_cout_num=OB`, `calculate_num=IB*OB`, `bias_len=CoP*8`, `weight_sum=bias_len+CoP*CiP*Kh*Kw`. Dedicated `conv11_weight` names its bias-prefix length input `weight_len`; general `conv_weight` names it `bias_len`. DMA rereads weights from `base+bias_len` when the parameter image ends; bias addresses wrap across output blocks. The final logical 3-output example still transmits all eight output pairs through padded16, including channel3..15 weight/bias zero. Loader simulations observe bias command address `0x1000`, length128, then weight address `0x1080`, length2304 (3x3) or256 (1x1).

Bias channel `oc` occupies bytes `oc*8..oc*8+7`: low32 signed Q16 little endian, high32 zero. Two consecutive slots form a128-bit DMA word. `conv_weight.v:594` / `conv11_weight.v:533` extract bus `[31:0]` and `[95:64]` into low/high32 of a64-bit bias pair; `conv_add.v:367-374` / `conv11_add.v:366-373` map those to output lanes0/1. Negative bias is sign interpreted from its low32 field; high32 slot padding remains zero. The tests use three distinct signed biases, output padding to16, and verify every loaded pair and last flag.

The historical exporter `migration/RK3568_PG100H-release/yolov5/ref/gen_weight_util_rk3568.py:7,41-82` sets output parallelism16. Its block order is therefore not compatible with the live output2 loader: after two words, live FIFO routing advances to the next tap, while the old exporter continues with output channels2..15 at the same tap. Old text lines display lane15 at the left and lane0 at the right, which is correct for `$readmemh` numerical words. Its active `txt2bin` implementation at612-628 writes `bytes.fromhex` without reversal, producing lane15-first byte files. The retained host `main_npu.cpp:129-149` copies file bytes directly to DMA. Neither historical16 output grouping nor that text-to-byte convention should be reused for these new lane0-first assets. Physical PCIe/AXI byte preservation was not exercised here.

## Exact actual-RTL simulation results

ModelSim SE64 10.6e compiles current RTL by path, unmodified, plus official Pango `GTP_APM_E2.v` and `GTP_GRS.v` from `C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation`. No `sim/npu/gtp_apm_e2_sim.v` replacement or legacy comparer is used. Every case has its own work directory and explicit local `modelsim.ini`; shared ModelSim/PDS state is not edited. Stimulus is driven on falling edges, output checked after it has settled. Vendor warnings about unused/unconnected primitive ports are retained in logs; checked outputs contain no X/Z.

| Live unmodified case | Complete valid48-bit words | Strict wrong words | X/Z | Last positions |
|---|---:|---:|---:|---|
| general 3x3, Ci3, Co3 padded16 |2048/2048|512|0|all8 exact|
| general 1x1, Ci3, Co3 padded16 |2048/2048|512|0|all8 exact|
| dedicated 1x1, Ci3, Co3 padded16 |2048/2048|512|0|all8 exact|
| general 3x3, Ci19 padded32, Co3 padded16 |4096/4096|1024|0|all16 exact|
| actual prepared task000 weights, Ci3, Co16, 3x3 |2048/2048|2048|0|all8 exact|

Independent Python golden uses original OIHW signed weights and original u8 row samples, scalar products and exact `&0xffffff` per lane. Lane0 occupies `[23:0]`, lane1 `[47:24]`. Each256-pixel interior stream covers all u8 codes in every real input lane, including128..255; synthetic weights differ by output/input/kernel position and include -128/+127. Input padding lanes contain affine zero-point23, with padded weights zero. 3x3 expected windows use stream columns `[x,x+1,x+2]`; 1x1 uses middle-row column `x+1`. A valid row supplies `W+2` contiguous core input samples with endpoint pad words, last on the final sample. The tested cores emit W words and one coincident last. The general core suppresses the first two delayed valid beats with `delay_cnt`; the dedicated core uses adjacent delayed-valid gating. Data shift registers run on every clock, so input bubbles are not safe for an arbitrary spatial stream.

The defect is local to the current multiplier wrappers' assumed latency:

* `conv_mul_E2.v:38-49` and `conv11_mul_E2.v:38-49` set X/Y_REG1, MULT_REG1, P_REG1, **USE_POSTADD0**.
* Official `GTP_APM_E2.v:444-446` says `pi=P_REG?pr:pc; P=USE_POSTADD?pi:mi`. Disabling postadd bypasses P_REG. X/Y input stage plus MULT stage gives2 registers; current external `DELAY=MUL_DELAY-3` adds1 for configured MUL_DELAY4, giving **3 actual registers**.
* Exhaustive scalar simulation checks all65,536 `(signed-int8,u8)` combinations for both wrappers, including complementary second signed lane. All pass with3-register alignment; all65,536 fail with4-register alignment (`unit_results.json`).
* With unchanged core valid timing, all words match a separate diagnostic scalar model of **one pixel ahead**, with the final word using weights from the next read bank after `mul_last`. This diagnostic compares the full count and tails too; it does not convert the strict failure into a pass (`simulation_results.json`).

For a concrete reviewable remedy, `--candidate-latency` creates **test-only GBK-byte-preserving copies** of each wrapper under the case directory, changing only `localparam DELAY = MUL_DELAY - 3;` to `MUL_DELAY - 2;`. All five complete golden streams then pass with zero mismatch, zero X/Z, exact counts and every last (`candidate_latency_results.json`). These historical copies demonstrate an additional output register restores configured4-cycle timing for MUL_DELAY4. The persistent isolated candidate below also validates the supported delay edges; production RTL remains unchanged, and synthesis/timing remain pending.

## Persistent isolated multiplier candidate

`fpga_v8_conv_mul_pair.v` is an ASCII, uniquely named Verilog-2001 candidate shared by both core types. It is a persistent implementation, not a generated latency edit or an alias declaring a production module name. Its interface retains `INT` for core compatibility but supports **INT=8 only**, with default **MUL_DELAY=4**. The official vendor mode is unchanged: signed 12-bit extensions of both weights, positive 9-bit extension of the u8 activation, SIMD multiplication, X/Y_REG1, MULT_REG1, P_REG1, and USE_POSTADD0. All **40 primitive ports** are explicit, including open unused outputs, zero unused data/reset inputs, and enabled clock enables. The unused mode controls retain the existing wrapper's MODEIN00110/MODEY000/MODEZ0000 settings.

`localparam DELAY = MUL_DELAY - 2` supplies the external pipeline. MUL_DELAY2 takes the bypass branch with no zero-length register array; MUL_DELAY3/4/6 add1/2/4 external32-bit stages. An input sampled at edge n must appear after edge **n+MUL_DELAY-1**. Unsupported INT and MUL_DELAY<2 select intentionally undefined, uniquely named configuration-error modules, so elaboration fails instead of silently bypassing the timing requirement. No simulation-only `$fatal` or overlapping generated units are used.

`run_candidate_mult.py` / `tb_candidate_mult.v` compile the persistent candidate with the actual official Pango APM and GRS models in local ModelSim libraries, in `.v` mode without `-sv`. Both lanes cover all **65,536 signed-int8 x u8 combinations** at every tested delay; lane b is the bitwise complement of lane a, so it independently covers the entire signed range. The delay4 case exercises the default parameter without overriding it. Input IDs, values, cycle count, exact output alignment, and both full product streams are checked. Only the first D-1 initial fill edges are excluded; all later idle and flush edges are checked too. X/Z is a failure and never drops a sample.

| MUL_DELAY | External32-bit stages | Complete products, lane a / lane b | Wrong words / X/Z |
|---:|---:|---:|---:|
|2|0|65,536 / 65,536|0 / 0|
|3|1|65,536 / 65,536|0 / 0|
|4 (default)|2|65,536 / 65,536|0 / 0|
|6|4|65,536 / 65,536|0 / 0|

All **524,288 required products** pass. Directed invalid configurations `(INT,MUL_DELAY)=(8,-1),(8,0),(8,1),(7,4),(9,4),(16,4)` all fail ModelSim elaboration with the expected missing configuration-error module. Rejection checks require a failing process result, the specific missing module, and no simulation acceptance marker; an unrelated tool failure cannot pass. Evidence: `candidate_mult_results.json`, each `pair_mult_*` complete stream/result/log, and the invalid-case `simulate.log` files.

`run_candidate_mac.py` / `tb_candidate_mac.v` generate only two test core copies under `pair_core_rtl`: **fpga_v8_test_conv_conv** and **fpga_v8_test_conv11_conv**. Byte-level edits change only each root declaration and the respective multiplier instance type to `fpga_v8_conv_mul_pair`; reversing those substitutions reproduces the production GBK bytes exactly. No copy declares either production core or multiplier module name. Both core copies compile against the same persistent candidate file. Production add/bias RTL is unchanged; it is outside this MAC rerun. The stimulus/capture schedule is identical to the original MAC test, and all six weight/data/golden fixture files are verified byte-identical to the original audited cases.

| Candidate MUL_DELAY4 case | Complete valid48-bit words | Wrong words / X/Z | Last positions |
|---|---:|---:|---|
|general3x3, Ci3, Co3 padded16|2048 / 2048|0 / 0|all8 exact|
|general1x1, Ci3, Co3 padded16|2048 / 2048|0 / 0|all8 exact|
|dedicated1x1, Ci3, Co3 padded16|2048 / 2048|0 / 0|all8 exact|
|general3x3, Ci19 padded32, Co3 padded16|4096 / 4096|0 / 0|all16 exact|
|prepared task000 weights, Ci3, Co16, 3x3|2048 / 2048|0 / 0|all8 exact|

The required five original golden streams pass **12,288 / 12,288 words**, zero mismatches, zero X/Z, and all48 last flags at the exact expected positions. Representative general3x3 and dedicated1x1 cases also pass at each MUL_DELAY2/3/6, adding **12,288 / 12,288 words** with zero mismatches/X/Z and all48 last flags exact. Evidence: `candidate_pair_mac_results.json`, `pair_core_rtl/copy_evidence.json`, and complete `pair_mac*` streams/results/logs.

All candidate valid simulations have **zero compiler/simulator warnings**. The historical live/copy-wrapper logs retain their missing-port warnings; the vendor models were neither modified nor suppressed. All34 production source hashes in `asset_bounds.json` match before and after both candidate runners. Candidate/core names were scanned against production declarations; the new isolated compilation set has no duplicate names. All new files and simulation libraries are under `conv_contract`; no PDS process, project change, IP change, board access, or production patch occurred.

At default delay4 the source adds one32-bit register stage per multiplier pair relative to the live wrapper. **Actual mapped resources and timing are pending**: no synthesis, placement/routing, or timing closure was run. This candidate fixes the demonstrated isolated arithmetic/latency defect; it does not verify the complete DMA/controller/MAC/add/finish/LUT/output-buffer engine, full-model scheduling or throughput, nor change the accumulator bounds below.

Further isolated live stage evidence:

* `conv_in_buf` and `conv11_in_buf`: all12 distinct128-bit words pass, writes include bubbles, exact final last. Source stores words unchanged and sequentially; downstream `in_ctrl` strides read addresses by input-block count, consistent with pixel-major HWC16.
* `conv_weight`3x3/general1x1 and `conv11_weight`: all16 weight beats and all8 distinct64-bit bias pairs pass, including padded channels and each last.
* `conv_add` and `conv11_add`: all128 two-lane output words pass after two separate input-block accumulation rows per output block, with three signed Q16 biases and bias/channel padding through16. Scale256 and zero128 give an independent scalar Q16 result. This test avoids half-LSB ties; it does not claim the two modules have identical rounding. General `conv_add` uses half-up, while `conv11_add` has active ties-to-even code.

These are isolated stage checks. They do not connect DMA+input controller+MAC+add+finish/LUT+out_buf into a complete engine, exercise stride2, validate full-network schedules, or accept a board image. Any separately verified finish module remains a separate piece of evidence.

## Accumulator bounds

`asset_bounds.json` includes every Conv task's independently recomputed bound and all30 trace extrema. The fixed numeric model uses **raw unsigned codes**, not codes already reduced by zero point; its folded Q16 bias applies the zero-point correction after raw MAC. For a full interior window and fixed signed weight tensor:

```
L_oc = 255*sum(min(W_oc,0))
U_oc = 255*sum(max(W_oc,0))
conservative_abs_oc = 255*sum(abs(W_oc))
```

These extrema cover independently chosen u8 inputs0..255. Bounds also safely enclose channel-prefix partial sums and padded windows. They do not establish which upstream neural-network activations are reachable.

For the **55 actual `numeric_layer` quantized weight tensors**, tasks that can exceed signed24/25/26 bits under this bound are respectively **none / none / none**. All stored `raw_accumulator_abs_bound_max` values equal independent recomputation. The largest conservative absolute bound is **7,636,485**, task86 (`[64,256,3,3]`), below signed24 maximum8,388,607. Largest exact full-range extrema across the model are **[-4,086,630,+3,554,955]**, also task86, fitting signed23. Largest exact single-input16-block magnitude is667,590, task80, fitting signed21. This is an analytical guarantee for these frozen coefficients, not a conclusion from sample frames.

The30 CPU traces span **[-205,091,+174,765]**, fitting signed19. No trace overflows24/25/26; the traces alone do not prove safety for all inputs. They are CPU arithmetic traces and do not establish RTL stream correctness.

Generic engine safety is different: arbitrary full-range signed-int8 weights over N terms have `[-32640*N,+32385*N]`. One16-input3x3 block has N144, range[-4,700,160,+4,663,440], fitting signed24. Accumulating512 inputs3x3 yields[-150,405,120,+149,230,080], requiring signed29;512 inputs1x1 require signed25. The live add stage has25-bit stored/scaled data and26-bit temporary addition. Its narrowing expression `{cin_add_cin[25],cin_add_cin[23:0]}` is **not ordinary modulo25 wrapping once out of range**, because it drops bit24 and keeps the26-bit sign. These engines are not generally safe for arbitrary coefficients.

Using the actual task shapes but allowing arbitrary int8 coefficients, the potentially overflowing task IDs are:

* signed24: 2,6,7,11,15,16,20,24,25,28,34,37,40,41,49,50,53,58,59,62,64,67,68,70,71,72,74,75,77,78,80,81,83,84,86,87.
* signed25: 11,15,16,20,24,25,40,41,53,58,59,62,67,68,71,72,74,75,77,78,80,81,83,84,86,87.
* signed26: 20,24,25,62,67,68,74,77,83,86.

Those lists describe replacement weights with the same shapes, not the present quantized model. Folded bias and postscale arithmetic are separate widths, not included in raw accumulator bounds.

## Reproduction

From this directory with Python/numpy and ModelSim installed:

```
python audit_contract.py
python run_loader.py
python run_units.py
python run_sim.py                     # expected exit1: strict current RTL failure
python run_sim.py --candidate-latency # expected exit0: test-only correction passes
python run_candidate_mult.py          # expected exit0: persistent candidate, delays2/3/4/6 and invalid guards
python run_candidate_mac.py           # expected exit0: original12,288 words plus12,288 delay-edge words
```

Per-case compile/simulation logs, exact expectations, complete observed streams, and machine-readable results remain under `conv_contract`. `asset_bounds.json` records production source SHA256 values. Those source hashes were rechecked unchanged after simulation. No legacy short-length matching or X-skipping acceptance is used.
