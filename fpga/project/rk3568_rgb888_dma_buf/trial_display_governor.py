"""Temporarily fix CPU governor for a 30-second sample, restoring it on exit."""
import subprocess,sys,shlex,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
path='/sys/devices/system/cpu/cpufreq/policy0/scaling_governor'
c=board_ssh.connect()
def command(code):
 rc,out,err=board_ssh.run(c,'python3 -c '+shlex.quote(code),timeout=20,sudo=True)
 if rc:raise RuntimeError(err)
 return out.strip()
old=command('from pathlib import Path; print(Path('+repr(path)+').read_text().strip())')
try:
 command('from pathlib import Path; Path('+repr(path)+').write_text("performance")')
 subprocess.run([sys.executable,str(Path(__file__).with_name('sample_runtime.py')),'2090','display_cpu_performance','/userdata/linaro/ov56401-reboot-original-1791609246127691735/original.log'],check=True)
finally:
 command('from pathlib import Path; Path('+repr(path)+').write_text('+repr(old)+')')
 print(json.dumps({'original_governor':old,'restored_governor':command('from pathlib import Path; print(Path('+repr(path)+').read_text().strip())')}))
 c.close()
