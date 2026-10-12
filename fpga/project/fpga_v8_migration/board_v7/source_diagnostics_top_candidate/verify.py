"""Reproducible local-only validation; no PDS or board access."""
from pathlib import Path
import subprocess,sys
P=Path(__file__).resolve().parent
for script in ['run.py','test.py','unit_regression.py','audit.py','physical_manifest.py','evidence.py']:
    subprocess.run([sys.executable,str(P/script)],check=True)
print('SDT_VERIFICATION_PASS')
