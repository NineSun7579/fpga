from pathlib import Path
import json,subprocess
from run_probe import idle
HERE=Path(__file__).resolve().parent
def run(name,inputs='A_original_inputs',dbflag=False):
    idle();out=HERE/name;out.mkdir(exist_ok=False);d=HERE/inputs
    sdc=out/'combined.fdc'
    sdc.write_bytes(b'\n'.join(p.read_bytes() for p in d.glob('*.fdc')))
    cmd=['C:/pango/PDS_2022.2-SP6.4/bin/ta.exe','-sdc',sdc.as_posix(),'-rtr',out.as_posix(),'-tcl',(HERE/(name+'.tcl')).as_posix(),(d/'synthesis.adf').as_posix()]
    if dbflag:cmd.insert(-1,'-db')
    with (out/'shell.log').open('wb') as f:p=subprocess.run(cmd,cwd=out,stdout=f,stderr=subprocess.STDOUT)
    (out/'result.json').write_text(json.dumps({'command':cmd,'exit_code':p.returncode},indent=2));print(name,p.returncode,flush=True)
if __name__=='__main__':run('ta_probe')
