"""Offline regression + protected rehash + final bundle sealing."""
from pathlib import Path
import ast,json,subprocess,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE/'runtime'))
from contract import load,sha,require
def main():
    run=subprocess.run([sys.executable,'-B',str(HERE/'regress.py')],capture_output=True,cwd=HERE)
    (HERE/'offline_regression.log').write_bytes(run.stdout+run.stderr);require(run.returncode==0,'Regression failed')
    run=subprocess.run([sys.executable,'-B',str(HERE/'controller.py'),'route'],capture_output=True,cwd=HERE)
    (HERE/'default_route_rejected.log').write_bytes(run.stdout+run.stderr)
    require(run.returncode!=0 and b'BLOCKED: no explicit main-session enable' in run.stderr,'Default route not blocked')
    require(not (HERE/'execution01').exists(),'Default guard created execution dir')
    for row in load(HERE/'reuse_ledger.json'):
        require(sha(row['source'])==row['before_sha256'] and sha(row['destination'])==row['after_sha256'],'Reuse script drift')
    before=load(HERE/'input_before.json');after={p:sha(p) for p in before};require(after==before,'Protected evidence/source drift')
    files=list(HERE.glob('*.py'))+list((HERE/'runtime').glob('*.py'))
    for p in files:ast.parse(p.read_bytes(),filename=str(p))
    require(all(p.read_bytes().startswith(b'error {BLOCKED:') for p in (HERE/'commands').glob('*.tcl')),'Tcl lock missing')
    (HERE/'final_review_checks.json').write_text(json.dumps({'offline_regression':load(HERE/'offline_regression.json'),'default_route_rejected':True,'execution01_absent':True,'pds_started':False,'bit_generated':False,'board_actions':False,'protected_input_files':len(before),'final_protected_hashes_unchanged':True,'reuse_before_after_verified':True,'AST_modules':len(files),'all_Tcl_locked':True},indent=2)+'\n',encoding='ascii')
    import seal;seal.main()
    manifest={p.relative_to(HERE).as_posix():sha(p) for p in HERE.rglob('*') if p.is_file() and p.name!='review_bundle_hashes.json'}
    (HERE/'review_bundle_hashes.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='ascii')
    print(run.stderr.decode('utf8',errors='replace').splitlines()[-1]);print('FINAL OFFLINE REVIEW PASS; protected files:',len(before),'bundle files:',len(manifest))
if __name__=='__main__':main()
