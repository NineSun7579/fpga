from pathlib import Path
import re,subprocess,json,hashlib
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent/'whole_candidate_v3_timing_route_01'
OUT=HERE/'dma_artifacts'
SIM=Path(r'C:\modeltech64_10.6e\win64')
def run(cmd,label):
    r=subprocess.run([str(x) for x in cmd],cwd=OUT,capture_output=True,timeout=120)
    data=r.stdout+r.stderr;(OUT/(label+'.log')).write_bytes(data)
    assert not r.returncode and b'** Error' not in data and b'** Fatal' not in data,data.decode(errors='replace')
    return data
def main():
    OUT.mkdir(exist_ok=True);(HERE/'rtl').mkdir(exist_ok=True)
    source=ROOT/'inputs/source/axi_dma/axi_dma_write.v'; raw=source.read_bytes()
    assert raw.count(b'reg [31:0] len;')==1
    new=raw.replace(b'module axi_dma_write',b'module axi_dma_write_tc02',1)
    new=new.replace(b'reg [31:0] len;',b'reg [32-AXI_BURST_SIZE:0] len;')
    target=HERE/'rtl/axi_dma_write_tc02.v';target.write_bytes(new)
    # Derive shared stimulus / compared output buses from the frozen public API.
    header=raw.split(b');',1)[0]
    header=re.sub(rb'//[^\r\n]*',b'',header)
    ports=[]
    for direction,width,name in re.findall(rb'\b(input|output)\s+(?:reg\s+)?(\[[^\]]+\])?\s*(\w+)\s*(?=,|$)',header,re.M):
        width=width.decode().replace('ID_WIDTH','4').replace('DATA_WIDTH','128').replace('KEEP_WIDTH','16')
        ports.append((direction.decode(),width,name.decode()))
    assert len(ports)==34,len(ports)
    lines=['`timescale 1ns/1ps','module tb_dma_tc02; parameter integer WAIT=1;']
    for d,w,n in ports:
        lines.append(('reg '+w+' '+n+'=0;' if d=='input' else 'wire '+w+' old_'+n+', new_'+n+';'))
    for mod,prefix in [('axi_dma_write','old'),('axi_dma_write_tc02','new')]:
        binds=','.join('.'+n+'('+ (n if d=='input' else prefix+'_'+n)+')' for d,w,n in ports)
        lines.append(mod+' #(.WAIT_FOR_DATA(WAIT),.BURST_LEN(16)) '+prefix+'_dut('+binds+');')
    oldbus=','.join('old_'+n for d,w,n in ports if d=='output')
    newbus=','.join('new_'+n for d,w,n in ports if d=='output')
    lines+=['always #4 clk=~clk;',
      'always @(negedge clk) if(!rst) begin',
      'm_axi_awready=$urandom_range(0,1);m_axi_wready=$urandom_range(0,1);',
      'data_in_valid=$urandom_range(0,1); data_in_available=32;',
      'end',
      'always @(posedge clk) begin',
      "if(rst) m_axi_bvalid<=0; else if(old_m_axi_wvalid && m_axi_wready && old_m_axi_wlast) m_axi_bvalid<=1; else if(m_axi_bvalid && old_m_axi_bready) m_axi_bvalid<=0;",
      "#1; if({"+oldbus+'} !== {'+newbus+'}) $fatal(1,"public output mismatch");',
      "if(old_dut.len !== {3'b0,new_dut.len}) $fatal(1,\"beat count mismatch\");",
      'end',
      'integer i,j;reg [31:0] size;',
      'initial begin',
      "data_in_keep=16'hffff;data_in=128'h123456;",
      'for(i=0;i<80;i=i+1) begin',
      "case(i) 0:size=0;1:size=1;2:size=15;3:size=16;4:size=17;5:size=4092;6:size=4096;7:size=32'hffffffff;8:size=32'hfffffff0;9:size=32'h80000001; default:size=$urandom;endcase",
      'rst=1;cmd_valid=0;abort_req=0;repeat(4) @(negedge clk);rst=0;',
      'wait(old_cmd_ready);@(negedge clk);cmd_len=size;cmd_addr=32\'h01800ff0;cmd_valid=1;',
      '@(negedge clk);cmd_valid=0;',
      'for(j=0;j<400;j=j+1) begin @(negedge clk);if(j==200) abort_req=1;end',
      'end',
      '$display("DMA_TC02_PASS cases=80");$finish;end',
      'initial begin #1000000;$fatal(1,"timeout");end','endmodule']
    (OUT/'tb_dma_tc02.sv').write_text('\n'.join(lines),encoding='ascii')
    run([SIM/'vlib.exe','work'],'vlib')
    run([SIM/'vlog.exe','-sv',source.parent/'stream_pipe.v',source,target,OUT/'tb_dma_tc02.sv'],'compile')
    for mode in [0,1]:
        data=run([SIM/'vsim.exe','-c','-onfinish','stop','work.tb_dma_tc02','-gWAIT='+str(mode),'-do','run -all; quit -f'],'simulation_wait_'+str(mode))
        assert b'DMA_TC02_PASS' in data
    assert source.read_bytes()==raw
    (OUT/'results.json').write_text(json.dumps({'cases':160,'wait_for_data_modes':[0,1],'cases_per_mode':80,'public_outputs_and_internal_beat_count_match':True,'candidate_sha256':hashlib.sha256(new).hexdigest(),'routed_timing_verified':False},indent=2))
    print('PASS 160 DMA comparison cases, WAIT_FOR_DATA=0/1',flush=True)
if __name__=='__main__':main()
