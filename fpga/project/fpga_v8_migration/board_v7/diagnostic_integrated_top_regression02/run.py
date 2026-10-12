"""Actual build02 full-top ModelSim regression; isolated byte copies only."""
from pathlib import Path
import hashlib, json, os, re, subprocess, gzip, shutil, importlib.util

P=Path(__file__).resolve().parent
B=P.parent/'source_diagnostics_timing_build_02'
O=P.parent/'source_diagnostics_top_candidate'
R=P.parent/'diagnostic_sync_top_regression01'
F=P.parents[1]/'whole_candidate_v7_route_01'
E=P.parent/'physical_subagent_evidence_01/fixed_06/physical_exact_09/input_hashes.json'
SIM=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(n,v): (P/n).write_text(json.dumps(v,indent=2),encoding='utf8')
def load_module(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
order=load_module('integrated_order',O/'sim_order.py')
old=load_module('prior_monitor',R/'run.py')
def clean(b): return re.sub(rb'/\*.*?\*/|//[^\r\n]*|\(\*.*?\*\)',b'',b,flags=re.S)
def outputs(p):
    b=clean(p.read_bytes()).split(b');',1)[0]
    names=[]
    for m in re.finditer(rb'\b(output|inout)\b(.*?)(?=\b(?:input|output|inout)\b|$)',b,re.S):
        d=re.sub(rb'\[[^\]]*\]|\b(?:wire|reg|signed)\b',b'',m[2])
        names.extend(x.decode() for x in re.findall(rb'\b[A-Za-z_]\w*\b',d))
    return names
def protected():
    roots=[B,O,F,P.parent/'source_diagnostics_route_02',E.parent]
    files=set()
    for root in roots:
        for f in root.rglob('*'):
            if f.is_file() and f.suffix.lower() in {'.v','.sv','.vh','.vp','.py','.pds','.fdc','.sdc','.json','.f','.do','.md'} and not any(x in f.parts for x in ['work','vendor','__pycache__']): files.add(f)
    files.update(f for f in (O/'vendor').rglob('*') if f.is_file())
    return {str(f):sha(f) for f in sorted(files)}
def prepare():
    save('frozen_before.json',protected())
    exact=json.loads(E.read_bytes());proof=[]
    for src,key in [(O/'v7_sdt_top.v','rtl/v7_sdt_top.v'),(O/'v7_sdt_camera.v','rtl/v7_sdt_camera.v'),(O/'v7_sdt_binding.v','rtl/v7_sdt_binding.v'),(F/'inputs/source/ov5640/ov5640_reg.v','inputs/source/ov5640/ov5640_reg.v'),(F/'rtl/fpga_v8_capture_control_axil_arm_v2.v','rtl/fpga_v8_capture_control_axil_arm_v2.v'),(F/'rtl/fpga_v8_capture_lease_tc04.v','rtl/fpga_v8_capture_lease_tc04.v')]:
        assert sha(src)==exact[key.replace('/','\\')],src
        proof.append(dict(source=str(src),sha256=sha(src),exact09_key=key))
    save('golden_exact09_provenance.json',dict(manifest=str(E),sha256=sha(E),files=proof))
    originals=[Path(s.strip().strip('"')) for s in (O/'compile.f').read_text().splitlines() if s.strip()]
    registered=json.loads((B/'manifest.json').read_text())['registered_sources']
    byname={Path(s).name:B/s for s in registered}
    contracts={}
    for variant in ['baseline','integrated']:
        D=P/variant;D.mkdir(exist_ok=True)
        files=[];rawfiles={};contract=[]
        for original in originals:
            source=original
            if variant=='integrated' and original.suffix!='.vp':
                if original.name=='fpga_v8_capture_lease_tc04.v': source=B/'rtl/fpga_v8_capture_lease_prefix.v'
                elif original.is_relative_to(F/'inputs'): source=B/original.relative_to(F)
                else:
                    assert original.name in byname,original
                    source=byname[original.name]
            # Preserve the original official simulation-library .vp models.
            if original.suffix=='.vp':
                source=(B/'inputs'/original.relative_to(F/'inputs')) if variant=='integrated' else original
            if source.is_relative_to(B): rel=source.relative_to(B)
            elif source.is_relative_to(F): rel=source.relative_to(F)
            else: rel=Path('rtl')/source.name
            target=D/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            # The baseline original compile list already points at simulation views.
            # Integrated views are regenerated from the actual registered build02 RTL.
            view=target
            if variant=='integrated' and source.name in [x.name for x in (O/'sim_views').glob('*.v')]:
                view=order.normalize(target,D/'sim_views'/source.name)
            files.append(view);rawfiles[source.name]=target
            contract.append(dict(original=str(original),source=str(source),source_sha256=sha(source),raw_copy=str(target),compiled=str(view),compiled_sha256=sha(view)))
        # Include files must come from the matching frozen source tree.
        source_root=B if variant=='integrated' else F
        include_copies=[]
        pending=[(Path(r['source']),Path(r['raw_copy'])) for r in contract]
        visited=set()
        while pending:
            src,dst=pending.pop()
            if src in visited:continue
            visited.add(src)
            for inc in re.findall(rb'`include\s+"([^"]+)"',src.read_bytes()):
                dep=src.parent/inc.decode('ascii')
                if not dep.exists():dep=source_root/'inputs/source/npu'/inc.decode('ascii')
                assert dep.exists(),('missing frozen include',src,inc)
                target=dst.parent/inc.decode('ascii')
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(dep.read_bytes())
                include_copies.append(dict(source=str(dep),copy=str(target),sha256=sha(dep)))
                pending.append((dep,target))
        save(variant+'/include_copies.json',include_copies)
        for src in (source_root/'inputs/source/npu').rglob('*.vh'):
            dst=D/src.relative_to(source_root);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
        for src in (source_root/'inputs/source/npu').glob('*.v'):
            dst=D/src.relative_to(source_root);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
        modules={}
        for f in files:
            for n in re.findall(rb'\bmodule\s+(\w+)',clean(f.read_bytes())):
                assert n.decode() not in modules,('duplicate',n,f)
                modules[n.decode()]=str(f)
        save(variant+'/registered_modules.json',modules)
        (D/'compile.f').write_text('\n'.join('"'+f.as_posix()+'"' for f in files))
        (D/'tb_sdt.sv').write_bytes((O/'tb_sdt.sv').read_bytes().replace(b'`include "scenario.vh"',b'`include "scenario.vh"\n`include "compare_monitor.vh"\n`include "integrated_monitor.vh"'))
        scenario=(O/'scenario.vh').read_bytes();assert scenario.count(b'$finish;')==1
        (D/'scenario.vh').write_bytes(scenario.replace(b'$finish;',(R/'reset_extension.vh').read_bytes()+b'\n$finish;'))
        (D/'compare_monitor.vh').write_text(old.make_monitor(),encoding='ascii')
        contracts[variant]=contract
        (D/'run.do').write_text('onerror {quit -code 1}\nset f [open hierarchy.txt w]\nforeach i [find instances -recursive /*] {puts $f $i}\nclose $f\nrun -all\nquit -f\n')
    save('replacement_contract.json',contracts)
    make_monitor()

def make_monitor():
    groups={}
    top=P/'baseline/rtl/v7_sdt_top.v'
    # Baseline original simulation view has all module-level declarations first.
    names=re.findall(rb'\b(?:wire|reg)\s*(?:\[[^\]]*\]\s*)?(\w+)\s*;',clean(top.read_bytes()))
    topnames=sorted(set(n.decode() for n in names if re.match(rb'(?:pcie_axi_|ddr_axi_|cam\d?_|ovreg_|diag_|v8_|rfg_|prep_|cmos|sfp|led)',n)))
    topnames=sorted(set(topnames+outputs(top)))
    for i in range(0,len(topnames),32): groups['top_'+str(i//32)]=['dut.'+x for x in topnames[i:i+32]]
    for inst in ['ov5640_top','cam2_ov5640_top','cam3_ov5640_top','cam4_ov5640_top']:
        groups[inst]=['dut.'+inst+'.'+n for n in outputs(O/'v7_sdt_camera.v')]
        groups[inst+'_reg']=['dut.'+inst+'.ov5640_reg.'+n for n in outputs(F/'inputs/source/ov5640/ov5640_reg.v')]
        groups[inst+'_counter']=['dut.'+inst+'.u_motion_tap.'+n for n in ['source_sequence','active_sequence','publish_sequence','overflow_count','short_frame_count']]
    for inst,fn in [('u_v8_capture_lease','fpga_v8_capture_lease_tc04.v'),('u_v8_capture_control','fpga_v8_capture_control_axil_arm_v2.v'),('u_v8_cooperative_core','fpga_v8_cooperative_core_rfg01.v'),('cam5_ov5640_ddr','fpga_v8_capture_ov5640_ddr_tc04.v'),('cam6_ov5640_ddr','ov5640_ddr_tc04.v')]:
        groups[inst]=['dut.'+inst+'.'+n for n in outputs(F/'rtl'/fn)]
    groups['lease_state']=['dut.u_v8_capture_lease.'+n for n in ['state[0]','state[1]','sequence[0]','sequence[1]','generation','next_sequence','writing_bank','coop_offer_bank','host_offer_bank','coop_rr','host_rr','coop_claimed[0]','coop_claimed[1]','coop_released[0]','coop_released[1]','host_claimed[0]','host_claimed[1]','host_released[0]','host_released[1]']]
    groups['lease_state']=[n.replace('.sequence[','.\\sequence [') for n in groups['lease_state']]
    save('trace_fields.json',groups)
    text=['integer integrated_fd, integrated_host=0, integrated_cam=0, integrated_neg=0, integrated_ctrl=0;','reg integrated_started=0;','initial integrated_fd=$fopen("integrated.trace","w");']
    for i,fields in enumerate(groups.values()):
        expr='{'+','.join(fields)+'}'
        text += [f'localparam INTEGRATED_BITS_{i}=$bits({expr});',f'reg [INTEGRATED_BITS_{i}-1:0] integrated_last_{i};']
    text+=['task integrated_sample(input integer kind);','begin']
    for i,fields in enumerate(groups.values()):
        expr='{'+','.join(fields)+'}'
        text += [f'if(!integrated_started || {expr} !== integrated_last_{i}) $fdisplay(integrated_fd,"%0t %0d {i} %h",$time,kind,{expr});',f'integrated_last_{i}={expr};']
    text+=['integrated_started=1;','end','endtask',
        'always @(posedge clk) begin #0.002; if($time>=20) begin integrated_host++;integrated_sample(0);end end',
        'always @(posedge camclk) begin #0.003; if($time>=20) begin integrated_cam++;integrated_sample(1);end end',
        'always @(negedge camclk) begin #0.004; if($time>=20) begin integrated_neg++;integrated_sample(2);end end',
        'always @(posedge ctrlclk) begin #0.005; if($time>=20) begin integrated_ctrl++;integrated_sample(3);end end',
        'final begin $fdisplay(integrated_fd,"SAMPLES %0d %0d %0d %0d",integrated_host,integrated_cam,integrated_neg,integrated_ctrl);$fclose(integrated_fd);$display("INTEGRATED_SAMPLES host=%0d cam=%0d neg=%0d ctrl=%0d",integrated_host,integrated_cam,integrated_neg,integrated_ctrl);end',
        'initial begin #20; '+''.join(f'if($size(dut.{inst}.u_motion_tap.u_detector.history)!=19200 || $bits(dut.{inst}.u_motion_tap.u_detector.history[0])!=8) $fatal(1,"motion history missing {inst}");' for inst in ['ov5640_top','cam2_ov5640_top','cam3_ov5640_top','cam4_ov5640_top'])+'$display("MOTION_RTL_HISTORY_PRESENT cameras=4 width=8 depth=19200 bitplanes=32");end']
    for v in ['baseline','integrated']: (P/v/'integrated_monitor.vh').write_text('\n'.join(text),encoding='ascii')

def tool(exe,args,D,log):
    r=subprocess.run([str(SIM/exe),*map(str,args)],cwd=D,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (D/log).write_bytes(r.stdout);t=r.stdout.decode('utf8','replace');print(D.name,log,t[-2200:],flush=True)
    assert r.returncode==0 and not re.search(r'\*\* (?:Error|Fatal)',t),log
    return t
def run():
    for v in ['baseline','integrated']:
        D=P/v
        tool('vmap.exe',['-c'],D,'vmap.log');tool('vmap.exe',['vendor',O/'vendor'],D,'vendor_binding.log')
        if not (D/'work').exists():tool('vlib.exe',['work'],D,'vlib.log')
        tool('vlog.exe',['+incdir+'+str(D/'inputs/source/npu'),'-f','compile.f'],D,'compile.log')
        tool('vlog.exe',['-sv','+incdir+'+str(D),'tb_sdt.sv'],D,'tb_compile.log')
        t=tool('vsim.exe',['-c','-vopt','-voptargs=+acc','-L','vendor','work.tb_sdt','-do','run.do'],D,'simulation.log')
        assert 'SDT_ALL_PASS checks=14540' in t and 'TOP_FOUR_RESET_PASS' in t and 'FAIL' not in t
    seal()
def seal():
    results={}
    for v in ['baseline','integrated']:
        D=P/v;t=(D/'simulation.log').read_text(errors='replace')
        results[v]=dict(markers=[l for l in t.splitlines() if 'PASS' in l or 'TOP_COMPARE_SAMPLES' in l or 'INTEGRATED_SAMPLES' in l or 'MOTION_RTL' in l],warnings=len(re.findall(r'\*\* Warning',t)))
    for name in ['comparison.trace','integrated.trace']:
        a=P/'baseline'/name;b=P/'integrated'/name
        assert a.stat().st_size==b.stat().st_size,('trace sizes',name)
        with a.open('rb') as af,b.open('rb') as bf:
            for count,x in enumerate(af,1):
                y=bf.readline();assert x==y,('trace mismatch',name,count,x[:300],y[:300])
            assert not bf.read()
        results[name]=dict(equal=True,records=count,bytes=a.stat().st_size,sha256=sha(a),start_ns=20)
        for f in [a,b]:
            with f.open('rb') as src,gzip.open(str(f)+'.gz','wb') as dst:shutil.copyfileobj(src,dst)
            f.unlink()
    h=(P/'integrated/hierarchy.txt').read_text()
    primitives=[l for l in h.splitlines() if 'source_diagnostics' in l and re.search(r'_ff\d \(GTP_DFF_(?:CE|PE)\)$',l)]
    assert sum('(GTP_DFF_CE)' in l for l in primitives)==28
    assert sum('(GTP_DFF_PE)' in l for l in primitives)==32
    required=['ov5640_top (v7_sdt_camera)','cam2_ov5640_top (v7_sdt_camera)','cam3_ov5640_top (v7_sdt_camera)','cam4_ov5640_top (v7_sdt_camera)','cam5_ov5640_ddr (fpga_v8_capture_ov5640_ddr_tc04)','cam6_ov5640_ddr (ov5640_ddr_tc04)','u_v8_capture_lease (fpga_v8_capture_lease_prefix)','u_v8_capture_control (fpga_v8_capture_control_axil_arm_v2)']
    for n in required: assert '/tb_sdt/dut/'+n in h,n
    motion=[l for l in h.splitlines() if l.endswith('/u_motion_tap/u_detector (block_motion_detector_tc05)')];assert len(motion)==4
    save('actual_parent_bindings.json',dict(required=required,CE_count=28,PE_count=32,primitive_instances=primitives,motion_detector_instances=motion,motion_history_bitplanes=32,motion_physical_RAM_instances_verified=False))
    before=json.loads((P/'frozen_before.json').read_text());after={f:sha(f) for f in before};save('frozen_after.json',after)
    assert before==after
    results['protected_files_unchanged']=len(before);results['pds_remote_device_used']=False
    save('results.json',results)
    print('INTEGRATED_FULL_TOP_PASS',json.dumps(results,indent=2),flush=True)
if __name__=='__main__':
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='seal':seal()
    else: prepare();run()
