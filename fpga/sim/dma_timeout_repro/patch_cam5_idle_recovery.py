"""Apply ASCII byte anchors, preserving every GBK byte and line ending."""
from pathlib import Path

root = Path(__file__).resolve().parents[2]
p = root / 'source/ov5640/ov5640_ddr/ov5640_ddr.v'
backup = Path(__file__).with_name('cam5_idle_recovery_before.v')
original = backup.read_bytes() if backup.exists() else p.read_bytes()
nl = b'\r\n' if b'\r\n' in original else b'\n'
s = original.replace(b'\r\n', b'\n')
old = b'assign dma_abort_req = capture_bad;'
new = b'''assign dma_abort_req = capture_bad;
// Idle capture metadata must not permanently block all future SOFs. Allow
// the admitted-SOF/controller pipeline to settle before treating it as stale.
// A busy engine or offered command always retains ownership of its AXI work.
reg [3:0] idle_stop_count;
wire idle_capture_stale = (idle_stop_count == 4'd8);
always @(posedge axi_clk) begin
    if(axi_rst || capture_flush || engine_busy || axi_cmd_valid ||
       m_vsync || !capture_open || !(capture_complete || capture_bad))
        idle_stop_count <= 0;
    else if(!idle_capture_stale) idle_stop_count <= idle_stop_count + 1'b1;
end'''
assert s.count(old) == 1
s = s.replace(old, new)
old = b'if(dma_abort || (dma_done && (!frame_active || !frame_good))) flush_count <= 4;'
new = b'if(dma_abort || (dma_done && (!frame_active || !frame_good)) || idle_capture_stale) flush_count <= 4;'
assert s.count(old) == 1
s = s.replace(old, new)
if not backup.exists(): backup.write_bytes(original)
p.write_bytes(s.replace(b'\n', nl))
assert [l for l in original.splitlines() if any(c > 127 for c in l)] == [l for l in p.read_bytes().splitlines() if any(c > 127 for c in l)]

# Reuse the established real-DMA/packer/FIFO/bus scoreboard and all recovery
# scenarios. Only deposit orphaned metadata; never force DUT AXI outputs.
tb = Path(__file__).with_name('tb_credit_recovery.sv').read_bytes()
tb = tb.replace(b'module tb_credit_recovery;', b'module tb_cam5_idle_recovery;')
anchor = b'if(aw_count!=b_count||bus_active||left!=0||zero_strobes==0)'
insert = b'''   // Reproduce the observed idle + zero-fault + complete capture trap.
   idle();
   @(negedge clk);
   camera.capture_open = 1;
   camera.capture_bad = 0;
   camera.pixel_count = PIXELS;
   camera.pixel_limit = PIXELS;
   repeat(24) @(negedge clk);
   if(camera.capture_stop || camera.capture_open)
     $fatal(1,"idle complete capture remains permanently closed");
   if(last_cnt!=10 || state!=1 || cv || av || bus_active)
     $fatal(1,"orphan recovery fabricated completion or AXI work");
   $display("PASS idle complete metadata flushed without publication or AXI work");
   send_frame('h3800,PIXELS);check_frame('h3800,BANK0,11);
   idle();@(negedge clk);
   camera.capture_open = 1;
   camera.capture_bad = 1;
   camera.pixel_count = 13;
   camera.pixel_limit = PIXELS;
   repeat(24) @(negedge clk);
   if(camera.capture_stop || abort_req || camera.capture_open)
     $fatal(1,"idle bad capture remains permanently closed");
   if(last_cnt!=11 || state!=1 || cv || av || bus_active)
     $fatal(1,"bad orphan recovery fabricated completion or AXI work");
   $display("PASS idle bad metadata flushed without publication or AXI work");
   send_frame('h4800,PIXELS);check_frame('h4800,BANK1,12);
'''
assert tb.count(anchor) == 1
tb = tb.replace(anchor, insert + anchor)
tb = tb.replace(b'PASS FRAME RECOVERY', b'PASS CAM5 IDLE RECOVERY')
Path(__file__).with_name('tb_cam5_idle_recovery.sv').write_bytes(tb)
do = Path(__file__).with_name('credit_recovery.do').read_bytes()
do = do.replace(b'work_credit_recovery', b'work_cam5_idle_recovery').replace(b'tb_credit_recovery', b'tb_cam5_idle_recovery')
Path(__file__).with_name('cam5_idle_recovery.do').write_bytes(do)
baseline = do.replace(b'work_cam5_idle_recovery', b'work_cam5_idle_baseline').replace(b'../../source/ov5640/ov5640_ddr/ov5640_ddr.v ', b'cam5_idle_recovery_before.v ')
Path(__file__).with_name('cam5_idle_baseline.do').write_bytes(baseline)
vendor = Path(__file__).with_name('credit_recovery_vendor.do').read_bytes()
vendor = vendor.replace(b'work_credit_vendor', b'work_cam5_idle_vendor').replace(b'tb_credit_recovery', b'tb_cam5_idle_recovery')
Path(__file__).with_name('cam5_idle_vendor.do').write_bytes(vendor)
boundary = Path(__file__).with_name('boundary.do').read_bytes().replace(b'work_boundary', b'work_cam5_boundary_fixed')
Path(__file__).with_name('cam5_boundary_fixed.do').write_bytes(boundary)
print('Patched one wrapper; GBK comment bytes preserved; generated isolated regression/baseline')
