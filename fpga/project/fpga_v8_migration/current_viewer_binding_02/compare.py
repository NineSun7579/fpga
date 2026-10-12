import json,hashlib,difflib,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
base=root.parent
src=root/'inputs/userdata/linaro/detview-driving-demo-src'
old=base/'viewer_native_candidate/src'
sha=lambda b:hashlib.sha256(b).hexdigest()
current=(src/'main.cpp').read_bytes()
start=current.index(b'    static float sigmoidf(')
end=current.index(b'    QMutex m_mutex;',start)
decoder=current[start:end]
(root/'current_retained_decoder.inc').write_bytes(decoder)
frozen=(base/'viewer_native_runtime_probe/dependencies/board/board_production_decoder.inc').read_bytes()
frozen_paths=[base/'viewer_native_runtime_probe/dependencies/board/board_production_decoder.inc',old/'viewer_native_guard.hpp',old/'raw_dfl_native.h',old/'viewer_native_qt.hpp',base/'viewer_native_candidate/candidate_manifest.json',base/'viewer_native_runtime_probe/decoder_and_conversion_binding.json']
local_inputs=[]
for p in frozen_paths:
 target=root/'inputs/frozen_0301'/p.name
 target.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(p,target)
 local_inputs.append({'source':str(p.relative_to(base)),'local':str(target.relative_to(root)),'sha256':sha(target.read_bytes())})
(root/'frozen_comparison_inputs.json').write_text(json.dumps(local_inputs,indent=2),encoding='utf-8')
(root/'decoder_diff.txt').write_text(''.join(difflib.unified_diff(frozen.decode().splitlines(True),decoder.decode().splitlines(True),fromfile='frozen_0301_decoder',tofile='current_retained_decoder')),encoding='utf-8')
(root/'main_vs_candidate.diff').write_text(''.join(difflib.unified_diff((old/'main.cpp').read_text(encoding='utf-8').splitlines(True),current.decode().splitlines(True),fromfile='old_native_candidate/main.cpp',tofile='current_retained/main.cpp')),encoding='utf-8')
files=[]
for p in sorted(src.rglob('*')):
 if not p.is_file():continue
 rel=p.relative_to(src); prev=old/rel
 files.append({'path':str(rel),'sha256':sha(p.read_bytes()),'old_candidate_sha256':sha(prev.read_bytes()) if prev.is_file() else None,'same_as_candidate':p.read_bytes()==prev.read_bytes() if prev.is_file() else None})
manifest=json.loads((root/'retrieval_manifest.json').read_text())
summary={'current_main_sha256':sha(current),'current_decoder_sha256':sha(decoder),'current_decoder_bytes':len(decoder),'frozen_decoder_sha256':sha(frozen),'frozen_decoder_bytes':len(frozen),'decoder_equal':decoder==frozen,'retrieved':sum(e['stable_match'] for e in manifest),'retrieval_failures':[e for e in manifest if not e['stable_match']],'files':files}
(root/'comparison.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='files'},indent=2))
