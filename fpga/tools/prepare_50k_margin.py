"""Apply the bus-validated margin table, preserving exact normal rollback inputs."""
from pathlib import Path
import json, shutil, sys, time
import build_50k_final as build

ROOT = Path(__file__).resolve().parents[2]
TEST = ROOT / 'project/sim/edge50k/margin_sccb'
BASE = build.ROOT / 'bitstream_final_50k_20261003_023911'
EXPECTED = '1cd4405242a95f054fec9b7dd1e3ec7b84a46f5a5d15a02fad9a6902534e7124'

def main():
    build.idle()
    for mode, count in [(0,357),(1,358)]:
        text = (TEST / f'mode_{mode}.log').read_text(errors='replace')
        assert f'TEST PASS mode={mode}' in text
        assert '** Fatal' not in text and '** Error' not in text
        for camera in (1,2):
            for round in (1,2):
                assert f'SCCB PASS camera={camera} run={round} commands={count}' in text
    build.check_inputs(BASE)
    assert build.sha(BASE / 'hdmi_ddr_ov5640_top.sbit') == '1df94407f27a81bfa963be9c0e7f89a3d44ef6ac295680d26aafb66884fdcf5e'
    candidate = TEST / 'reg_config.v'
    assert build.sha(candidate) == EXPECTED
    backup = ROOT / 'project/sim/edge50k/current_normal_023911_backup'
    backup.mkdir(exist_ok=False)
    for name in ('reg_config.v','hdmi_ddr_ov5640_top.v','sfp_video_tx.v'):
        shutil.copy2(build.ROOT / 'source/rtl' / name, backup / name)
    shutil.copy2(BASE / 'input_sha256.json', backup / 'input_sha256.json')
    build.save(backup / 'rollback.json', {'archive':str(BASE), 'bitstream':str(BASE / 'hdmi_ddr_ov5640_top.sbit'),
        'bit_sha256':build.sha(BASE / 'hdmi_ddr_ov5640_top.sbit'), 'backup_created':time.strftime('%Y-%m-%d %H:%M:%S')})
    target = build.ROOT / 'source/rtl/reg_config.v'
    target.write_bytes(candidate.read_bytes())
    old = json.loads((BASE / 'input_sha256.json').read_text())
    current = build.inputs()
    changed = [n for n in old.keys() | current.keys() if old.get(n) != current.get(n)]
    assert changed == ['source/rtl/reg_config.v'], changed
    archive = build.prepare()
    for name in ('mode_0.log','mode_1.log','effective_register_map.json','baseline_commands.mem'):
        shutil.copy2(TEST / name, archive / name)
    shutil.copy2(Path(__file__), archive / Path(__file__).name)
    tag = archive.name.removeprefix('bitstream_final_50k_')
    evidence = ROOT / 'log' / ('six_margin_board_' + tag)
    handoff = ROOT / 'log' / ('six_margin_' + tag + '_handoff.json')
    flash = ROOT / 'project' / ('flash_50k_margin_' + tag + '.tcl')
    flash.write_text('cfg_scan_chain\ncfg_assign_file -file %s -device_index 0\ncfg_program -device_index 0\n' % (archive / 'hdmi_ddr_ov5640_top.sbit').as_posix(), encoding='ascii')
    shutil.copy2(ROOT / 'project/tools/finish_normal_023911.py', archive / 'finish_normal_023911.py')
    launch = {'archive':str(archive), 'baseline':str(BASE), 'evidence':str(evidence), 'handoff':str(handoff),
              'flash_tcl':str(flash), 'backup':str(backup), 'status':'prepared', 'objective_complete':False}
    build.save(ROOT / 'log/50k_margin_launch.json', launch)
    print(json.dumps(launch), flush=True)

if __name__ == '__main__':
    main()
