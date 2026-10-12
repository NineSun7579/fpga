"""Independent directed verification. Never writes production sources or runs PDS."""
from pathlib import Path
import hashlib, json, subprocess

ROOT = Path(__file__).resolve().parent
ART = ROOT / 'sim_six_background_extra'
SRC = ROOT / 'integrated_six_background/source'
BIN = Path('C:/modeltech64_10.6e/win64')

def run(args, name, marker=None):
    p = subprocess.run([str(x) for x in args], cwd=ART, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (ART/name).write_bytes(p.stdout)
    text = p.stdout.decode('utf8', errors='replace')
    if p.returncode or '** Error:' in text or '** Fatal:' in text or (marker and marker not in text):
        raise RuntimeError(name+'\n'+text[-6000:])
    print('PASS '+name, flush=True)
    return text

def main():
    ART.mkdir(exist_ok=True)
    protected = list(SRC.rglob('*')) + list((ROOT/'integrated_six_background/project').rglob('*'))
    protected += [ROOT/'make_six_background.py', ROOT/'verify_six_background.py', ROOT/'background_tb.sv']
    # Project build outputs can legitimately change during concurrent PDS.
    protected = [p for p in protected if p.is_file() and (p.suffix in ('.v','.sv','.pds','.fdc') or p.parent==ROOT)]
    before = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    lib = ART/'work'
    if not lib.exists(): run([BIN/'vlib.exe',lib], 'vlib.log')
    raw = (ROOT.parent/'sim/dma_timeout_repro/tb_frame_recovery.sv').read_bytes()
    raw = raw.replace(b' ov5640_ddr #', b''' wire ts,tv,tbad,tp; wire [15:0] tpx;
 wire quiet,q; wire [3071:0] rec;
 wire [31:0] ba; wire [7:0] bl; wire bav,bwv,bwl,bbr;
 wire [127:0] bwd; wire [15:0] bws;
 reg bbv=0; integer bleft=0,boff=0,bbeat=0,baw=0,bb=0,btag=0;
 integer seed_seen=0,first_pixel=1,bcam_bank=0,bi,bindex,bexpect,success_bg=0,raw_flush_pulses=0;
 reg [15:0] bm[0:262143]; reg [1:0] old0=0,old1=0;
 background_six #(.WIDTH(32),.HEIGHT(16),.DEADLINE(1048576)) branch(
 .clk(clk),.rst(rst),.enable(1'b1),.invalidate(12'd0),
 .sof({5'd0,ts}),.pixel_valid({5'd0,tv}),.source_bad({5'd0,tbad}),
 .raw_publish({5'd0,tp}),.pixels({80'd0,tpx}),.source_sequence({160'd0,last_cnt}),
 .quiescent(quiet),.quarantine(q),.records(rec),.awaddr(ba),.awlen(bl),
 .awvalid(bav),.awready(!bbv && bleft==0),.wdata(bwd),.wstrb(bws),
  .wvalid(bwv),.wlast(bwl),.wready(1'b1),.bresp(2'd0),.bvalid(bbv),.bready(bbr));
  reg [51:0] previous_tap=0;
  integer tap_edges=0,aligned_sofs=0,aligned_publications=0,aligned_faults=0;
  always @(posedge clk) begin
   if(rst) previous_tap=0;
   else begin
    if({branch.cameras[0].producer.sof,branch.cameras[0].producer.pixel_valid,
        branch.cameras[0].producer.source_bad,branch.cameras[0].producer.raw_publish,
        branch.cameras[0].producer.pixel,branch.cameras[0].producer.source_sequence}!==previous_tap)
     $fatal(1,"real RAW chain tap tuple phase mismatch");
    tap_edges=tap_edges+1;
    if(previous_tap[51])aligned_sofs=aligned_sofs+1;
    if(previous_tap[48])aligned_publications=aligned_publications+1;
    if(previous_tap[49])aligned_faults=aligned_faults+1;
    previous_tap={ts,tv,tbad,tp,tpx,last_cnt};
   end
  end
 always @(posedge clk) if(!rst) begin
  if(tp)begin
   if(tbad || !camera.capture_flush)$fatal(1,"RAW counter pulse must export during nonfault local flush");
   raw_flush_pulses=raw_flush_pulses+1;
  end
  if(ts)first_pixel=1;
  if(tv && first_pixel)begin seed_seen=tpx;first_pixel=0;end
  if(bav && !bbv && bleft==0)begin
   baw=baw+1;bleft=bl+1;boff=ba-32'h0a280000;bbeat=0;
   bcam_bank=boff/32'h40000;
   if(rec[bcam_bank*256+:2]!=1)$fatal(1,"RAW chain guard before AW");
  end
  if(bwv && bleft>0)begin
   if(bwl!=(bleft==1))$fatal(1,"chain WLAST");
   for(bi=0;bi<8;bi=bi+1)if(bws[bi*2+:2]==3)bm[boff+bbeat*8+bi]=bwd[bi*16+:16];
   if(boff%32'h40000==256)btag=btag+1;
   bbeat=bbeat+1;bleft=bleft-1;if(bleft==0)bbv<=1;
  end
  if(bbv && bbr)begin bbv<=0;bb=bb+1;end
  if(rec[1:0]==2 && old0!=2)verify_bg(0);
  if(rec[257:256]==2 && old1!=2)verify_bg(1);
  old0<=rec[1:0];old1<=rec[257:256];
 end
 task verify_bg(input integer bank);
 integer i,expected;
 begin
  if(rec[bank*256+128+:32]!==last_cnt)$fatal(1,"chain sequence not hardware RAW counter");
  if({bm[bank*262144+257],bm[bank*262144+256]}!==last_cnt)$fatal(1,"chain memory tag");
  for(i=0;i<128;i=i+1)begin
   expected=(seed_seen+(i/16)*64+(i%16)*2)%65536;
   if(bm[bank*262144+i]!==16'(expected))$fatal(1,"chain CPU even-coordinate pixel %0d",i);
  end
  success_bg=success_bg+1;
  $display("EXTRA_RAW_PUBLICATION bank=%0d hardware_counter=%h pixels=128",bank,last_cnt);
 end endtask
 ov5640_ddr #''', 1)
    # Memory index covers two HMIC banks, including unused gaps.
    raw=raw.replace(b'bm[0:262143]', b'bm[0:524287]')
    raw=raw.replace(b' camera(\n',b' camera(\n .bg_sof(ts),.bg_valid(tv),.bg_bad(tbad),.bg_raw_publish(tp),.bg_pixel(tpx),\n',1)
    raw=raw.replace(b'   wait(last_cnt==seq);idle();',b'   wait(last_cnt==seq);idle(); wait(quiet); repeat(3)@(negedge clk);')
    raw=raw.replace(b'   if(camera.ov5640_ddr_w.cnt',b'   wait(quiet); if(rec[1:0]==1 || rec[257:256]==1)$fatal(1,"failed RAW kept background busy");\n   if(camera.ov5640_ddr_w.cnt')
    raw=raw.replace(b'  $display("PASS tag BRESP error',b'  wait(quiet); if(success_bg!=6 || rec[257:256]!=0)$fatal(1,"failed RAW tag B published thumbnail");\n  $display("PASS tag BRESP error')
    raw=raw.replace(b'  stall_b=0;check_frame',b'  if(success_bg!=9 || rec[1:0]!=1)$fatal(1,"thumbnail published before delayed RAW tag B");\n  stall_b=0;check_frame')
    raw=raw.replace(b'  $finish;',b'''   wait(quiet); repeat(8)@(negedge clk);
   if(success_bg!=10)$fatal(1,"missing real RAW/background successes %0d",success_bg);
   // Deposit only initial counter state to reach wrap without 2^32 frames.
   camera.ov5640_ddr_w_ctrl.last_cnt=32'hffffffff;
   camera.ov5640_ddr_w_ctrl.frame_cnt=32'hffffffff;
   camera.bg_sequence_q=32'hffffffff;
   send_frame('h3800,PIXELS);check_frame('h3800,BANK0,0);
   repeat(8)@(negedge clk);
   if(success_bg!=11 || raw_flush_pulses!=11 || baw!=bb || !quiet || q)$fatal(1,"chain final ledger");
    $display("EXTRA_RAW_CHAIN_PASS successes=%0d background_AW=%0d B=%0d tags=%0d RAW_AW=%0d RAW_B=%0d wrap_counter=%h successful_flush_exports=%0d",success_bg,baw,bb,btag,aw_count,b_count,last_cnt,raw_flush_pulses);
    if(aligned_publications!=11 || aligned_sofs<11 || aligned_faults==0)$fatal(1,"missing actual-chain tap events");
    $display("EXTRA_TAP_PHASE_PASS edges=%0d sofs=%0d publications=%0d fault_cycles=%0d latency=1",tap_edges,aligned_sofs,aligned_publications,aligned_faults);
   $finish;''')
    (ART/'raw_chain_tb.sv').write_bytes(raw)
    full=raw.replace(b'module tb_frame_recovery;',b'module tb_full_raw_chain;')
    full=full.replace(b'wire ts,tv,tbad,tp;',b'wire [15:0] raw_available; wire ts,tv,tbad,tp;')
    full=full.replace(b'.bg_pixel(tpx),',b'.bg_pixel(tpx),.axi_data_available(raw_available),')
    full=full.replace(b'.WD_LIMIT(64)',b'.WD_LIMIT(64),.WAIT_FOR_DATA(1)')
    full=full.replace(b'.data_in(data),',b'.data_in(data),.data_in_available(raw_available),')
    full=full.replace(b'localparam WORDS=64;',b'localparam WORDS=38400;')
    full=full.replace(b"BANK1=32'h20000",b"BANK1=32'h100000")
    full=full.replace(b'mem[0:196607]',b'mem[0:2097151]')
    full=full.replace(b'.WIDTH(32),.HEIGHT(16)',b'.WIDTH(640),.HEIGHT(480)')
    full=full.replace(b'boff%32\'h40000==256',b'boff%32\'h40000==153600')
    full=full.replace(b'+257]',b'+153601]').replace(b'+256]',b'+153600]')
    full=full.replace(b'i<128;',b'i<76800;')
    full=full.replace(b'(i/16)*64+(i%16)*2',b'(i/320)*1280+(i%320)*2')
    full=full.replace(b'bm[bank*262144+i]',b'bm[bank*262144+(i/128)*256+(i%128)]')
    full=full.replace(b'pixels=128',b'pixels=76800')
    begin=full.index(b'  integer a,t,s;') if b'  integer a,t,s;' in full else full.index(b' integer a,t,s;')
    full=full[:begin]+b''' integer a,t,s,bg_before;
 initial begin
  for(j=0;j<2097152;j=j+1)mem[j]=8'hcc;
  repeat(6)@(negedge clk);rst=0;idle();
  send_frame('h1000,PIXELS);check_frame('h1000,BANK0,1);
  send_frame('h2000,PIXELS);check_frame('h2000,BANK1,2);
  a=abort_count;t=tag_count;s=last_cnt;bg_before=success_bg;tag_error=1;
  send_frame('h3000,PIXELS);wait(abort_count==a+1);idle();wait(quiet);tag_error=0;
  if(last_cnt!=s || success_bg!=bg_before || req!=0 || rec[1:0]!=0 || rec[128+:32]!=3 || btag!=2)
   $fatal(1,"full RAW failed tag B published thumbnail");
  $display("EXTRA_FULL_RAW_FAILED_TAG_PASS counter=%h invalid_guard=%h predicted_retry_sequence=%0d",last_cnt,rec[31:0],rec[128+:32]);
  send_frame('h4000,PIXELS);check_frame('h4000,BANK0,3);
  camera.ov5640_ddr_w_ctrl.last_cnt=32'hffffffff;
  camera.ov5640_ddr_w_ctrl.frame_cnt=32'hffffffff;
  camera.bg_sequence_q=32'hffffffff;
  send_frame('h5000,PIXELS);check_frame('h5000,BANK1,0);
  repeat(8)@(negedge clk);
  if(success_bg!=4 || raw_flush_pulses!=4 || baw!=bb || !quiet || q || aw_count!=b_count)
   $fatal(1,"full RAW chain final ledger");
   $display("EXTRA_FULL_RAW_CHAIN_PASS successes=%0d failed_tag=1 background_AW=%0d B=%0d tags=%0d RAW_AW=%0d RAW_B=%0d wrap_counter=%h successful_flush_exports=%0d",success_bg,baw,bb,btag,aw_count,b_count,last_cnt,raw_flush_pulses);
   if(aligned_publications!=4 || aligned_sofs!=5 || aligned_faults==0)$fatal(1,"missing full-chain tap events");
   $display("EXTRA_FULL_TAP_PHASE_PASS edges=%0d sofs=%0d publications=%0d fault_cycles=%0d latency=1",tap_edges,aligned_sofs,aligned_publications,aligned_faults);
  $finish;
 end
 initial begin #30000000;$fatal(1,"full RAW chain timeout");end
endmodule
'''
    (ART/'full_raw_chain_tb.sv').write_bytes(full)
    sources=[SRC/'axi_dma/axi_dma_write.v',SRC/'axi_dma/stream_pipe.v',*list((SRC/'ov5640/ov5640_ddr').glob('*.v')),
             ROOT.parent/'sim/dma_timeout_repro/fifo_models.sv', SRC/'delivery/background_producer.v',SRC/'delivery/background_six.v']
    run([BIN/'vlog.exe','-work',lib,'-sv',*sources,ART/'raw_chain_tb.sv',ART/'full_raw_chain_tb.sv',ROOT/'background_extra_fault_tb.sv'], 'compile.log')
    logs=[]
    def sim(top,name,marker,extra=()):
        logs.append(run([BIN/'vsim.exe','-c','-quiet','-onfinish','exit','-lib',lib,top,*extra,
                         '-do','onerror {quit -code 2}; run -all; quit -code 0'],name,marker))
    sim('tb_frame_recovery','raw_chain.log','EXTRA_RAW_CHAIN_PASS')
    sim('tb_full_raw_chain','full_raw_chain.log','EXTRA_FULL_RAW_CHAIN_PASS')
    for case in range(8): sim('background_extra_fault_tb',f'fault_{case}.log','EXTRA_FAULT_PASS',[f'-gCASE={case}'])
    sim('background_extra_fifo_tb','fifo.log','EXTRA_FIFO_PASS')
    run([BIN/'vlog.exe','-work',lib,ROOT/'sim_six_batch/vendor_endpoint_stubs.v',ROOT/'sim_six_background/pcie_fifo_modelsim.v'], 'pcie_compile.log')
    run([BIN/'vlog.exe','-work',lib,'-sv',ROOT/'background_extra_memory_tb.sv'], 'memory_compile.log')
    sim('background_extra_memory_tb','memory.log','EXTRA_MEMORY_PASS')
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    if before!=after: raise RuntimeError('Protected file content changed during run')
    receipt={'simulation_executions':12,'scenario_results':45,'protected_file_hashes_unchanged':len(before),'production_files_written':0,
             'raw_chain_success_frames':11,'raw_abort_cases':7,'full_raw_chain_success_frames':4,
             'full_raw_failed_tag_B':1,'fault_cases':8,'fifo_cases':2,
             'full_size_camera_bank_reads':12,'read_bytes_each':153616,
             'counter_initialization':'simulation-only deposit ffffffff into real controller counters and pulse history',
             'pcie_model':'existing normalized ModelSim copy, vendor endpoint stubs; production read state machine',
             'protected_sha256':before,
             'simulation_pcie_copy_sha256':hashlib.sha256((ROOT/'sim_six_background/pcie_fifo_modelsim.v').read_bytes()).hexdigest(),
             'pass_lines':[line for text in logs for line in text.splitlines() if 'PASS' in line or 'EXTRA_RAW_PUBLICATION' in line]}
    (ART/'receipt.json').write_text(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
