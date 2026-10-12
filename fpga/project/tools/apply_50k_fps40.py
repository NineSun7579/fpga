"""Prepare tested real-row/VTS520 experiment after guard board acceptance."""
from pathlib import Path
import json
import shutil
import build_50k_final as build

ROOT = Path(__file__).resolve().parents[2]
launch = json.loads((ROOT / 'log/50k_fps_guard_launch.json').read_text())
BASE = Path(launch['archive'])
handoff = json.loads((ROOT / 'log/50k_fps_guard_review.json').read_text())
assert handoff.get('accepted') is True, 'Guard board acceptance must complete first'
build.idle()
build.check_inputs(BASE)
merge = ROOT / 'project/sim/fps50k_real_rows'
sensor = ROOT / 'project/sim/fps50k_sensor'
for folder, name in [(merge,'real_phase.log'),(merge,'real_40.log')]:
    text = (folder / name).read_bytes()
    assert b'# TEST PASS' in text and b'fullA=0 fullB=0 errors=0' in text
    assert b'SNAPSHOT real=960 repeat=0 black=0' in text
for mode in (0,1):
    text = (sensor / f'mode_{mode}.log').read_bytes()
    assert f'TEST PASS mode={mode}'.encode() in text
    assert b'** Fatal' not in text and b'** Error' not in text
for name, folder in [('cam2_merge.v',merge),('reg_config.v',sensor)]:
    target = build.ROOT / 'source/rtl' / name
    backup = folder / ('pre40_' + name)
    if not backup.exists():
        shutil.copy2(target,backup)
    assert build.sha(target) == build.sha(backup)
    target.write_bytes((folder / name).read_bytes())
old = json.loads((BASE / 'input_sha256.json').read_text())
new = build.inputs()
changed = sorted(n for n in old.keys() | new.keys() if old.get(n) != new.get(n))
assert changed == ['source/rtl/cam2_merge.v','source/rtl/reg_config.v'], changed
archive = build.prepare()
manifest = {'baseline':str(BASE), 'changes':changed,
    'candidate_hashes':{n:new[n] for n in changed},
    'baseline_hashes':{n:old[n] for n in changed},
    'rollback_sha256':build.sha(BASE / 'hdmi_ddr_ov5640_top.sbit'),
    'VTS':520,'HTS':2000,'exposure_ceiling':499,
    'objective_complete':False}
build.save(archive / 'fps40_candidate.json',manifest)
for folder,name in [(merge,'real_phase.log'),(merge,'real_40.log'),
                    (sensor,'mode_0.log'),(sensor,'mode_1.log')]:
    shutil.copy2(folder / name,archive / name)
build.save(ROOT / 'log/50k_fps40_launch.json',dict(manifest,archive=str(archive)))
print('FPS40_ARCHIVE: ' + str(archive))
