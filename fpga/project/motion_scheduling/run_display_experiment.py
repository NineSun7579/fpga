import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'project/motion_scheduling/board_viewer.py'
p = argparse.ArgumentParser()
p.add_argument('--build-receipt', required=True, type=Path)
p.add_argument('--start-receipt', required=True, type=Path)
a = p.parse_args()
results = {}
def run(action, start, *extra):
    proc = subprocess.run([sys.executable,str(TOOL),action,'--start-receipt',str(start),*extra],
                          cwd=ROOT,capture_output=True,text=True)
    print(proc.stdout,flush=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr+proc.stdout)
    line = [line for line in proc.stdout.splitlines() if line.startswith('Session receipt: ')][-1]
    return Path(line.split(': ',1)[1])

for enabled in (0,1):
    source = a.start_receipt if enabled==0 else Path(results['off_start'])
    start=run('experiment_switch',source,'--gating','1','--hud-batch',str(enabled),
              '--build-receipt',str(a.build_receipt))
    key='off' if enabled==0 else 'on'
    results[key+'_start']=str(start)
    results[key+'_observe']=str(run('observe',start,'--seconds','120'))
    Path(__file__).with_name('display_experiment_receipts.json').write_text(json.dumps(results,indent=2))
print('Display experiment complete; motion gating and HUD batching enabled.',flush=True)
