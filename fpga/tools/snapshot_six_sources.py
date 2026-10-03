import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = Path(sys.argv[1])
project_file = root / 'project_build/project.pds'
paths = set()
for raw in re.findall(rb'\(_file\s+"([^"]+)"', project_file.read_bytes()):
    source = Path(raw.decode('gbk'))
    if not source.is_absolute():
        source = project_file.parent / source
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    paths.add(source)
for folder in ('source', 'ipcore'):
    paths.update(source for source in (root / folder).rglob('*')
                 if source.is_file() and '.bak' not in source.name)
manifest = {}
with zipfile.ZipFile(destination / 'sources.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for source in sorted(paths):
        name = source.relative_to(root).as_posix()
        content = source.read_bytes()
        manifest[name] = hashlib.sha256(content).hexdigest()
        archive.writestr(name, content)
(destination / 'source_sha256.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Archived', len(manifest), 'source and IP files')
