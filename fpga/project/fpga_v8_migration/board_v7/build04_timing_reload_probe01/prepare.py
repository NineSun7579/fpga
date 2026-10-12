from pathlib import Path
import json,hashlib,shutil,sqlite3,zlib,re
E=Path(__file__).resolve().parent; BOARD=E.parent
F=BOARD/'build04_final_route_runtime01'; B=BOARD/'source_diagnostics_timing_build_04'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,o):
 p=E/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(o,f,indent=2)
def main():
 copies=[]
 def copy(src,dst):
  dst.parent.mkdir(parents=True,exist_ok=True)
  if dst.exists():raise RuntimeError('Refuse overwrite '+str(dst))
  before=sha(src);shutil.copy2(src,dst)
  assert before==sha(src)==sha(dst)
  copies.append(dict(source=str(src),copy=str(dst),sha256=before,bytes=dst.stat().st_size))
 for root,dest in [(B/'evidence/runtime/mapping60_01/isolated_mapping_work/device_map',E/'inputs/device_map'),(F/'constraints',E/'inputs/constraints')]:
  for p in root.rglob('*'):
   if p.is_file():copy(p,dest/p.relative_to(root))
 for n in ['candidate_specific_expectation_contract.json','coverageproof.json','clock_offline_audit.json','route_copy_plan.json']:
  copy(F/n,E/'reference'/n)
 assert sha(E/'inputs/device_map/v7_sdt_top_map.adf')=='3a0478381bb9761f677937bf0a55374119fc2b6ce683d847d8a1dda2aacd5419'
 save('copy_manifest.json',copies)
 extract_docs()
 print('Prepared',len(copies),'copies')
def extract_docs():
 qch=Path('C:/pango/PDS_2022.2-SP6.4/bin/helpDoc_pango.qch')
 db=sqlite3.connect('file:'+qch.as_posix()+'?mode=ro',uri=True)
 rows=db.execute('SELECT Name,Data FROM FileNameTable JOIN FileDataTable ON FileNameTable.FileId=FileDataTable.Id').fetchall()
 refs=[]
 for name,data in rows:
  if not data:continue
  try:raw=zlib.decompress(data[4:])
  except zlib.error:continue
  if re.search(rb'(?:read_sdc|read_fdc|read_constraint|load_constraint|report_exceptions|report_clock|reset_timing|report_timing|input_db_file)',raw,re.I):
   out=E/'official_docs'/name.replace('\\','/').lstrip('/');out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(raw)
   refs.append(dict(name=name,path=str(out),sha256=sha(out),bytes=len(raw)))
 save('official_document_index.json',dict(qch=str(qch),sha256=sha(qch),documents=refs))
 print('Extracted',len(refs),'official help documents')
if __name__=='__main__':
 import sys
 if '--docs-only' in sys.argv:extract_docs()
 else:main()
