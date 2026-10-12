from continue_fixed import PDS,busy
from pathlib import Path
import subprocess,json
R=Path(__file__).resolve().parent/'fixed_06/tiny_match10'
R.mkdir(exist_ok=True)
rtl='''module tiny(input clk,input [1:0] d,output [1:0] q);
genvar i; generate for(i=0;i<2;i=i+1) begin:cameras
leaf source(clk,d[i],q[i]); end endgenerate
endmodule
module leaf(input clk,input d,output reg q);
reg mailbox; always @(posedge clk) begin mailbox<=d; q<=mailbox; end
endmodule
'''
variants={'dot':'cameras[0].source.mailbox/CLK','slash':'cameras[0]/source/mailbox/CLK','escaped':r'cameras\[0\].source.mailbox/CLK','wild':'*source.mailbox/CLK','regexp':r'^cameras\[0\]\.source\.mailbox/CLK$'}
for name,pat in variants.items():
 assert not busy()
 w=R/name;w.mkdir();(w/'tiny.v').write_text(rtl)
 sel='-hierarchical '+('-regexp ' if name=='regexp' else '')
 fdc='create_clock -name clk -period 20 [get_ports clk]\nset_max_delay 7.123 -datapath_only -from [get_pins '+sel+'{'+pat+'}] -to [get_pins -hierarchical {*source.q/D}]\n'
 (w/'tiny.fdc').write_text(fdc)
 t='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nadd_design {'+(w/'tiny.v').as_posix()+'}\nadd_constraint -logic -fdc {'+(w/'tiny.fdc').as_posix()+'}\ncompile -top_module tiny -force_to_run\nsynthesize -ads -force_to_run\ndev_map -force_to_run\nreport_timing -input_db_file {'+(w/'device_map/tiny_map.adf').as_posix()+'} -force_to_run -delay_type max -max_path 100 -nworst 2 -input_pins TRUE -report_exception TRUE\n'
 (w/'run.tcl').write_text(t)
 with (w/'run.log').open('wb') as log:p=subprocess.run([str(PDS),'-file',str(w/'run.tcl'),'-work_dir',str(w),'-project_name','tiny'],stdout=log,stderr=subprocess.STDOUT)
 raw=(w/'run.log').read_bytes();errs=[x.decode('ascii','backslashreplace') for x in raw.splitlines() if x.startswith(b'E:') or b'Timing-4003' in x]
 reports=list(w.rglob('*.rtr'));evidence={str(x.relative_to(w)):x.read_bytes().decode('ascii','backslashreplace') for x in reports}
 nonempty=any('Startpoint' in v and 'MaxDelay Path' in v for v in evidence.values())
 (w/'result.json').write_text(json.dumps({'exit':p.returncode,'errors':errs,'timing_reports':evidence,'nonempty_maxdelay':nonempty,'acceptance':p.returncode==0 and not errs and nonempty},indent=2)); print(name,p.returncode,errs,'nonempty_maxdelay',nonempty,flush=True)
