"""Prepare isolated 40-fps timing candidate; do not alter active build inputs."""
from pathlib import Path
import json
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'ov5640_sfp480p_test/ov5640_sfp480p_test/bitstream_final_50k_20261003_033106'
TEST = ROOT / 'project/sim/fps50k_sensor'
TEST.mkdir(exist_ok=True)
with zipfile.ZipFile(BASE / 'sources.zip') as z:
    original = z.read('source/rtl/reg_config.v')
    candidate = original
    # At the observed ~29.8 fps cadence, 705->520 implies ~40.4 fps.
    # Hardware frequency/readback is not inferred from this calculation.
    edits = [(329,0x380e02,0x380e02),(330,0x380fc1,0x380f08),
             (336,0x3a0202,0x3a0201),(337,0x3a03ac,0x3a03f3),
             (344,0x3a1402,0x3a1401),(345,0x3a15ac,0x3a15f3)]
    for index, old, new in edits:
        pattern = rb'(' + str(index).encode() + rb'\s*:reg_data\s*<=24\x27h)' + f'{old:06x}'.encode()
        candidate, count = re.subn(pattern, lambda m:m[1]+f'{new:06x}'.encode(), candidate, flags=re.I)
        assert count == 1, index
    pairs = re.findall(rb'(\d+)\s*:reg_data\s*<=24\x27h([0-9a-fA-F]{6})', candidate)
    commands = {int(i):int(word,16) for i,word in pairs}
    assert len(commands) == len(pairs)
    effective = {word>>8:word&255 for i,word in sorted(commands.items()) if i<357}
    for address,value in {0x3811:0x10,0x3801:0x80,0x3805:0xbf,
                          0x3808:2,0x3809:0x80,0x380a:1,0x380b:0xe0,
                          0x380e:2,0x380f:8}.items():
        assert effective[address] == value
    (TEST / 'reg_config.v').write_bytes(candidate)
    for name in ['i2c_com.v','power_on_delay.v']:
        (TEST / name).write_bytes(z.read('source/rtl/' + name))
(TEST / 'baseline_commands.mem').write_text(''.join(f'78{commands.get(i,0xffffff):06x}\n' for i in range(357)))
for name in ['actual_sensor_instances.vh','tb_sensor_colorbar.sv','run.ps1']:
    shutil.copy2(ROOT / 'project/sim/edge50k/margin_sccb' / name, TEST / name)
(TEST / 'timing_candidate.json').write_text(json.dumps({'VTS':520,'HTS':2000,
    'exposure_ceiling':499,'estimated_fps_if_cadence_scales':29.8*705/520,
    'preserved_output':[640,480], 'production_modified':False,
    'requires_board_measurement':True}, indent=2))
print(TEST)
