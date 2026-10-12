"""Sequential same-binary off/on experiment, ending with motion gating enabled."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'project/motion_scheduling/board_viewer.py'
LOG = ROOT / 'log/100h_motion'
steps = []
def run(action, start, *extra):
    args = [sys.executable, str(TOOL), action, '--start-receipt', str(start), *extra]
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    print(proc.stdout, flush=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr + proc.stdout)
    lines=[x for x in proc.stdout.splitlines() if x.startswith('Session receipt: ')]
    receipt=Path(lines[-1].split(': ',1)[1])
    steps.append(dict(action=action, receipt=str(receipt)))
    Path(__file__).with_name('experiment_progress.json').write_text(json.dumps(steps,indent=2))
    return receipt

off_start=LOG/'motion_viewer_experiment_switch_40adb8b5a75747e895b5fc452d0f12c8.json'
off_observe=run('observe',off_start,'--seconds','120')
on_start=run('experiment_switch',off_start,'--gating','1')
on_observe=run('observe',on_start,'--seconds','120')
Path(__file__).with_name('experiment_receipts.json').write_text(json.dumps(dict(
    off_start=str(off_start),off_observe=str(off_observe),on_start=str(on_start),on_observe=str(on_observe)),indent=2))
print('Paired observations complete; motion gating is enabled.',flush=True)
