import json
from pathlib import Path
root=Path(__file__).resolve().parent
files=json.loads((root/'discovery.json').read_text())['files']
paths=[e['path'] for e in files]
paths += ['/usr/lib/librknnrt.so','/proc/2740/exe']
metadata=json.loads((root/'elf_sdk_model_metadata.json').read_text())
paths += [e['path'] for e in metadata['models'] if any(key in e['path'] for key in ['trafficlight','wb_v4_combo','wb_v8_w25_nop2c2f'])]
(root/'selection.json').write_text(json.dumps(paths,indent=2),encoding='utf-8')
