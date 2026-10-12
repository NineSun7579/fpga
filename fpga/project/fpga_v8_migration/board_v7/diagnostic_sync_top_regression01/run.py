"""Isolated full-top RTL regression. No PDS or hardware commands."""
from pathlib import Path
import hashlib, json, os, re, subprocess, gzip, shutil

P = Path(__file__).resolve().parent
O = P.parent / 'source_diagnostics_top_candidate'
C = P.parent / 'diagnostic_sync_register_timing_candidate'
SIM = Path(os.environ.get('MODELSIM_BIN', 'C:/modeltech64_10.6e/win64'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name, value): (P/name).write_text(json.dumps(value, indent=2), encoding='utf8')
def tool(exe, args, cwd, log):
    r = subprocess.run([str(SIM/exe), *map(str,args)], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (P/log).write_bytes(r.stdout)
    text = r.stdout.decode('utf8','replace')
    print(log, text[-1800:], flush=True)
    assert r.returncode == 0 and not re.search(r'\*\* (?:Error|Fatal)', text), log
    return text

def prepare():
    protected = {}
    historical_differences=[]
    for root, fn in [(O,'compiled_hashes.json'),(O,'source_hashes.json'),(C/'evidence','frozen_inputs.json')]:
        for f,h in json.loads((root/fn).read_text()).items():
            current=sha(f)
            if current!=h:
                # A past report also froze an unrelated active PDS project.
                # It is never a compile input for this RTL-only regression.
                assert root==C/'evidence' and Path(f).suffix=='.pds' and 'source_diagnostics_timing_build' in f, ('stale frozen simulation input',f)
                historical_differences.append({'path':f,'historical_sha256':h,'current_sha256':current,'used_in_simulation':False})
            protected[f]=current
    save('historical_input_differences.json',historical_differences)
    for root in [O,C/'rtl_primitive',C/'baseline']:
        for f in root.iterdir():
            if f.is_file(): protected[str(f)]=sha(f)
    # Protect active timing build and independent map project without writing either.
    for root in P.parent.glob('*'):
        if root.is_dir() and ('timing_build' in root.name or 'primitive_map' in root.name):
            for f in root.rglob('*'):
                if f.is_file() and f.suffix.lower() in {'.v','.sv','.vh','.pds','.fdc','.sdc','.py','.json'}:
                    protected[str(f)]=sha(f)
    save('frozen_inputs.json', protected)
    original = [Path(s.strip().strip('"')) for s in (O/'compile.f').read_text().splitlines() if s.strip()]
    names = {'v7_sfd_candidate.v','v7_sdt_bus.v'}
    assert {f.name for f in original if f.name in names}==names
    contract = {}
    for variant in ['baseline','primitive']:
        D=P/variant; D.mkdir(exist_ok=True)
        (D/'rtl').mkdir(exist_ok=True)
        files=[]
        for f in original:
            if f.name in names:
                target=D/'rtl'/f.name
                source=f if variant=='baseline' else C/'rtl_primitive'/f.name
                target.write_bytes(source.read_bytes())
                contract[str(target)]={'source':str(source),'sha256':sha(target)}
                f=target
            files.append(f)
        mods={}
        for f in files:
            for n in re.findall(rb'(?m)^\s*module\s+(\w+)',f.read_bytes()):
                assert n.decode() not in mods, ('duplicate registered module',n,f)
                mods[n.decode()]=str(f)
        save(variant+'/registered_modules.json',mods)
        (D/'compile.f').write_text('\n'.join('"'+f.as_posix()+'"' for f in files))
        (D/'tb_sdt.sv').write_bytes((O/'tb_sdt.sv').read_bytes().replace(b'`include "scenario.vh"',b'`include "scenario.vh"\n`include "compare_monitor.vh"'))
        scenario=(O/'scenario.vh').read_bytes()
        assert scenario.count(b'$finish;')==1
        scenario=scenario.replace(b'$finish;',b'\n'+(P/'reset_extension.vh').read_bytes()+b'\n$finish;')
        (D/'scenario.vh').write_bytes(scenario)
        monitor=make_monitor()
        (D/'compare_monitor.vh').write_text(monitor,encoding='ascii')
        (D/'run.do').write_text('onerror {quit -code 1}\nset f [open hierarchy.txt w]\nforeach i [find instances -recursive /*] {puts $f $i}\nclose $f\nrun -all\nquit -f\n')
    save('replacement_contract.json',contract)
    save('evidence_links.json',{'original_top_report':str(O/'REPORT.md'),'original_top_log':str(O/'top_simulation.log'),'source_2038':str(O/'source_regression.log'),'bus_11986_original':str(O/'unit_regression/tb_v7_sdb.log'),'bus_11986_corrected':str(O/'unit_regression/corrected_bus.log'),'primitive_source_bus_comparison':str(C/'evidence/primitive_results.json'),'mapped_INIT_audit':str(C/'evidence/primitive_parameter_audit.json')})

def make_monitor():
    fields=['u_awready','u_wready','u_bvalid','u_bresp','u_arready','u_rvalid','u_rresp','dma_rdata','dut.axi_rst','dut.camera_ctrl_rst_n']
    b='dut.source_diagnostics'
    fields += [b+'.'+n for n in ['cam_reset','invalid','valid','available','overrun','rv','re','m_awvalid','m_awaddr','m_wvalid','m_wdata','m_wstrb','m_bready','m_arvalid','m_araddr','m_rready']]
    for g in range(4):
        fields += [f'{b}.epoch[{g}]', f'{b}.cameras[{g}].reset_pipe']
        fields += [f'{b}.cameras[{g}].source.{n}' for n in ['cr','hr','ack_sync','req_sync','overrun_sync','request','ack','mailbox','host_bank','read_data','read_valid','read_error','snapshot_valid','seq_q']]
    # Fixed generous width, zero padding is deterministic. Changed records retain
    # exact four-state values; identical consecutive samples are losslessly omitted.
    expr='{'+','.join(fields)+'}'
    return '''integer trace_fd, host_samples=0, cam_samples=0, reset_samples=0;
reg [8191:0] trace_last; reg trace_started=0;
initial begin trace_fd=$fopen("comparison.trace","w"); if(!trace_fd) $fatal(1,"trace open"); end
task trace_sample(input integer kind);
 reg [8191:0] value;
 begin
 value='''+expr+''';
 if(!trace_started || value !== trace_last) $fdisplay(trace_fd,"%0t %0d %h",$time,kind,value);
 trace_started=1;trace_last=value;
 end
endtask
always @(posedge clk) begin #0.002; if($time>=20) begin host_samples++;trace_sample(0);end end
always @(posedge camclk) begin #0.003; if($time>=20) begin cam_samples++;trace_sample(1);end end
always @(dut.source_diagnostics.cam_reset or dut.axi_rst) begin
 #0.004; if($time>=20) begin reset_samples++;trace_sample(2);end
end
final begin
 $fdisplay(trace_fd,"SAMPLES %0d %0d %0d",host_samples,cam_samples,reset_samples);
 $fclose(trace_fd);
 $display("TOP_COMPARE_SAMPLES host=%0d cam=%0d reset=%0d",host_samples,cam_samples,reset_samples);
end
'''

def seal():
    results={}
    for variant in ['baseline','primitive']:
        text=(P/variant/'simulation.log').read_text(errors='replace')
        assert 'SDT_ALL_PASS checks=14540' in text and 'TOP_FOUR_RESET_PASS' in text and 'FAIL' not in text
        results[variant]={'markers':[s for s in text.splitlines() if 'PASS' in s or 'TOP_COMPARE_SAMPLES' in s], 'warnings':len(re.findall(r'\*\* Warning',text)), 'trace_sha256':sha(P/variant/'comparison.trace')}
    a=P/'baseline/comparison.trace';b=P/'primitive/comparison.trace'
    assert a.stat().st_size==b.stat().st_size
    lines=0
    with a.open('rb') as af,b.open('rb') as bf:
        for lines,x in enumerate(af,1):
            y=bf.readline();assert x==y, ('four-state comparison mismatch',lines,x[:120],y[:120])
        assert not bf.read()
    results['exact_four_state_trace_comparison']={'equal':True,'records':lines,'bytes':a.stat().st_size,'start_ns':20,'post_NBA_delays_ps':[2,3,4]}
    hierarchy=(P/'primitive/hierarchy.txt').read_text()
    bindings=[s for s in hierarchy.splitlines() if 'source_diagnostics' in s and re.search(r'(?:reset_pipe|cr|hr|ack_sync|req_sync|overrun_sync)_ff\d \(GTP_DFF_(?:CE|PE)\)$',s)]
    assert len(bindings)==60, ('actual primitive instance count',len(bindings))
    assert sum('(GTP_DFF_CE)' in s for s in bindings)==28
    assert sum('(GTP_DFF_PE)' in s for s in bindings)==32
    save('actual_parent_bindings.json',{'top':'/tb_sdt/dut','bus_module':'v7_sdt_bus','source_module':'v7_sfd_candidate','CE_count':28,'PE_count':32,'primitive_instances':bindings,'registered_sources':json.loads((P/'primitive/registered_modules.json').read_text())})
    frozen=json.loads((P/'frozen_inputs.json').read_text())
    assert all(sha(f)==h for f,h in frozen.items())
    results['protected_hashes_unchanged']=len(frozen)
    results['pds_invoked']=False;results['physical_mapping_verified']=False
    for f in [a,b]:
        with f.open('rb') as src,gzip.open(str(f)+'.gz','wb') as dst:shutil.copyfileobj(src,dst)
        f.unlink()
    save('results.json',results)
    hashes={str(f.relative_to(P)):sha(f) for f in P.rglob('*') if f.is_file() and not any(x in f.parts for x in ['work','__pycache__']) and f.name!='hashlog.json'}
    save('hashlog.json',hashes)
    print('FULL_TOP_PRIMITIVE_REGRESSION_PASS',json.dumps(results,indent=2),flush=True)

def main():
    prepare()
    F=O.parents[1]/'whole_candidate_v7_route_01'
    for variant in ['baseline','primitive']:
        D=P/variant
        tool('vmap.exe',['-c'],D,variant+'/vmap_copy.log')
        tool('vmap.exe',['vendor',O/'vendor'],D,variant+'/vendor_binding.log')
        if not (D/'work').exists():tool('vlib.exe',['work'],D,variant+'/vlib.log')
        tool('vlog.exe',['+incdir+'+str(F/'inputs/source/npu'),'-f','compile.f'],D,variant+'/compile.log')
        tool('vlog.exe',['-sv','+incdir+'+str(D),'tb_sdt.sv'],D,variant+'/tb_compile.log')
        text=tool('vsim.exe',['-c','-vopt','-voptargs=+acc','-L','vendor','work.tb_sdt','-do','run.do'],D,variant+'/simulation.log')
        assert 'SDT_ALL_PASS checks=14540' in text and 'TOP_FOUR_RESET_PASS' in text and 'FAIL' not in text
    seal()

if __name__=='__main__':main()
