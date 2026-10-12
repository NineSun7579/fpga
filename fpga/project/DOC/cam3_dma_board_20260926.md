# DMA ledger repair: board evidence and pending acceptance

## Flashed version

- Artifact: `bitstream_cam3_verified_20260926_193700/top.sbit`
- SHA256: `66677BBCEC0AA4793D0F4B6C86841C2F4BC30DCADE8D2A79D26C65E6AA2CE56B`
- Build timing: All Constraints Met; cam3 slow setup WNS 4.826 ns.
- Deployment returned FLASH_RESULT SUCCESS.
- DMA regression evidence: `sim/dma_timeout_repro/fixed.log`; baseline failure in `baseline_failure.log`.

## Board findings

Screenshots `cam3_verify_20260926_193807_a.png` and `_b.png` are actually 999x562.
The original validation assertion assumed width 1000 and stopped after capture.
Offline pixel comparison is recorded in `cam3_verify_20260926_193807.json`.
ROIs exclude overlay, y=200..405, x=0..333 / 333..666 / 666..999.
Changed pixels (maximum RGB difference >8): 0 / 68265 / 4608.
Cam3 is striped, not a valid camera scene. Cam2 is fragmented. Cam1 has no
ROI changes in this pair. These results do not meet the three-camera goal.

With viewer stopped, successive AW_B samples were:

| Camera | Sample 0 | Sample 1 | Sample 2 |
|---|---|---|---|
| 1 | 45c545c5 | 49974998 | 4c464c46 |
| 2 | 47794779 | 4b4b4b4b | 4dfa4dfa |
| 3 | 28772878 | 2b022b02 | 2c712c72 |

All three write counters progressed. This supports recovery from the previous
permanent shared write wedge, but does not prove complete valid video frames.
Raw VSYNC samples: cam1 2388/2478/2568, cam2 2390/2480/2570,
cam3 385671/399037/412392, approximately two seconds between samples.

## Diagnostic correction awaiting next bitstream

The first added I2C/HREF/system offsets +4/+8/+C were inaccessible: PCIe M01
ignores address bits [3:0], as documented in ov5640_reg.v. Reading a 16-byte
block or individually requesting these offsets yielded zeros; those zeros
must not be interpreted as failed sensor identity/configuration.

`tools/fix_cam3_diag_alignment.py` backs up and edits bytes to map diagnostics
onto +0x50 (I2C), +0x90 (raw HREF), +0xD0 (system), replacing prior debug-only
readbacks. Existing control registers and AW/B/state/raw-VSYNC remain intact.
The corrected SSH probe is `/tmp/probe_cam3_identity.py`.
System word actual packing: transaction count [21:6], SDA [3], SCL [2],
reset_n [0]. I2C word: NACK counter [31:16], sensor ID [15:0] expected 0x5640.

The aligned diagnostic version is building in project_kf. It has not yet
been flashed or validated at the time of this record. Viewer is stopped.

## Acceptance checklist

- [x] DDR FIFO self-lock reproduced and fixed in real FIFO IP simulation.
- [x] Register decode fixed and validated in four-window simulation.
- [x] DMA timeout wedge reproduced; repaired AW/W/B ledger regression passes.
- [x] DMA repair bitstream flashed via existing programmer; RK3568 via SSH.
- [ ] Correctly aligned I2C/HREF diagnostics read on hardware.
- [ ] Third camera shows a recognizable, complete camera scene.
- [ ] All three cameras update concurrently, verified with paired image ROIs
      and frame evidence; noise, stripes, title fps and tags alone do not pass.
- [ ] On success stop this round immediately, leaving cam1 purple artifacts
      as a later task.
