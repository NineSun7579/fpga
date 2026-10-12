from pathlib import Path
import csv,json
P=Path(__file__).resolve().parent
signals=set((P/'diagnostics_signals.txt').read_text().splitlines())
rows=[]
for i in range(4):
 b=f'/tb_elab/dut/source_diagnostics/cameras[{i}]'
 def add(s,width,clk,role):
  full=b+'/'+s;assert full in signals,full
  rows.append(dict(simulation=full,rtl=full.replace('/tb_elab/dut/',''),width=width,clock=clk,requirement=role))
 add('reset_pipe',4,'axi_clk','ASYNC_REG; async assert / four-cycle release; pulse-width and recovery/removal')
 for s,w,c,r in [
  ('cr',2,f'cmos{i+1}_pclk','ASYNC_REG reset release'),('hr',2,'axi_clk','ASYNC_REG reset release'),
  ('request',1,f'cmos{i+1}_pclk','source toggle to req_sync[0]'),('req_sync',3,'axi_clk','ASYNC_REG; only first stage asynchronous exception'),
  ('ack',1,'axi_clk','ack toggle to ack_sync[0]'),('ack_sync',2,f'cmos{i+1}_pclk','ASYNC_REG; only first stage asynchronous exception'),
  ('sticky_overrun',1,f'cmos{i+1}_pclk','status to overrun_sync[0]'),('overrun_sync',2,'axi_clk','ASYNC_REG'),
  ('mailbox',512,f'cmos{i+1}_pclk','bundled data launch; held until ack'),('host_bank',512,'axi_clk','bundled data destination; max_delay <= 2*T_axi, not masked by clock_groups/false_path'),
  ('raw_vs_d',2,f'cmos{i+1}_pclk','synchronous alignment, NOT a CDC synchronizer'),('href_d',2,f'cmos{i+1}_pclk','synchronous alignment'),
  ('accept_d',2,f'cmos{i+1}_pclk','synchronous alignment'),('valid_d',1,f'cmos{i+1}_pclk','half-cycle negedge binding output to posedge; preserve real setup/hold')]:add('source/'+s,w,c,r)
for i,cam in enumerate(['ov5640_top','cam2_ov5640_top','cam3_ov5640_top','cam4_ov5640_top']):
 b=f'/tb_elab/dut/{cam}/ov5640'
 for s in ['cmos_frame_valid_r','cmos_frame_vsync_r']:
  full=b+'/'+s; assert full in signals,full
  rows.append(dict(simulation=full,rtl=full.replace('/tb_elab/dut/',''),width=1,clock=f'cmos{i+1}_pclk',requirement='negedge launch to diagnostic posedge; preserve half-cycle setup/hold, no added reset'))
with (P/'physical_hierarchy.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(P/'physical_hierarchy.json').write_text(json.dumps(rows,indent=2))
print('PHYSICAL_HIERARCHY_VALIDATED',len(rows),'objects against actual elaboration')
