"""Byte-frozen regression02 actual integrated golden versus boolean-only candidate."""
from pathlib import Path
import hashlib,json,re,subprocess,os,shutil,gzip,difflib,sys
P=Path(__file__).resolve().parent
R=P.parent/'diagnostic_integrated_top_regression02'
C=P.parent/'build01_global_sta_review01/camera_boolean_candidate01'
SIM=Path(os.environ.get('MODELSIM_BIN','C:/modeltech64_10.6e/win64'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()
def save(n,v): (P/n).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf8')
def clean(b): return re.sub(rb'/\*.*?\*/|//[^\r\n]*|\(\*.*?\*\)',b'',b,flags=re.S)
def protected():
    files=set()
    for root in [R,C,P.parent/'source_diagnostics_timing_build_02',P.parent/'diagnostic_sync_register_map02',P.parent/'source_diagnostics_top_candidate']:
        for f in root.rglob('*'):
            if f.is_file() and not any(x in f.parts for x in ['work','__pycache__']) and f.suffix.lower() not in ['.gz','.trace']: files.add(f)
    return {str(f):sha(f) for f in sorted(files)}
def replace(b,a,z):
    assert b.count(a)==1,('replacement cardinality',a[:160],b.count(a))
    return b.replace(a,z)
def normalized(b): return b.replace(b'\r\n',b'\n')
def freeze_check():
    before=json.loads((P/'frozen_before.json').read_text(encoding='utf8'))
    after={f:sha(f) for f in before};save('frozen_after.json',after)
    # The parent session may update this observation-only status report. No RTL,
    # script, project, model, manifest or evidence input has an exception.
    observation=str(P.parent/'source_diagnostics_timing_build_02/STATUS.md')
    changes=[dict(path=f,before=before[f],after=after[f]) for f in before if before[f]!=after[f]]
    forbidden=[x for x in changes if x['path']!=observation]
    save('freeze_audit.json',dict(total_observed=len(before),protected_count=len(before)-(observation in before),excluded_observation_file=observation,observation_before=before.get(observation),observation_after=after.get(observation),changes=changes,forbidden_changes=forbidden))
    assert not forbidden,('protected source/input drift preserved',forbidden)
    return len(before)-(observation in before)
def prepare():
    save('frozen_before.json',protected())
    files=[Path(x.strip().strip('"')) for x in (R/'integrated/compile.f').read_text().splitlines() if x.strip()]
    assert len(files)==243
    contracts={}
    for variant in ['golden','candidate']:
        D=P/variant;D.mkdir(exist_ok=True)
        # Copy only source/config inputs, never old simulation outputs or libraries.
        for f in (R/'integrated').rglob('*'):
            if f.is_file() and f.suffix.lower() in ['.v','.sv','.vh','.vp','.diff'] and 'work' not in f.parts:
                dst=D/f.relative_to(R/'integrated');dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(f.read_bytes())
        compiled=[D/f.relative_to(R/'integrated') for f in files]
        if variant=='candidate':
            p=D/'rtl/v7_sfd_candidate.v';b=normalized(p.read_bytes())
            cg=normalized((C/'golden_v7_sfd_candidate.v').read_bytes())
            cc=normalized((C/'candidate_v7_sfd_candidate.v').read_bytes())
            gcounter=cg[:cg.index(b'endmodule')+len(b'endmodule')].replace(b'golden_sfd_counter',b'v7_sfd_counter')
            ccounter=cc[:cc.index(b'endmodule')+len(b'endmodule')].replace(b'candidate_sfd_counter',b'v7_sfd_counter')
            # Keep build02 header, reset primitives, attributes, mailbox and every other byte.
            start=b.index(b'module v7_sfd_counter');end=b.index(b'endmodule')+len(b'endmodule')
            assert b[start:end]==gcounter[gcounter.index(b'module v7_sfd_counter'):]
            b=b[:start]+ccounter[ccounter.index(b'module v7_sfd_counter'):]+b[end:]
            old=b"    v7_sfd_counter #(.W(16)) cg(cam_clk,rst_c,edge_vs | href,1'b0,\n        count_on & seen_href & !href & !(&gap_q),gap_q,);"
            new=b"    v7_camera_gap_boolean cg(cam_clk,rst_c,capture_vsync,vs_q,href,\n        count_on & seen_href & !href & !(&gap_q),gap_q);"
            b=replace(b,old,new)
            b+=cc[cc.index(b'\n// Clear priority'):]
            # Preserve original line endings.
            if b'\r\n' in p.read_bytes():b=b.replace(b'\n',b'\r\n')
            p.write_bytes(b)
            p=D/'rtl/ov5640_cdc_tc04.v';b=normalized(p.read_bytes())
            g=normalized((C/'golden_ov5640_cdc_tc04.v').read_bytes());c=normalized((C/'candidate_ov5640_cdc_tc04.v').read_bytes())
            start=g.index(b'                end else if (src_frame_start) begin');end=g.index(b'\n                end',g.index(b'drop_prefix[stat_slice] <= (&src_drop',start))
            a=g[start:end]
            start=c.index(b'                end else begin\n                    count_prefix');end=c.index(b'\n                end',start)
            b=replace(b,a,c[start:end])
            if b'\r\n' in p.read_bytes():b=b.replace(b'\n',b'\r\n')
            p.write_bytes(b)
        (D/'compile.f').write_text('\n'.join('"'+x.as_posix()+'"' for x in compiled))
        modules={}
        for f in compiled:
            for m in re.findall(rb'\bmodule\s+(\w+)',clean(f.read_bytes())):
                assert m.decode() not in modules,('collision',m,f)
                modules[m.decode()]=str(f)
        save(variant+'/registered_modules.json',modules)
        contracts[variant]=[dict(golden_source=str(a),source=str(b),golden_sha256=sha(a),sha256=sha(b)) for a,b in zip(files,compiled)]
        for name in ['tb_sdt.sv','scenario.vh','compare_monitor.vh','integrated_monitor.vh']:
            (D/name).write_bytes((R/'integrated'/name).read_bytes())
        tb=(D/'tb_sdt.sv').read_bytes();tb=replace(tb,b'`include "integrated_monitor.vh"',b'`include "integrated_monitor.vh"\n`include "boolean_monitor.vh"');(D/'tb_sdt.sv').write_bytes(tb)
        (D/'run.do').write_text('onerror {quit -code 1}\nset f [open hierarchy.txt w]\nforeach i [find instances -recursive /*] {puts $f $i}\nclose $f\nrun -all\nquit -f\n')
    save('replacement_contract.json',contracts)
    delta=[]
    for a,b in zip(contracts['golden'],contracts['candidate']):
        if a['sha256']!=b['sha256']:
            aa=Path(a['source']);bb=Path(b['source']);delta.append(bb.relative_to(P/'candidate').as_posix())
            (P/(bb.name+'.diff')).write_text(''.join(difflib.unified_diff(aa.read_bytes().decode('latin1').splitlines(True),bb.read_bytes().decode('latin1').splitlines(True),fromfile='regression02 actual integrated',tofile='boolean candidate')),encoding='utf8')
    assert delta==['rtl/ov5640_cdc_tc04.v','rtl/v7_sfd_candidate.v'] or set(delta)=={'rtl/ov5640_cdc_tc04.v','rtl/v7_sfd_candidate.v'},delta
    save('compile_delta.json',dict(files=243,byte_identical=241,changed=delta))
    groups={}
    # All module-level diagnostic state and wires, excluding implementation-only counter prefixes.
    diag=clean((P/'golden/rtl/v7_sfd_candidate.v').read_bytes()).split(b'module v7_sfd_candidate',1)[1]
    names=set(m.decode() for m in re.findall(rb'\b(?:wire|reg)\s*(?:\[[^\]]*\]\s*)?(\w+)\s*(?:[=;,])',diag))
    names.update(['bytes_q','aligned_q','native_q','overlap_q','raw_overlap_q','segments_q','odd_q','odd_next','gap_q','seq_q','seq_next','mailbox','host_bank','prev_aligned','prev_native','prev_segments','prev_end_aligned','prev_bad','have_prev','vs_q','href_q','parity','armed'])
    for i in range(4):
        base=f'dut.source_diagnostics.cameras[{i}].source.'
        groups[f'diag{i}']=[base+n for n in sorted(names)]
        groups[f'counter{i}']=[base+counter+'.'+n for counter in ['cb','ca','cn','co','cro','cs','cod','cq'] for n in ['q','next_q','prefix']]+[base+'cg.q']
    cdc=['src_count','src_drop','count_prefix','drop_prefix','src_vs_q','src_frame_start','drop_increment','src_snapshot_count','src_snapshot_drop']
    cdcbytes=clean((P/'golden/rtl/ov5640_cdc_tc04.v').read_bytes())
    # Extract all simple module-level state, ports covered by original monitor.
    cdc=['vsync_sync','hsync_sync','empty','full','wr_en','rd_en','dout','video_valid_r','src_vs_q','src_toggle','src_count','src_drop','src_seq','src_snapshot','src_frame_start','drop_increment','count_prefix','drop_prefix','snapshot_s1','snapshot_s2','toggle_sync','toggle_seen','out_vs_q','out_count','out_snapshot','dbg_cdc_input','dbg_cdc_output','dbg_cdc_drop','dbg_cdc_seq']
    for inst in ['ov5640_top','cam2_ov5640_top','cam3_ov5640_top','cam4_ov5640_top']:
        groups[inst+'_cdc']=['dut.'+inst+'.ov5640.ov5640_cdc.'+n for n in cdc]
    save('boolean_trace_fields.json',groups)
    original=json.loads((R/'trace_fields.json').read_text());save('trace_fields.json',original)
    text=['integer boolean_fd,boolean_samples=0;','reg boolean_started=0;','initial boolean_fd=$fopen("boolean.trace","w");']
    for i,fields in enumerate(groups.values()):text.append(f'reg [$bits('+ '{'+','.join(fields)+'}'+f')-1:0] boolean_last_{i};')
    text+=['task boolean_sample(input integer kind);','begin','boolean_samples=boolean_samples+1;']
    for i,fields in enumerate(groups.values()):
        expr='{'+','.join(fields)+'}'
        text.append(f'if(!boolean_started || {expr} !== boolean_last_{i}) $fdisplay(boolean_fd,"%0t %0d {i} %h",$time,kind,{expr});boolean_last_{i}={expr};')
    text.append('boolean_started=1;')
    text+=['end','endtask','always @(posedge clk) begin #0.002;boolean_sample(0);end','always @(posedge camclk) begin #0.003;boolean_sample(1);end','always @(negedge camclk) begin #0.004;boolean_sample(2);end','always @(posedge ctrlclk) begin #0.005;boolean_sample(3);end','final begin $fdisplay(boolean_fd,"SAMPLES %0d",boolean_samples);$fclose(boolean_fd);end']
    for v in ['golden','candidate']:(P/v/'boolean_monitor.vh').write_text('\n'.join(text),encoding='ascii')
def tool(exe,args,D,log):
    with (D/log).open('wb') as f:r=subprocess.run([str(SIM/exe),*map(str,args)],cwd=D,stdout=f,stderr=subprocess.STDOUT)
    t=(D/log).read_text(errors='replace');print(D.name,log,t[-1500:],flush=True)
    assert r.returncode==0 and not re.search(r'\*\* (?:Error|Fatal)',t),log
    return t
def run():
    vendor=P.parent/'source_diagnostics_top_candidate/vendor'
    for v in ['golden','candidate']:
        D=P/v
        tool('vmap.exe',['-c'],D,'vmap.log');tool('vmap.exe',['vendor',vendor],D,'vendor_binding.log');tool('vlib.exe',['work'],D,'vlib.log')
        tool('vlog.exe',['+incdir+'+str(D/'inputs/source/npu'),'-f','compile.f'],D,'compile.log')
        tool('vlog.exe',['-sv','+incdir+'+str(D),'tb_sdt.sv'],D,'tb_compile.log')
        t=tool('vsim.exe',['-c','-vopt','-voptargs=+acc','-L','vendor','work.tb_sdt','-do','run.do'],D,'simulation.log')
        assert 'SDT_ALL_PASS checks=14540' in t and 'TOP_FOUR_RESET_PASS' in t and 'FAIL' not in t
    audit()
def audit():
    results={};mismatches=[]
    for v in ['golden','candidate']:
        D=P/v;t=(D/'simulation.log').read_text(errors='replace')
        results[v]=dict(markers=[x for x in t.splitlines() if 'PASS' in x or 'SAMPLES' in x or 'MOTION_RTL' in x],warnings=len(re.findall(r'\*\* Warning',t)))
        h=(D/'hierarchy.txt').read_text();pr=[l for l in h.splitlines() if 'source_diagnostics' in l and re.search(r'_ff\d \(GTP_DFF_(?:CE|PE)\)$',l)]
        assert sum('(GTP_DFF_CE)' in x for x in pr)==28 and sum('(GTP_DFF_PE)' in x for x in pr)==32
        gap=[l for l in h.splitlines() if re.search(r'/source/cg \(',l)];cdc=[l for l in h.splitlines() if l.endswith('/ov5640_cdc (ov5640_cdc_tc04)')]
        assert len(gap)==4 and len(cdc)==4,(gap,cdc)
        assert all(('v7_camera_gap_boolean' if v=='candidate' else 'v7_sfd_counter') in x for x in gap)
        results[v]['bindings']=dict(gap=gap,cdc=cdc,primitives=pr)
    for name in ['comparison.trace','integrated.trace','boolean.trace']:
        a=P/'golden'/name;b=P/'candidate'/name;xs=ys=0;first=[]
        with a.open('rb') as af,b.open('rb') as bf:
            for count,x in enumerate(af,1):
                y=bf.readline();xs+=len(re.findall(rb'[xXzZ]',x.split(b' ',3)[-1]));ys+=len(re.findall(rb'[xXzZ]',y.split(b' ',3)[-1]))
                if x!=y and len(first)<20:first.append(dict(record=count,golden=x.decode(errors='replace')[:2000],candidate=y.decode(errors='replace')[:2000]))
            extra=bf.read(2048)
        equal=not first and not extra and a.stat().st_size==b.stat().st_size
        results[name]=dict(equal=equal,records=count,bytes=a.stat().st_size,golden_sha256=sha(a),candidate_sha256=sha(b),golden_XZ_digits=xs,candidate_XZ_digits=ys,first_mismatches=first,extra_candidate=extra.decode(errors='replace'))
        if not equal:mismatches.append(name)
    try:
        results['protected_files_unchanged']=freeze_check();results['freeze_pass']=True
    except AssertionError as e:
        results['freeze_pass']=False;results['freeze_failure']=str(e)
        freeze=json.loads((P/'freeze_audit.json').read_text(encoding='utf8'))
        results['protected_files_unchanged']=freeze['protected_count']-len(freeze['forbidden_changes'])
    results['pds_remote_device_used']=False;results['timing_claim']=False
    results['functional_pass']=not mismatches;results['pass']=not mismatches and results['freeze_pass'];save('results.json',results)
    assert not mismatches,('trace mismatches preserved',mismatches)
    for v in ['golden','candidate']:
        for name in ['comparison.trace','integrated.trace','boolean.trace']:
            f=P/v/name
            with f.open('rb') as src,gzip.open(str(f)+'.gz','wb') as dst:shutil.copyfileobj(src,dst)
            f.unlink()
    print('REGRESSION03_FULL_TOP_FUNCTIONAL_PASS freeze_pass='+str(results['freeze_pass']),flush=True)
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='audit':audit()
    elif len(sys.argv)>1 and sys.argv[1]=='run':run()
    else:prepare();run()
