"""Guarded, isolated PDS seed retry; no source edits or hardware access."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import time

project = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parent
source = project.parent / 'source'
seed = int(sys.argv[1])
guard = subprocess.run(['powershell', '-NoProfile', '-Command',
    '@(Get-Process -Name pds,pds_shell -ErrorAction SilentlyContinue).Count'],
    capture_output=True, text=True, check=True)
assert guard.stdout.strip() == '0', 'PDS already active'
backup = project / ('seed_retry_backup_' + str(time.time_ns()))
backup.mkdir()
pdsfile = project / 'project.pds'
raw = pdsfile.read_bytes()
(backup / 'project.pds').write_bytes(raw)
newline = b'\r\n' if b'\r\n' in raw else b'\n'
marker = b'(_command cmd_pnr' + newline
assert raw.count(marker) == 1
start = raw.index(marker) + len(marker)
end = raw.index(b'(_db_output', start)
head = raw[start:end]
head = re.sub(rb'\s*\(_option gplace_seed \(_integer \d+\)\)', b'', head)
raw = raw[:start] + b'            (_option gplace_seed (_integer ' + str(seed).encode() + b'))' + newline + head + raw[end:]
pdsfile.write_bytes(raw)
for name in ('compile', 'synthesize', 'device_map', 'place_route', 'report_timing',
             'generate_netlist', 'generate_bitstream'):
    folder = project / name
    if folder.exists():
        folder.rename(backup / name)
inputs = {str(p.relative_to(project.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in source.rglob('*') if p.is_file()}
command = ['C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe', '-project', str(pdsfile),
           '-run', 'report_timing', '-work_dir', str(project)]
receipt = dict(seed=seed, command=command, inputs=inputs, status='running',
               project_sha256=hashlib.sha256(raw).hexdigest(), backup=str(backup))
manifest = project / f'seed_{seed}_manifest.json'
manifest.write_text(json.dumps(receipt, indent=2))
start_time = time.time()
with (project / f'seed_{seed}_pds.log').open('wb') as log:
    result = subprocess.run(command, cwd=project, stdout=log, stderr=subprocess.STDOUT)
receipt.update(status='finished', return_code=result.returncode,
               wall_seconds=time.time()-start_time,
               source_inputs_unchanged=all(hashlib.sha256((project.parent / p).read_bytes()).hexdigest()==h
                                           for p,h in inputs.items()))
summary = project / 'place_route/top_timing_summary_after_hold_fix.txt'
receipt['timing_summary'] = summary.read_text() if summary.exists() else None
manifest.write_text(json.dumps(receipt, indent=2))
assert receipt['source_inputs_unchanged'], 'Source changed during build'
print(json.dumps({k:v for k,v in receipt.items() if k not in ('inputs','timing_summary')}, indent=2))
print(receipt['timing_summary'])
raise SystemExit(result.returncode)
