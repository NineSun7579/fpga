from pathlib import Path
import json,re,hashlib,xml.etree.ElementTree as ET
E=Path(__file__).resolve().parent;W=E/'work/place_route'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
root=ET.parse(W/'prr.db').getroot();tables={}
for t in root.findall('table'):
 tables[t.get('id')]={'attributes':t.attrib,'columns':[d.text or '' for d in t.findall('column_headers/data')],'rows':[[d.text or '' for d in r.findall('data')] for r in t.findall('row')]}
raw=(E/'pnr.log').read_bytes();errors=[x.decode('ascii','backslashreplace') for x in raw.splitlines() if re.search(rb'^\s*E:|Timing-4006|STA-3016|\b(?:unknown|unresolved|fatal)\b',x,re.I)]
messages=tables.get('pnr_messages',{}).get('rows',[]);native_errors=[r for r in messages if any(v.strip().lower() in {'error','fatal'} for v in r) or re.search(r'Timing-4006|STA-3016|\b(?:unknown|unresolved|fatal)\b',' '.join(r),re.I)]
result={'native_prr_sha256':sha(W/'prr.db'),'tables':tables,'raw_errors':errors,'native_errors':native_errors,'official_pnr_done':b'Process "Place & Route" done.' in raw,'timing_log_lines':[x.decode('ascii','backslashreplace') for x in raw.splitlines() if re.search(rb'slack|violation|constraint.*violat',x,re.I)],'timing_files':{str(p):{'sha256':sha(p),'text':p.read_bytes().decode('ascii','backslashreplace')} for p in W.glob('*timing*') if p.is_file()},'acceptance':{'diagnostic_routing_only':True,'timing':False,'reload':False,'bit':False,'IO_final':False},'discrepancy_policy':'Retain native summaries and hold-fix log independently; do not replace either with favorable values.'}
path=E/'native_route_diagnostics.json'
if path.exists():raise RuntimeError('Refuse overwrite')
path.write_text(json.dumps(result,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
print('RAW_ERRORS',len(errors),'NATIVE_ERRORS',len(native_errors),'IO_ROWS',len(tables.get('pnr_io_report',{}).get('rows',[])))
