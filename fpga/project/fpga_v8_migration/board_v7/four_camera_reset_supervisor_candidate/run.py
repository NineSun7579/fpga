from pathlib import Path
import hashlib, json, os, subprocess, sys, difflib

HERE=Path(__file__).resolve().parent
REVIEW=HERE.parent/'four_camera_recovery_review'
ROOT=HERE.parents[1]/'whole_candidate_v7_route_01'
REC=HERE.parent/'cdc_boundary_recovery_candidate'
TOOLS=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
VENDOR=Path('C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')

def hashes():
    dirs=[ROOT,REC,REVIEW,HERE.parent/'cdc_boundary_candidate',HERE.parents[2]/'source',HERE.parents[2]/'ipcore']
    result={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for d in dirs for p in d.rglob('*')
            if p.is_file() and p.suffix.lower() in ('.v','.vh','.sv','.md','.py','.pds','.fdc')}
    for p in HERE.parents[2].glob('project*/project.pds'):
        result[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def replace(s,a,b):
    assert a in s,a
    return s.replace(a,b)

def derive(name, edits):
    p=REVIEW/('tb_'+name+'.sv');old=p.read_bytes().decode('ascii');s=old
    for a,b in edits: s=replace(s,a,b)
    (HERE/p.name).write_text(s)
    (HERE/(p.name+'.diff')).write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile=str(p),tofile=p.name)))

# Test-only configuration epoch coincides with clean test setup reset. This is
# NOT proposed production wiring. Runtime injected faults never drive epoch.
def supervisor_instance(fault_input, abort_output, extras='', capture="4'd0", writer="4'd0"):
    return f'''
reg cold_req=0;
always @(negedge clk) cold_req<=!rst;
wire session_fault,supervisor_cold;
four_camera_reset_supervisor #(.CLOCK_LIMIT(10000)) supervisor(
 .clk(clk),.epoch_reset(rst),.cold_request(cold_req),.source_clk({{4{{clk}}}}),
 .i2c_start_en(4'hf),.cam_init_done(4'hf),.ov_rst_n(4'hf),.video_reset(rst),
 .boundary_fault({fault_input}),.capture_abort_req({capture}),.writer_abort({writer}),
 .camera_session_fault(session_fault),.transport_abort({abort_output}),.cold_system_reset(supervisor_cold));
{extras}
'''

def generate():
    top=(ROOT/'rtl/fpga_v8_cooperative_top_v2_rfg01.v').read_bytes()
    binding=(ROOT/'rtl/ov5640_tc03_binding.v').read_bytes()
    start=top[top.index(b'reg [15:0] camera_startup_count'):top.index(b'`ifdef USE_OV5640',top.index(b'reg [15:0] camera_startup_count'))]
    power=binding[binding.index(b'reg [$clog2(CLK_FREQ/1000*7)'):binding.index(b'assign cam_pwdn')]
    extract=(REVIEW/'startup_extract.v').read_bytes()
    assert start in extract and power in extract,'actual startup extraction is stale'
    derive('ledger',[
      ('abort_req=0,','fault_in=0,'),
      ('axi_dma_write_tc04 #', 'wire abort_req;wire [3:0] broadcast_abort;\nassign abort_req=broadcast_abort[0];\n'+supervisor_instance('{3\'d0,fault_in}','broadcast_abort')+'\naxi_dma_write_tc04 #'),
      ('abort_req=0;','fault_in=0;'),('abort_req=1;','fault_in=1;'),
      ('rst=0;repeat(3) tick();','rst=0;repeat(40) tick();')])
    derive('shared',[
      ('cmd=0,fault=0;','cmd=0,fault_in=0;\nwire [3:0] fault;'+supervisor_instance('fault_in','fault')),
      ('fault=0;','fault_in=0;'),('fault=(which','fault_in=(which'),
      ('rst=0;repeat(10)tick();','rst=0;repeat(40)tick();'),
      ('((which==1||k==0)?1:0)','1'),('((which==0&&k!=0)?1:0)','0'),
      ('integer errors=0','reg [2:0] held_owner;\ninteger errors=0'),
      ('repeat(150)tick();','held_owner=owner;repeat(150)begin tick();check(busy && owner==held_owner,"owner changed before actual vendor completion");end')])
    derive('binding',[
      ('wire fault;','wire fault,local_fault,supervisor_cold;wire [3:0] broadcast_abort;\nassign fault=broadcast_abort[0];'),
      ('wire [1:0] req;', 'wire [1:0] req;'+supervisor_instance("{3'd0,local_fault}",'broadcast_abort',capture="{3'd0,abort_req}",writer="{3'd0,ab}").replace('wire session_fault,supervisor_cold;','wire session_fault;')),
      ('.system_reset(rst)', '.system_reset(supervisor_cold)'),('.boundary_fault(fault)', '.boundary_fault(local_fault)'),
      ('rst=0;repeat(30) tick();','rst=0;repeat(60) tick();')])
    old=(REVIEW/'tb_startup.sv').read_bytes().decode('ascii')
    s=replace(old,'wire [3:0] bad_fault,good_fault;', '''wire [3:0] bad_fault,good_fault;
reg epoch=1,request=0;
wire supervisor_cold,session_fault,admit;wire [3:0] started,scam;
four_camera_reset_supervisor supervisor(.clk(video),.epoch_reset(epoch),.cold_request(request),
 .source_clk(scam),.i2c_start_en({4{cam_rst_n}}),.cam_init_done({4{cam_rst_n}}),.ov_rst_n({4{cam_rst_n}}),
 .video_reset(axi_rst),.boundary_fault(good_fault),.capture_abort_req(4'd0),.writer_abort(4'd0),
 .cold_system_reset(supervisor_cold),.camera_session_fault(session_fault),.admission_enable(admit),.source_started(started));''')
    s=replace(s,'cdc_recovery good(.system_reset(cold)','assign scam[i]=cam;\n  cdc_recovery good(.system_reset(supervisor_cold)')
    s=replace(s,'#1000; axi_rst=0;','#100;epoch=0;request=1;#900; axi_rst=0;')
    s=replace(s,'cold=0; repeat(20) @(negedge video);','cold=0; repeat(100) @(negedge video);\n  if(!admit || session_fault) begin $display("FAIL supervised actual startup");errors++;end')
    start=s.index('  // Opposite ordering:')
    end=s.index('  $finish;',start)
    s=s[:start]+'''  axi_rst=1;repeat(10) @(negedge video);axi_rst=0;repeat(10) @(negedge video);
  if(!session_fault || supervisor_cold || admit) begin $display("FAIL warm reset reauthorized");errors++;end
  $display("SUPERVISED_ACTUAL_STARTUP warm_fault=%b cold=%b errors=%0d",session_fault,supervisor_cold,errors);
'''+s[end:]
    (HERE/'tb_startup.sv').write_text(s)
    (HERE/'tb_startup.sv.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True))))

sources=[ROOT/'rtl/axi_dma_write_tc04.v',ROOT/'inputs/source/axi_dma/stream_pipe.v',
 ROOT/'rtl/fpga_v8_ddr_write_arbiter.v',ROOT/'rtl/fpga_v8_ddr_adapter_tc03.v',
 REC/'cdc_recovery.v',REC/'cdc_order_meta.v',REC/'ddr_recovery.v',REC/'ddr_ctrl_recovery.v',
 ROOT/'rtl/parent_tc04_e7f19e0d9596.v',ROOT/'inputs/source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v',
 REVIEW/'startup_extract.v',HERE/'four_camera_reset_supervisor.v',HERE/'four_camera_supervised_boundary.v']
for name in ('ov5640_cdc_fifo','ov5640_ddr_fifo_DRM','ov5640_ddr_fifo','ddr_fifo16_w','ddr_fifo16_r'):
    d=ROOT/'inputs/ipcore'/name
    sources += [d/(name+'.v'),*sorted((d/'rtl').glob('*.v'))]
sources += [VENDOR/(n+'.v') for n in ('GTP_DRM18K_E1','GTP_DRM36K_E1','GTP_GRS')]

def run(build,exe,args,log):
    with (build/log).open('wb') as f:
        result=subprocess.run([str(TOOLS/exe),*map(str,args)],cwd=build,stdout=f,stderr=subprocess.STDOUT)
    if result.returncode: raise RuntimeError((build/log).read_text(errors='replace')[-8000:])

before=hashes()
(HERE/'protected_before.json').write_text(json.dumps(before,indent=2))
try:
    generate()
    for name in (sys.argv[1:] or ('supervisor','startup','ledger','binding','shared')):
        build=HERE/name;build.mkdir(exist_ok=True)
        if not (build/'work').exists():run(build,'vlib.exe',['work'],'vlib.log')
        run(build,'vlog.exe',['-sv',*sources,HERE/('tb_'+name+'.sv')],'compile.log')
        run(build,'vsim.exe',['-c','-voptargs=+acc','work.tb_'+name,'-do','onerror {quit -code 1}; run -all; quit -code 0'],'simulation.log')
        text=(build/'simulation.log').read_text(errors='replace')
        print('\n'.join(l for l in text.splitlines() if any(t in l for t in ('SUPERVISOR','SUPERVISED_','REVIEW_','FAIL'))),flush=True)
        assert 'errors=0' in text and 'FAIL' not in text,name
finally:
    after=hashes();changed=[p for p in before if before[p]!=after.get(p)]
    (HERE/'protected_result.json').write_text(json.dumps({'files':len(before),'changed':changed},indent=2))
    assert not changed,changed
    print('PROTECTED_UNCHANGED',len(before))
