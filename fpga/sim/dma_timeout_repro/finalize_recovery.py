from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[2]
def edit(name,fn):
 p=root/name;s=p.read_bytes();n=fn(s);assert n!=s
 bak=p.with_name(p.name+'.finalize.bak');assert not bak.exists()
 shutil.copyfile(p,bak);p.write_bytes(n)
def top(s):
 decl=b''
 for cam in [b'cam',b'cam2',b'cam3']:
  line=b'wire '+cam+b'_dma_abort, '+cam+b'_dma_abort_req;\n'
  assert line in s;s=s.replace(line,b'');decl+=line
 pos=s.index(b'wire [7:0]                  prep_frame_cnt;')
 return s[:pos]+decl+s[pos:]
edit('source/top.v',top)
def ctrl(s):
 s=s.replace(b'// aborting it would leave a pending frame with no new tag for the host.',b'// only its successful B response publishes the buffer and success counters.')
 s=s.replace(b"// [FRTAG 2026-09-14] sticky vsync latch: a vsync pulse arriving while the tag\n    // states are running must not be lost (previously a 1-cycle rise pulse).",b'// Only latch admitted SOF while idle. Busy-frame markers are discarded;\n    // replaying one after retirement would restart in the middle of a frame.')
 return s
edit('source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v',ctrl)
def tb(s):
 s=s.replace(b'reg rst=1,sv=0,pv=0;',b'reg auto_ack=1;\n reg rst=1,sv=0,pv=0;')
 s=s.replace(b'  ack=3;repeat(2)@(negedge clk);ack=0;',b'  if(auto_ack)begin ack=3;repeat(2)@(negedge clk);ack=0;end')
 mark=b'  if(aw_count!=b_count||bus_active'
 pos=s.index(mark)
 add=b'''  // Retain both pending requests, overwrite only the selected bank, then fail.
  auto_ack=0;
  send_frame('he000,PIXELS);check_frame('he000,BANK1,8);
  send_frame('hf000,PIXELS);check_frame('hf000,BANK0,9);
  if(req!=3)$fatal(1,"expected two retained valid bank requests");
  a=abort_count;t=tag_count;
  send_frame('h1800,13);sof();wait(abort_count==a+1);idle();
  if(req!=1||last_cnt!=9||prev_base!=BANK0||tag_count!=t)$fatal(1,"dirty target bank still valid or previous good bank lost");
  $display("PASS dirty bank request invalidated; last good bank remains valid after abort");
  // No publication until the tag's actual B response, even after all W data.
  auto_ack=1;
  send_frame('h2800,PIXELS);wait(cur_tag);@(negedge clk);stall_b=1;
  wait(bv);repeat(100)@(negedge clk);
  if(last_cnt!=9||req!=1||prev_base!=BANK0||aborted)$fatal(1,"published tag before successful B");
  stall_b=0;check_frame('h2800,BANK1,10);
  $display("PASS tag B backpressure longer than WD_LIMIT never publishes early");
'''
 return s[:pos]+add+s[pos:]
edit('sim/dma_timeout_repro/tb_frame_recovery.sv',tb)
