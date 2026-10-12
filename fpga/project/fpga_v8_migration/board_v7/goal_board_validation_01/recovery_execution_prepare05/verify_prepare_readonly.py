"""Offline verification of real default/dry-run output and refresh evidence hashes."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('prepare05_controller',HERE/'controller.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
def forbidden(*a,**kw):
    raise AssertionError('Default/dry-run attempted SSH, subprocess or execution')
c.connect=forbidden
c.refresh=forbidden
c.execute_phase=forbidden
c.subprocess.run=forbidden
checks=[]
for name,args in [('default',[]),('dry_run',['--dry-run'])]:
    sys.argv=['controller.py',*args]
    output=io.StringIO()
    with contextlib.redirect_stdout(output):
        code=c.main()
    raw=output.getvalue().encode('utf-8')
    (HERE/(name+'.stdout.txt')).write_bytes(raw)
    result=json.loads(raw)
    assert code==0 and result['status']=='prepared_only' and result['board_changed'] is False and result['accepted'] is False
    checks.append(dict(case=name,exit_code=code,stdout_sha256=hashlib.sha256(raw).hexdigest(),ssh_or_subprocess_allowed=False,retained_directory=result['retained_directory']))
for path in HERE.glob('*.py'):
    ast.parse(path.read_bytes())
refresh=HERE/'run_b115656b2183'
receipts=[]
for p in refresh.glob('*.receipt.json'):
    r=json.loads(p.read_bytes());name=p.name.removesuffix('.receipt.json')
    for label,suffix in [('command','command.txt'),('stdout','stdout.txt'),('stderr','stderr.txt')]:
        assert r[label+'_sha256']==hashlib.sha256((refresh/(name+'.'+suffix)).read_bytes()).hexdigest()
    assert r['exit_code']==0
    receipts.append(p.name)
result=dict(status='offline_checks_passed',checks=checks,verified_refresh_directory=str(refresh),verified_raw_receipts=receipts,controller_sha256=c.sha(HERE/'controller.py'),accepted=False,board_mutation_executed=False)
(HERE/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
