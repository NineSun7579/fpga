192245 receiver identity audit

The six byte-exact extracted files in extracted/ match both the archive's
source_sha256.json and current production bytes:

- source/top.v
- source/sfp/sfp_rx_link.v (actual 100H wrapper; no hsst_test module is used)
- source/sfp/sfp_video_rx.v
- source/sfp/sfp_rx_cam_if.v
- source/sfp/video_async_fifo.v
- ipcore/hsst_sfp/hsst_sfp.v

Full hashes, archive checksums and rechecked replay results: evidence.json.
Reproduce with python audit.py. It writes only within this isolated directory.
All 725 ZIP entries match the archived manifest. The archived project registers
the receiver sources and HSST IP. bit.log records analysis of these paths and
final bit generation at 2026-10-02 19:45:08. The six sources were snapshotted
before the build. The final archive top.sbit is 3,791,112 bytes, SHA256:
c3f07533e37e77ab734d37a5a4ba4ed8ebc8af0841e09fa43f2dcc076f16a44a.
project/flash_six_verified_20261002.tcl assigns that archived file.
This is documentary source/build provenance, not a cryptographic build
attestation or a fresh observation of the currently programmed device.

The manifest's project_build/generate_bitstream/top.sbit entry is the previous
44d6a5... bit included in the pre-build snapshot. It must not be presented as
the final C3F checksum. The final C3F checksum above was computed independently.

Existing currentwork_compile.log identifies the production wrapper and decoder
used by run_tests.py; their test manifest hashes match the exact archive.
Thus its 12 currentwork cases cover the exact archived wrapper/decoder and
need no duplicate simulation. All 24 saved pixel outputs were freshly compared
against all 614,400 golden RGB565 values in order. Baseline, 128 isolated
two-byte insertions and 128 isolated two-byte deletions each cover offsets
0,1,2,3 for both receivers. Each case has one SOF and zero overflow; edited
cases have at least 128 reacquisitions. The other 12 oldwork cases remain a
conservative older-selector test, not the exact 192245 receiver.

TX candidate SHA256 is
29a637f725a48323b8f8351221183cf823afa5917a41098bc748cd61969793cc.
The captured full frame contains 307,200 guard words and 307,200 payload
words, not a tiny sample or 312 KB guard block. Guards alone are 1,228,800
data bytes before K flags/line encoding. This capture is a 50K TX experiment;
it is not the 100H bitstream. Top uses IMG_W=1280, SPLIT_W=640, FIFO_D=1024.
100H CH2 IP is GE_MODE, GE CTC (2SKIP), GE_AUTO enabled, skip BC(K)/50(D).

Remaining limits: HSST vendor IP is stubbed in the replay; GE automatic
transformations are not simulated. Splitter, CDC FIFO, top and IP are verified
by source identity only, not dynamically covered by these wrapper/decoder
replays. No PDS, IP modification, production edit, JTAG or RK action was used.
