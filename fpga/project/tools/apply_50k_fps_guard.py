"""Apply simulated tail guard only and prepare an immutable audited build."""
from pathlib import Path
import json
import shutil
import build_50k_final as build

ROOT = Path(__file__).resolve().parents[2]
TEST = ROOT / 'project/sim/fps50k_merge'
BASE = build.ROOT / 'bitstream_final_50k_20261003_033106'
build.idle()
build.check_inputs(BASE)
log = (TEST / 'equal_guard.log').read_bytes()
assert b'# TEST PASS' in log and b'fullA=0 fullB=0 errors=0' in log
assert b'SNAPSHOT real=960 repeat=0 black=0' in log
manifest = json.loads((TEST / 'candidate.json').read_text())
candidate = TEST / 'cam2_merge.v'
assert build.sha(candidate) == manifest['candidate_sha256']
target = build.ROOT / 'source/rtl/cam2_merge.v'
assert build.sha(target) == manifest['baseline_sha256']
backup = TEST / 'rollback_cam2_merge.v'
if not backup.exists():
    shutil.copy2(target, backup)
assert build.sha(backup) == manifest['baseline_sha256']
target.write_bytes(candidate.read_bytes())
old = json.loads((BASE / 'input_sha256.json').read_text())
new = build.inputs()
changed = [n for n in old.keys() | new.keys() if old.get(n) != new.get(n)]
assert changed == ['source/rtl/cam2_merge.v'], changed
archive = build.prepare()
for name in ['equal_guard.log', 'candidate.json', 'rollback_cam2_merge.v']:
    shutil.copy2(TEST / name, archive / name)
build.save(ROOT / 'log/50k_fps_guard_launch.json', {'archive':str(archive),
    'baseline':str(BASE), 'change':'100us frame-tail drain guard; sensor registers unchanged',
    'status':'prepared','target_fps':[40,40], 'objective_complete':False})
print('FPS_GUARD_ARCHIVE: ' + str(archive))
