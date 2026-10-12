from pathlib import Path
p=Path(__file__).resolve().parent
s=(p/'tb_timeout.sv').read_bytes()
s=s.replace(b'module tb_timeout;',b'module tb_timeout_recovery;')
s=s.replace(b'wire [2:0] cr,dr,done',b'wire [2:0] aborted;\nwire [2:0] cr,dr,done')
s=s.replace(b'integer ac[0:2]',b'integer aborts[0:2];\ninteger ac[0:2]')
s=s.replace(b'.clk(clk),.rst(rst),.cmd_valid',b".abort_req(1'b0),.data_in_abort(aborted[g]),\n .clk(clk),.rst(rst),.cmd_valid")
s=s.replace(b"ws[g]!==16'hffff",b"ws[g]!==16'h0000")
s=s.replace(b'zero/full strobe',b'zero/zero strobe')
s=s.replace(b'if(done[g]) begin',b'if(done[g]&&aborted[g])$fatal(1,"done and abort overlap");\n  if(aborted[g])aborts[g]=aborts[g]+1;\n  if(g==2&&done[g])$fatal(1,"abort incorrectly reported success");\n  if(done[g]||aborted[g]) begin')
s=s.replace(b'clen[i]=0;ac[i]=0;',b'clen[i]=0;aborts[i]=0;ac[i]=0;')
s=s.replace(b' $finish;',b' if(aborts[0]!=0||aborts[1]!=0||aborts[2]!=2)$fatal(1,"abort attribution wrong");\n $display("PASS separate success/abort: cam1=5/0 cam2=1/0 cam3=0/2");\n $finish;')
(p/'tb_timeout_recovery.sv').write_bytes(s)
print('Created tb_timeout_recovery.sv from existing three-camera timeout regression')
