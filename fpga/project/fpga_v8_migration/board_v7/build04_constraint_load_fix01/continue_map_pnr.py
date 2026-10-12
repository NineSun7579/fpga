"""Durable serial continuation: wait existing build, fresh MAP, isolated real PNR, reports."""
from pathlib import Path
import sys,os,time,json,ctypes,shutil,re,subprocess,traceback,xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
import runner as r
from native_audit import cdb,pairs,sites
E=r.E;W=r.W;BOARD=r.BOARD;R=E/'route_attempt01';P=R/'work'
sha=r.sha
def save(name,obj):
 if (E/name).exists():
  p=Path(name);name=str(p.with_name(p.stem+'_retry_'+str(time.time_ns())+p.suffix))
 return r.save(name,obj)
def wait_build(pid):
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_bool,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
 k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.OpenProcess(0x100000,False,pid)
 save('continuation_wait_binding.json',{'existing_build_pid':pid,'continuation_pid':os.getpid(),'started':time.time(),'handle_opened':bool(h)})
 if h:
  last=0
  try:
   while k.WaitForSingleObject(h,3000)==258:
    if time.time()-last>30:
     print('串行等待既有build controller退出：PID '+str(pid)+'；不重启、不争抢PDS',flush=True);last=time.time()
  finally:k.CloseHandle(h)
 assert (E/'synthesis_ready.json').is_file(),'Existing build did not complete successful synthesis/export'
 receipt=json.loads((E/'synthesize02_receipt.json').read_bytes());assert receipt['rc']==0 and not receipt['errors']
 exportreceipt=json.loads((E/'synthesis_native_export_receipt.json').read_bytes());assert exportreceipt['rc']==0 and not exportreceipt['errors']
 assert json.loads((E/'synthesis_native_parser_receipt.json').read_bytes())['rc']==0
 print('既有build已退出，真实synthesis/export/graph receipts完成',flush=True)
def route_save(name,obj):
 p=R/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='ascii') as f:json.dump(obj,f,indent=2,ensure_ascii=True)
def stage_tool(label,text,cwd):return r.tool('route01_'+label,text,cwd)
def export_route(adf):
 dest=R/'native';ana=dest/'analysis';dump=dest/'synthesis_export/synthesis_dump.txt'
 ana.mkdir(parents=True);dump.parent.mkdir()
 stage_tool('export',r.ARCH+'.switch_db -input {'+adf.as_posix()+'} -output {'+dump.as_posix()+'}\n',dest)
 shutil.copy2(r.B/'runtime/analysis_tools/parse_objects.py',ana/'parse_objects.py')
 result=subprocess.run([sys.executable,'-B',str(ana/'parse_objects.py')],cwd=ana,capture_output=True)
 (ana/'parser.log').write_bytes(result.stdout+result.stderr)
 route_save('native_parser_receipt.json',{'rc':result.returncode,'dump_sha256':sha(dump),'ADF_sha256':sha(adf)})
 assert result.returncode==0,'Routed graph parser failed'
 return json.loads((ana/'graph.json').read_bytes()),dump
def raw_cdb(dump):
 raw=dump.read_bytes();start=raw.find(b'(CDB ');assert start>=0;depth=0;stop=None
 for m in re.finditer(rb'"(?:[^"\\]|\\.)*"|[()]',raw[start:]):
  if m[0]==b'(':depth+=1
  elif m[0]==b')':
   depth-=1
   if depth==0:stop=start+m.end();break
 assert stop is not None
 c=raw[start:stop];p=R/'native_CDB_raw.txt';p.write_bytes(c)
 route_save('native_CDB_binding.json',{'dump_sha256':sha(dump),'CDB_sha256':sha(p),'start':start,'end':stop,'contains_15238':b'15238' in c,'old_CLKGP':bool(re.search(rb'\(CLKGP\b',c))})
 assert b'15238' in c and not re.search(rb'\(CLKGP\b',c),'Actual routed CDB replacement failed'
 return c
def pinlist(pp):return '{'+' '.join('{'+p+'}' for p in sorted(set(pp)))+'}'
def summary(raw):
 out={};kind=None
 for line in raw.splitlines():
  m=re.match(rb'\s*(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):',line)
  if m:kind=m[1].decode()+' '+m[2].decode();out[kind]=[];continue
  if kind:
   vals=line.split();size=5 if kind.startswith('Minimum Pulse') else 6
   if len(vals)==size:
    try:out[kind].append({'launch':vals[0].decode(),'capture':vals[1].decode() if size==6 else vals[0].decode(),'wns':float(vals[-4]),'tns':float(vals[-3]),'failing_endpoints':int(vals[-2]),'total_endpoints':int(vals[-1])})
    except ValueError:pass
   if line.startswith(b'='):kind=None
 return out
def paths(raw):
 rows=[]
 for chunk in re.split(rb'(?=^\s*Startpoint\s*:)',raw,flags=re.M):
  a=re.search(rb'^\s*Startpoint\s*:\s*(\S+)',chunk,re.M);b=re.search(rb'^\s*Endpoint\s*:\s*(\S+)',chunk,re.M)
  slack=re.search(rb'Slack\s*\((MET|VIOLATED)\)\s+(-?\d+(?:\.\d+)?)',chunk)
  if not a or not b or not slack:continue
  fields={}
  for field in ['Path Type','Path Class','Timing Exception','Clock Skew']:
   match=re.search(rb'^\s*'+field.encode()+rb'\s*:\s*([^\r\n]+)',chunk,re.M)
   if match:fields[field]=match[1].decode('ascii','backslashreplace').strip()
  corners=re.search(rb'Path Type\s*:\s*max\s*\((slow|fast) corner\)',chunk,re.I)
  rows.append({'start':a[1].decode(),'end':b[1].decode(),'slack':float(slack[2]),'corner':corners[1].decode().lower() if corners else None,'fields':fields,'MaxDelay_15_238':bool(re.search(rb'(?:MaxDelay|Max Delay|max_delay)[^\r\n]*15\.238',chunk,re.I)),'raw':chunk.decode('ascii','backslashreplace')})
 return rows
def verify60(g,dump):
 planned=json.loads((E/'native60_site_binding.json').read_bytes())['rows'];raw=dump.read_bytes();placements={}
 pattern=rb'\(INSTANNOTATE\s+\(INSTREF\s+([^\s)]+)\s*\)\s+\(PLACE\s+([^\s]+)\s+\(DEVINSTREF\s+([^\s]+)\s+\(SITEREF\s+(\d+)\s+(\d+)'
 for m in re.finditer(pattern,raw):placements.setdefault(m[1].decode().lstrip('\\'),[]).append(m[3].decode()+'_'+m[4].decode()+'_'+m[5].decode())
 rows=[]
 for item in planned:
  target=item['source'];cand=[c for c,rec in g['primitives'].items() if (c==target or c.startswith(target+'/')) and c+'/CLK' in g['pin_net'] and c+'/D' in g['pin_net'] and c+'/Q' in g['pin_net']]
  assert len(cand)==1,('Routed storage target mismatch',item,cand)
  cell=cand[0];actual=sorted(set(placements.get(cell,[])))
  rows.append({**item,'routed_cell':cell,'native_sites':actual,'passed':actual==[item['site']]})
 route_save('native_distinct60_sites.json',{'rows':rows,'distinct_storage':len({x['routed_cell'] for x in rows}),'distinct_sites':len({s for x in rows for s in x['native_sites']}),'site_matches':sum(x['passed'] for x in rows)})
 assert len(rows)==60 and len({x['routed_cell'] for x in rows})==60 and all(x['passed'] for x in rows),'Routed 60 sites differ'
 return placements
def io_retention(g,placements):
 db=P/'place_route/prr.db';raw=db.read_bytes()
 m=re.search(rb'<table\b[^>]*\bid="pnr_io_report"[^>]*>.*?</table>',raw,re.S);assert m
 (R/'native_IO112_raw.xml').write_bytes(m[0]);tree=ET.fromstring(m[0]);headers=[d.text or '' for d in tree.findall('column_headers/data')]
 rows=[[d.text or '' for d in row.findall('data')] for row in tree.findall('row')];assert len(rows)==112
 baseline=BOARD/'source_diagnostics_timing_build_01/place_route/prr.db';bm=re.search(rb'<table\b[^>]*\bid="pnr_io_report"[^>]*>.*?</table>',baseline.read_bytes(),re.S);assert bm
 base=ET.fromstring(bm[0]);bh=[d.text or '' for d in base.findall('column_headers/data')];br={row.findall('data')[0].text:dict(zip(bh,[d.text or '' for d in row.findall('data')])) for row in base.findall('row')}
 differences=[]
 for row in rows:
  for key,value in dict(zip(headers,row)).items():
   if br.get(row[0],{}).get(key)!=value:differences.append({'port':row[0],'field':key,'baseline':br.get(row[0],{}).get(key),'fresh':value})
 route_save('native_IO112_comparison.json',{'native_table_sha256':sha(R/'native_IO112_raw.xml'),'baseline':str(baseline),'baseline_sha256':sha(baseline),'table_bytes_equal':m[0]==bm[0],'differences':differences,'ports':len(rows)})
 mapped=json.loads((E/'mapping_native/analysis/graph.json').read_bytes());motion=[];hsst=[]
 def params(rec):
  out={}
  def walk(v):
   if isinstance(v,list):
    if v and v[0]=='PARAMETER':out[v[1]]=v[2:]
    else:
     for q in v:walk(q)
  walk(rec.get('default_parameters',[]));walk(rec.get('parameters',[]));return out
 for cell,rec in mapped['primitives'].items():
  ar=g['primitives'].get(cell)
  if 'u_motion_tap/u_detector/history_' in cell and rec['type'].startswith('gopDRM'):
   motion.append({'cell':cell,'parameters_equal':bool(ar and params(ar)==params(rec)),'ports_equal':bool(ar and ar['ports']==rec['ports']),'native_sites':placements.get(cell,[])})
  if cell.endswith('/gophsst'):
   hsst.append({'cell':cell,'parameters_equal':bool(ar and params(ar)==params(rec)),'native_sites':placements.get(cell,[])})
 route_save('HSST_motion_retention.json',{'motion':motion,'HSST':hsst,'motion_count':len(motion),'HSST_count':len(hsst)})
 return not differences and m[0]==bm[0] and len(motion)==32 and len(hsst)==5 and all(x['parameters_equal'] and x['ports_equal'] for x in motion) and all(x['parameters_equal'] and x['native_sites']==['HSSTLP_364_918'] for x in hsst)
def pnr():
 assert not R.exists(),'Refuse existing route attempt'
 R.mkdir();P.mkdir();copies=[]
 for folder in ['compile','synthesize','device_map']:
  shutil.copytree(W/folder,P/folder)
  for q in (W/folder).rglob('*'):
   if q.is_file():
    dest=P/folder/q.relative_to(W/folder);assert sha(q)==sha(dest);copies.append({'source':str(q),'copy':str(dest),'sha256':sha(q)})
 route_save('fresh_stage_copyhash.json',copies)
 sourceguards={str(p):sha(p) for p in W.rglob('*') if p.is_file()}
 route_save('candidate02_before_route.json',sourceguards)
 adf=P/'device_map/v7_sdt_top_map.adf';pcf=P/'device_map/v7_sdt_top.pcf'
 helpraw=(BOARD/'build04_diagnostic_behavior_route01/help.log').read_bytes()
 for option in [b'-fix_hold_violation_in_route',b'-fix_hold_violation_iterations',b'-optimize_multi_corner_timing',b'-fix_hold_violation',b'-report_timing']:assert option in helpraw
 route_save('official_PNR_option_binding.json',{'help':str(BOARD/'build04_diagnostic_behavior_route01/help.log'),'help_sha256':sha(BOARD/'build04_diagnostic_behavior_route01/help.log'),'iterations':12,'route_holdfix':True,'fresh_mapADF':str(adf),'fresh_mapADF_sha256':sha(adf)})
 text=r.ARCH+'add_constraint {'+pcf.as_posix()+'}\npnr -force_to_run -input_db_file {'+adf.as_posix()+'} -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_in_route TRUE -fix_hold_violation_iterations 12 -report_timing\n'
 print('新map/PCF隔离复制完成；开始真实PNR，multi_corner + route holdfix，iterations=12',flush=True)
 stage_tool('pnr',text,P)
 routed=P/'place_route/v7_sdt_top_pnr.adf';assert routed.is_file()
 g,dump=export_route(routed);raw_cdb(dump);pp=pairs(g)
 route_save('native_mailbox_pairs1280.json',{'rows':pp,'unique':len({(x['launch_CLK'],x['capture_D']) for x in pp}),'graph_sha256':sha(R/'native/analysis/graph.json')})
 placements=verify60(g,dump);retained=io_retention(g,placements)
 stage_tool('global10',r.ARCH+'report_timing -force_to_run -input_db_file {'+routed.as_posix()+'} -delay_type min_max -report_exception TRUE -max_path 10 -nworst 1\n',R/'global10')
 stage_tool('mailbox1280',r.ARCH+'report_timing -force_to_run -input_db_file {'+routed.as_posix()+'} -delay_type max -report_exception TRUE -input_pins TRUE -max_path 2560 -nworst 1 -from '+pinlist(x['launch_CLK'] for x in pp)+' -to '+pinlist(x['capture_D'] for x in pp)+'\n',R/'mailbox1280')
 report=R/'global10/report_timing/v7_sdt_top.rtr';raw=report.read_bytes();ss=summary(raw);critical=paths(raw);minima={key:min((x['wns'] for x in values),default=None) for key,values in ss.items()}
 mbreport=R/'mailbox1280/report_timing/v7_sdt_top.rtr';mb=paths(mbreport.read_bytes());expected={(x['launch_CLK'],x['capture_D'],corner) for x in pp for corner in ['slow','fast']}
 scored=[x for x in mb if (x['start'],x['end'],x['corner']) in expected]
 coverage={(x['start'],x['end'],x['corner']) for x in scored if x['MaxDelay_15_238']}
 old_async=[i for i in range(1,5) if re.search(rb'^\s*cmos'+str(i).encode()+rb'_pclk\s+asynchronous',raw,re.M)]
 ddr=bool(re.search(rb'^\s*ddrphy_sysclk\s+131\.2500\s+MHz',raw,re.M))
 route_save('native_STA_actual.json',{'summaries':ss,'minima_ns':minima,'critical_paths':critical,'report_sha256':sha(report),'old_async':old_async,'DDR131_25':ddr})
 route_save('native_mailbox_exception_coverage.json',{'expected':2560,'records':scored,'exact_15_238_records':len(coverage),'coverage_complete':coverage==expected,'report_sha256':sha(mbreport)})
 assert coverage==expected and len(scored)==2560 and not old_async and ddr,'Routed replacement budget/coverage failed'
 assert all(sha(p)==h for p,h in sourceguards.items()),'candidate02 drift caused by PNR'
 r.guard()
 timingpass=len(minima)==10 and all(v is not None and v>=0 for v in minima.values()) and all(x['slack']>=0 for x in scored)
 status='PASS_FRESH_CDB_PNR_TIMING' if timingpass and retained else 'FAIL_REAL_PNR_TIMING_OR_RETENTION'
 route_save('actual_review_handoff.json',{'status':status,'PNR_completed':True,'timing_pass':timingpass,'retention_pass':retained,'minima_ns':minima,'fresh_mapADF_sha256':sha(adf),'PNR_ADF':str(routed),'PNR_ADF_sha256':sha(routed),'native_CDB_sha256':sha(R/'native_CDB_raw.txt'),'budget_ns':15.238,'old_camera_async':old_async,'exact_pair_corner_coverage':len(coverage),'sites':60,'source_files':741,'registered':186,'DDR_MHz':131.25,'bit':False,'program':False,'next':'PNR failure must be fixed with placement/skew/data-delay changes; no exemptions' if not timingpass else 'Main-session timing and retention review before any bit generation'})
 save('actual_review_handoff.json',json.loads((R/'actual_review_handoff.json').read_bytes()))
 (R/'RESULT_ZH.md').write_text('本轮实际结果：'+status+'\n\n真实global10最小slack(ns)：'+json.dumps(minima,ensure_ascii=False)+'\n\n15.238精确pair/corner覆盖：'+str(len(coverage))+'/2560；60site精确对应；DDR131.25MHz。源码741/186保持，旧失败与本轮全部原始日志保留。未生成bit、未远端/编程。\n',encoding='utf-8')
 print('真实PNR与全部原生报告交付：'+status+'；'+json.dumps(minima),flush=True)
def main():
 wait_build(75408)
 k,h=r.lock()
 try:
  cc=cdb('compile_native');sc=cdb('synthesis_native')
  save('phase_CDB_replacement_review.json',{'compile_empty':cc.strip()==b'(CDB \r\n  )' or len(cc)<30,'compile_has_budget':b'15238' in cc,'synthesis_has_budget':b'15238' in sc,'synthesis_old_CLKGP':bool(re.search(rb'\(CLKGP\b',sc)),'compile_CDB_sha256':sha(E/'compile_native_CDB_raw.txt'),'synthesis_CDB_sha256':sha(E/'synthesis_native_CDB_raw.txt')})
  assert b'15238' in sc and not re.search(rb'\(CLKGP\b',sc),'Fresh synthesis replacement not loaded'
  original_tool=r.tool
  def maptool(label,text,cwd,project_stage=None):
   if label=='native_clock_exception':
    save('MAP_report_deferred_official_phase.json',{'reason':'Official report_timing expects routed PNR DB; MAP CDB native audit precedes PNR reporting','planned_command':text,'MAP_pass_is_independent_of_report_phase':True})
    print('MAP原生CDB已核验；report_timing按官方要求延至真实PNR后',flush=True);return b''
   return original_tool(label,text,cwd,project_stage)
  r.tool=maptool;r.mapping();r.tool=original_tool
  print('真实新MAP完成；无旧CLKGP、budget15238、1280unique/60site核验完成',flush=True)
  pnr()
 finally:k.ReleaseMutex(h);k.CloseHandle(h)
if __name__=='__main__':
 try:main()
 except BaseException:
  failure={'traceback':traceback.format_exc(),'time':time.time(),'controller_pid':os.getpid(),'bit':False,'program':False}
  save('continuation_failure_'+str(time.time_ns())+'.json',failure)
  if R.exists():
   route_save('failure_'+str(time.time_ns())+'.json',failure)
   (R/'FAILURE_ZH.md').write_text('真实串行controller未通过：\n\n'+failure['traceback']+'\n失败日志和所有阶段原样保留；不具备bit资格。',encoding='utf-8')
  if not (E/'actual_review_handoff.json').exists():save('actual_review_handoff.json',{'status':'FAIL_REAL_CONTINUATION','failure':failure,'map_completed':(E/'mapping02_receipt.json').exists(),'PNR_started':(E/'route01_pnr_process.json').exists(),'PNR_completed':(E/'route01_pnr_receipt.json').exists(),'bit':False,'program':False})
  try:r.guard()
  except BaseException:save('continuation_guard_failure_'+str(time.time_ns())+'.json',{'traceback':traceback.format_exc()})
  print(traceback.format_exc(),flush=True);sys.exit(1)
