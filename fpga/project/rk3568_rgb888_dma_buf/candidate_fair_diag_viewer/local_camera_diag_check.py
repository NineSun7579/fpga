"""Byte-level copied-RTL map checks and CameraWorker early-continue wiring checks."""
from pathlib import Path
import difflib

root = Path(__file__).resolve().parent
rtl = root.parent / "hardware_baseline/integrated_six_batch/source"
reg = (rtl / "ov5640/ov5640_reg.v").read_bytes()
decode = (rtl / "ov5640/ovreg_axil_decode.v").read_bytes()
ddr = (rtl / "ov5640/ov5640_ddr/ov5640_ddr.v").read_bytes()
top = (rtl / "ov5640/ov5640_top.v").read_bytes()
ctrl = (rtl / "ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v").read_bytes()
cdc = (rtl / "ov5640/ov5640/ov5640_cdc.v").read_bytes()
# Do not decode RTL as UTF-8: GBK comments can break even ASCII searches.
for literal in [b"REG_ACK       = BASE_ADDR + 32'h00", b"REG_DBG_VSYNCS    = BASE_ADDR + 32'h20",
                b"REG_DBG_CAM_WORDS = BASE_ADDR + 32'h30", b"REG_DBG_BEAT_CNT  = BASE_ADDR + 32'ha0",
                b"REG_DBG_BEAT_LAST = BASE_ADDR + 32'hf0"]:
    assert literal in reg, literal
for off, signal in [(b"190", b"input"), (b"1a0", b"output"), (b"1b0", b"drop"), (b"1c0", b"seq")]:
    assert b"BASE_ADDR + 32'h" + off + b": rdata <= dbg_cdc_" + signal in reg
    assert b"s_araddr[8:0] == 9'h" + off in decode
assert b"(s_araddr[11:9] < 4)" in decode
assert b"cdc_read ? {s_araddr[11:9], 1'b0}" in decode
assert b"assign dbg_reject_counts = {diag_overflows, diag_shorts}" in ddr
assert b"{capture_overflow, diag_short, 1'b0," in ddr
assert b"!frame_active, pixel_count[27:0]}" in ddr
assert b"dbg_input_pixels <= diag_input_count" in ddr
assert b"dbg_vs_ff[2:1] == 2'b01" in top
assert b"else if(publish) last_cnt <= last_cnt + 32'd1" in ctrl
assert b"src_snapshot <= {src_seq + 32'd1, src_drop, src_count}" in cdc
assert b"src_count <= {31'd0, s_valid}" in cdc
assert b"src_drop <= {31'd0, (s_valid && full)}" in cdc
assert b"out_count <= {31'd0, video_valid}" in cdc
source = (root / "main.cpp").read_text(encoding="utf-8-sig")
original = (root.parent / "candidate_fair_viewer/main.cpp").read_text(encoding="utf-8-sig")
changes = difflib.SequenceMatcher(None, original.splitlines(), source.splitlines()).get_opcodes()
assert all(tag in ("equal", "insert") for tag, *_ in changes), "Existing fair acquisition path changed"
worker = source[source.index("class CameraWorker"):source.index("class CameraThread")]
loop = worker[worker.index("while (running_)"):]
assert loop.index("diagnostic.tick(") < loop.index("continue;")
assert loop.index("diagnostic.result(result)") < loop.index("if (result == 0)")
assert "if (diagnosticEnabled) {" in loop
assert "if (diagnosticEnabled) diagnostic.result(result);" in loop
helper = source[source.index("void cameraDiagRead("):source.index("/* 六路采集线程")]
assert "regRead(camera_diag::bases[camera] + camera_diag::offsets[i]" in helper
assert "scheme2Quarantine(" in helper
assert "regWrite" not in helper and "openDev" not in helper and "FairDmaGuard" not in helper
assert "w.wait();" in source # workers retire before their stack owner PangoDev
print("CAMERA_DIAG_SOURCE_PASS byte-RTL offsets/decoder/semantics; before early continues; owner-only read helper")
