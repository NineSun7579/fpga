"""Split per-target SHA-256 manifests into each release subpackage."""
import hashlib
import json
from pathlib import Path

root = Path('D:/race/ov56401/project/cam5_resolution/release_3_2_0a/fpga_repo/Release-3.2.0a').resolve()
manifest = json.loads((root / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
for component in ('fpga50', 'fpga100', 'rk3568'):
    items = [r for r in manifest['files'] if r['component'] == component]
    out = root / component / ('MANIFEST_' + component.upper() + '.json')
    out.write_text(json.dumps(dict(component=component, count=len(items), files=items), indent=2) + '\n', encoding='utf-8')
    print(component, len(items))
