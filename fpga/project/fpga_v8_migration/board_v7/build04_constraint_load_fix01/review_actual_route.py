"""Independent actual route audit and concrete failing-path/site handoff."""
import sys,json,re,time
from pathlib import Path
sys.dont_write_bytecode=True
import runner as r
import continue_map_pnr as c
from binding_review import review
from native_audit import messages
E=r.E;R=E/'route_attempt01'
def main():
 receipt=json.loads((E/'route01_global10_receipt.json').read_bytes())
 assert receipt['rc']==0 and not receipt['errors'],'Only consume complete native reports'
 mbreceipt=json.loads((E/'route01_mailbox1280_receipt.json').read_bytes())
 assert mbreceipt['rc']==0 and not mbreceipt['errors']
 review(E/'mapping_native/analysis/graph.json',E/'mapping_native_CDB_raw.txt',1280,R/'mapping_exact_binding_review.json')
 binding=review(R/'native/analysis/graph.json',R/'native_CDB_raw.txt',1280,R/'PNR_exact_binding_review.json')
 report=R/'global10/report_timing/v7_sdt_top.rtr';raw=report.read_bytes();ss=c.summary(raw);paths=c.paths(raw)
 assert set(ss)=={a+' '+b for a in ['Setup','Hold','Recovery','Removal','Minimum Pulse Width'] for b in ['Slow','Fast']}
 assert all(ss.values()),'Every corner/check must have native rows'
 minima={k:min(x['wns'] for x in v) for k,v in ss.items()}
 failures=[p for p in paths if p['slack']<0]
 sites=json.loads((R/'native_distinct60_sites.json').read_bytes())['rows']
 proposals=[]
 for p in sorted(failures,key=lambda x:x['slack']):
  cells={p['start'].rsplit('/',1)[0],p['end'].rsplit('/',1)[0]}
  relevant=[s for s in sites if s['routed_cell'] in cells or any(s['routed_cell'] in p['raw'] for _ in [0])]
  physical=list(dict.fromkeys(re.findall(r'\b(?:CLM[AB]|SRB|IOLHR|IOBD)_\d+_\d+',p['raw'])))
  proposals.append({'start':p['start'],'end':p['end'],'slack_ns':p['slack'],'path_type':p['fields'].get('Path Type'),'clock_skew':p['fields'].get('Clock Skew'),'related_fixed_sites':relevant,'actual_path_sites':physical,'adjustment_candidate':'评估相关launch/capture固定site靠近并平衡同一时钟树分支；保留60个唯一目标与原始attempt，候选site须另行官方合法性验证。' if relevant else '该最差路径无直接固定60site命中；先评估其原生clock skew及实际路径site，再决定placement/route参数。'})
 with (R/'failing_paths_site_candidates.json').open('x',encoding='ascii') as f:json.dump({'minima_ns':minima,'paths':proposals,'actual_report_sha256':r.sha(report),'constraints_changed':False},f,indent=2)
 expected={(p['launch_CLK'],p['capture_D'],corner) for p in binding['rows'] for corner in ['slow','fast']}
 mbreport=R/'mailbox1280/report_timing/v7_sdt_top.rtr';mb=c.paths(mbreport.read_bytes())
 scored=[p for p in mb if (p['start'],p['end'],p['corner']) in expected]
 covered={(p['start'],p['end'],p['corner']) for p in scored if p['MaxDelay_15_238']}
 assert covered==expected and len(scored)==2560,'Native actual 15.238 exception coverage incomplete'
 assert not re.search(rb'^\s*cmos[1-4]_pclk\s+asynchronous',raw,re.M)
 assert re.search(rb'^\s*ddrphy_sysclk\s+131\.2500\s+MHz',raw,re.M)
 src=json.loads((E/'sourcehash.json').read_bytes());assert len(src['hashes'])==741
 assert all(r.sha(r.W/n)==h for n,h in src['hashes'].items())
 registered=json.loads((E/'registration186.json').read_bytes());assert len(registered)==186
 messages();r.guard()
 passed=all(v>=0 for v in minima.values()) and all(p['slack']>=0 for p in scored)
 result={'timing_pass':passed,'minima_ns':minima,'1280_unique_pair_budget_binding':True,'2560_corner_exception_coverage':True,'source741_byte_equal':True,'registration186':True,'PNR_ADF_sha256':r.sha(R/'work/place_route/v7_sdt_top_pnr.adf'),'bit_generated':False,'remote_operation':False,'retention_audit':'native_IO112_comparison.json and HSST_motion_retention.json','failing_path_count':len(failures)}
 with (R/'INDEPENDENT_ACTUAL_REVIEW.json').open('x',encoding='ascii') as f:json.dump(result,f,indent=2)
 text='真实新MAP/PNR独立核验：'+('时序PASS' if passed else '时序FAIL')+'\n\n'+json.dumps(minima,ensure_ascii=False)+'\n\n原生1280 unique预算绑定和2560角点exception覆盖均已核验；源码741字节一致/登记186。未bit、未远端。\n'
 if proposals:
  p=proposals[0];text+='\n最差实际路径：'+p['start']+' → '+p['end']+'；slack '+str(p['slack_ns'])+' ns；clock skew '+str(p['clock_skew'])+'。相关site候选见 failing_paths_site_candidates.json，尚未改sites。\n'
 (R/'INDEPENDENT_RESULT_ZH.md').write_text(text,encoding='utf-8')
 print(text,flush=True)
if __name__=='__main__':main()
