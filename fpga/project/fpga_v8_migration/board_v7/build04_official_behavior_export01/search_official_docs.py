from pathlib import Path
import sqlite3,zlib,json,hashlib,re
E=Path(__file__).resolve().parent
p=Path('C:/pango/PDS_2022.2-SP6.4/bin/helpDoc_pango.qch')
c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
print(c.execute("select name from sqlite_master where type='table'").fetchall())
print(c.execute('pragma table_info(FileNameTable)').fetchall())
print(c.execute('pragma table_info(FileDataTable)').fetchall())
out=E/'official_docs';out.mkdir(exist_ok=True)
hits=[]
for name,blob in c.execute('select n.Name,d.Data from FileNameTable n join FileDataTable d on n.FileId=d.Id'):
 if not blob: continue
 try: raw=zlib.decompress(blob[4:])
 except zlib.error: continue
 if any(t in raw for t in [b'create_vlog_netlist',b'func_sim_only',b'gen_netlist']):
  target=out/(re.sub('[^A-Za-z0-9_.-]','_',name))
  target.write_bytes(raw)
  hits.append({'name':name,'saved':str(target),'sha256':hashlib.sha256(raw).hexdigest()})
  text=re.sub('<[^>]+>',' ',raw.decode('utf8','replace'))
  for m in re.finditer('create_vlog_netlist|func_sim_only|gen_netlist',text): print(name,text[max(0,m.start()-200):m.start()+1200])
(out/'receipt.json').write_text(json.dumps({'source':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'hits':hits},indent=2),encoding='utf8')
