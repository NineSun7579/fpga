from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[2]
def change(name, old, new):
 p=root/name
 s=p.read_bytes();a=old.encode('ascii');b=new.encode('ascii')
 assert a in s,(name,old)
 i=1
 while p.with_name(p.name+f'.recovery{i}.bak').exists():i+=1
 shutil.copyfile(p,p.with_name(p.name+f'.recovery{i}.bak'))
 p.write_bytes(s.replace(a,b))
change('source/ov5640/ov5640_ddr/ov5640_ddr_w.v',
 '    assign capture_overflow = (wr_en && full) || (fifo_we && out_full);\n','')
change('source/ov5640/ov5640_ddr/ov5640_ddr_w.v',
 '    assign dbg_axi_cnt = axi_cnt;',
 '    assign capture_overflow = !local_rst && ((wr_en && full) || (fifo_we && out_full));\n    assign dbg_axi_cnt = axi_cnt;')
# Source starvation timer does not punish a healthy stream for AXI backpressure.
change('source/axi_dma/axi_dma_write.v',
 "|| (w_progress == 1'b1))", "|| (w_progress == 1'b1) || data_in_valid || !t_m_axi_wready)")
change('source/axi_dma/axi_dma_write.v',
 '!w_progress && (wd_cnt == WD_LIMIT)', '!data_in_valid && t_m_axi_wready && !w_progress && (wd_cnt == WD_LIMIT)')
