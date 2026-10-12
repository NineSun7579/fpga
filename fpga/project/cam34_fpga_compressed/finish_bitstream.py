from pathlib import Path
import subprocess,time,json,hashlib,sys
root=Path(__file__).resolve().parent
# Follow the owned PnR process; no second PDS instance is started until it exits.
for attempt in range(720):
 r=json.loads((root/'pnr_receipt.json').read_bytes())
 if r.get('status')=='finished':break
 time.sleep(5)
else:raise RuntimeError('PnR did not finish within one hour')
assert r['return_code']==0,'PnR failed'
timing=root/'project/place_route/top_timing_summary_after_hold_fix.txt'
text=timing.read_text(encoding='utf-8',errors='replace')
assert 'All Constraints Met' in text,'Timing not met; image generation refused'
check=subprocess.run(['powershell','-NoProfile','-Command','Get-Process pds,pds_shell -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName'],capture_output=True,text=True)
assert not check.stdout.strip(),'PnR process still active'
cmd=[r'C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe','-project',str(root/'project/project.pds'),'-run','gen_bit_stream','-work_dir',str(root/'project')]
receipt={'status':'running','command':cmd,'started_at_local_unix':time.time(),'timing_sha256':hashlib.sha256(timing.read_bytes()).hexdigest()}
(root/'bitstream_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
with (root/'bitstream.log').open('wb') as log:p=subprocess.run(cmd,cwd=root/'project',stdout=log,stderr=subprocess.STDOUT)
receipt.update(status='finished',return_code=p.returncode,wall_seconds=time.time()-receipt['started_at_local_unix'])
image=root/'project/generate_bitstream/top.sbit'
if image.exists():receipt.update(image=str(image),bytes=image.stat().st_size,sha256=hashlib.sha256(image.read_bytes()).hexdigest())
(root/'bitstream_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt,indent=2),flush=True);assert p.returncode==0 and image.exists()
