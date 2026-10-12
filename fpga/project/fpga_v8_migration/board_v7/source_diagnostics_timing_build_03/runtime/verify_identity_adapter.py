"""Read-only actual build01 calibration and negative tests; no PDS or acceptance."""
import copy
import sys
from preflight import HERE,BOARD,load,sha,require
from physical_flow import TOOLS,record,classify_processes
sys.path.insert(0,str(TOOLS))
from graph_adapter import Resolver,classify
from routed_identity import truth_proof,bind_clock_leaf

def main():
    e=BOARD/'source_diagnostics_timing_build_01/evidence'
    files={n:e/n for n in ['routed/analysis/graph.json','actual_post_constraints/analysis/graph.json',
                           'actual_post_constraints/analysis/manifest.json','coverageproof_synthesis.json','dev_map.log','pnr.log']}
    hashes={n:sha(p) for n,p in files.items()}
    g=load(files['routed/analysis/graph.json']);sg=load(files['actual_post_constraints/analysis/graph.json'])
    m=load(files['actual_post_constraints/analysis/manifest.json'])
    result=truth_proof(g,sg,m,HERE/'runtime/libraries/routed_truth_reference.py.txt')
    require(result['passed'],'Actual old build01 all2048 function calibration failed')
    result['calibration_only']=True;result['build03_physical_pass']=False
    record('identity_calibration_data.json',result)
    bindings=[];coverage=[]
    for camera in load(files['coverageproof_synthesis.json'])['cameras']:
        rows=[bind_clock_leaf(g,l,[files['dev_map.log'],files['pnr.log']]) for l in camera['synthesis']['leaves']]
        leaves=Resolver(g).clock_leaves(camera['camera'])
        require({p for r in rows for p in r['physical']}==set(leaves['leaves']),'Actual root/clone/cleanup leaf coverage mismatch')
        bindings.extend(rows);coverage.append(leaves)
    cleaned=[r for r in bindings if r['status']=='tool_cleanup'];copies=[r for r in bindings if r['status']=='equivalent_fanout_copies']
    require(len(cleaned)==12 and len(copies)==1 and len(copies[0]['physical'])==2,'Actual cleanup/copy evidence changed')
    negatives={}
    def rejects(label,call):
        try:call()
        except (RuntimeError,AssertionError) as exc:negatives[label]=str(exc)
        else:raise RuntimeError('Negative fixture incorrectly accepted: '+label)
    rejects('packed_storage_independent60',lambda:classify(g))
    require('Packed storage' in negatives['packed_storage_independent60'],'Packing rejection must remain explicit')
    rejects('missing_without_cleanup',lambda:bind_clock_leaf(g,cleaned[0]['logical'],[]))
    cell=copies[0]['physical'][1].rsplit('/',1)[0]
    bad=copy.copy(g);bad['pin_net']=dict(g['pin_net']);bad['pin_net'][cell+'/D']=g['pin_net'][cell+'/CLK']
    rejects('non_equivalent_clone',lambda:bind_clock_leaf(bad,copies[0]['logical'],[]))
    buffered=[p for p in result['pairs'] if not p['direct_Q_to_D']]
    require(len(buffered)==1 and buffered[0]['connection_semantics']=='identity_path','Buffered actual pair must not claim direct connection')
    routecell=next(t['driver'].rsplit('/',1)[0] for t in buffered[0]['driver_trace'] if t['type']=='gopCLKROUTE')
    bad=copy.copy(g);bad['primitives']=dict(g['primitives']);bad['primitives'][routecell]=copy.deepcopy(g['primitives'][routecell])
    def corrupt(value):
        if isinstance(value,list):
            if value and value[0]=='PARAMETER' and value[1]=='INITA':
                def flip(v):
                    if isinstance(v,list):
                        if v and v[0]=='B':v[2]='"'+'1'*int(v[1])+'"'
                        else:
                            for child in v:flip(child)
                flip(value)
            else:
                for child in value:corrupt(child)
    corrupt(bad['primitives'][routecell]['default_parameters']);corrupt(bad['primitives'][routecell]['parameters'])
    rejects('nonidentity_CLKROUTE',lambda:Resolver(bad).trace_driver(g['pin_net'][buffered[0]['physical'][1]]))
    fixture=[{'ProcessId':1,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python x/board_v7/diagnostic_sync_register_map02/recover.py'},
             {'ProcessId':2,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python x/board_v7/source_diagnostics_timing_build_01/resume_actual_graph.py'},
             {'ProcessId':3,'ParentProcessId':0,'Name':'python.exe','CommandLine':'python other/recover.py'}]
    busy,_=classify_processes(fixture,99);require([p['ProcessId'] for p in busy]==[1,2],'Tools-empty controller lifetime guard failed')
    require(all(sha(files[n])==h for n,h in hashes.items()),'Actual calibration inputs changed during review')
    record('identity_adapter_review.json',{'status':'FUNCTION_AND_CLOCK_CALIBRATION_PASS_INDEPENDENT60_EXPECTED_FAIL',
           'input_hashes':hashes,'resolved_bits':2048,'register_bits':1320,'zero_bits':728,'buffered_pairs':buffered,
           'bindings':bindings,'clock_coverage':coverage,'negative_tests':negatives,
           'queue_controller_lifetime_fixture_pass':True,'runtime_adapter_sha256':sha(TOOLS/'graph_adapter.py'),
           'truth_producer_sha256':sha(TOOLS/'routed_identity.py'),'build03_fresh_graph_test':'PENDING',
           'physical_signoff':False,'no_tools_or_device':True})
    print('实际2048=1320register+728zero PASS；12清理+双copy+单identity路径 PASS；packed独立60预期FAIL；队列生命周期PASS',flush=True)

if __name__=='__main__':main()
