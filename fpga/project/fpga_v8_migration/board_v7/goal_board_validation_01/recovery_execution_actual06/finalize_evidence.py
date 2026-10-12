"""Offline evidence audit; no board, tool or network actions."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import controller as c
import run_actual as r

r.archive_review()
results={}
for name in ('controller.py','admission_guard.py','inspect_startup_readonly.py','run_actual.py','finalize_evidence.py'):
    ast.parse((c.HERE/name).read_text())
results['syntax']='pass'
for label,args in [('default',[]),('dry_run',['--dry-run'])]:
    p=subprocess.run([sys.executable,'-B',str(c.HERE/'controller.py'),*args],cwd=c.HERE,capture_output=True)
    (c.HERE/(label+'.stdout.txt')).write_bytes(p.stdout)
    (c.HERE/(label+'.stderr.txt')).write_bytes(p.stderr)
    doc=json.loads(p.stdout)
    assert p.returncode==0 and doc['board_changed'] is False and doc['accepted'] is False
    results[label]=dict(exit_code=p.returncode,stdout_sha256=hashlib.sha256(p.stdout).hexdigest(),stderr_sha256=hashlib.sha256(p.stderr).hexdigest(),board_changed=doc['board_changed'])
review=json.loads((c.HERE/'source_review.json').read_bytes())
assert all(c.sha(c.GOAL/'recovery_execution_prepare05'/n)==h for n,h in review['original_sha256'].items())
results['prepare05_original_hashes_unchanged']=True
results['qualified_bit_sha256']=c.sha(c.BIT)
assert results['qualified_bit_sha256']==c.EXPECTED_BIT
connects=[]
for path in sorted(c.HERE.glob('fresh_*/connect.receipt.json')):
    doc=json.loads(path.read_bytes()); assert doc['connected'] is False
    connects.append(dict(path=str(path),sha256=c.sha(path),**doc))
assert len(connects)==3
blocked=dict(status='blocked_before_fresh_board_binding',reviewer=r.REVIEWER,reviewed_utc=c.utc(),reviewed_scope=['cancel-before-reboot','reboot','post-reboot'],review_completed=True,execution_ready=False,accepted=False,boot_before=None,endpoint=None,parent_bdf=None,qualified_v7_bit_sha256=c.EXPECTED_BIT,producer_inventory=[dict(path='/userdata/detview-driving-demo/detview-driving-demo',sha256='72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703')],exclusive_operator_control=True,held_trial_authorized=False,blocker='192.168.10.203:22 SSH TCP connect timeout on all three bounded fresh attempts; no current boot/BDF can be bound',source_review_sha256=c.sha(c.HERE/'source_review.json'),connect_attempts=connects,offline_delivery_verification_exit_code=0,offline_delivery_stdout_sha256=c.sha(c.HERE/'verify_delivery.offline.stdout.txt'),board_actions_executed=False,admission_changed=False,cancel_executed=False,vendor_receipt=None,vendor_DONE=None,reboot_executed=False,new_boot=None,current_driver_fresh=None,qualification_accepted=False,goal_complete=False)
c.save(c.HERE/'execution_plan.reviewed_blocked.json',blocked)
c.save(c.HERE/'verification.json',results)
files={str(p.relative_to(c.HERE)):dict(bytes=p.stat().st_size,sha256=c.sha(p)) for p in c.HERE.rglob('*') if p.is_file() and p.name!='manifest.json'}
c.save(c.HERE/'manifest.json',dict(utc=c.utc(),status=blocked['status'],files=files))
print(json.dumps(dict(status=blocked['status'],verification=results,connect_attempts=len(connects),board_actions_executed=False),indent=2))
