"""Archive exact build inputs without touching GBK source contents."""
import hashlib,json,sys,zipfile,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
dest=Path(sys.argv[1])
project=root/'project_kf/project.pds'
paths=set()
for raw in re.findall(rb'\(_file\s+"([^"]+)"',project.read_bytes()):
    p=Path(raw.decode('gbk'))
    if not p.is_absolute():p=project.parent/p
    p=p.resolve()
    if not p.is_file():raise FileNotFoundError(p)
    paths.add(p)
# Include generated IP collateral and Verilog includes for audit.
for folder in ('source','ipcore'):
    paths.update(p for p in (root/folder).rglob('*') if p.is_file() and '.bak' not in p.name)
manifest={}
with zipfile.ZipFile(dest/'sources.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(paths):
        name=p.relative_to(root).as_posix()
        data=p.read_bytes();manifest[name]=hashlib.sha256(data).hexdigest()
        z.writestr(name,data)
(dest/'source_sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Archived',len(manifest),'source and IP files')
