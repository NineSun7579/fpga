import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'project/motion_scheduling/board_viewer.py'
HERE = Path(__file__).resolve().parent
results = {}
current = ROOT / 'log/100h_motion/motion_viewer_experiment_switch_4f81379ff6e9474fa60f0abb0dcbd549.json'
def run(action, start, *extra):
    proc = subprocess.run([sys.executable,str(TOOL),action,'--start-receipt',str(start),*extra],
                          cwd=ROOT,capture_output=True,text=True)
    print(proc.stdout,flush=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr+proc.stdout)
    line=[line for line in proc.stdout.splitlines() if line.startswith('Session receipt: ')][-1]
    return Path(line.split(': ',1)[1])
def save():
    (HERE/'historical_experiment_receipts.json').write_text(json.dumps(results,indent=2))

for label,build in [('historical','053c691e05d07408'),('current','4550d74c95942794')]:
    current=run('experiment_switch',current,'--gating','0','--hud-batch','0','--bench','0',
                '--build-receipt',str(ROOT/'project/performance_100h/builds'/build/'receipt.json'))
    results[label+'_start']=str(current);save()
    results[label+'_observe']=str(run('observe',current,'--seconds','120'));save()
current=run('experiment_switch',current,'--gating','1','--hud-batch','1','--bench','1')
results['restored_start']=str(current);save()
print('Historical/current comparison complete; optimized motion configuration restored.',flush=True)
