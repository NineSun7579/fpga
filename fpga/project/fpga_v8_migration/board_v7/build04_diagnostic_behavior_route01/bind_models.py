from pathlib import Path
import sys,json,re,hashlib,collections
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;I=Path('C:/pango/PDS_2022.2-SP6.4')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def save(n,x):
 p=E/n
 if p.exists():raise RuntimeError('Refuse overwrite '+str(p))
 p.write_text(json.dumps(x,indent=2,ensure_ascii=True)+'\n',encoding='ascii')
def clean(s):return re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
def named(s):return {m.group(1):m.group(2).strip() for m in re.finditer(r'\.(\w+)\s*\(\s*([^()]*)\s*\)',s)}
def instances(raw):
 text=re.sub(r'//[^\n]*','',raw);out={};unparsed=[]
 pattern=r'\b(V_\w+|GTP_\w+)\s*(?:/\*\s*(.*?)\s*\*/\s*)?(?:#\s*\((.*?)\)\s*)?(\\[^\s]+|[A-Za-z_$][\w$]*)\s*\((.*?)\)\s*;'
 for m in re.finditer(pattern,text,re.S):
  name=m.group(4).lstrip('\\');out[name]={'type':m.group(1),'logical_origin':m.group(2),'parameters':named(m.group(3) or ''),'ports':named(m.group(5)),'raw_statement':m.group(0)}
 for m in re.finditer(r'\bdefparam\s+(\\[^\s]+|[\w$./\[\]-]+)\s*\.\s*(\w+)\s*=\s*([^;]+);',text):
  name=m.group(1).lstrip('\\')
  if name in out:out[name]['parameters'][m.group(2)]=m.group(3).strip()
  else:unparsed.append(m.group(0))
 return out,unparsed
def main():
 files=[]
 for p in (E/'functional').rglob('*'):
  if p.is_file() and p.suffix.lower() in {'.v','.vo','.netlist'}:
   raw=p.read_bytes().decode('ascii',errors='backslashreplace')
   if re.search(r'\bV_\w+\b',raw):files.append((p,raw))
 if not files:raise RuntimeError('No actual V_* functional netlist found')
 cells={};sources={};unparsed=[]
 for p,raw in files:
  xx,uu=instances(raw);cells.update(xx);unparsed+=uu;sources[str(p)]=sha(p)
 save('functional_instance_inventory.json',{'sources':sources,'cells':cells,'types':dict(collections.Counter(c['type'] for c in cells.values())),'unparsed_defparams':unparsed})
 models={}
 for family in ['bsim','simulation']:
  for p in (I/'arch/vendor/pango/verilog'/family).rglob('*.v'):
   text=clean(p.read_bytes().decode('ascii',errors='backslashreplace'))
   for m in re.finditer(r'\b(?:module|primitive)\s+(\w+)',text):models.setdefault(m.group(1),[]).append({'path':str(p),'sha256':sha(p)})
 used={c['type'] for c in cells.values()};used.update(['V_FFASYN','V_FFSYN','V_LUT5','V_MUX2LUT6','INT_LUTMUX2_UDP','INT_LUTMUX4_UDP','GTP_DFF_C','GTP_DFF_P','GTP_GRS'])
 queue=list(used);closure={};missing=[]
 while queue:
  typ=queue.pop()
  if typ in closure:continue
  candidates=models.get(typ,[])
  if not candidates:missing.append(typ);closure[typ]=[];continue
  closure[typ]=candidates
  for entry in candidates:
   text=clean(Path(entry['path']).read_bytes().decode('ascii',errors='backslashreplace'))
   for dep in re.findall(r'\b(?:V_\w+|INT_\w+_UDP|GTP_\w+)\b',text):
    if dep!=typ and dep not in closure:queue.append(dep)
 save('official_library_binding.json',{'netlists':sources,'actual_types':sorted({c['type'] for c in cells.values()}),'closure':closure,'missing':missing,'ambiguities':{k:v for k,v in closure.items() if len(v)>1},'official_root':str(I),'cp_contract_sha256':sha(E/'official_cp_contract.json')})
 rows=load(E/'mapped_routed_identity_bridge.json')['rows'];result=[]
 for row in rows:
  c=row['mapped_cell'];matches={n:v for n,v in cells.items() if n==c or n.startswith(c+'/') or n.startswith(c+'_') or (v.get('logical_origin') or '').startswith(c+'/')}
  result.append({'logical':row['logical'],'mapped_cell':c,'routed_cell':row.get('routed_cell'),'routed_parameters':row.get('routed_parameters'),'candidate_V_instances':matches,'binding_state':'UNREVIEWED_EXACT_PREFIX_CANDIDATES','reason':'Candidate identity requires exact ports/net and parameter checks; no automatic prefix acceptance.'})
 save('official_model_binding_candidates60.json',{'rows':result,'missing_candidate_rows':[r['logical'] for r in result if not r['candidate_V_instances']],'netlist_sources':sources,'unknown_types':[t for t in used if t not in models],'unparsed_defparams':unparsed})
 print('V_INSTANCES',len(cells),'TYPES',dict(collections.Counter(c['type'] for c in cells.values())),'MISSING_LIBRARIES',missing)
if __name__=='__main__':main()
