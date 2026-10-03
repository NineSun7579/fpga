This archive is INVALID FOR HARDWARE USE. Do not program or release its bitstream.

Standalone PNR omitted the generated physical PCF. Actual placement has sys_clk
at P3 instead of P20, sfp0_tx_disable at J16 instead of H12, sfp0_los at G8
instead of E16, and sfp1_tx_disable at F19 instead of F16. All 40 implemented
GPIO placements differ from the original FDC; 16 camera inputs also have the
wrong implemented IO standard (LVCMOS33 instead of LVCMOS12).

Passing STA does not validate these physical connections. Files are preserved
for diagnosis only. The corrected runner requires actual placement/electrical
audits on both original and timing-audited databases before bit generation.
