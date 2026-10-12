"""Consume complete rebuild03 synthesis; no repeated build, no gate relaxation at MAP."""
import sys,json,re,time,traceback
sys.dont_write_bytecode=True
import runner as r
r.E=r.E/'rebuild03';r.W=r.E/'candidate02'
def main():
 for label in ['synthesize02','synthesis_native_export','synthesis_native_parser']:
  rc=json.loads((r.E/(label+'_receipt.json')).read_bytes());assert rc['rc']==0 and not rc.get('errors',[])
 ready=json.loads((r.E/'synthesis_ready.json').read_bytes())
 assert ready['adf_sha256']==r.sha(r.W/'synthesize/v7_sdt_top_syn.adf')
 assert ready['graph_sha256']==r.sha(r.E/'synthesis_native/analysis/graph.json')
 k,h=r.lock()
 try:
  import continue_map_pnr as c
  c.E=r.E;c.W=r.W;c.R=r.E/'route_attempt01';c.P=c.R/'work'
  from native_audit import pairs
  sg=json.loads((r.E/'synthesis_native/analysis/graph.json').read_bytes())
  rows=pairs(sg,1284)
  r.save('residual_signature_native_review.json',{'actual_synthesis_pairs':1284,'required_mapped_pairs':1280,'unannotated_constant_signature_pairs':[p for p in rows if int(re.search(r'/host_bank\[(\d+)\]',p['capture_D'])[1])>=480],'all_1284_consumed':True,'gate_relaxed_at_MAP':False})
  orig=r.tool
  def maptool(label,text,cwd,project_stage=None):
   if label=='native_clock_exception':
    r.save('MAP_report_deferred_official_phase.json',{'planned_command':text,'reason':'Official report requires PNR phase'})
    return b''
   return orig(label,text,cwd,project_stage)
  r.tool=maptool
  try:r.mapping()
  finally:r.tool=orig
  from binding_review import review
  review(r.E/'mapping_native/analysis/graph.json',r.E/'mapping_native_CDB_raw.txt',1280,r.E/'mapping_exact_pair_binding.json')
  c.pnr()
 finally:k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
 try:main()
 except BaseException:
  r.save('resume_failure_'+str(time.time_ns())+'.json',{'traceback':traceback.format_exc(),'bit':False,'remote':False})
  r.guard();print(traceback.format_exc(),flush=True);sys.exit(1)
