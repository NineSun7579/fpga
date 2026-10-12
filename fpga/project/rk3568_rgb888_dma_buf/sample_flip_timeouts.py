"""Matched original-runtime and newly appended Xorg flip-timeout observation."""
import json,subprocess,sys,shlex,re
import deploy_candidate as d
p=d.ROOT/'flip_timeout_observation';p.mkdir(exist_ok=True)
r=json.loads((d.ROOT/'deploy_1791613638189975800/receipt.json').read_text());s=d.Session(p,r)
try:
 b=s.rpc('snapshot',pid=24297,active_sha=d.ACTIVE)
 rc,o,e=s.board.run(s.client,'readlink /proc/24297/fd/1; cat /proc/uptime',timeout=15,sudo=True)
 assert rc==0;log=o.splitlines()[0];uptime_start=float(o.splitlines()[1].split()[0])
 with s.client.open_sftp() as f:start=f.stat('/var/log/Xorg.0.log').st_size
 subprocess.run([sys.executable,str(d.ROOT/'sample_runtime.py'),'24297','flip_observed',log],check=True)
 with s.client.open_sftp() as f:
  with f.open('/var/log/Xorg.0.log','rb') as h:h.seek(start);new=h.read()
 (p/'xorg_new.log').write_bytes(new)
 rc,o,e=s.board.run(s.client,'cat /proc/uptime; cat /sys/kernel/debug/dri/0/state',timeout=15,sudo=True)
 (p/'drm_state.log').write_text(o+e)
 counts={crtc:len(re.findall(r'crtc-'+crtc+r' flip timeout',new.decode(errors='replace'))) for crtc in ('72','96')}
 result={'identity':b['identity'],'uptime_start':uptime_start,'new_flip_timeouts':counts,'log_offset':start}
 (p/'receipt.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
finally:s.client.close()
