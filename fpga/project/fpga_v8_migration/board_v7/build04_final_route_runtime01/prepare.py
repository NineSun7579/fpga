"""Executable offline preparation. No vendor process or external write path."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'runtime'))
from contract import BOARD,SOURCE,CONTRACT,load,sha,require,verify_inputs,validate_mapping
def save(name,obj):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def bindings():
    m=load(SOURCE/'manifest.json');out={}
    for key in ['full_source_copy_hashes','protected_hashes','build03_full_hashes','official_model_hashes']:
        for n,h in m[key].items():
            p=(SOURCE/n if key=='full_source_copy_hashes' else Path(m['baseline_root'])/n if key=='build03_full_hashes' else Path(n))
            require(sha(p)==h,'Immutable binding drift '+str(p));out[str(p)]=h
    for n,h in load(BOARD/'build04_route_prepare01/fresh_graph_input_binding.json').items():require(sha(n)==h,'ADF/raw binding drift');out[n]=h
    for n,h in load(SOURCE/'evidence/runtime/mapping60_01/mapping_artifact.json').items():require(sha(n)==h,'Map DB drift');out[n]=h
    for folder in ['source_diagnostics_timing_build_02','source_diagnostics_timing_build_03','source_diagnostics_timing_build_04']:
        for p in (BOARD/folder/'runtime').rglob('*'):
            if p.is_file():out[str(p)]=sha(p)
    for p in (SOURCE/'constraints_live').glob('*'):
        if p.is_file():out[str(p)]=sha(p)
    for n in ['manifest.json','source04hash.json','project.pds','evidence/runtime/final_receipt_review.json','evidence/runtime/mapping60_01/final_result.json']:
        out[str(SOURCE/n)]=sha(SOURCE/n)
    return out
def main():
    verify_inputs();before=bindings();save('input_before.json',before)
    analysis=HERE/'analysis';analysis.mkdir(exist_ok=True)
    for n in ['graph.json','objects.json']:shutil.copyfile(SOURCE/'evidence/runtime/actual/analysis'/n,analysis/n)
    for n in ['resolve_manifest.py','graph_adapter.py']:shutil.copyfile(HERE/'runtime'/n,analysis/n)
    run=subprocess.run([sys.executable,'-B',str(analysis/'resolve_manifest.py')],cwd=analysis,capture_output=True)
    (HERE/'fresh_resolve.log').write_bytes(run.stdout+run.stderr);require(run.returncode==0,'Fresh resolve failed')
    m=load(analysis/'manifest.json');g=load(analysis/'graph.json');pairs=validate_mapping(m,g)
    save('logical_to_physical_2048.json',{'logical':m['resolved'],'physical':pairs,'contract_sha256':sha(HERE/'candidate_specific_expectation_contract.json')})
    from derive_new_constraints import derive
    raw,proof=derive(SOURCE/'evidence/runtime/compile/analysis/graph.json',analysis/'graph.json',analysis/'manifest.json',SOURCE/'inputs/source/constraints/clock.fdc')
    from clock_audit import audit
    clock=audit(raw,proof);dest=HERE/'constraints';dest.mkdir(exist_ok=True);(dest/'clock.fdc').write_bytes(raw)
    for n in ['cdc.fdc','ddr3.fdc','ov5640.fdc','pcie.fdc','sfp.fdc']:shutil.copyfile(SOURCE/'constraints_live'/n,dest/n)
    save('coverageproof.json',proof);save('clock_offline_audit.json',clock)
    targets=[{'start':p['CLK'],'end':p['D'],'corner':c,'logical_members':p['logical_members']} for p in pairs for c in ['Slow','Fast']]
    require(len({(r['start'],r['end'],r['corner']) for r in targets})==2560,'Target duplication');save('physical_targets2560.json',targets)
    from graph_adapter import classify
    classified=classify(g);save('synthesis_classification60.json',classified)
    plan=[];execution=HERE/'execution01'
    for folder,src in [('rtl',SOURCE/'rtl'),('inputs',SOURCE/'inputs'),('compile',SOURCE/'compile'),('synthesize',SOURCE/'synthesize'),('device_map',SOURCE/'evidence/runtime/mapping60_01/isolated_mapping_work/device_map')]:
        for p in src.rglob('*'):
            if p.is_file():plan.append({'source':str(p),'destination':str(execution/'inputs'/folder/p.relative_to(src)),'sha256':sha(p),'bytes':p.stat().st_size})
    for p in dest.glob('*'):plan.append({'source':str(p),'destination':str(execution/'constraints'/p.name),'sha256':sha(p),'bytes':p.stat().st_size})
    plan.append({'source':str(SOURCE/'project.pds'),'destination':str(execution/'original_project_DO_NOT_RUN.pds'),'sha256':sha(SOURCE/'project.pds'),'bytes':(SOURCE/'project.pds').stat().st_size})
    save('route_copy_plan.json',{'candidate_id':HERE.name,'source_candidate_id':SOURCE.name,'execution_root':str(execution),'files':plan,'copy_allowed':False,'new_project':'Fresh shell set_arch/add_constraint; original project archived only'})
    from commands import generate
    generate(pairs,classified)
    save('signoff_manifest.json',{'schema':'build04-final-route-signoff/v1','candidate_id':HERE.name,'source_candidate_id':SOURCE.name,'contract_sha256':sha(HERE/'candidate_specific_expectation_contract.json'),'source741':741,'registered186':186,'logical2048':2048,'unique_pairs1280':1280,'records2560':2560,'gate_requirements':{'global10':['Setup','Hold','Recovery','Removal','Minimum Pulse Width'],'targeted60':{'independent_sync':28,'independent_reset':32,'reset_recovery_removal_corners':128,'reset_MPW_corners':64,'later_sync16_setup_hold_corners':64,'mailbox_pair_corners':2560},'IO112bank':['112 exact joins','3 differential contracts','internal bank identity','VCCIO','IOSTANDARD','VREF','termination','drive','PCB binding'],'HSST':['baseline exact sites','dedicated connections'],'motion32':['DRM36K geometry','read_first','data/address connectivity'],'timing_reload':['old group absent','exact364','complement exact sets','15.238 actual exception','DDR131.25','no remap','mapped graph unchanged']},'all_physical_gates_passed':False,'accepted':False,'reviewer':None,'board_verified':False,'bit_allowed':False})
    after={p:sha(p) for p in before};require(before==after,'Protected inputs changed during preparation');save('input_after.json',after)
    save('offline_result.json',{'status':'OFFLINE_PREPARE_PASS_PHYSICAL_BLOCKED','fresh_resolve_errors':len(m['errors']),'logical':2048,'register_logical':1320,'zero':728,'aliases':40,'unique_physical':1280,'physical_targets':2560,'clock':clock,'input_hashes_unchanged':True,'pds_started':False,'route_enabled':False,'blocking':['mapping60 exact primitive/clock/alias/official behavior proof','IO112 full internal-bank/electrical evidence','main-session explicit bound enable','independent measured CDB timing replacement/no-remap proof before signoff']})
    print('OFFLINE PREPARE PASS: exact2048/1280/2560, U368-B4=364,15.238ns,DDR131.25; physical gates BLOCKED')
if __name__=='__main__':main()
