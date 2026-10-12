"""Read-only clock and temperature observation concurrent with display workload."""
import json,shlex,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_ssh
code=r'''
from pathlib import Path
import time,json,collections
paths={'cpu':Path('/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq'),
 'gpu':Path('/sys/class/devfreq/fde60000.gpu/cur_freq'),
 'temperature':Path('/sys/class/thermal/thermal_zone0/temp')}
rows=[]
for i in range(60):
 rows.append({'time':time.monotonic(),**{k:int(p.read_text()) for k,p in paths.items()}})
 time.sleep(.5)
print(json.dumps({'rows':rows,'histograms':{k:dict(collections.Counter(x[k] for x in rows)) for k in paths}}))
'''
c=board_ssh.connect()
try:
 rc,out,err=board_ssh.run(c,'python3 -c '+shlex.quote(code),timeout=40,sudo=True)
 if rc:raise RuntimeError(err)
 Path(__file__).with_name('display_clock_sample.json').write_text(out,encoding='utf-8')
 print(json.dumps(json.loads(out)['histograms'],indent=2))
finally:c.close()
