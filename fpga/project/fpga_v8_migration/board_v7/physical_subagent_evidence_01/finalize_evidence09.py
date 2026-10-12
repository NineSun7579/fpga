from pathlib import Path
import json,re,hashlib,collections
BASE=Path(__file__).resolve().parent
OUT=BASE/'fixed_06/physical_exact_09'
report=json.loads((OUT/'evidence/streamed_routed_coverage.json').read_bytes())
dump=(OUT/'final_export/routed_dump.txt').read_bytes()
instances={}
for m in re.finditer(rb'\(INSTANCE (\\?[^\s]+)\s+\(VIEWREF \S+ \(CELLREF (\S+)',dump):
    instances[m[1].decode('ascii').lstrip('\\')]=m[2].decode('ascii')
srl={ip:typ for ip,typ in instances.items() if ip.startswith('source_diagnostics/') and typ.startswith('gopSRL')}
mail={}
for corner in ['Slow','Fast']:
    data=report['coverage']['mailbox_'+corner]
    rows=data['records'];budget=all('MaxDelay Path 15.238ns -datapath_only' in r['exception'] for r in rows)
    endpoints=all(r['start'].rsplit('/',2)[-2]=='opit_0' and r['end'].rsplit('/',2)[-2]=='opit_0' for r in rows)
    present=all(r['start'].rsplit('/',1)[0] in instances and r['end'].rsplit('/',1)[0] in instances for r in rows)
    assert data['covered']==1320 and not data['missing'] and budget and endpoints and present and data['worst_slack']>0
    mail[corner]={'physical_pairs':1320,'canonical_equivalence_classes':1280,'worst_slack_ns':data['worst_slack'],'all_1320_have_budget':budget,'routed_instance_identity_checked':present}
sta=json.loads((OUT/'evidence/final_sta_summary.json').read_bytes())
io=json.loads((OUT/'evidence/io_audit.json').read_bytes())
hsst=json.loads((OUT/'evidence/hsst_actual_phy_audit.json').read_bytes())
guard=json.loads((BASE.parent/'source_diagnostics_route_01/build01_guard.json').read_bytes())
root=BASE.parent/'source_diagnostics_route_02';inputs=json.loads((OUT/'input_hashes.json').read_bytes());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bad=[p for p,h in guard.items() if sha(Path(p))!=h];drift=[p for p,h in inputs.items() if sha(root/p)!=h]
route=root/'place_route/v7_sdt_top_pnr.adf';receipt=json.loads((OUT/'pnr_artifact.json').read_bytes());assert sha(route)==receipt['sha256'] and not bad and not drift
result={'routed_db':str(route),'routed_sha256':sha(route),'routed_bytes':route.stat().st_size,'mailbox_passed':True,'mailbox':mail,'io_passed':io['passed'],'hsst_passed':hsst['sites_identical_to_baseline'] and hsst['dedicated_connections_identical_to_baseline'],'motion_ram_slices':32,'ten_groups_passed':False,'ten_groups':[{'section':s['section'],'corner':s['corner'],'failing_endpoints':s['sum_failing_endpoints'],'worst_slack':min(r['worst_slack_ns'] for r in s['rows'])} for s in sta['all_corner_summaries']],'new_cdc_passed':False,'diagnostic_srl_instances':srl,'reset_observed_recovery_worst_ns':min(v['worst_slack'] for k,v in report['reset'].items() if k.endswith('Recovery')),'sync_later_coverage_per_corner':4,'sync_later_expected':16,'protected_files':len(guard),'protected_mismatches':bad,'input_mismatches':drift,'bit_permitted':False,'bit_generated':False,'remote_or_program':False,'remaining':['Repair setup/recovery timing with source-backed CDC/reset analysis','Prevent/validate SRL mapping of diagnostic synchronizer and reset chains','Complete independent later-stage/reset timing coverage after mapping repair','Repeat full acceptance before generating local bit']}
(OUT/'acceptance_gates.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['ten_groups','diagnostic_srl_instances','remaining']},indent=2));print('Diagnostic SRL mappings',len(srl))
