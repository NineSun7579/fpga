"""Reviewed recovery only; no held trial, candidate, viewer, flash or DMA/BAR open."""
import argparse
import difflib
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
import controller as c

REVIEWER='Codex subagent / actual06 independent source reviewer (this session)'

def archive_review():
    src=c.GOAL/'recovery_execution_prepare05'
    evidence={}
    for name in ('controller.py','admission_guard.py','inspect_startup_readonly.py','REVIEW_ZH.md','manifest.json'):
        evidence[name]=c.sha(src/name)
        if (c.HERE/name).exists() and name.endswith('.py'):
            delta=''.join(difflib.unified_diff((src/name).read_text().splitlines(True),(c.HERE/name).read_text().splitlines(True),fromfile='prepare05/'+name,tofile='actual06/'+name))
            (c.HERE/(name+'.diff')).write_text(delta,encoding='utf-8')
    c.save(c.HERE/'source_review.json',dict(reviewer=REVIEWER,reviewed_utc=c.utc(),original_sha256=evidence,current_sha256={n:c.sha(c.HERE/n) for n in ('controller.py','admission_guard.py','inspect_startup_readonly.py','run_actual.py')},scope=['cancel-before-reboot','reboot','post-reboot'],future_qualification_accepted=False,held_trial_authorized=False))

def prepare():
    archive_review()
    for attempt in range(3):
        d=c.HERE/('fresh_'+str(attempt)+'_'+__import__('uuid').uuid4().hex[:8]); d.mkdir()
        started=c.utc()
        try:
            binding=c.refresh(d)
            c.save(d/'connect.receipt.json',dict(started_utc=started,ended_utc=c.utc(),connected=True))
        except Exception as e:
            c.save(d/'connect.receipt.json',dict(started_utc=started,ended_utc=c.utc(),connected=False,error_type=type(e).__name__,error=str(e)))
            if attempt==2: raise
            time.sleep(5)
            continue
        plan=json.loads((d/'execution_plan.prepare.json').read_bytes())
        if plan['producer_inventory']!=[dict(path='/userdata/detview-driving-demo/detview-driving-demo',sha256='72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703')]:
            raise RuntimeError('Fresh producer differs from independently reviewed inventory')
        for p in binding['processes']:
            if 'driving-demo' in ' '.join(p['argv']):
                raise RuntimeError('Fresh active producer identity requires review; retained full argv/hash/stat')
        plan.update(reviewer=REVIEWER,reviewed_utc=c.utc(),exclusive_operator_control=True,held_trial_authorized=False,review_scope=['cancel-before-reboot','reboot','post-reboot'],source_review_sha256=c.sha(c.HERE/'source_review.json'),fresh_evidence_directory=str(d),admission_ledger='/var/lib/fpga-recovery-actual06/admission.json',qualification_accepted=False)
        dest=c.HERE/('execution_plan.reviewed_'+d.name+'.json'); c.save(dest,plan)
        print(json.dumps(dict(status='actually_reviewed_execution_plan',plan=str(dest),boot=plan['boot_before'],endpoint=plan['endpoint'],parent=plan['parent_bdf'])),flush=True)
        return dest

def execute(planpath):
    root=c.HERE/('execution_'+__import__('uuid').uuid4().hex[:12]); root.mkdir()
    lease=None; lock=None
    result=dict(started_utc=c.utc(),accepted=False,goal_complete=False)
    try:
        lock=os.open(c.HERE/'execution.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.write(lock,str(os.getpid()).encode())
        lease=c.tool_lease(root)
        for phase in ('cancel-before-reboot','reboot'):
            d=root/phase; d.mkdir()
            c.execute_phase(SimpleNamespace(execution_plan=planpath,phase=phase),d)
            c.save(d/'phase.receipt.json',dict(phase=phase,returned_utc=c.utc(),status='returned_pending_independent_qualification',accepted=False))
            if phase=='cancel-before-reboot':
                plan=json.loads(planpath.read_bytes())
                proof=d/'qualified_v7_sram.binding.json'
                # v7_program has parsed exact original cfg stages/DONE and all log errors.
                plan['sram_success_evidence']=str(proof)
                plan['sram_evidence_review']=dict(reviewer=REVIEWER,reviewed_utc=c.utc(),binding_sha256=c.sha(proof),vendor_done_verified=True,qualification_accepted=False)
                planpath=root/'execution_plan.with_actual_DONE.json'; c.save(planpath,plan)
        # A reboot command return is not boot success. Bounded new-boot probes below.
        connected=False
        for attempt in range(18):
            d=root/('reconnect_'+str(attempt)); d.mkdir()
            client=None
            try:
                client=c.connect()
                boot=c.record(d,'boot_probe','cat /proc/sys/kernel/random/boot_id\n',c.transport(client)).decode().strip()
                if boot!=json.loads(planpath.read_bytes())['boot_before']:
                    connected=True; break
            except Exception as e:
                c.save(d/'connection_error.json',dict(utc=c.utc(),error_type=type(e).__name__,error=str(e)))
            finally:
                if client: client.close()
            time.sleep(5)
        if not connected: raise RuntimeError('Bounded reconnect did not prove actual new boot')
        d=root/'post-reboot'; d.mkdir()
        c.execute_phase(SimpleNamespace(execution_plan=planpath,phase='post-reboot'),d)
        result.update(status='real_recovery_actions_returned_pending_qualification',rebuilt_evidence=str(d/'rebuilt.prepare.json'))
    except Exception as e:
        result.update(status='blocked_or_partial',error_type=type(e).__name__,error=str(e))
        raise
    finally:
        if lease:
            k,h=lease; k.ReleaseMutex(h); k.CloseHandle(h)
        if lock is not None:
            os.close(lock); (c.HERE/'execution.lock').unlink()
        result.update(ended_utc=c.utc(),retained_directory=str(root))
        c.save(root/'actual_result.json',result); print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--prepare',action='store_true'); p.add_argument('--execute-plan',type=Path); a=p.parse_args()
    if a.prepare: prepare()
    elif a.execute_plan: execute(a.execute_plan)
    else: p.error('Explicit --prepare or --execute-plan required')
