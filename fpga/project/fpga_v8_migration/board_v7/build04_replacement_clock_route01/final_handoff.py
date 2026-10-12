from pathlib import Path
import json,re,hashlib,time
from collect_actual import critical,summary,tables
E=Path(__file__).resolve().parent;BOARD=E.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,o):
 with (E/n).open('x',encoding='ascii') as f:json.dump(o,f,indent=2,ensure_ascii=True)
def main():
 if not (E/'TA_disable_single_rawreceipt.json').exists():raise RuntimeError('Target tool sequence incomplete')
 pairs=json.loads((E/'fresh_mailbox_pairs_v2.json').read_bytes());expected={(r['start'],r['end'],c) for r in pairs['pairs'] for c in ['Slow','Fast']};scored=set();reports=[]
 for p in (E/'reports').rglob('*.rtr'):
  raw=p.read_bytes();records=critical(raw);local=set()
  for r in records:
   cm=re.search(r'\b(slow|fast) corner\b',r.get('Path Type',''),re.I)
   key=(r.get('Startpoint','').split(' (')[0],r.get('Endpoint','').split(' (')[0],cm[1].capitalize() if cm else None)
   if key in expected and 'max' in r.get('Timing Exception','').lower() and '15.238' in r['raw']:local.add(key)
  if 'mailbox1280_actual' in p.parts:scored.update(local)
  reports.append({'path':str(p),'sha256':sha(p),'native_summaries':summary(raw),'scored_records':records,'MaxDelay15_238_exact_pair_corners':len(local),'old_camera_async':[i for i in range(1,5) if re.search(rb'^\s*cmos'+str(i).encode()+rb'_pclk\s+asynchronous\s+cmos'+str(i).encode()+rb'_pclk\s*$',raw,re.M)]})
 save('fresh_STA_target_receipts.json',{'reports':reports,'expected_unique_pairs':1280,'expected_pair_corners':2560,'scored_pair_corners_with_actual_MaxDelay15_238':len(scored),'missing_pair_corners':sorted(expected-scored),'coverage_complete':scored==expected,'fresh_route_sha256':sha(E/'work/place_route/v7_sdt_top_pnr.adf'),'prohibition':'No no_check, no report replacement, no credit for untimed/cut paths'})
 b=BOARD/'source_diagnostics_timing_build_04';manifest=json.loads((b/'manifest.json').read_bytes())
 drift=[n for n,h in manifest['full_source_copy_hashes'].items() if sha(b/n)!=h];registered=[x.decode() for x in re.findall(rb'\(_file "([^"]+)"',(b/'project.pds').read_bytes()) if x.startswith((b'rtl/',b'inputs/'))]
 save('source_current_validation.json',{'local741':len(manifest['local_hashes']),'full_source_files':len(manifest['full_source_copy_hashes']),'registered186':len(registered),'registration_equal':registered==manifest['registered_sources'],'source_drift':drift})
 sta=json.loads((E/'native_STA_actual.json').read_bytes());global_result=next(x for x in sta if 'global10' in x['path'])
 sites=json.loads((E/'fresh_distinct60_sites_v3.json').read_bytes());ret=json.loads((E/'HSST_motion_native_retention_v3.json').read_bytes());io=json.loads((E/'native_IO112_comparison.json').read_bytes())
 ta=(E/'TA_disable_single.log').read_bytes();ta_errors=[x.decode('ascii','backslashreplace') for x in ta.splitlines() if re.search(rb'^\s*E:|Flow-0110|Timing-4006|STA-3016',x)]
 single_ta=json.loads((E/'TA_native_single_actual_rawreceipt.json').read_bytes());single_log=(E/'TA_native_single_actual.log').read_bytes()
 single_ta['actual_errors']=[x.decode('ascii','backslashreplace') for x in single_log.splitlines() if re.search(rb'^\s*E:',x)]
 single_ta['scope']='Three relevant clocks and actual native single-pair pins loaded successfully; STA crashed with missing physical timing models; no measured 15.238 pass'
 native_CDB=(E/'native_CDB_raw.txt').read_bytes();pnr=json.loads((E/'pnr_rawreceipt.json').read_bytes())
 result={'schema':'actual-replacement-clock-PNR-handoff/v1','PNR_completed':pnr['rc']==0,'PNR_seconds':pnr['end']-pnr['start'],'source_mapADF_sha256':sha(E/'work/device_map/v7_sdt_top_map.adf'),'fresh_PNR_sha256':sha(E/'work/place_route/v7_sdt_top_pnr.adf'),'replacement_clock_file_sha256':sha(E/'work/constraints/clock.fdc'),'CDB_contains_15238':b'15238' in native_CDB,'old_camera_async_in_actual_global10':global_result['old_camera_async'],'clock_replacement_verified':False,'STA_minima_ns':global_result['minima'],'actual60_distinct_storage':sites['distinct_cells'],'actual60_distinct_sites':sites['distinct_sites'],'native_PCF_site_matches':sites['site_match_rows'],'mailbox1280_fresh_bindings':pairs['resolved'],'mailbox2560_MaxDelay_actual_coverage':len(scored),'IO112_native':io['ports'],'IO_comparisons':io['comparisons'],'motion32_parameters_retained':len(ret['motion_rows'])==32 and all(x['parameters_equal'] and x['ports_equal'] for x in ret['motion_rows']),'HSST_native_retention':ret['HSST_rows'],'TA_single_probe_errors':ta_errors,'bit_eligible':False,'bit_generated':False,'programmed':False,'board_access':False,'acceptance':'FAIL: actual timing CDB still has old asynchronous camera groups and no replacement MaxDelay; same-domain setup/hold/removal violations remain','collector_failures_preserved':['failure.json','routed/analysis/parse_objects.py initial premature partial-copy parse; replaced by completed official export receipt and routed02 parser output','fresh_mailbox_pairs.json five buffers resolved in v2','fresh_distinct60_sites_v2.json native escaped PLACE tokens decoded in v3']}
 save('actual_review_handoff.json',result)
 save('official_TA_native_single_failure.json',single_ta)
 hashes={str(p.relative_to(E)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in E.rglob('*') if p.is_file() and p.name!='evidence_hashes_final.json'};save('evidence_hashes_final.json',hashes)
 print('PNR COMPLETE; REAL ACCEPTANCE FAIL; PAIR_CORNERS',len(scored),'MINIMA',global_result['minima'])
if __name__=='__main__':main()
