"""Port latest reviewed acceptance and producer with explicit local dependencies."""
from prepare03 import HERE, OLD, BOARD, load, sha, save, require
from pathlib import Path

def main():
    r=HERE/'runtime'
    require(not (r/'routed_acceptance.py').exists(),'Refuse overwrite acceptance port')
    p=OLD/'runtime/routed_acceptance.py'
    raw=p.read_text(encoding='utf-8')
    raw=raw.replace("BOARD/'build01_binding_review01/review.py'", "Path(__file__).resolve().parent/'libraries/routed_truth_reference.py.txt'")
    raw=raw[:raw.index('def audit_all(route):')]
    (r/'routed_acceptance.py').write_text(raw,encoding='utf-8')
    p=OLD/'runtime/prepare_local_delivery.py';raw=p.read_text(encoding='utf-8')
    raw=raw.replace("str(BOARD/'physical_subagent_evidence_01/audit_fixed.py')", "str(runtime/'global_audit.py')")
    raw=raw.replace("str(BOARD.parent/'whole_candidate_v2_route_01/summarize_route.py')", "str(runtime/'libraries/summarize_route.py')")
    raw=raw.replace("str(BOARD.parent/'whole_candidate_v2_route_01/audit_final.py')", "str(runtime/'libraries/raw_audit.py')")
    raw=raw.replace("str(BOARD/'build01_binding_review01/review.py')", "str(runtime/'libraries/routed_truth_reference.py.txt')")
    raw=raw.replace("load(BOARD / 'source_diagnostics_route_01/build01_guard.json')", "load(Path(__file__).resolve().parent/'baseline_data/protected_guard.json')")
    raw=raw.replace("'source_diagnostics_timing_build_02'", "'source_diagnostics_timing_build_03'")
    # Producer ends at an independent review request. The main-owned assembler
    # and consumer remain read-only audit role inputs; never imported or patched.
    raw=raw[:raw.index('    if not acceptance.is_file():')] + '''    result['status']='LOCAL_BIT_SIGNOFF_PASS_INDEPENDENT_ACCEPTANCE_REQUIRED'
    result['independent_acceptance_required']=str(acceptance)
    record('actual_result.json',result)
    status('LOCAL_BIT_PASS_WAIT_MAIN_INDEPENDENT_REVIEW_NO_DEVICE_OPERATION')
    return result
'''
    (r/'prepare_local_delivery.py').write_text(raw,encoding='utf-8')
    p=OLD/'runtime/verify_identity_adapter.py';raw=p.read_text(encoding='utf-8')
    raw=raw.replace("BOARD/'build01_binding_review01/review.py'", "HERE/'runtime/libraries/routed_truth_reference.py.txt'")
    raw=raw.replace("'build02_physical_pass'", "'build03_physical_pass'").replace("'build02_fresh_graph_test'", "'build03_fresh_graph_test'")
    raw=raw.replace("python x/diagnostic_sync_register_map_01/recover.py", "python x/board_v7/diagnostic_sync_register_map02/recover.py")
    raw=raw.replace("python x/source_diagnostics_timing_build_01/resume_actual_graph.py", "python x/board_v7/source_diagnostics_timing_build_01/resume_actual_graph.py")
    raw=raw.replace("record('identity_adapter_review.json'", "record('identity_adapter_review.json'")
    (r/'verify_identity_adapter.py').write_text(raw,encoding='utf-8')
    save('evidence/runtime_port/acceptance_port_provenance.json',{'source_hashes':{str(OLD/'runtime'/n):sha(OLD/'runtime'/n) for n in
          ['routed_acceptance.py','prepare_local_delivery.py','verify_identity_adapter.py']},
          'producer_main_import_removed':True,'main_consumer_unchanged':True,'local_only':True})

if __name__=='__main__':main()
