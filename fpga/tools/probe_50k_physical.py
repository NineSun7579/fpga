from pathlib import Path
import subprocess
import shutil
import sys

root = Path(__file__).resolve().parents[2] / 'ov5640_sfp480p_test/ov5640_sfp480p_test'
work = root / 'physical_flow_proof'
work.mkdir(exist_ok=True)
db = work / 'probe_route.adf'
if not db.exists():
    shutil.copy2(root / 'place_route/hdmi_ddr_ov5640_top_pnr.adf', db)
commands = sys.argv[1:] or ['help']
text = '\n'.join(['set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484',
                   'mpnr -input {' + db.as_posix() + '}', *commands, 'exit', ''])
p = subprocess.run(['C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe'], cwd=work,
                   input=text.encode('ascii'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
(work / 'probe.log').write_bytes(p.stdout)
print(p.stdout.decode('gb18030', errors='replace'))
