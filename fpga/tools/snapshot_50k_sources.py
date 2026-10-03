import hashlib
import json
import sys
import zipfile
from pathlib import Path

root = Path(sys.argv[1])
destination = Path(sys.argv[2])
paths = [path for path in (root / 'source').rglob('*') if path.is_file()]
paths.extend(root.glob('*.fdc'))
manifest = {}
with zipfile.ZipFile(destination / 'sources.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(paths):
        name = path.relative_to(root).as_posix()
        content = path.read_bytes()
        manifest[name] = hashlib.sha256(content).hexdigest()
        archive.writestr(name, content)
(destination / 'source_sha256.json').write_text(json.dumps(manifest, indent=2))
print('Archived', len(manifest), '50K source files')
