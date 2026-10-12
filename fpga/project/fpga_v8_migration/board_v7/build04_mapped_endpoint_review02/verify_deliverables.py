"""Independently check produced evidence and protected inputs; no PDS calls."""
from pathlib import Path
import json,hashlib,shutil
H=Path(__file__).resolve().parent;B=H.parent/'source_diagnostics_timing_build_04';E=B/'evidence/runtime/mapping60_01'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
before=load(H/'before_hashes.json');after=load(H/'after_hashes.json')
assert before==after
assert all(sha(p)==v for p,v in before.items())
rr=load(H/'rows60.json');rows=rr['rows'];g=load(E/'mapping/analysis/graph.json')
assert len(rows)==60 and len({x['cell'] for x in rows})==60
assert len({g['pin_net'][x['Q']] for x in rows})==60
assert len({x['planned_site'] for x in rows})==60
assert all(not x['errors'] and [k for k,v in x['checks'].items() if not v]==['official_gop_behavior_decoded'] for x in rows)
lut=[x for x in rows if x['type']=='gopLUT6Q_Cell_139'];assert len(lut)==12
assert all(len(x['complete_LUT_truth_table'])==64 and all(v['actual']==v['I'][0] for v in x['complete_LUT_truth_table']) and len(x['reachable_truth_table'])==32 and all(v['actual']==0 for v in x['reachable_truth_table']) for x in lut)
pairs=load(H/'adjacent_Q_D.json');assert len(pairs['rows'])==36
assert all(g['pin_net'][x['previous_Q']]==g['pin_net'][x['capture_D']] for x in pairs['rows'])
assert sha(H/'native_reparse/analysis/graph.json')==sha(E/'mapping/analysis/graph.json')
assert sha(H/'native_reparse/analysis/parse_objects.py')==sha(E/'mapping/analysis/parse_objects.py')
assert sha(H/'native_reparse/synthesis_export/synthesis_dump.txt')==sha(E/'mapping/synthesis_export/synthesis_dump.txt')
assert load(E/'final_result.json')['status']=='FAIL' and load(H/'final_result.json')['status']=='FAIL'
models=load(H/'official_model_evidence.json')
assert all(sha(p)==v['sha256'] for p,v in models['models'].items())
assert all(sha(p)==v for p,v in models['official_GTP_models'].items())
assert sha(models['packing_rule_path'])==models['packing_rule_sha256']
log=Path('C:/Users/NineSun/.local/share/opencode/shell/292d05f2ca9892d4af74cecc9a48e5b592e79454/sh_11486c76d001OXT7SfMpXSindY.out')
if log.is_file():shutil.copy2(log,H/'local_review_execution.log')
checks={'status':'PASS_EVIDENCE_INTEGRITY_ONLY','functional_audit_status':'FAIL','protected_files_verified':len(before),'exact_rows_verified':60,'LUT6Q_full_truth_tables_verified':12,'adjacency_direct_net_equality_verified':36,'reparsed_native_graph_identical':True,'parser_source_identical':True,'parser_log_original_sha256':sha(E/'mapping/analysis/parser.log'),'parser_log_review_sha256':sha(H/'native_reparse/analysis/parser.log'),'parser_logs_identical':sha(E/'mapping/analysis/parser.log')==sha(H/'native_reparse/analysis/parser.log'),'original_mapping60_FAIL_preserved':True,'local_review_log_sha256':sha(H/'local_review_execution.log') if (H/'local_review_execution.log').exists() else None}
(H/'verification_receipt.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='ascii')
print(json.dumps(checks,indent=2))
