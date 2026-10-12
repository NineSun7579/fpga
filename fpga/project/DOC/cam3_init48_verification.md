# cam3 initialization at 48 MHz

This note supersedes unsupported conclusions in rounds 6 and 7.

- Runtime PLL changes that yielded frozen buffers did not establish whether initialization at 48 or 54 MHz would work. Old frozen images cannot establish frequency independence of the corruption.
- Register BASE+0xd0 reads dbg_sys_status, not a DDR address. 0x420d encodes sensor initialization status, including 264 executed commands. It does not indicate a stall at 44% of a frame.
- A few FSM snapshots and the low eight bits of a state-age counter do not prove a permanent deadlock. Counters that continue advancing require further investigation.
- Reconfiguration recovered measured frame rates in one later attempt. DDR calibration has not been established as the cause of earlier low rates.

## New build

Only cam3 overrides SENSOR_PLL_MULT to 0x30. The default remains 0x54 for cam1/cam2. The parameter passes through ov5640_top and ov5640 to ov5640_i2c_rgb565_cfg, where register 0x3036 uses it. Original source bytes were backed up as timestamped .bak files.

Artifact: bitstream_cam3_init48_20260927_103702/top.sbit

SHA256: 5091DD1AC5140A4E9A2E8F155E1845F205902E59469D2DCDEEF4A6155BF8A5D9

Deployment: tools/deploy_cam3_init48.py and flash_cam3_init48.tcl. Verification reads counters and raw buffers; no runtime sensor writes are made. Evidence is retained in tp/init48_evidence.

## cam2 before this deployment

Six raw frames from both banks show a stable boundary between columns 460 and 461 (zero based). This excludes a display-only composition error for these captured frames. Row-boundary comparisons support a stream offset but do not yet identify whether the fault is in capture, buffering, DDR writing, or DMA reading. Evidence: tp/cam2_evidence_84mhz/REPORT.md.
