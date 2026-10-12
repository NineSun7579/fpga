from probe import E,sha,save
from pathlib import Path
import re,json,time
p=E/'probes/mapped_graph01/mapped_dump.txt';s=p.read_bytes()
start=s.rfind(b'\n  (CDB ');end=s.find(b'\n  (UATTR ',start)
assert start>=0 and end>start
cdb=s[start:end];out=E/'mapped_native_CDB_raw.txt'
with out.open('xb') as f:f.write(cdb)
rows=[]
for m in re.finditer(rb'\(CLKGP\s*\n(?:(?!\n    \)).)*\n    \)',cdb,re.S):
 block=m.group();name=re.search(rb'\(NAME\s+"?([^"\)]+)',block)
 rows.append(dict(name=name.group(1).decode().strip(),async_value=bool(re.search(rb'\(ASYNC 1\)',block)),raw=block.decode('ascii')))
def raw(p):return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p))
summary=dict(time=time.time(),all_local_queues_completed=True,tool_sequence=['help01','mapped_reload01','ta_help01','ta_mapped01','ta_diagnostic01','diagnostic_reload01 (mutex busy; no tool)','diagnostic_reload02','ta_diagnostic02','mapped_graph01','ta_commands01','diagnostic_cdb01'],mapped_ADF_actual_graph_export=True,map_adf_sha256=sha(E/'inputs/device_map/v7_sdt_top_map.adf'),mapped_graph=raw(p),mapped_CDB=raw(out),mapped_old_async_groups=rows,mapped_CDB_budget15_238_present=b'15.238' in cdb,TA_inventory_executed=False,TA_attempt_rcs={n:json.loads((E/'probes'/n/'receipt.json').read_bytes())['exit_code'] for n in ['ta_mapped01','ta_diagnostic01','ta_diagnostic02','ta_commands01']},reported_CDB_export=dict(exit_code=0,expected_output_exists=(E/'probes/diagnostic_cdb01/reported_dump.txt').exists(),accepted=False,limitation='RTP ADF .switch_db returned success without producing requested graph file; no CDB proof inferred'),coverage_all_unverified=True,gate_eligible=False,production_reload_proven=False,implicit_prerequisite_reruns=False,protected_input_hash_count=2710,protected_input_drift=[],bit=False,remote=False,flash=False)
save(E/'followup_summary.json',summary)
gap=json.loads((E/'timing_reload_gaps.json').read_bytes())
for k,v in gap['coverage'].items():v['raw_files'] += [raw(out),raw(p),raw(E/'followup_summary.json')]
gap['coverage']['CDB_raw_binding']['method']+=' Successful official .switch_db real MAP graph export includes original native CDB with all four old async groups and original DDR MCP entries; no replacement CDB claimed.'
gap['coverage']['mapped_graph_unchanged']['method']+=' Actual mapped graph exported independently after real attempts; mapADF/native source/copy hashes identical; successful reload remains unsupported.'
save(E/'timing_reload_gaps_final.json',gap)
save(E/'evidence_hashes_followup.json',[raw(p) for p in E.rglob('*') if p.is_file() and p.name!='evidence_hashes_followup.json'])
print('FINAL: real mapped graph/CDB exported; production replacement reload blocked; all nine coverage false')
