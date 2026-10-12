# Isolated CAM3/4 timing candidate

Prepared for parent review only. Target policy is fresh CAM1/2/5/6 at 40 FPS and CAM3/4 at 30 FPS, with the deployed motion functionality and six video paths retained. This candidate changes only CAM3/4 sensor VTS. It does not establish achieved FPS; host capture/display limits and measured board rates remain the parent's responsibility.

The immutable input is `project/motion_100h/run_20261003_212303/inputs`, with that run's `project.pds` and `input_sha256.json`. Verified baseline bit SHA256: `e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7`. This identifies the archived motion bit; no device readback or programming was performed here. Frozen manifest SHA256: `e1059783fe49166f4507257dafc57ce4abc06e27e294607ce07b59c5401c6c0a`. All 694 source/IP files were hash checked against it.

`fpga/source/top.v` is a byte-preserving GBK copy from the frozen source, with exactly two changed lines: 1571 and 1672, inside `cam3_ov5640_top` and `cam4_ov5640_top`. Both `.TOTAL_V_PIXEL (12'd984)` values become `12'd843`. CAM3/4 retain 640x480, HTS 1896, PLL multiplier `8'h30`, VSYNC qualification, and all other settings. Motion RTL, result records, DDR, PCIe, SFP CAM5/6, and CAM1/2 are byte-identical to the frozen baseline. The baseline motion implementation supplies CAM1–4 records; CAM5/6 motion records are zero, as before.

Candidate top SHA256: `ce3d9714f7806b0d70e01332ba56138ca83de337a4f3101ac0f0fa52ae43ddab`; baseline top SHA256: `ba90f96605423210f9563990a470e0d9585529c4f7edcda1c086bf3fae3c45b2`. At an assumed actual 48 MHz PCLK, `48e6 / (1896 * 843)` is approximately 30.0314 FPS. The previous nominal value is approximately 25.7281 FPS. These calculations assume the sensor uses the programmed frame length and does not extend it for exposure.

`fpga/cloned.pds` copies the exact frozen project metadata, rebasing every registered source/IP path to the frozen inputs and replacing its sole top entry with the isolated top. All 386 registered paths resolve. No live `project/source` input is used. All six registered FDCs are unchanged, including CAM3/4 `20.833 ns` PCLK periods (48 MHz), CAM1/2 `11.905 ns`, PLLs, root clocks, and pin constraints. `fpga/preparation.json` records the hashes. Protected vendor IP is never edited.

The actual parameter path is `top.v` → `ov5640_top.TOTAL_V_PIXEL` → `ov5640.TOTAL_V_PIXEL` → configuration ROM `total_v_pixel[12:0]`. The 12-bit literal is widened to the ROM's 13-bit input. The ROM emits a 24-bit `{16-bit register address, 8-bit value}` transaction. Static byte checks verify this path and PLL forwarding; dynamic simulation covers the real frozen ROM, rather than a rewritten register model.

ModelSim 10.6e passed in `fpga/sim_qiw5obx2/receipt.json` with the complete log in `simulation.log`. The test runs natural initialization with synthetic I2C transaction completion, without forcing the internal ROM index. It checks all 264 transactions in four profiles (default PLL/VTS984, CAM3/4 PLL0x30/VTS984, candidate CAM3, candidate CAM4): 1,056 total. It checks read/write direction, 9-bit ROM indices through 263, unchanged full-ROM values, geometry, HTS, PLL, and exposure writes. This is a configuration-ROM test, not an electrical SCCB test or full video/motion simulation.

| ROM index | Register | Frozen CAM3/4 | Candidate CAM3/4 |
|---|---|---|---|
| 209 | 0x3036 PLL multiplier | 0x30 | 0x30 |
| 223–224 | 0x3808/09 width | 0x0280 = 640 | same |
| 225–226 | 0x380a/0b height | 0x01e0 = 480 | same |
| 227–228 | 0x380c/0d HTS | 0x0768 = 1896 | same |
| 229–230 | 0x380e/0f VTS | 0x03d8 = 984 | 0x034b = 843 |
| 236–237 | 0x3a02/03 60 Hz max exposure | 0x1710 = 5904 | same |
| 238–239 | 0x3a14/15 first 50 Hz max exposure | 0x1710 = 5904 | same |
| 246–247 | 0x3a14/15 final 50 Hz max exposure | 0x02e0 = 736 | same |

The byte scan of the entire actual ROM finds one VTS high/low pair, with no later VTS override. It finds both writes to the 50 Hz exposure maximum, so the final value is 736 rather than 5904. No writes to 0x3500–0x3503 (exposure/manual control), 0x350c/0x350d (AEC frame length), 0x3a00 (AEC control), or 0x3a0d/0x3a0e (banding maxima) are present in this ROM. Their effective sensor values depend on reset/default state and later runtime control. The 60 Hz maximum exceeds candidate VTS; exposure behavior and low-light frame extension need board observation. No exposure or banding setting was changed and no sensor register was written.

Run from the workspace root:

```powershell
python project/per_camera_fps/fpga/prepare.py
python project/per_camera_fps/fpga/simulate.py
python project/per_camera_fps/fpga/build_later.py --check
# Parent invokes only after reviewing and declaring readiness:
python project/per_camera_fps/fpga/build_later.py --run
```

Readiness passed without a vendor launch. `build_later.py` is standalone and never calls the inherited build's launcher/preparation/status writers. It uses the inspected motion build stage order and the successful frozen `strong_pnr.tcl` options, including multi-corner timing and hold repair. Its read-only validators come from `motion_100h/build.py`; it suppresses bytecode writes outside this directory.

Each actual build allocates a unique private `fpga/build_*/work` and private byte-identical source/IP copies, rebasing the runtime project there so vendor regeneration cannot touch frozen IP. It does not reuse or delete any existing outputs. `tasklist` must show no PDS GUI/shell, backend or programming process before every vendor stage. Commands use argument arrays with `shell=False`, no GUI, download or SSH. `--check` verifies frozen provenance, project paths and a matching passing simulation receipt. There is an exclusive candidate build lock.

The runner saves commands, tasklist snapshots, per-stage logs and SHA256s, input manifest, runtime project identity, mapped/synthesized/physical-constraint hashes, complete area/report evidence, exact final multi-corner STA rows/report hash, routed DB hash, and candidate bit SHA256. Pin and HSST placement/pad equivalence plus full final STA must pass before candidate bit generation. A new candidate motion RAM/read-first/resource review remains required before deployment; the inherited bit's review is not asserted for a newly mapped design. The receipt labels a successful output `built_for_parent_review`, with all artifacts retained on failure.

Allow approximately 33 minutes for a full vendor build; actual duration is unknown until run. The parent has started the isolated vendor build through `build_later.py --run`. Programming and candidate hardware deployment have not been performed. Final timing, area, sensor rates, frame freshness, six-video acceptance and retained motion behavior remain unmeasured for this candidate.
