from pathlib import Path
import subprocess,json,hashlib,datetime
HERE=Path(__file__).resolve().parent
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
def idle():
    p=subprocess.run(['powershell','-NoProfile','-Command',"Get-Process | Where-Object { $_.ProcessName -match '^(pds|pds_shell|ta|de)$' } | Select-Object Id,ProcessName | ConvertTo-Json"],capture_output=True)
    assert not p.stdout.strip(),p.stdout
def run(name):
    idle()
    out=HERE/name;out.mkdir(exist_ok=False)
    cmd=[str(PDS),'-file',str(HERE/(name+'.tcl')),'-work_dir',str(out),'-project_name',name]
    with (out/'shell.log').open('wb') as log:
        p=subprocess.run(cmd,cwd=out,stdout=log,stderr=subprocess.STDOUT)
    (out/'result.json').write_text(json.dumps({'command':cmd,'exit_code':p.returncode},indent=2))
    print(name,p.returncode,flush=True)
if __name__=='__main__':run('probe')
