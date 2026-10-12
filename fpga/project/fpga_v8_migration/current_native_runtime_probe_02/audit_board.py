import json,hashlib,sys
from pathlib import Path
from board_inventory import identity
paths=json.loads(Path(__file__).with_name('audit_paths.json').read_text())
rows=[]
for p in paths:
 try:
  f=Path(p); rows.append(dict(path=p,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size))
 except Exception as e: rows.append(dict(path=p,error=str(e)))
print(json.dumps(dict(process=identity(),files=rows),indent=2))
