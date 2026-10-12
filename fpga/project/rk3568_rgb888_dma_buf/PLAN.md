# RK3568 FPGA RGB888 DMA-BUF input integration

User selected FPGA RGB565-to-RGB888 conversion, PCIe DMA into a shared buffer,
and RKNN input binding. All implementation and new artifacts are confined to
D:\race\ov56401. D:\race\fpga is protected from changes. Existing IP and
archives remain intact; work uses this isolated directory.

## Acceptance

- Preserve exact camera/frame identity between RAW analytics and RGB inference.
- Preserve RGB order, bit replication, model geometry, padding and detections.
- Display continues receiving RGB565; RAW analytics, stereo and HDMI continue.
- RKNN remains on RK3568. Existing legacy FPGA NPU RAW input is unchanged.
- DMA-BUF allocation, importer mapping and slot ownership must be validated;
  PCIe bus addresses must not be used as NPU physical addresses.
- Validate input/native-output parity before live before/after measurements.
- Record CPU, fresh camera FPS, display FPS and RKNN completions separately.
- SRAM-only deployment with verified original runtime rollback; SPI untouched.

## Context from completed experiment

The previous isolated 240-pair DMA-BUF experiment matched all input/native
output bytes. Process CPU14.002→6.183ms (-55.84%) and stage throughput
24.850→25.149/s (+1.20%). This tested a640-square V8 model; live MVP uses
640x480 input and needs its original contexts, output layout and decoder.
The currently restored runtime uses original FPGA image SHA256
fcb2e44d5b97d9857e72610d543300e747dcc4a822e8797bbf5d5418ddd01122
and viewer SHA256
73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100.
These are prior observations; recheck live identities before deployment.

## Work underway

Locate source and protocol equivalents within ov56401; inspect current viewer
and FPGA interfaces before implementing a candidate. Original viewer six DMA
slots overlap the standalone2MiB input slot, so that layout cannot be reused.
Acquire RAW and RGB from one lease and carry owned input/frame metadata to
inference. Do not relabel a newly claimed frame as an earlier analytics frame.
Build an isolated candidate with a default-off flag and reviewed rollback.
