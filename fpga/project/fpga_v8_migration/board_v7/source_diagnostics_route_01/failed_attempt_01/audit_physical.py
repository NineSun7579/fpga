"""Reuse TC05's inherited raw STA/DRM/HSST gates with diagnostic top identity."""
from prepare_route import *
import importlib.util, sys, types

def main():
    migration=HERE.parents[1]
    origin=migration/'whole_candidate_v2_route_01'
    spec=importlib.util.spec_from_file_location('summarize_route',origin/'summarize_route.py')
    summary=importlib.util.module_from_spec(spec);sys.modules['summarize_route']=summary;spec.loader.exec_module(summary)
    summary.HERE=HERE;summary.EVIDENCE=HERE/'evidence';summary.EVIDENCE.mkdir(exist_ok=True)
    guard=json.loads((HERE/'build01_guard.json').read_bytes())
    before=json.loads((HERE/'pnr_input_hashes.json').read_bytes())
    def guards():return {p:sha(Path(p)) for p in guard}
    def inputs():return {p:sha(HERE/p) for p in before}
    save('protected_before.json',guard);save('inputs_before.json',before)
    runner=types.ModuleType('run_route');runner.guards=guards;runner.inputs=inputs;sys.modules['run_route']=runner
    source=(origin/'audit_final.py').read_bytes()
    edits=[(b'fpga_v8_cooperative_top_v2.rtr',b'v7_sdt_top.rtr'),
           (b"HERE.parents[1] / 'motion_100h/run_20261003_212303/phy_audit.json'",b"Path("+repr(str(migration/'motion_100h/run_20261003_212303/phy_audit.json')).encode('ascii')+b")"),
           (b'max_path 15000',b'max_path 200000')]
    for old,new in edits:
        assert source.count(old)==1,(old,source.count(old));source=source.replace(old,new)
    save('physical_gate_reuse.json',{'source':str(origin/'audit_final.py'),'original_sha256':sha(origin/'audit_final.py'),'executed_sha256':hashlib.sha256(source).hexdigest(),'exact_edits':[x.decode() for x,y in edits],'upstream_chain':'TC05 -> TC04 -> TC02 -> raw final audit','diagnostic_top':'v7_sdt_top','programming_performed':False})
    scope={'__name__':'route01_physical_audit','__file__':str(origin/'audit_final.py')}
    exec(compile(source,str(origin/'audit_final.py'),'exec'),scope);scope['main']()
    stages={s:summary.extract(HERE/s/db,s) for s,db in [('synthesize','snr.db'),('place_route','prr.db')]}
    save('evidence/stage_tables.json',stages)
    baseline=json.loads((migration/'whole_candidate_v7_route_01/evidence/stage_tables.json').read_bytes())
    pins=stages['place_route']['pnr_io_report']['rows'];old=baseline['place_route']['pnr_io_report']['rows']
    assert len(pins)==112 and pins==old,'Actual PCB IO pins/electrical attributes changed'
    log=(HERE/'compile/run.log').read_bytes()
    modules=set(x.decode() for x in re.findall(rb'Elaborating module (\w+)',log))
    required={'block_motion_detector_tc05','axi_dma_write_tc04','ov5640_cdc_tc04','fpga_v8_reset_fault_guard_02'}
    assert required<=modules
    diagnostics={x for x in modules if 'source' in x and ('diag' in x or 'frame' in x)}
    assert diagnostics,'Diagnostic source identity missing'
    save('evidence/identity_pin_audit.json',{'passed':True,'io_pins':112,'identical_to_frozen_tc05':True,'required_modules':sorted(required),'diagnostic_modules':sorted(diagnostics),'compile_log_sha256':sha(HERE/'compile/run.log')})
    print('PASS raw full physical gates; mailbox/reset detailed coverage still separate',flush=True)
if __name__=='__main__':main()
