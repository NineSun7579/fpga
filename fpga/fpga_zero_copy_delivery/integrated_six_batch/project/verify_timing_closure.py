"""Produce a closure receipt only from finished build and real timing reports."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

project = Path(__file__).resolve().parent
seed = int(sys.argv[1])
guard = subprocess.run(['powershell', '-NoProfile', '-Command',
    '@(Get-Process -Name pds,pds_shell -ErrorAction SilentlyContinue).Count'],
    capture_output=True, text=True, check=True)
assert guard.stdout.strip() == '0', 'PDS still active; do not inspect partial reports'
build = json.loads((project / f'seed_{seed}_manifest.json').read_text())
assert build['status'] == 'finished' and build['return_code'] == 0, build['status']
assert build['source_inputs_unchanged']
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert all(digest(project.parent / p) == h for p,h in build['inputs'].items())
raw = (project / 'project.pds').read_bytes()
assert re.search(rb'\(_option gplace_seed \(_integer ' + str(seed).encode() + rb'\)\)', raw)
subprocess.run([sys.executable, str(project / 'audit_sources.py')], cwd=project, check=True)
reports = [project / 'place_route/top_timing_summary_after_hold_fix.txt',
           project / 'report_timing/top.rtr']
texts = {str(p.relative_to(project)):p.read_bytes().decode('gbk', errors='replace').replace('\r','')
         for p in reports}
all_met = all('Design Summary : All Constraints Met.' in t for t in texts.values())
clock_lines = {name:[x.strip() for x in text.splitlines() if
                   re.match(r'\s*(cmos2_pclk|ddrphy_sysclk)\s+(cmos2_pclk|ddrphy_sysclk)\s',x)]
               for name,text in texts.items()}
violations = {name:[x.strip() for x in text.splitlines() if 'VIOLATED' in x]
              for name,text in texts.items()}
result = dict(status='timing_closed' if all_met else 'timing_violated', seed=seed,
              command=build['command'], return_code=build['return_code'],
              wall_seconds=build['wall_seconds'], sources_unchanged=True,
              source_inputs=build['inputs'], project_sha256=digest(project / 'project.pds'),
              report_sha256={str(p.relative_to(project)):digest(p) for p in reports},
              clock_lines=clock_lines, violations=violations,
              engine_test_receipt=json.loads((project / 'timing_engine_test_receipt.json').read_text()),
              generator_recipe='make_six_batch.py generates the exact original two RTL transforms; rerun_seed.py '+str(seed)+' applies only the project placement seed and builds',
              programmed=False, board_access=False)
(project / f'seed_{seed}_closure_receipt.json').write_text(json.dumps(result, indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('source_inputs','engine_test_receipt')}, indent=2))
raise SystemExit(0 if all_met else 1)
