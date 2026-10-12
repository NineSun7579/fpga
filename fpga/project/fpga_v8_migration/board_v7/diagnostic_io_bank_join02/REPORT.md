# Actual IO connection evidence (read-only)

Exact physical connections: 112/112; previous missing rows resolved: 49/49.
Unresolved ports: []. Differential pair contracts: 3/3.

Only this new diagnostic directory was written. No PDS, board operations, build04 changes, installation binary scans, or controllerguard operations were performed.

The existing routed and actual_final_pnr graphs bind to different synthesis exports. Their objects/input hashes were verified and recorded, but neither graph was reused for acceptance. A fresh sparse graph is derived from the requested routed_dump.txt; hierarchical instance paths are exact flattened TOP INSTREF values. The original parser helpers decode ADIF identifiers/INDEXED bits; no substring target-name matching occurs.

Each accepted row joins IO-report port/loc to exactly one pinout row, checks the actual TOP PAP_IO_LOC for the exact scalar/array bit when present, then follows the actual NET/CONNECT/PORTREF to exactly one primitive external pad pin. sfp_tx_disable has no TOP PAP_IO_LOC: its loc is established by exact report/pinout port+loc and the connected primitive PLACE, and the absent attribute is explicitly recorded. Its operator definition establishes the I/O/IO/O_B/IO_B pad contract. The exact INSTREF has one IOBD/IOBS PLACE matching the pinout package site. Raw ADIF, byte ranges (zero-based, end exclusive), snippet hashes, complete input hashes and script hashes are in join_result.json. Rows include full array NET blocks as well as the exact bit CONNECT. connection_graph.json is a sparse graph bound to the same target hash.

mem_ck and mem_ck_n resolve separately to O and O_B, with a verified DIFFO_OUT->DIFFO_IN net. Each mem_dqs[k]/mem_dqs_n[k] resolves separately to IO and IO_B for the same exact TOP bit k, with DIFFI_OUT->DIFFI_IN verified. The final routed DQS output has no direct DIFFO link: the positive I pin is driven by IOL.DO_P; the negative I pin is driven by IOLOTCMP.O, whose IN and TS connect to the same IOL.DO_CAS_OUT and IOL.TO_CAS_OUT. These four actual nets and both source instances/definitions are recorded. Positive and negative pads have their own actual IOBD/IOBS sites. Bit/polarity is not inferred from adjacent sites or an opit substring.

Function-derived counts: {'BANKL4': 6, 'BANKL5': 27, 'BANKL3': 29, 'BANKR5': 28, 'BANKR4': 22}. Native IO-report bank counts: {'BANKL6': 112}. Pinout bank counts: {'BANKL6': 112}.
FuncName versus native IO-report conflicts: 112/112; exact ports are listed in JSON.

Physical connection and bank-like function naming remain separate claims. FuncName-derived BANK labels are descriptive package-function inference only. They do not prove native usedIO internal BANK objects, internal bank metadata completeness, or explain away native bank contradictions. internal_bank_metadata_verified=false, usedIO_internal_bank_objects_verified=false, IO_gate_passed=false and IOgate=false are retained.

| Port | Loc | Actual net | Primitive pad | PLACE | Accepted |
|---|---|---|---|---|---|
| button_rst_n | M15 | button_rst_n | button_rst_n_ibuf/opit_0/I | IOBD_0_624 | True |
| cmos1_data[0] | Y18 | cmos1_data[0] | cmos1_data_ibuf[0]/opit_0/I | IOBD_0_450 | True |
| cmos1_data[1] | AA19 | cmos1_data[1] | cmos1_data_ibuf[1]/opit_0/I | IOBD_0_426 | True |
| cmos1_data[2] | AB20 | cmos1_data[2] | cmos1_data_ibuf[2]/opit_0/I | IOBS_0_420 | True |
| cmos1_data[3] | V19 | cmos1_data[3] | cmos1_data_ibuf[3]/opit_0/I | IOBS_0_432 | True |
| cmos1_data[4] | L13 | cmos1_data[4] | cmos1_data_ibuf[4]/opit_0/I | IOBS_0_666 | True |
| cmos1_data[5] | AB22 | cmos1_data[5] | cmos1_data_ibuf[5]/opit_0/I | IOBS_0_486 | True |
| cmos1_data[6] | Y19 | cmos1_data[6] | cmos1_data_ibuf[6]/opit_0/I | IOBS_0_444 | True |
| cmos1_data[7] | AB21 | cmos1_data[7] | cmos1_data_ibuf[7]/opit_0/I | IOBD_0_492 | True |
| cmos1_href | N15 | cmos1_href | cmos1_href_ibuf/opit_0/I | IOBS_0_306 | True |
| cmos1_pclk | T18 | cmos1_pclk | cmos1_pclk_ibuf/opit_0/I | IOBS_0_360 | True |
| cmos1_rst_n | V18 | cmos1_rst_n | cmos1_rst_n_obuf/opit_0/O | IOBD_0_438 | True |
| cmos1_scl | R14 | cmos1_scl | cmos1_scl_obuf/opit_0/O | IOBS_0_372 | True |
| cmos1_sda | P14 | nt_cmos1_sda | ov5640_top.ov5640.i2c_dri.sda_tri/opit_0/IO | IOBD_0_378 | True |
| cmos1_vsync | W17 | cmos1_vsync | cmos1_vsync_ibuf/opit_0/I | IOBS_0_408 | True |
| cmos2_data[0] | U17 | cmos2_data[0] | cmos2_data_ibuf[0]/opit_0/I | IOBD_0_390 | True |
| cmos2_data[1] | V20 | cmos2_data[1] | cmos2_data_ibuf[1]/opit_0/I | IOBS_0_474 | True |
| cmos2_data[2] | R16 | cmos2_data[2] | cmos2_data_ibuf[2]/opit_0/I | IOBS_0_336 | True |
| cmos2_data[3] | P15 | cmos2_data[3] | cmos2_data_ibuf[3]/opit_0/I | IOBD_0_342 | True |
| cmos2_data[4] | W19 | cmos2_data[4] | cmos2_data_ibuf[4]/opit_0/I | IOBD_0_468 | True |
| cmos2_data[5] | W20 | cmos2_data[5] | cmos2_data_ibuf[5]/opit_0/I | IOBS_0_462 | True |
| cmos2_data[6] | P17 | cmos2_data[6] | cmos2_data_ibuf[6]/opit_0/I | IOBS_0_348 | True |
| cmos2_data[7] | AB18 | cmos2_data[7] | cmos2_data_ibuf[7]/opit_0/I | IOBS_0_396 | True |
| cmos2_href | U18 | cmos2_href | cmos2_href_ibuf/opit_0/I | IOBS_0_384 | True |
| cmos2_pclk | P16 | cmos2_pclk | cmos2_pclk_ibuf/opit_0/I | IOBD_0_318 | True |
| cmos2_rst_n | AA21 | cmos2_rst_n | cmos2_rst_n_obuf/opit_0/O | IOBS_0_510 | True |
| cmos2_scl | U20 | cmos2_scl | cmos2_scl_obuf/opit_0/O | IOBD_0_480 | True |
| cmos2_sda | N17 | nt_cmos2_sda | cam2_ov5640_top.ov5640.i2c_dri.sda_tri/opit_0/IO | IOBD_0_354 | True |
| cmos2_vsync | R17 | cmos2_vsync | cmos2_vsync_ibuf/opit_0/I | IOBS_0_312 | True |
| cmos3_data[0] | C18 | cmos3_data[0] | cmos3_data_ibuf[0]/opit_0/I | IOBD_0_1062 | True |
| cmos3_data[1] | E18 | cmos3_data[1] | cmos3_data_ibuf[1]/opit_0/I | IOBS_0_1032 | True |
| cmos3_data[2] | F18 | cmos3_data[2] | cmos3_data_ibuf[2]/opit_0/I | IOBD_0_1038 | True |
| cmos3_data[3] | C20 | cmos3_data[3] | cmos3_data_ibuf[3]/opit_0/I | IOBS_0_984 | True |
| cmos3_data[4] | D20 | cmos3_data[4] | cmos3_data_ibuf[4]/opit_0/I | IOBD_0_990 | True |
| cmos3_data[5] | B16 | cmos3_data[5] | cmos3_data_ibuf[5]/opit_0/I | IOBS_0_1134 | True |
| cmos3_data[6] | B15 | cmos3_data[6] | cmos3_data_ibuf[6]/opit_0/I | IOBD_0_1140 | True |
| cmos3_data[7] | E14 | cmos3_data[7] | cmos3_data_ibuf[7]/opit_0/I | IOBS_0_1170 | True |
| cmos3_href | A16 | cmos3_href | cmos3_href_ibuf/opit_0/I | IOBS_0_1110 | True |
| cmos3_pclk | E13 | cmos3_pclk | cmos3_pclk_ibuf/opit_0/I | IOBD_0_1176 | True |
| cmos3_rst_n | C19 | cmos3_rst_n | cmos3_rst_n_obuf/opit_0/O | IOBS_0_1056 | True |
| cmos3_scl | C13 | cmos3_scl | cmos3_scl_obuf/opit_0/O | IOBD_0_1128 | True |
| cmos3_sda | A15 | nt_cmos3_sda | cam3_ov5640_top.ov5640.i2c_dri.sda_tri/opit_0/IO | IOBD_0_1116 | True |
| cmos3_vsync | B13 | cmos3_vsync | cmos3_vsync_ibuf/opit_0/I | IOBS_0_1122 | True |
| cmos4_data[0] | C14 | cmos4_data[0] | cmos4_data_ibuf[0]/opit_0/I | IOBD_0_1188 | True |
| cmos4_data[1] | D15 | cmos4_data[1] | cmos4_data_ibuf[1]/opit_0/I | IOBS_0_1146 | True |
| cmos4_data[2] | D14 | cmos4_data[2] | cmos4_data_ibuf[2]/opit_0/I | IOBD_0_1152 | True |
| cmos4_data[3] | F20 | cmos4_data[3] | cmos4_data_ibuf[3]/opit_0/I | IOBS_0_996 | True |
| cmos4_data[4] | F19 | cmos4_data[4] | cmos4_data_ibuf[4]/opit_0/I | IOBD_0_1002 | True |
| cmos4_data[5] | A14 | cmos4_data[5] | cmos4_data_ibuf[5]/opit_0/I | IOBS_0_1098 | True |
| cmos4_data[6] | A13 | cmos4_data[6] | cmos4_data_ibuf[6]/opit_0/I | IOBD_0_1104 | True |
| cmos4_data[7] | C17 | cmos4_data[7] | cmos4_data_ibuf[7]/opit_0/I | IOBS_0_1074 | True |
| cmos4_href | F14 | cmos4_href | cmos4_href_ibuf/opit_0/I | IOBS_0_1206 | True |
| cmos4_pclk | D17 | cmos4_pclk | cmos4_pclk_ibuf/opit_0/I | IOBD_0_1080 | True |
| cmos4_rst_n | C15 | cmos4_rst_n | cmos4_rst_n_obuf/opit_0/O | IOBS_0_1182 | True |
| cmos4_scl | B17 | cmos4_scl | cmos4_scl_obuf/opit_0/O | IOBD_0_1092 | True |
| cmos4_sda | F13 | nt_cmos4_sda | cam4_ov5640_top.ov5640.i2c_dri.sda_tri/opit_0/IO | IOBD_0_1212 | True |
| cmos4_vsync | B18 | cmos4_vsync | cmos4_vsync_ibuf/opit_0/I | IOBS_0_1086 | True |
| free_clk | V4 | free_clk | free_clk_ibuf/opit_0/I | IOBD_372_468 | True |
| heart_beat_led | K17 | heart_beat_led | heart_beat_led_obuf/opit_0/O | IOBD_0_660 | True |
| mem_a[0] | T1 | nt_mem_a[0] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[0].u_outbuft_addr0/opit_0/O | IOBD_372_600 | True |
| mem_a[10] | U3 | nt_mem_a[10] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[10].u_outbuft_addr0/opit_0/O | IOBD_372_540 | True |
| mem_a[11] | AA1 | nt_mem_a[11] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[11].u_outbuft_addr0/opit_0/O | IOBD_372_528 | True |
| mem_a[12] | AB1 | nt_mem_a[12] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[12].u_outbuft_addr0/opit_0/O | IOBS_372_522 | True |
| mem_a[13] | AB3 | nt_mem_a[13] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[13].u_outbuft_addr0/opit_0/O | IOBD_372_516 | True |
| mem_a[14] | AB2 | nt_mem_a[14] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[14].u_outbuft_addr0/opit_0/O | IOBS_372_510 | True |
| mem_a[1] | U1 | nt_mem_a[1] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[1].u_outbuft_addr0/opit_0/O | IOBS_372_594 | True |
| mem_a[2] | U2 | nt_mem_a[2] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[2].u_outbuft_addr0/opit_0/O | IOBD_372_588 | True |
| mem_a[3] | V2 | nt_mem_a[3] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[3].u_outbuft_addr0/opit_0/O | IOBS_372_582 | True |
| mem_a[4] | R3 | nt_mem_a[4] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[4].u_outbuft_addr0/opit_0/O | IOBD_372_576 | True |
| mem_a[5] | R2 | nt_mem_a[5] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[5].u_outbuft_addr0/opit_0/O | IOBS_372_570 | True |
| mem_a[6] | W2 | nt_mem_a[6] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[6].u_outbuft_addr0/opit_0/O | IOBD_372_564 | True |
| mem_a[7] | Y2 | nt_mem_a[7] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[7].u_outbuft_addr0/opit_0/O | IOBS_372_558 | True |
| mem_a[8] | W1 | nt_mem_a[8] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[8].u_outbuft_addr0/opit_0/O | IOBD_372_552 | True |
| mem_a[9] | Y1 | nt_mem_a[9] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[9].u_outbuft_addr0/opit_0/O | IOBS_372_546 | True |
| mem_ba[0] | AA3 | nt_mem_ba[0] | ddr3/u_ddrphy_top/ddrphy_slice_top/k_mem_ba[0].u_outbuft_ba/opit_0/O | IOBS_372_498 | True |
| mem_ba[1] | AA5 | nt_mem_ba[1] | ddr3/u_ddrphy_top/ddrphy_slice_top/k_mem_ba[1].u_outbuft_ba/opit_0/O | IOBD_372_492 | True |
| mem_ba[2] | AB5 | nt_mem_ba[2] | ddr3/u_ddrphy_top/ddrphy_slice_top/k_mem_ba[2].u_outbuft_ba/opit_0/O | IOBS_372_486 | True |
| mem_cas_n | U6 | mem_cas_n | ddr3/u_ddrphy_top/ddrphy_slice_top/u_outbuft_casn/opit_0/O | IOBD_372_414 | True |
| mem_ck | Y4 | mem_ck | ddr3/u_ddrphy_top/ddrphy_slice_top/u_outbuftco_ck/opit_0/O | IOBD_372_480 | True |
| mem_ck_n | AA4 | mem_ck_n | ddr3/u_ddrphy_top/ddrphy_slice_top/u_outbuftco_ck/opit_1/O_B | IOBS_372_474 | True |
| mem_cke | W4 | mem_cke | ddr3/u_ddrphy_top/ddrphy_slice_top/u_outbuft_cke/opit_0/O | IOBS_372_462 | True |
| mem_cs_n | V5 | mem_cs_n | ddr3/u_ddrphy_top/ddrphy_slice_top/u_outbuft_csn/opit_0/O | IOBS_372_408 | True |
| mem_dm[0] | N5 | nt_mem_dm[0] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/u_outbuft_dm/opit_0/O | IOBS_372_618 | True |
| mem_dm[1] | L5 | nt_mem_dm[1] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/u_outbuft_dm/opit_0/O | IOBD_372_696 | True |
| mem_dq[0] | P6 | nt_mem_dq[0] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[0].u_iobuf_dq/opit_0/IO | IOBD_372_624 | True |
| mem_dq[10] | M2 | nt_mem_dq[10] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/dq_loop[2].u_iobuf_dq/opit_0/IO | IOBS_372_714 | True |
| mem_dq[11] | M3 | nt_mem_dq[11] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/dq_loop[3].u_iobuf_dq/opit_0/IO | IOBD_372_720 | True |
| mem_dq[12] | K3 | nt_mem_dq[12] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/dq_loop[4].u_iobuf_dq/opit_0/IO | IOBS_372_738 | True |
| mem_dq[13] | L3 | nt_mem_dq[13] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/dq_loop[5].u_iobuf_dq/opit_0/IO | IOBD_372_744 | True |
| mem_dq[14] | J4 | nt_mem_dq[14] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/dq_loop[6].u_iobuf_dq/opit_0/IO | IOBS_372_750 | True |
| mem_dq[15] | K4 | nt_mem_dq[15] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/dq_loop[7].u_iobuf_dq/opit_0/IO | IOBD_372_756 | True |
| mem_dq[1] | M5 | nt_mem_dq[1] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[1].u_iobuf_dq/opit_0/IO | IOBS_372_630 | True |
| mem_dq[2] | M6 | nt_mem_dq[2] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[2].u_iobuf_dq/opit_0/IO | IOBD_372_636 | True |
| mem_dq[3] | N2 | nt_mem_dq[3] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[3].u_iobuf_dq/opit_0/IO | IOBS_372_642 | True |
| mem_dq[4] | P2 | nt_mem_dq[4] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[4].u_iobuf_dq/opit_0/IO | IOBD_372_648 | True |
| mem_dq[5] | P1 | nt_mem_dq[5] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[5].u_iobuf_dq/opit_0/IO | IOBS_372_666 | True |
| mem_dq[6] | R1 | nt_mem_dq[6] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[6].u_iobuf_dq/opit_0/IO | IOBD_372_672 | True |
| mem_dq[7] | N4 | nt_mem_dq[7] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[7].u_iobuf_dq/opit_0/IO | IOBD_372_684 | True |
| mem_dq[8] | J6 | nt_mem_dq[8] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/dq_loop[0].u_iobuf_dq/opit_0/IO | IOBS_372_702 | True |
| mem_dq[9] | K6 | nt_mem_dq[9] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/dq_loop[1].u_iobuf_dq/opit_0/IO | IOBD_372_708 | True |
| mem_dqs[0] | P5 | nt_mem_dqs[0] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/genblk1.u_iobufco_dqs/opit_0/IO | IOBD_372_660 | True |
| mem_dqs[1] | M1 | nt_mem_dqs[1] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/genblk1.u_iobufco_dqs/opit_0/IO | IOBD_372_732 | True |
| mem_dqs_n[0] | P4 | nt_mem_dqs_n[0] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/genblk1.u_iobufco_dqs/opit_1/IO_B | IOBS_372_654 | True |
| mem_dqs_n[1] | L1 | nt_mem_dqs_n[1] | ddr3/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/genblk1.u_iobufco_dqs/opit_1/IO_B | IOBS_372_726 | True |
| mem_odt | R6 | mem_odt | ddr3/u_ddrphy_top/ddrphy_slice_top/u_outbuft_odt/opit_0/O | IOBD_372_402 | True |
| mem_ras_n | W5 | mem_ras_n | ddr3/u_ddrphy_top/ddrphy_slice_top/u_outbuft_rasn/opit_0/O | IOBS_372_420 | True |
| mem_rst_n | T3 | mem_rst_n | mem_rst_n_obuf/opit_0/O | IOBS_372_606 | True |
| mem_we_n | W6 | mem_we_n | ddr3/u_ddrphy_top/ddrphy_slice_top/u_outbuft_wen/opit_0/O | IOBD_372_426 | True |
| pclk_led | J16 | pclk_led | pclk_led_obuf/opit_0/O | IOBS_0_912 | True |
| perst_n | M16 | perst_n | perst_n_ibuf/opit_0/I | IOBS_0_618 | True |
| ref_led | M17 | ref_led | ref_led_obuf/opit_0/O | IOBS_0_612 | True |
| sfp_tx_disable | F15 | sfp_tx_disable | sfp_tx_disable_obuf/opit_0/O | IOBS_0_1218 | True |
