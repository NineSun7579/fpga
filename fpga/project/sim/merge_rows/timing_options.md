# Clock/service options for parent session

The only production edit in this subagent is `cam2_merge.v:167`:
`a_de_r | a_push_eol` -> `a_push | a_push_eol`. No pipeline or clock edit was
applied. All tests below compile modified production capture/FIFO/merge RTL.

## Verified functional results

`run_all.ps1` completed nine cases. Negative controls (original row cap bug,
and inadequate 62.5 MHz burst service) failed as expected; all seven positive
cases passed. Relevant logs:

| Log | Input | Output |
|---|---|---|
| burst84_100m.log | ~84 MHz byte PCLK, 480 rows, HTS2000 VTS705 | 2 complete frames; zero errors/full/malformed |
| burst84_125m.log | Same, 125 MHz merge | Same |
| overscan84_100m.log | ~84 MHz byte PCLK, 481 rows | Same; extra rows capped |
| overscan84_125m.log | Same, 125 MHz merge | Same |

Per output frame: A=307200, B=307200, merged=614400, 480 rows, all pixels
checked. Captured first/last rows and pixels match the camera generator. Vendor
clock divider models are used. The capture startup-zero assumption is explained
in README.md; these are functional simulations, not routed timing evidence.

## Camera programming evidence

`reg_config.v` currently programs 0x3035=0x21, 0x3036=0x69, 0x3037=0x13,
0x3108=0x01, 0x3824=0x04, width=640, height=480, HTS=2000, VTS=705.
With the commented 24 MHz XCLK, the conventional OV5640 clock-tree interpretation
is VCO=24/3*105=840 MHz, system divider 2 and PLL root divider 2, then PCLK
root divider 1 and divider 5 from 0x3034[3:0]=0xA, giving 84 MHz byte PCLK.
This is a register-derived expectation; actual board PCLK still needs measurement
and register readback. Auto exposure may extend vertical timing, so 15 fps alone
does not establish a slow active pixel clock.

## Likely timing paths: hypotheses pending current STA

1. `video_async_fifo.v` async memory read `mem[rbin[9:0]]` feeds line-buffer
   write data and EOL decision in `cam2_merge.v:242/270`. Address decode/mux
   (if LUTRAM is not inferred), EOL select, exact-640 compare, ready/page enable
   and line-buffer write decode are possible long paths. `apop/bpop` also feed
   binary increment -> XOR Gray encode -> empty compare in FIFO read control.
2. `cam2_merge.v:296` reads 640-entry memories and selects A page or B
   page/snapshot/black using state, `b_rep` and `snap_valid`, then registers
   `c_data`. Poor RAM inference can create a large read mux followed by another
   bank mux; register bank results first and select them on the next clock.
3. `cam2_merge.v:371` snapshot copy reads B page at `cpy_cnt`, selects source,
   and writes snapshot memory in one cycle. Separating RAM read and snapshot
   write breaks the path, but copying needs a pipeline drain cycle.
4. `a_ready[a_page]`/`b_ready[b_page]` -> pop -> FIFO pointer logic, and
   `b_ready[b_cur]` -> `b_rep` are small muxes, but may have high fanout. Use
   separate bank-ready wires and explicit one-hot write enables if STA identifies
   control fanout or decode as the bottleneck.

The saved timing summary in place_route reports TX setup WNS +2.625 ns but
does not contain path endpoints and is not evidence for the proposed direct125
configuration or the reported previous -0.97 ns violation. Parent should use
the actual failing path report before selecting a pipeline change.

## Recommended direct125 implementation strategy

Direct existing HSST 125 MHz clock needs no generated IP modification and has
functional margin: current 1926-clock pair service is 15.408 us, against
23.81 us input row spacing. Parent owns clock routing/constraints/build.

For line-buffer read timing, read each bank into its own clocked data register,
then select from those registers on the next clock. Delay the corresponding
state-derived valid, source/repeat selection and VS by that same clock. This
preserves A/B adjacency and all 1280 DE clocks; ensure the last A pixel and first
B pixel selectors refer to the read stage, not current FSM state. Memory reads
must retain suitable inference and consumed pages must not be reused before
the last read has been captured.

For FIFO-read/write timing, add a token register per camera with a valid bit
and registered write address/page. Hold/reserve the destination until a pending
EOL is applied; do not allow another pop based solely on stale ready state.
Otherwise the next row's first token can write into a page just sealed by EOL.
Use a proper one-stage valid/ready transfer, preserving ordered pixel+EOL tokens.

Do not claim timing closure from the 125 MHz functional pass. It requires a
current constrained routed build after whichever path-specific edit is selected.

## Existing-clock alternative: eliminate COPY overhead

67.5 MHz is insufficient with the present 1926-clock pair service, but is not
inherently insufficient if snapshot copying is removed. While outputting a real
B row, write each selected B pixel directly into `b_memL[b_rcnt]`, and set
`snap_valid` when the final write commits. Skip S_COPY and proceed directly to
the inter-row gap/frame state. All snapshot reads happen on repeated rows, and
all snapshot writes on real rows, so the modes are mutually exclusive.

Estimated service becomes 1286 clocks/pair: at existing 62.5 MHz this is
20.576 us, requiring ~54.0 MHz rather than 80.9 MHz. Thus the existing62.5
clock could suffice without any PLL/top change. This is a proposal, not a tested
repair. Register B bank outputs before snapshot write if needed for timing;
carry index and last-valid with data, and account for the drain at frame end.
Verify real->repeat, repeat->real, last row, and simultaneous page refill before
accepting it. This alternative may be preferable if direct125 closure is costly.
