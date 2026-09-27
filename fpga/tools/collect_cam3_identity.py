"""Collect the aligned hardware diagnostics over SSH with viewer stopped."""
from pathlib import Path
import datetime
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
command="killall -9 camview 2>/dev/null; pkill -9 -f '[r]un_camview' 2>/dev/null; sleep 1; timeout 30 python3 -u /tmp/probe_cam3_identity.py"
result=subprocess.run([sys.executable,str(root/'tools/sshx.py'),command,
                       '--sudo','--tries','2','--timeout','40'],cwd=root,
                      stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
path=root/('cam3_identity_'+stamp+'.log')
path.write_bytes(result.stdout)
sys.stdout.buffer.write(result.stdout)
print('\nSaved:',path)
raise SystemExit(result.returncode)
