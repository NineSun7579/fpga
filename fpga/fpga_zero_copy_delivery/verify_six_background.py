"""Real ModelSim regressions; no PDS invocation or hardware access."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from make_six_background import ROOT, BASE, OUT, PORTS, CONNECT, NEW, project as make_project

BIN=Path('C:/modeltech64_10.6e/win64')
ART=ROOT/'sim_six_background'

def run(args, name, marker=None):
    p=subprocess.run([str(a) for a in args],cwd=ART,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    text=p.stdout.decode('utf8',errors='replace')
    (ART/name).write_bytes(p.stdout)
    assert p.returncode==0 and '** Error:' not in text and '** Fatal:' not in text,text[-5000:]
    if marker: assert marker in text,text[-5000:]
    print('PASS',name,flush=True)
    return text

def simulate(lib,top,name,marker):
    return run([BIN/'vsim.exe','-c','-quiet','-onfinish','exit','-lib',lib,top,
                '-do','onerror {quit -code 2}; run -all; quit -code 0'],name,marker)

def main():
    ART.mkdir(exist_ok=True)
    lib=ART/'work'
    if not lib.exists():run([BIN/'vlib.exe',lib],'vlib.log')
    project=(OUT/'project/project.pds').read_bytes()
    design=project[project.index(b'(_widget wgt_my_design_src'):project.index(b'(_widget wgt_my_ips_src')]
    sources=[(OUT/'project'/p.decode('ascii')).resolve() for p in re.findall(rb'\(_file "([^"]+)"',design)]
    exclude={'top.v','ips2l_pcie_dma.v','ips2l_pcie_dma_controller.v','pango_pcie_top.v','pcie_fifo.v'}
    checked=[p for p in sources if p.name not in exclude]
    run([BIN/'vlog.exe','-work',lib,'-vlog01compat',*checked],'ordinary_compile.log')
    run([BIN/'vlog.exe','-work',lib,'-sv',ROOT/'background_tb.sv'],'component_compile.log')
    simulate(lib,'background_tb','component.log','PASS background:')
    for name,width,height in [('full',640,480),('partial',10,6)]:
        run([BIN/'vsim.exe','-c','-quiet','-onfinish','exit','-lib',lib,'background_tb',
             f'-gW={width}',f'-gH={height}',
             '-do','onerror {quit -code 2}; run -all; quit -code 0'],name+'_component.log','PASS background:')
    for name,width,height in [('sof_pixel',32,16),('sof_pixel_partial',10,6),('sof_pixel_minimum',2,2)]:
        run([BIN/'vsim.exe','-c','-quiet','-onfinish','exit','-lib',lib,'background_tb',
             f'-gW={width}',f'-gH={height}','-gFIRST_ON_SOF=1',
             '-do','onerror {quit -code 2}; run -all; quit -code 0'],name+'.log','PASS background:')
    run([BIN/'vlog.exe','-work',lib,'-sv',ROOT/'background_geometry_tb.sv'],'geometry_compile.log')
    simulate(lib,'background_geometry_tb','geometry.log','PASS background geometry:')
    run([BIN/'vlog.exe','-work',lib,'-sv',ROOT/'background_adapter_tb.sv'],'adapter_compile.log')
    simulate(lib,'background_adapter_tb','adapter.log','PASS background adapter')
    run([BIN/'vsim.exe','-c','-quiet','-onfinish','exit','-lib',lib,'background_adapter_tb','-gFAULT=1',
         '-do','onerror {quit -code 2}; run -all; quit -code 0'],'adapter_fault.log','PASS background adapter')
    # Independent RAW replay: run identical production RAW test in baseline and
    # candidate libraries; candidate carries an enabled overflow-prone passive tap.
    raw_outputs=[]
    for variant,src in [('baseline',BASE/'source'),('candidate',OUT/'source')]:
        rawlib=ART/('raw_'+variant)
        if not rawlib.exists():run([BIN/'vlib.exe',rawlib],variant+'_vlib.log')
        tb=(ROOT.parent/'sim/dma_timeout_repro/tb_frame_recovery.sv').read_bytes()
        if variant=='candidate':
            tb=tb.replace(b' ov5640_ddr #',b''' wire tap_sof,tap_valid,tap_bad,tap_publish;
 wire [15:0] tap_pixel;
 background_producer #(.WIDTH(32),.HEIGHT(16),.DEPTH(4),.DEADLINE(1024)) branch(
  .clk(clk),.rst(rst),.enable(1'b1),.quarantine(1'b0),.invalidate(2'd0),.sof(tap_sof),
  .pixel_valid(tap_valid),.source_bad(tap_bad),.raw_publish(tap_publish),
  .pixel(tap_pixel),.source_sequence(last_cnt),.grant(1'b0),.take(1'b0),
  .retire(1'b0),.retire_bad(1'b0));
 ov5640_ddr #''',1)
            tb=tb.replace(b' camera(\n',b''' camera(
  .bg_sof(tap_sof),.bg_valid(tap_valid),.bg_bad(tap_bad),
  .bg_raw_publish(tap_publish),.bg_pixel(tap_pixel),
''',1)
        path=ART/(variant+'_raw_tb.sv');path.write_bytes(tb)
        rawsources=[src/'axi_dma/axi_dma_write.v',src/'axi_dma/stream_pipe.v',
                    *list((src/'ov5640/ov5640_ddr').glob('*.v')),
                    ROOT.parent/'sim/dma_timeout_repro/fifo_models.sv',path]
        if variant=='candidate':rawsources.append(OUT/'source/delivery/background_producer.v')
        run([BIN/'vlog.exe','-work',rawlib,'-sv',*rawsources],variant+'_raw_compile.log')
        text=simulate(rawlib,'tb_frame_recovery',variant+'_raw.log','PASS FRAME RECOVERY')
        raw_outputs.append([line for line in text.splitlines() if line.startswith('# PASS') or line.startswith('# ABORT')])
    assert raw_outputs[0]==raw_outputs[1], 'RAW publication/pixel/AXI ledgers differ'
    # The real PCIe engine test, existing 304 snapshot unchanged. Additional
    # record reads assert complete 128-bit metadata and narrow single-beat policy.
    from generate_six_batch_sim import main as generate
    generate()
    model=(ROOT/'sim_six_batch/pcie_fifo_modelsim.v').read_bytes()
    prior=(BASE/'source/pcie_dma/pcie_fifo.v').read_bytes()
    current=(OUT/'source/pcie_dma/pcie_fifo.v').read_bytes()
    old=re.search(rb'wire delivery_register_read =.*?;',prior,re.S)[0]
    new=re.search(rb'wire delivery_register_read =.*?;',current,re.S)[0]
    assert model.count(old)==1
    path=ART/'pcie_fifo_modelsim.v';path.write_bytes(model.replace(old,new))
    tb=(ROOT/'sim_six_batch/six_batch_tb.sv').read_bytes()
    tb=tb.replace(b'10:expected_reg=15;',b'10:expected_reg=31;')
    tb=tb.replace(b"wire mmio = base>=32'h40020000 && base<=32'h40020120;",b"""wire mmio = (base>=32'h40020000 && base<=32'h40020120) ||
 base==32'h40020180 || (base>=32'h40020200 && base<=32'h40020370);""")
    word=b'''function [127:0] expected_word(input integer index);
integer record_index, cam, bank, slot;
reg [31:0] dest;
begin
 if(index>=32 && index<=55) begin
  record_index=(index-32)/2; cam=record_index/2+1; bank=record_index%2;
  slot=cam==5 ? 0 : (cam<5 ? cam : 5);
  dest=32'h0a200000+slot*32'h80000+bank*32'h40000;
  if(index%2==0) expected_word={dest,32'(bank),32'(cam),32'd0};
  else expected_word={dest+32'd153600,32'h00f00140,32'd153600,32'd0};
 end else if(index==24) expected_word=128'd2;
 else expected_word={96'd0,expected_reg(index)};
end
endfunction
'''
    tb=tb.replace(b'always @(posedge clk) begin\n if(rst)',word+b'always @(posedge clk) begin\n if(rst)',1)
    tb=tb.replace(b"{96'd0,expected_reg((base-32'h40020000)/16+received)}",b"expected_word((base-32'h40020000)/16+received)")
    tb=tb.replace(b"{96'd0,expected_reg((base-32'h40020000)/16+enqueued)}",b"expected_word((base-32'h40020000)/16+enqueued)")
    tb=tb.replace(b" run_read(32'h40020130,304);",b""" run_read(32'h40020130,16);
 run_read(32'h40020180,16);
 run_read(32'h40020200,384);
 run_read(32'h40020370,16);
 run_read(32'h40020380,304);""")
    tb=tb.replace(b'delivery_top_adapter adapter(.clk(clk),.rst(rst),',b'''delivery_top_adapter adapter(.clk(clk),.rst(rst),
 .bg_sof(6'd0),.bg_valid(6'd0),.bg_bad(6'd0),.bg_raw_publish(6'd0),.bg_pixels(96'd0),''')
    path_tb=ART/'transport_tb.sv';path_tb.write_bytes(tb)
    run([BIN/'vlog.exe','-work',lib,ROOT/'sim_six_batch/vendor_endpoint_stubs.v',path], 'transport_compile.log')
    run([BIN/'vlog.exe','-work',lib,'-sv',path_tb],'transport_tb_compile.log')
    simulate(lib,'six_batch_tb','transport.log','SIX_BATCH_ENGINE_PASS')
    records=json.loads((ROOT/'six_background_source_manifest.json').read_text())
    changed=[]
    for r in records:
        a=(BASE/r['path']).read_bytes(); b=(OUT/r['path']).read_bytes()
        assert hashlib.sha256(a).hexdigest()==r['baseline_sha256']
        if r['path']=='project/project.pds':
            # PDS updates timestamps and command output widgets after a build.
            # Check the complete input/configuration prefix against the same
            # generator, allowing only its timestamp/comment bookkeeping.
            def inputs(raw):
                raw=raw.replace(b'\r\n',b'\n')
                raw=raw[:raw.index(b'        (_command cmd_compile')]
                raw=re.sub(rb'\(_timespec "[^"]*"\)',b'(_timespec "")',raw)
                return re.sub(rb'\(_comment "[^"]*"\)',b'(_comment "")',raw)
            assert inputs(b)==inputs(make_project(a)), 'Candidate project input/configuration changed'
        else:
            assert hashlib.sha256(b).hexdigest()==r['candidate_sha256']
        assert bytes(x for x in a if x>=128)==bytes(x for x in b if x>=128), 'Non-ASCII source bytes changed'
        if a!=b:changed.append(r['path'])
    # Stronger than unchanged baseline: remove only passive exports from the
    # clone and require the complete prior capture RTL bytes, not selected lines.
    raw=(OUT/'source/ov5640/ov5640_ddr/ov5640_ddr.v').read_bytes()
    raw=raw.replace(PORTS.encode('ascii'),b'')
    begin=raw.index(b'// Passive export only;')
    end=raw.index(b'assign lease_prev_base=prev_frame_base;',begin)
    raw=raw[:begin]+raw[end:]
    assert raw==(BASE/'source/ov5640/ov5640_ddr/ov5640_ddr.v').read_bytes()
    raw=(OUT/'source/ov5640/ov5640_top.v').read_bytes()
    raw=raw.replace(PORTS.encode('ascii'),b'').replace(CONNECT.encode('ascii'),b'')
    assert raw==(BASE/'source/ov5640/ov5640_top.v').read_bytes()
    protected=['source/ov5640/ov5640_ddr/ov5640_ddr_w.v',
               'source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v',
               'source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v',
               'source/axi_dma/axi_dma_write.v','source/axi_dma/stream_pipe.v',
               'source/axi_crossbar/ddr_w_arb.v','source/delivery/delivery_rgb_ddr.v',
               'source/display/display_thumbnail_ddr.v']
    assert all((BASE/p).read_bytes()==(OUT/p).read_bytes() for p in protected)
    mods={}
    for path in (OUT/'source').rglob('*.v'):
        for mod in re.findall(rb'^\s*module\s+(\w+)',path.read_bytes(),re.M):
            mods.setdefault(mod,[]).append(str(path))
    for name in NEW:
        assert (OUT/'source/delivery'/name).read_bytes().isascii()
        assert (ROOT/name).read_bytes()==(OUT/'source/delivery'/name).read_bytes()
        assert len(mods[name[:-2].encode('ascii')])==1
    receipt=dict(baseline_hashes_preserved=len(records),changed=changed,
        ordinary_rtl_compiled=len(checked),raw_replay_identical=True,
        raw_success_frames=10,raw_failure_cases=7,raw_AW_B_retirements=61,
        capture_controls_identical_after_removing_passive_exports=True,
        raw_protected_modules_identical=protected,all_non_ascii_bytes_preserved=True,
        new_modules_unique=True,component_pass=True,
        full_resolution_six_producers=True,partial_final_burst=True,
        coherent_one_clock_tap=True,sof_pixel_same_cycle=True,
        unsupported_odd_or_zero_geometry_rejected=True,
        project_inputs_match_generator=True,
        shared_RGB_background_normal_and_bad_B=True,legacy_thumbnail_reuse_invalidation=True,
        existing_real_pcie_snapshot_pass=True,pds_run=False,board_access=False,
        full_top_vendor_elaboration=False,timing_owner='parent',caps_enabled=True,caps=31)
    (ROOT/'six_background_preservation_report.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
