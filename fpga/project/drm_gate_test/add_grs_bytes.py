from pathlib import Path
here=Path(__file__).parent
p=here/'tb_drm_gate.sv'
b=p.read_bytes().replace(b'always #5 clk=~clk;',b'always #5 clk=~clk;\nGTP_GRS GRS_INST(.GRS_N(!rst));',1)
b=b.replace(b'.axi_data(data_out),',b'.axi_data_last(), .dbg_axi_cnt(), .dbg_axi_num(), .dbg_zdin(), .dbg_zout(),\n .axi_data(data_out),',1)
p.write_bytes(b)
p=here/'run_test.py'
b=p.read_bytes().replace(b'sources=list(primitives.values())+sources',b"sources=[primitive_dir/'GTP_GRS.v']+list(primitives.values())+sources",1)
p.write_bytes(b)
