"""Seal only this external diagnostic bundle after all real checks finish."""
import difflib,json
from setup_review import HERE,B04,PREP,BOARD,sha,save
def main():
    results={}
    for stage in ['actual','mapping60_01_mapping','compile']:
        p=HERE/f'independent_raw_{stage}.json';v=json.loads(p.read_bytes())
        assert v['status']=='PASS_OFFLINE_RAW_CONNECTIVITY_ONLY' and not v['errors'];results[stage]=v
    review=json.loads((HERE/'review_result.json').read_bytes());assert review['unique_pairs']==1280 and not review['runtime_STA_passed']
    mapped=json.loads((HERE/'mapped_1280_connectivity.json').read_bytes())
    assert len(mapped['rows'])==len({(r['launch_Q'],r['capture_D']) for r in mapped['rows']})==1280
    assert sum(len(r['logical_aliases']) for r in mapped['rows'])==1320
    assert json.loads((HERE/'constraint_draft_exact_audit.json').read_bytes())['DDR_MHz_computed']==131.25
    assert json.loads((HERE/'build01_equal_lane_structural_proof.json').read_bytes())['status']=='PASS_OFFLINE_EQUAL_TRAJECTORY_PROOF'
    oldroot=BOARD/'source_diagnostics_timing_build_01/evidence/actual'
    olddump=oldroot/'synthesis_export/synthesis_dump.txt';oldmanifest=json.loads((oldroot/'analysis/manifest.json').read_bytes())
    assert sha(olddump)==oldmanifest['source_dump_sha256']
    raw=olddump.read_bytes();bits=[240]+[480+i for i in range(32) if (0x53464401>>i)&1]
    counts={f'{bank}[{bit}]':raw.count(f'(INSTANCE \\{bank}[{bit}] '.encode()) for bank in ['mailbox','host_bank'] for bit in bits}
    assert all(v>0 for v in counts.values())
    save('build01_original_ADIF_binding.json',{'source':str(olddump),'sha256':sha(olddump),'manifest_bound_dump_sha256':oldmanifest['source_dump_sha256'],'actual_independent_instance_token_counts':counts,'note':'Instance declarations are in reusable camera CELL definitions; hierarchy expansion creates four distinct camera domains.'})
    m=json.loads((B04/'manifest.json').read_bytes());local=[]
    assert len(m['local_hashes'])==741 and len(m['registered_sources'])==186
    for rel,h in m['local_hashes'].items():
        got=sha(B04/rel);assert got==h,(rel,h,got);local.append({'path':rel,'expected':h,'actual':got})
    binding=json.loads((HERE/'input_binding.json').read_bytes());assert all(sha(p)==h for p,h in binding.items())
    oldbinding=json.loads((PREP/'fresh_graph_input_binding.json').read_bytes());previous=[]
    for p,h in oldbinding.items():assert sha(p)==h;previous.append({'path':p,'sha256':h})
    source=(PREP/'offline_fresh_synthesis/analysis/graph_adapter.py').read_text(encoding='utf8');new=(HERE/'analysis/graph_adapter.py').read_text(encoding='utf8')
    (HERE/'strict_keepbuf_adapter.diff').write_text(''.join(difflib.unified_diff(source.splitlines(True),new.splitlines(True),fromfile='read_only_original/graph_adapter.py',tofile='external_review/graph_adapter.py')),encoding='utf8')
    assert (HERE/'analysis/derive_new_constraints.py').read_bytes()==(PREP/'offline_fresh_synthesis/analysis/derive_new_constraints.py').read_bytes()
    save('final_review_receipt.json',{'status':'COMPLETE_OFFLINE_DIAGNOSTIC_WITH_FINITE_ACCEPTANCE_BLOCKERS','local_741_hashes_verified':local,'registered_sources_count':186,'full_source_copy_entry_count':len(m['full_source_copy_hashes']),'source03_boolean_same':json.loads((HERE/'source_identity.json').read_bytes())['source03_candidate_equal'],'previous_fresh_graph_hashes_verified':previous,'independent_raw_graph_checks':results,'input_drift':[],'unique_pairs':1280,'logical_bits':2048,'constant_zero_bits':728,'register_resolution_rows':1320,'shared_extra_logical_aliases':40,'frozen_derive_byte_equal':True,'frozen_expected1320_gate_passed':False,'runtime_STA_passed':False,'constraints_qualified':False,'blockers':['Independent new candidate expected-count revision required; never inherit old1320 reports.','Fresh routed1280 pairs * Slow/Fast corners exactly2560 scored MaxDelay15.238 records, plus complete2048 logical coverage and728 constant proof required.','Mapping semantics PASS, IO/full endpoint review, no-remap timing reload and real PnR/STA remain other agents/authorized future flow responsibilities.'],'pds_started':False,'remote_actions':False})
    files={str(p.relative_to(HERE)):sha(p) for p in HERE.rglob('*') if p.is_file() and p.name not in {'final_bundle_hashes.json','output_hashes.json'} and '__pycache__' not in p.parts}
    save('final_bundle_hashes.json',files)
    print('sealed',len(files),'external artifacts;741/186 verified; independent raw checks complete; runtime gate closed')
if __name__=='__main__':main()
