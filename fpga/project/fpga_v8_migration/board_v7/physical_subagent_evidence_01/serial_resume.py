"""Resume preparation using verified top encoding, then audit routed outputs."""
from pathlib import Path
import subprocess,sys
HERE=Path(__file__).resolve().parent
subprocess.run(['powershell','-NoProfile','-Command','Wait-Process -Id 60164 -ErrorAction SilentlyContinue'],capture_output=True)
out=HERE/'fixed_06'
if not (out/'synthesize_launch.json').exists():
    result=subprocess.run([sys.executable,'-u',str(HERE/'continue_fixed.py')])
    if result.returncode:sys.exit(result.returncode)
if (out/'pnr_artifact.json').exists():
    sys.exit(subprocess.run([sys.executable,'-u',str(HERE/'audit_fixed.py')]).returncode)
sys.exit('No verified routed DB; inspect failure evidence before restarting')
