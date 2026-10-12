from pathlib import Path
import json,hashlib,subprocess,time
root=Path(__file__).resolve().parent
for _ in range(720):
 r=json.loads((root/'bitstream_receipt.json').read_bytes())
 if r.get('status')=='finished':break
 time.sleep(5)
else:raise RuntimeError('Image generation timeout')
assert r['return_code']==0 and Path(r['image']).exists()
assert subprocess.run(['powershell','-NoProfile','-Command','@(Get-Process pds,pds_shell -ErrorAction SilentlyContinue).Count'],capture_output=True,text=True).stdout.strip()=='0'
tcl=root/'report_final_image.tcl';tcl.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\nreport_timing -input_db_file {'+(root/'project/place_route/top_pnr.adf').as_posix()+'} -force_to_run -delay_type min_max -nworst 1 -max_path 120 -input_pins TRUE\n',encoding='ascii')
cmd=[r'C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe','-file',str(tcl),'-work_dir',str(root/'project')]
with(root/'final_image_timing.log').open('wb')as log:p=subprocess.run(cmd,cwd=root/'project',stdout=log,stderr=subprocess.STDOUT)
assert p.returncode==0
summary=root/'project/place_route/top_timing_summary_after_hold_fix.txt';detail=root/'project/report_timing/top.rtr'
for f in [summary,detail]:
 text=f.read_text(errors='replace');assert 'Design Summary : All Constraints Met.'in text and 'Slack (VIOLATED)'not in text,str(f)
print('FINAL_IMAGE_BOTH_TIMING_REPORTS_PASS',flush=True)
r['pre_generation_timing_sha256']=r['timing_sha256'];r['timing_sha256']=hashlib.sha256(summary.read_bytes()).hexdigest();r['detailed_timing_sha256']=hashlib.sha256(detail.read_bytes()).hexdigest();r['post_generation_timing_passed']=True
assert hashlib.sha256(Path(r['image']).read_bytes()).hexdigest()==r['sha256']
(root/'bitstream_receipt.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r,indent=2),flush=True)
