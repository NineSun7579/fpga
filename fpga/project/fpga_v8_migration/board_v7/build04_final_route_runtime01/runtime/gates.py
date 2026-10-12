"""Evidence adoption requires exact coverage, byte provenance and main review.

Independent reviewers supply semantic receipts, never a resultfile/status PASS.
This module does not claim to infer official primitive behavior from a cell name.
"""
import json
from contract import HERE,BOARD,SOURCE,load,sha,require,verify_inputs
REQUIREMENTS={
 'mapping60':{'distinct_storage60','exact_D_Q_CE_reset','official_primitive_behavior','exact_clock_roots','logical_cr_alias_identity','native_PCF_exact60','mapped_graph_binding'},
 'IO112bank':{'join112','differential3','internal_bank_objects','bank_conflict_explained','VCCIO','IOSTANDARD','VREF','termination','drive','PCB'},
 'timing_reload':{'official_no_prerequisites','mapped_graph_unchanged','old_group_absent','exact_U368_B4_364','complement_exact','MaxDelay15.238','DDR131.25','same_domain_preserved','CDB_raw_binding'}
}
def bound_files(items):
    require(items,'Empty raw evidence coverage')
    for x in items:
        p=__import__('pathlib').Path(x['path']);require(p.is_file() and p.stat().st_size==x['bytes'] and x['bytes']>0 and sha(p)==x['sha256'],'Raw evidence hash/size mismatch')
def check():
    require((HERE/'main_enable.json').is_file(),'BLOCKED: no explicit main-session enable bound to mapping60, IO112bank and measured timing reload evidence')
    enable=load(HERE/'main_enable.json')
    require(enable.get('schema')=='main-session-route-enable/v1' and enable.get('enabled') is True and enable.get('reviewer') and enable.get('session_id'),'Main session explicit enable missing')
    verify_inputs()
    require(enable.get('candidate_id')==HERE.name and enable.get('contract_sha256')==sha(HERE/'candidate_specific_expectation_contract.json'),'Enable candidate/contract mismatch')
    seal=load(HERE/'runtime_seal.json');require(enable.get('runtime_seal_sha256')==sha(HERE/'runtime_seal.json'),'Enable runtime mismatch')
    for n,h in seal.items():require(sha(HERE/n)==h,'Runtime/plan drift '+n)
    before=load(HERE/'input_before.json')
    for n,h in before.items():require(sha(n)==h,'Immutable input drift '+n)
    for kind,needed in REQUIREMENTS.items():
        adoption=enable['evidence'][kind];p=__import__('pathlib').Path(adoption['path'])
        require(sha(p)==adoption['sha256'],'Receipt not explicitly approved by main session')
        r=load(p)
        require(r.get('schema')=='independent-physical-evidence/v1' and r.get('kind')==kind and r.get('reviewer') and r.get('independent') is True,'Unreviewed evidence')
        require(r.get('source_candidate_id')==SOURCE.name and r.get('contract_sha256')==sha(HERE/'candidate_specific_expectation_contract.json'),'Evidence candidate/contract mismatch')
        require(r.get('map_adf_sha256')==sha(SOURCE/'evidence/runtime/mapping60_01/isolated_mapping_work/device_map/v7_sdt_top_map.adf'),'Evidence maps wrong DB')
        claims=r['coverage'];require(set(claims)==needed,'Missing/extra semantic coverage '+kind)
        for name,claim in claims.items():
            require(claim.get('verified') is True and claim.get('method') and claim.get('raw_files'),'Unclosed semantic claim '+name)
            bound_files(claim['raw_files'])
        if kind=='mapping60':
            expected={x['target'] for x in load(BOARD/'production60_target_prepare01/site_candidate_plan.json')['rows']}
            rows=r['endpoint_bindings'];require(len(rows)==60 and {x['logical'] for x in rows}==expected,'Mapping logical exact60 mismatch')
            require(len({x['physical_cell'] for x in rows})==len({x['site'] for x in rows})==60,'Aliased physical storage/site')
            require(all(x.get('official_model_sha256') and x.get('clock_root') and x.get('D') and x.get('Q') and x.get('reset') and x.get('control_semantics') for x in rows),'Incomplete primitive identity')
        elif kind=='IO112bank':
            rows=r['ports'];require(len(rows)==len({x['port'] for x in rows})==112 and len(r['differential_pairs'])==3,'Incomplete IO exact coverage')
            require(all(all(x.get(k) is not None for k in ['internal_bank','pin','VCCIO','IOSTANDARD','VREF','termination','drive']) for x in rows),'IO internal-bank/electrical gap')
        else:
            require(r.get('replacement_clock_sha256')==sha(HERE/'constraints/clock.fdc') and r.get('measured') is True,'Unmeasured/wrong replacement clock')
            require(r.get('retained_clock_pairs')==load(HERE/'coverageproof.json')['retained_clock_pairs'],'Reload relation sets differ')
    return enable
