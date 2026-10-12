"""Only component compile/synthesis; single PDS instance checked each stage."""
from pathlib import Path
import subprocess,json,time,hashlib
HERE=Path(__file__).resolve().parent;WORK=HERE/'component_01'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
def main():
    receipt={'scope':'component only, common clock; no PnR/PCIe/CDC proof','stages':[]}
    for stage in ['compile','synthesize']:
        check=subprocess.run(['powershell.exe','-NoProfile','-Command',
          '$items=@(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | Select-Object Id,ProcessName); ConvertTo-Json -InputObject $items -Compress'],capture_output=True,text=True,check=True)
        processes=json.loads(check.stdout.strip() or '[]')
        (WORK/f'process_check_{stage}.json').write_text(json.dumps(processes,indent=2))
        if processes:raise RuntimeError('Another PDS instance exists; component launch blocked')
        cmd=[str(PDS),'-project',str(WORK/'project.pds'),'-run',stage,'-work_dir',str(WORK)]
        started=time.monotonic()
        with (WORK/f'{stage}_stdout.log').open('wb') as out:
            r=subprocess.run(cmd,cwd=WORK,stdout=out,stderr=subprocess.STDOUT)
        receipt['stages'].append({'command':cmd,'returncode':r.returncode,'seconds':time.monotonic()-started})
        (WORK/'run_results.json').write_text(json.dumps(receipt,indent=2))
        if r.returncode:raise RuntimeError(f'{stage} failed; exact log retained')
    print('COMPONENT_SYNTHESIS_FINISHED')
if __name__=='__main__':main()
