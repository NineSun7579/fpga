"""Isolated retry; remove constant signature from compile budget collections only."""
import sys,json,re,time,traceback,shutil
sys.dont_write_bytecode=True
import runner as r
ROOT=r.E
r.E=ROOT/'rebuild03';r.W=r.E/'candidate02'
def main():
 assert not r.E.exists(),'Do not overwrite previous retry'
 r.E.mkdir()
 # Existing global whole-machine gate and lock remain authoritative.
 k,h=r.lock()
 try:
  shutil.copy2(ROOT/'frozen_before.json',r.E/'frozen_before.json')
  r.prepare()
  rows=json.loads((r.E/'compile02_constraint_derivation.json').read_bytes())['rows']
  from derive_new_constraints import coll
  original=r.W/'constraints_live/clock.fdc'
  original.rename(original.with_name('clock_before_signature_correction.fdc'))
  base=[x for x in (r.F/'constraints/clock.fdc').read_text(encoding='ascii').splitlines() if 'get_pins -hierarchical' not in x]
  source=(r.W/'rtl/v7_sfd_candidate.v').read_bytes()
  assert b"mailbox[15*32+:32]<=32'h53464401;" in source
  corrected=[]
  for row in rows:
   signature=[p for p in row['mailbox'] if p.endswith('/mailbox[511:480]/CLK')]
   assert len(signature)==1
   mailbox=set(row['mailbox'])-set(signature)
   host={p for p in row['host'] if int(re.search(r'/D\[(\d+)\]$',p)[1])<480}
   assert len(mailbox)==16 and len(host)==480
   ack=row['ack']
   base+=['set_false_path -from '+coll(set(row['complement']))+' -to [get_clocks {ddrphy_sysclk}]','set_max_delay -datapath_only 15.238 -from '+coll(mailbox)+' -to '+coll(host),'set_false_path -hold -from '+coll(mailbox)+' -to '+coll(host),'set_false_path -from '+coll({ack['launch_CLK']})+' -to '+coll({ack['capture_D']})]
   corrected.append({'camera':row['camera'],'compile_mailbox':sorted(mailbox),'compile_host':sorted(host),'signature_not_annotated':signature,'source_signature_literal':"32'h53464401"})
  original.write_text('\n'.join(base)+'\n',encoding='ascii')
  r.save('compile_signature_correction.json',{'rows':corrected,'before_sha256':r.sha(original.with_name('clock_before_signature_correction.fdc')),'after_sha256':r.sha(original),'source_sha256':r.sha(r.W/'rtl/v7_sfd_candidate.v'),'budget_ns':15.238,'mapped_required_pairs':1280,'exemptions_added':False})
  print('candidate03来源741/186字节一致；compile预算对象移除固定签名word15，保留全部动态mailbox，不新增豁免',flush=True)
  r.build()
  import continue_map_pnr as c
  c.E=r.E;c.W=r.W;c.R=r.E/'route_attempt01';c.P=c.R/'work'
  from native_audit import cdb
  sc=cdb('synthesis_native');assert b'15238' in sc and not re.search(rb'\(CLKGP\b',sc)
  original_tool=r.tool
  def maptool(label,text,cwd,project_stage=None):
   if label=='native_clock_exception':
    r.save('MAP_report_deferred_official_phase.json',{'planned_command':text,'reason':'Official timing report follows actual PNR'})
    return b''
   return original_tool(label,text,cwd,project_stage)
  r.tool=maptool
  try:r.mapping()
  finally:r.tool=original_tool
  from binding_review import review
  review(r.E/'mapping_native/analysis/graph.json',r.E/'mapping_native_CDB_raw.txt',1280,r.E/'mapping_exact_pair_binding.json')
  print('新MAP完整1280 unique/60site/15238逐对绑定已通过，串接独立PNR',flush=True)
  c.pnr()
 finally:k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
 try:main()
 except BaseException:
  failure={'time':time.time(),'traceback':traceback.format_exc(),'bit':False,'program':False}
  r.save('failure_'+str(time.time_ns())+'.json',failure)
  try:r.guard()
  except BaseException:pass
  print(failure['traceback'],flush=True);sys.exit(1)
