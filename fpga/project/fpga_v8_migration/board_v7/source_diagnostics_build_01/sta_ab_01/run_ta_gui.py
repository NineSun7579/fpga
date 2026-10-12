from pathlib import Path
import subprocess,json,sys,shutil
from run_probe import idle
HERE=Path(__file__).resolve().parent
name=sys.argv[1] if len(sys.argv)>1 else 'ta_cli_db_only'
idle();out=HERE/name;out.mkdir(exist_ok=False)
d=HERE/'A_original_inputs';sdc=out/'combined.sdc'
if len(sys.argv)>2:sdc.write_bytes((HERE/sys.argv[2]).read_bytes())
else:sdc.write_bytes(b'\n'.join(p.read_bytes() for p in d.glob('*.fdc')))
db=out/'synthesis.adf';shutil.copy2(d/'synthesis.adf',db)
cmd=['C:/pango/PDS_2022.2-SP6.4/bin/ta.exe','-sdc',sdc.as_posix(),'-rtr',out.as_posix(),db.as_posix()]
if '--empty' in sys.argv:cmd=cmd[:1]
with (out/'shell.log').open('wb') as f:
 p=subprocess.Popen(cmd,cwd=out,stdout=f,stderr=subprocess.STDOUT)
 (out/'launch.json').write_text(json.dumps({'command':cmd,'pid':p.pid},indent=2))
 rc=p.wait()
(out/'result.json').write_text(json.dumps({'command':cmd,'exit_code':rc},indent=2))
reports=HERE/'Timing Analyzer'
own_reports=[f for f in out.iterdir() if f.is_file() and f.suffix in ('.snr','.rtr','.db')]
if own_reports:
 snapshot=out/'report_snapshot';snapshot.mkdir()
 for report in own_reports:shutil.copy2(report,snapshot/report.name)
elif reports.exists():shutil.copytree(reports,out/'report_snapshot')
print(name,rc,flush=True)
