from pathlib import Path
import json,re,hashlib,xml.etree.ElementTree as ET,importlib.util,shutil,sys
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;BOARD=E.parent;W=E/'work/place_route'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (E/n).open('x',encoding='ascii') as f:json.dump(x,f,indent=2,ensure_ascii=True)
def tables(p):
 return {t.get('id'):{'attributes':t.attrib,'columns':[d.text or '' for d in t.findall('column_headers/data')],'rows':[[d.text or '' for d in r.findall('data')] for r in t.findall('row')]} for t in ET.parse(p).getroot().findall('table')}
def summary(raw):
 lines=raw.splitlines();out={};kind=None
 for line in lines:
  m=re.match(rb'\s*(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):',line)
  if m:kind=m[1].decode()+' '+m[2].decode();out[kind]=[];continue
  if kind:
   vals=line.split()
   expected=5 if kind.startswith('Minimum Pulse') else 6
   if len(vals)==expected:
    try:
     row={'launch':vals[0].decode(),'capture':vals[1].decode() if expected==6 else vals[0].decode(),'wns':float(vals[-4]),'tns':float(vals[-3]),'failing_endpoints':int(vals[-2]),'total_endpoints':int(vals[-1])}
     out[kind].append(row)
    except ValueError:pass
   if line.startswith(b'='):kind=None
 return out
def critical(raw):
 chunks=re.split(rb'(?=^\s*Startpoint\s*:)',raw,flags=re.M);rows=[]
 for c in chunks:
  m=re.search(rb'Slack\s*\((MET|VIOLATED)\)\s+(-?\d+(?:\.\d+)?)',c)
  if not m:continue
  fields={}
  for f in [b'Startpoint',b'Endpoint',b'Path Type',b'Path Class',b'Timing Exception']:
   mm=re.search(rb'^\s*'+f+rb'\s*:\s*(.*)',c,re.M)
   if mm:fields[f.decode()]=mm[1].decode('ascii','backslashreplace')
  fields.update(slack=float(m[2]),raw=c.decode('ascii','backslashreplace'))
  rows.append(fields)
 return rows
def main():
 prr=W/'prr.db';native=tables(prr);save('native_prr_tables.json',{'path':str(prr),'sha256':sha(prr),'tables':native})
 rawprr=prr.read_bytes();iom=re.search(rb'<table\b[^>]*\bid="pnr_io_report"[^>]*>.*?</table>',rawprr,re.S)
 if iom:(E/'native_IO112_raw.xml').write_bytes(iom[0])
 io=native['pnr_io_report'];fields=io['columns'];ports={r[0]:dict(zip(fields,r)) for r in io['rows']}
 comparisons=[]
 baselines=[BOARD/'source_diagnostics_timing_build_01/route_attempt_03/place_route/prr.db',BOARD/'source_diagnostics_timing_build_01/place_route/prr.db',BOARD/'build04_diagnostic_behavior_route01/work/place_route/prr.db']
 for p in baselines:
  if not p.is_file():continue
  tab=tables(p)['pnr_io_report'];bp={r[0]:dict(zip(tab['columns'],r)) for r in tab['rows']}
  diffs=[]
  for port,row in ports.items():
   for f,v in row.items():
    if bp.get(port,{}).get(f)!=v:diffs.append({'port':port,'field':f,'baseline':bp.get(port,{}).get(f),'fresh':v})
  comparisons.append({'path':str(p),'sha256':sha(p),'baseline_ports':len(bp),'same_ports':set(bp)==set(ports),'differences':diffs,'electrical_differences':[x for x in diffs if x['field'] not in {'BANK','IO_REGISTER','CONSTRAINT'}]})
  bm=re.search(rb'<table\b[^>]*\bid="pnr_io_report"[^>]*>.*?</table>',p.read_bytes(),re.S)
  comparisons[-1]['native_IO_table_bytes_equal']=bool(iom and bm and iom[0]==bm[0])
  comparisons[-1]['baseline_IO_table_sha256']=hashlib.sha256(bm[0]).hexdigest() if bm else None
 save('native_IO112_comparison.json',{'fresh_sha256':sha(prr),'ports':len(ports),'native_columns':fields,'comparisons':comparisons,'method':'Compare exact native XML text field values from byte-bound raw reports; no bank inference or report rewriting'})
 reports=list(W.glob('*.rtr'))+list((E/'reports/global10').rglob('*.rtr'))
 result=[]
 for p in reports:
  raw=p.read_bytes();ss=summary(raw);crit=critical(raw)
  result.append({'path':str(p),'sha256':sha(p),'summaries':ss,'minima':{k:min((r['wns'] for r in rows),default=None) for k,rows in ss.items()},'critical_paths':crit,'old_camera_async':[c for c in range(1,5) if re.search(rb'^\s*cmos'+str(c).encode()+rb'_pclk\s+asynchronous\s+cmos'+str(c).encode()+rb'_pclk\s*$',raw,re.M)],'actual_maxdelay_15_238':bool(re.search(rb'MaxDelay|Max Delay|max_delay',raw,re.I) and b'15.238' in raw)})
 save('native_STA_actual.json',result)
 if (E/'routed_dump.txt').is_file():
  raw=(E/'routed_dump.txt').read_bytes();start=raw.find(b'(CDB ');depth=0;stop=None
  for m in re.finditer(rb'"(?:[^"\\]|\\.)*"|[()]',raw[start:]):
   if m[0]==b'(':depth+=1
   elif m[0]==b')':
    depth-=1
    if depth==0:stop=start+m.end();break
  if start<0 or stop is None:raise RuntimeError('No complete native CDB')
  (E/'native_CDB_raw.txt').write_bytes(raw[start:stop]);save('native_CDB_binding.json',{'dump_sha256':sha(E/'routed_dump.txt'),'start':start,'end':stop,'CDB_sha256':sha(E/'native_CDB_raw.txt'),'contains_15238':b'15238' in raw[start:stop],'old_async_lines':[x.decode('ascii','backslashreplace') for x in raw[start:stop].splitlines() if b'cmos' in x and (b'GROUP' in x or b'CLOCK' in x)]})
 print('IO',len(ports),'REPORTS',[(x['path'],x['minima'],x['old_camera_async']) for x in result])
if __name__=='__main__':main()
