from pathlib import Path
import json,re,hashlib
P=Path(__file__).resolve().parent
F=P.parents[1]/'whole_candidate_v7_route_01'
hashes=json.loads((P/'source_hashes.json').read_text())
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items())
conflicts=[]
for root in [P.parents[2]/'source',P.parent,F/'rtl',F/'inputs/source']:
 for f in root.rglob('*'):
  if f.suffix not in ['.v','.sv'] or P in f.parents:continue
  if re.search(rb'\bmodule\s+(v7_sdt_top|v7_sdt_camera|v7_sdt_binding|v7_sdt_bus|tb_sdt)\b',f.read_bytes()):conflicts.append(str(f))
assert not conflicts,conflicts
def clean(b):return re.sub(rb'\s+',b'',re.sub(rb'/\*.*?\*/|//[^\r\n]*',b'',b,flags=re.S))
dup=[]
for item in json.loads((P/'ip_duplicates.json').read_text()):
 a=Path(item['omitted']);b=Path(item['retained'][0]);same=clean(a.read_bytes())==clean(b.read_bytes())
 dup.append(dict(omitted=str(a),retained=str(b),identical_tokens=same))
assert all(x['identical_tokens'] for x in dup),dup
actual=[]
if (P/'hierarchy.txt').exists():
 actual=[x.split(' ')[0] for x in (P/'hierarchy.txt').read_text().splitlines()]
 for suffix in ['axi_crossbar_7x3','axi_to_axi_lite','source_diagnostics','ovreg_axil_decode_u']:
  assert any(x.endswith('/'+suffix) for x in actual),suffix
 for i,cam in enumerate(['ov5640_top','cam2_ov5640_top','cam3_ov5640_top','cam4_ov5640_top']):
  assert any(x.endswith('/'+cam+'/ov5640/cmos_capture') for x in actual),cam
report={'hashes_unchanged':len(hashes),'new_module_conflicts':conflicts,'ip_duplicates':dup,'elaborated_instances':len(actual)}
compiled=json.loads((P/'compiled_hashes.json').read_text())
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in compiled.items())
report['compiled_inputs_unchanged']=len(compiled)
warnings={}
for name in ['compile.log','elaboration.log','top_simulation.log']:
 text=(P/name).read_text()
 entries=[line for line in text.splitlines() if '** Warning' in line]
 codes={}
 for line in entries:
  code=re.search(r'\((?:vsim|vopt|vlog)-\d+\)',line)
  key=code.group() if code else 'uncoded'
  codes[key]=codes.get(key,0)+1
 warnings[name]={'count':len(entries),'by_code':codes,'messages':sorted(set(entries))}
(P/'warnings.json').write_text(json.dumps(warnings,indent=2))
(P/'audit.json').write_text(json.dumps(report,indent=2))
print('AUDIT_PASS',len(hashes),'hashes;',len(actual),'actual instances')
