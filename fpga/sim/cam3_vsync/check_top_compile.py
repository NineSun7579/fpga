"""Compare standalone top compilation to its pre-edit byte backup."""
from pathlib import Path
import re
import subprocess
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
top = ROOT / 'source/top.v'
baseline = sorted(top.parent.glob('top.v.bak_cam3_vsync_*'))[-1]
(HERE / 'top_baseline.v').write_bytes(baseline.read_bytes())
errors = []
for label, path in [('baseline', HERE / 'top_baseline.v'), ('current', top)]:
    result = subprocess.run([r'C:\modeltech64_10.6e\win64\vlog.exe',
                             '+define+USE_OV5640', str(path)],
                            cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (HERE / ('compile_top_' + label + '.log')).write_bytes(result.stdout)
    messages = [re.sub(rb'^.*?\(vlog-', b'(vlog-', line) for line in result.stdout.splitlines()
                if line.startswith(b'** Error')]
    errors.append(messages)
    print(label, 'return', result.returncode, 'errors', len(messages))
assert errors[0] == errors[1], 'Top diagnostics changed'
print('PASS: identical pre-existing standalone top compilation diagnostics')
