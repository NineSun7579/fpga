"""Execute audited guard experiment only after the full build has completed."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
launch = json.loads((ROOT / 'log/50k_fps_guard_launch.json').read_text())
archive = Path(launch['archive'])
status = json.loads((archive / 'status.json').read_text())
if status['status'] != 'complete':
    raise RuntimeError('Build has not completed; no waiting or programming performed')
tag = archive.name.removeprefix('bitstream_final_50k_')
flash = ROOT / 'project' / ('flash_50k_fps_guard_' + tag + '.tcl')
flash.write_text('cfg_scan_chain\ncfg_assign_file -file %s -device_index 0\ncfg_program -device_index 0\n'
                 % (archive / 'hdmi_ddr_ov5640_top.sbit').as_posix(), encoding='ascii')
evidence = ROOT / 'log' / ('six_fps_guard_board_' + tag)
command = [sys.executable, str(ROOT / 'project/tools/finish_normal_023911.py'),
           '--archive',str(archive),'--baseline',launch['baseline'],
           '--evidence',str(evidence),'--handoff',str(ROOT / 'log/50k_fps_guard_handoff.json'),
           '--flash-tcl',str(flash),'--fps-guard']
raise SystemExit(subprocess.call(command))
