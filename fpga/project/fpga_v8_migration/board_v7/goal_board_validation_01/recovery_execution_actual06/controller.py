"""Serial recovery preparation. Default is offline dry-run; --refresh is SSH read-only.

Future execution is deliberately phase-scoped and requires an independently reviewed
plan binding the live boot/endpoint/parent and the exact startup admission commands.
This file never manufactures an accepted owner preflight or session certificate.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import uuid
import threading
from datetime import datetime, timezone

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
M = GOAL.parents[1]
V7 = M/'whole_candidate_v7_route_01'
BIT = V7/'bitstream_01/generate_bitstream/fpga_v8_cooperative_top_v2_rfg01.sbit'
EXPECTED_BIT = 'dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60'
TOOLS = M.parent/'tools'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def utc():
    return datetime.now(timezone.utc).isoformat()

def save(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def record(directory, name, command, runner):
    raw = command.encode()
    (directory/(name+'.command.txt')).write_bytes(raw)
    started = utc()
    try:
        code, out, err = runner(command)
    except Exception as exc:
        code, out, err = -1, b'', (type(exc).__name__ + ': ' + str(exc)).encode()
    for suffix, data in [('stdout.txt',out),('stderr.txt',err)]:
        (directory/(name+'.'+suffix)).write_bytes(data)
    receipt = dict(started_utc=started, ended_utc=utc(), exit_code=code, command_sha256=hashlib.sha256(raw).hexdigest(), stdout_sha256=hashlib.sha256(out).hexdigest(), stderr_sha256=hashlib.sha256(err).hexdigest())
    save(directory/(name+'.receipt.json'),receipt)
    if code:
        raise RuntimeError(name+' failed; retained raw rc/output')
    return out

def connect():
    # Exact established connection provider from recovery_state_refresh03; no guessed credentials.
    sys.path.insert(0, str(TOOLS))
    from board_host import ssh_connect, board_host
    if board_host() != '192.168.10.203':
        raise RuntimeError('Established host resolution changed')
    return ssh_connect()

def transport(client):
    def run(command):
        _, out, err = client.exec_command(command, timeout=120)
        a,b = out.read(),err.read()
        return out.channel.recv_exit_status(),a,b
    return run

def refresh(directory):
    source = GOAL/'recovery_state_refresh03/collect_readonly.py'
    spec = importlib.util.spec_from_file_location('refresh03', source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    client = connect()
    try:
        run = transport(client)
        for name, command in mod.COMMANDS.items():
            record(directory, name, command, run)
        command = "sudo -n python3 - <<'PREPARE05_READONLY'\n"+(HERE/'inspect_startup_readonly.py').read_text()+"\nPREPARE05_READONLY\n"
        startup = json.loads(record(directory,'startup',command,run))
        finalboot = record(directory,'boot_final','cat /proc/sys/kernel/random/boot_id\n',run).decode().strip()
        pci = json.loads((directory/'pci.stdout.txt').read_text())
        owners = json.loads((directory/'owners.stdout.txt').read_text())
        if startup['scan_errors'] or owners['scan_errors']:
            raise RuntimeError('Incomplete actual proc/startup scan')
        if startup['holders'] or owners['owners']:
            raise RuntimeError('Actual device holders present; no automatic signals')
        for endpoint in pci['endpoints']:
            if any(c['returncode'] != 0 for c in endpoint['commands'].values()):
                raise RuntimeError('PCI probe command failed')
        if finalboot != pci['boot_id'] or finalboot != owners['boot_id'] or finalboot != startup['boot_id']:
            raise RuntimeError('Boot changed during read-only refresh')
        binding = dict(boot_before=finalboot, endpoints=pci['endpoints'], holders=startup['holders'], processes=startup['processes'], startup=startup['startup'], scan_errors=startup['scan_errors'], qualified_v7_bit=str(BIT), qualified_v7_bit_sha256=sha(BIT), qualified_v7_manifest_sha256=sha(V7/'delivery_manifest.json'), ssh_helper_sha256=sha(TOOLS/'board_host.py'), refresh03_sha256=sha(source), admission_persistently_held=False, drained_proven=False, accepted=False)
        save(directory/'binding.json',binding)
        hashes=[c for c in startup['commands'] if c['argv'][0]=='sha256sum']
        if len(pci['endpoints'])==1 and hashes and hashes[0]['returncode']==0:
            endpoint=pci['endpoints'][0]
            line=hashes[0]['stdout'].splitlines()[0].split(maxsplit=1)
            save(directory/'execution_plan.prepare.json',dict(reviewer='',boot_before=finalboot,endpoint=endpoint['endpoint'],parent_bdf=endpoint['parent_bdf'],qualified_v7_bit_sha256=sha(BIT),producer_inventory=[dict(path=line[1].strip(),sha256=line[0])],binding_sha256=sha(directory/'binding.json'),exclusive_operator_control=False,held_trial_authorized=False,enumeration_command='',driver_binding_verify_command='',sram_success_evidence='',post_reboot_evidence='',manifest='',owner_preflight='',startup_qualification_evidence=''))
        return binding
    finally:
        client.close()

def recipe(binding=None):
    return dict(status='prepared_only', accepted=False, mode='sram_only', bit=str(BIT), bit_sha256=sha(BIT), board_changed=False, binding=binding,
      serial_order=[
        'independent exact argv/exe/starttime review -> persistent autostart admission hold -> full proc fd/maps no-owner scan; never stop actual MP4 by PID',
        'read Command -> masked BME clear -> actual readback -> sysfs reset_method bus -> actual reset rc -> Command BME=0',
        f'{sys.executable} {M / "timing_correction_05/program_board.py"} (no arguments; complete qualified V7 SRAM; verify raw DONE/vendor receipt)',
        'explicit reboot action -> reconnect -> boot_before != boot_after; refresh actual RC/endpoint/driver; hold persists across reboot',
        'fresh independently reviewed boardOwnerPreflight/v1 before SBR assert; preflight never derived from empty holders alone',
        'qualified V7 held-SBR startup trial: parent BRIDGE_CONTROL=0040:0040 -> read bit6 -> full V7 SRAM -> read bit6 -> BRIDGE_CONTROL=0000:0040 -> actual enumeration/binding evidence',
        'stop for actual held-SBR qualification review; no final candidate execution until qualified build manifest and actual independent acceptance',
        f'{sys.executable} {GOAL / "capture_program_session.py"} --execute --manifest <actual-qualified-new-manifest> --owner-preflight <actual-fresh-independent-preflight> (under held SBR, then release; no additional post-program SBR)',
        'actual new_validate_board consumer and post-program runtime/screenshot evidence on matching boot; no inferred accepted'],
      limitations=['held-SBR core first-start/physical PERST evidence remains unproven', 'enumeration/driver rebind may introduce implicit reset; exact board path must be reviewed', 'V7 legacy program_board has no owner-preflight CLI and writes no programSession/v1; do not pass V7 through candidate consumer', 'persistent admission must cover actual autostart plus arbitrary new submissions; process absence is not a durable hold', 'prepare05 is not an independent verifier'])

def admission_command(plan,mode):
    return "sudo -n python3 - <<'ADMISSION05'\n"+(HERE/'admission_guard.py').read_text()+f"\nmain({mode!r}, {plan['producer_inventory']!r})\nADMISSION05\n"

def tool_lease(directory):
    import ctypes
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
    k.CreateMutexW.restype=ctypes.c_void_p
    k.ReleaseMutex.argtypes=[ctypes.c_void_p]; k.CloseHandle.argtypes=[ctypes.c_void_p]
    k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]; k.WaitForSingleObject.restype=ctypes.c_ulong
    h=k.CreateMutexW(None,False,'Global\\ov56401_PDS_single_instance')
    existed=ctypes.get_last_error()==183
    acquired=False; waits=[]
    if h:
        for attempt in range(20):
            result=k.WaitForSingleObject(h,30000)
            waits.append(dict(utc=utc(),wait_result=result))
            if result in (0,128): acquired=True; break
            if result!=258: break
            print('Waiting before any board mutation: global PDS mutex still owned',flush=True)
    save(directory/'global_mutex.json',dict(utc=utc(),pid=os.getpid(),name='Global\\ov56401_PDS_single_instance',object_existed=existed,waits=waits,acquired=acquired))
    if not acquired:
        if h: k.CloseHandle(h)
        raise RuntimeError('Global PDS mutex unavailable after bounded wait; no board mutation')
    try:
        query="Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {$_.Name -match '^(pds|pds_shell|pnr|ta|bitgen|pne|ppc|ppp|synth|cdt_js|cdt_cfg|cdt_cfg_shell|programmer)\\.exe$'} | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
        def local(_):
            p=subprocess.run(['powershell.exe','-NoProfile','-Command',query],capture_output=True,timeout=30)
            return p.returncode,p.stdout,p.stderr
        if record(directory,'global_tool_idle',query,local).strip():
            raise RuntimeError('Global vendor tools active; no board mutation')
        # Vendor performs this check again. It does not acquire a nested global mutex.
        import socket
        with socket.socket() as sock: sock.bind(('127.0.0.1',65426))
        return k,h
    except Exception:
        k.ReleaseMutex(h); k.CloseHandle(h); raise

def v7_program(directory, name, boot):
    cmd=[sys.executable,str(M/'timing_correction_05/program_board.py')]
    def local(_):
        p=subprocess.run(cmd,cwd=M/'timing_correction_05',capture_output=True)
        return p.returncode,p.stdout,p.stderr
    raw=record(directory,name,subprocess.list2cmdline(cmd),local).decode('utf-8')
    decoder=json.JSONDecoder(); candidates=[]
    for pos,ch in enumerate(raw):
        if ch!='{': continue
        try:
            obj,_=decoder.raw_decode(raw[pos:])
            if isinstance(obj,dict) and obj.get('retained_directory') and obj.get('bit_sha256')==EXPECTED_BIT: candidates.append(obj)
        except json.JSONDecodeError: pass
    if len(candidates)!=1: raise RuntimeError('Exactly one V7 receipt required')
    r=candidates[0]
    if r.get('status')!='success' or r.get('mode')!='sram' or r.get('target')!='PG2L100H' or not r.get('stages') or not all(r['stages'].values()):
        raise RuntimeError('V7 SRAM stages incomplete')
    original=Path(r['retained_directory'])/'receipt.json'
    if json.loads(original.read_bytes())!=r: raise RuntimeError('Original V7 receipt mismatch')
    sys.path.insert(0,str(GOAL))
    from new_validate_board import vendor_parser
    parse,errors=vendor_parser()
    logs={str(Path(p).resolve()):sha(p) for p in r['logs']}
    cfg=[Path(p) for p in r['logs'] if 'cfg' in Path(p).name.lower() and Path(p).suffix=='.log']
    if len(cfg)!=1: raise RuntimeError('Missing original cfg log')
    stages,failures=parse(cfg[0].read_bytes().decode('gb18030').replace('\r\n','\n'),'sram')
    if failures or stages!=r['stages'] or not all(stages.values()): raise RuntimeError('Raw vendor SRAM/DONE parse failed')
    if r.get('stage_errors') or any(errors.search(Path(p).read_bytes().decode('gb18030')) for p in r['logs'] if Path(p)!=cfg[0]):
        raise RuntimeError('Vendor server/client raw log errors')
    save(directory/(name+'.binding.json'),dict(original_receipt=str(original),receipt_sha256=sha(original),log_sha256=logs,bit_sha256=EXPECTED_BIT,boot_before=boot,accepted=False))

def monitored_program(run,directory,parent,program):
    stopped=threading.Event();failed=[]
    def watch():
        n=0
        while not stopped.is_set():
            try:
                value=record(directory,'held_sample_'+str(n),f'sudo -n setpci -s {parent} BRIDGE_CONTROL',run).decode().strip()
                if len(value)!=4 or int(value,16)==65535 or not int(value,16)&64:
                    raise RuntimeError('SBR sample lost assertion')
                n+=1
            except Exception as e:
                failed.append(type(e).__name__); return
            stopped.wait(0.25)
    thread=threading.Thread(target=watch,daemon=True);thread.start()
    try:
        program()
    finally:
        stopped.set();thread.join(timeout=130)
    if thread.is_alive() or failed:
        raise RuntimeError('SBR monitor failed; retain asserted state and actual logs')

def bridge_action(run,directory,parent,asserted):
    # Word mask only; preserve all bits other than SBR bit6 and reject all-ones.
    command=f"""sudo -n python3 - <<'BRIDGE05'
import subprocess
parent={parent!r}
def rd():
 p=subprocess.run(['setpci','-s',parent,'BRIDGE_CONTROL'],capture_output=True,text=True)
 print('read',p.returncode,p.stdout,p.stderr,flush=True)
 assert p.returncode==0 and len(p.stdout.strip())==4
 v=int(p.stdout.strip(),16); assert v!=65535
 return v
old=rd()
subprocess.run(['setpci','-s',parent,'BRIDGE_CONTROL={'0040' if asserted else '0000'}:0040'],check=True)
new=rd()
assert old & ~64 == new & ~64
assert bool(new & 64)=={asserted!r}
BRIDGE05
"""
    record(directory,'sbr_assert' if asserted else 'sbr_release',command,run)

def execute_phase(args, directory):
    # Future main-reviewer use only. Reviewed concrete remote commands are not invented here.
    plan = json.loads(args.execution_plan.read_text(encoding='utf-8-sig'))
    if args.phase not in ('cancel-before-reboot','reboot','post-reboot'):
        raise RuntimeError('actual06 scope excludes held trials and candidate')
    required = ('reviewer','boot_before','endpoint','parent_bdf','producer_inventory','exclusive_operator_control')
    if not all(plan.get(k) for k in required):
        raise RuntimeError('Concrete reviewed execution plan incomplete')
    if plan.get('qualified_v7_bit_sha256') != EXPECTED_BIT:
        raise RuntimeError('Wrong recovery bit binding')
    if plan['producer_inventory'] != [dict(path='/userdata/detview-driving-demo/detview-driving-demo',sha256='72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703')]:
        raise RuntimeError('actual06 only authorizes exact reviewed driving producer ELF')
    # Never start programmer while other PDS work is active.
    if args.phase in ('cancel-before-reboot','held-v7','held-candidate'):
        probe = subprocess.run(['powershell.exe','-NoProfile','-Command','Get-Process pds,pds_shell,programmer -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id'],capture_output=True)
        if probe.stdout.strip():
            raise RuntimeError('PDS/programmer active; execution deferred')
    client = connect()
    try:
        run = transport(client)
        boot = record(directory,'execution_boot','cat /proc/sys/kernel/random/boot_id\n',run).decode().strip()
        if args.phase!='post-reboot' and boot != plan['boot_before']:
            raise RuntimeError('Reviewed boot stale')
        import re
        ep, parent = plan['endpoint'], plan['parent_bdf']
        if not all(re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', s) for s in (ep,parent)):
            raise RuntimeError('Invalid BDF')
        # Bind topology and device IDs again before any action.
        check = f"test $(cat /sys/bus/pci/devices/{ep}/vendor) = 0x0755 && test $(cat /sys/bus/pci/devices/{ep}/device) = 0x0755 && test $(basename $(dirname $(readlink -f /sys/bus/pci/devices/{ep}))) = {parent}"
        if args.phase=='post-reboot':
            if boot==plan['boot_before']: raise RuntimeError('Boot did not change')
            record(directory,'admission_post_reboot',admission_command(plan,'verify'),run)
            # Read-only refresh uses a new local evidence directory; no assumed BDF after reboot.
            sub=directory/'post_reboot';sub.mkdir();binding=refresh(sub)
            if len(binding['endpoints'])!=1: raise RuntimeError('Actual unique endpoint not enumerated')
            if binding['boot_before']!=boot: raise RuntimeError('Boot changed during post-reboot refresh')
            save(directory/'rebuilt.prepare.json',dict(boot_before=plan['boot_before'],boot_after=boot,binding_sha256=sha(sub/'binding.json'),accepted=False))
            return
        if args.phase=='release-sbr':
            record(directory,'admission_verify',admission_command(plan,'verify'),run)
            record(directory,'release_parent_identity',f'test $(cat /sys/bus/pci/devices/{parent}/class) = 0x060400',run)
            bridge_action(run,directory,parent,False)
            save(directory/'release_only.json',dict(accepted=False,reason='explicit recovery release; does not certify program or runtime'))
            return
        record(directory,'execution_identity',check+f' && test $(cat /sys/bus/pci/devices/{parent}/class) = 0x060400',run)
        record(directory,'admission_verify',admission_command(plan,'hold' if args.phase=='cancel-before-reboot' else 'verify'),run)
        if args.phase=='reboot':
            evidence=Path(plan['sram_success_evidence'])
            proof=json.loads(evidence.read_bytes())
            if proof.get('bit_sha256')!=EXPECTED_BIT or proof.get('boot_before')!=boot or sha(proof['original_receipt'])!=proof['receipt_sha256']:
                raise RuntimeError('Missing actual full V7 SRAM evidence')
            if any(sha(p)!=h for p,h in proof['log_sha256'].items()): raise RuntimeError('Vendor log drift')
            # SSH may disconnect on reboot; retain its actual status. Never invent boot_after.
            interrupted=False
            try:
                record(directory,'reboot_action','sudo -n systemctl reboot',run)
            except RuntimeError:
                receipt=json.loads((directory/'reboot_action.receipt.json').read_bytes())
                if receipt['exit_code']!=-1: raise
                interrupted=True
            save(directory/'reboot_requested.json',dict(boot_before=boot,transport_interrupted=interrupted,reboot_success_proven=False,accepted=False,next='bounded reconnect then post-reboot must prove actual different boot'))
            return
        if args.phase in ('held-v7','held-candidate'):
            if not plan.get('held_trial_authorized') or not plan.get('enumeration_command') or not plan.get('driver_binding_verify_command'):
                raise RuntimeError('Concrete reviewed held trial/enumeration/binding commands missing')
            if not plan.get('post_reboot_evidence'):
                raise RuntimeError('Actual rebuilt evidence missing')
            rebuilt=json.loads(Path(plan['post_reboot_evidence']).read_bytes())
            if rebuilt['boot_after']!=boot or rebuilt['boot_before']==boot: raise RuntimeError('Rebuilt evidence boot mismatch')
            if args.phase=='held-candidate':
                # Local verify and preflight happen BEFORE SBR, then the unmodified consumer
                # checks the same independently accepted preflight under SBR without DMA open.
                if not plan.get('startup_qualification_evidence'): raise RuntimeError('V7 trial independent startup qualification missing')
                qualification=json.loads(Path(plan['startup_qualification_evidence']).read_bytes())
                if qualification.get('accepted') is not True or not qualification.get('reviewer'): raise RuntimeError('Startup review not accepted')
                sys.path.insert(0,str(GOAL))
                from new_program_candidate import verify,verify_owner_preflight,load
                manifest=Path(plan['manifest']);preflight=Path(plan['owner_preflight'])
                m,bit=verify(manifest)
                verify_owner_preflight(load(preflight),sha(manifest),m['bitstream']['sha256'])
            # BME clear/readback before SBR only; unavailable endpoint under held SBR is
            # not interpreted as BME=0. Initial cancellation reset is never repeated here.
            clear=f"sudo -n setpci -s {ep} COMMAND=0000:0004 && sudo -n setpci -s {ep} COMMAND"
            value=record(directory,'held_entry_bme',clear,run).decode().strip()
            if len(value)!=4 or int(value,16)==65535 or int(value,16)&4: raise RuntimeError('Held entry BME invalid')
            bridge_action(run,directory,parent,True)
            # On any failure leave SBR asserted, admission held, retain logs. Only
            # explicit release-sbr may release; never auto rollback into DMA activity.
            if args.phase=='held-v7':
                monitored_program(run,directory,parent,lambda:v7_program(directory,'held_v7_sram',boot))
            else:
                cmd=[sys.executable,str(GOAL/'capture_program_session.py'),'--execute','--manifest',str(manifest),'--owner-preflight',str(preflight)]
                def local(_):
                    p=subprocess.run(cmd,cwd=GOAL,capture_output=True)
                    return p.returncode,p.stdout,p.stderr
                monitored_program(run,directory,parent,lambda:record(directory,'candidate_program_session',subprocess.list2cmdline(cmd),local))
            held=record(directory,'sbr_still_held',f'sudo -n setpci -s {parent} BRIDGE_CONTROL',run).decode().strip()
            if len(held)!=4 or int(held,16)==65535 or not int(held,16)&64: raise RuntimeError('SBR did not remain asserted')
            bridge_action(run,directory,parent,False)
            record(directory,'enumeration',plan['enumeration_command'],run)
            record(directory,'driver_binding',plan['driver_binding_verify_command'],run)
            record(directory,'admission_after_release',admission_command(plan,'verify'),run)
            sub=directory/'post_release';sub.mkdir();refresh(sub)
            save(directory/'trial.prepare.json',dict(status='actual_actions_pending_independent_review',accepted=False,boot=boot))
            return
        if args.phase!='cancel-before-reboot': raise RuntimeError('Unknown phase')
        # Clear only BME, reject short/all-ones reads, require bus reset and readback.
        command = f"""sudo -n python3 - <<'RESET05'
import subprocess
from pathlib import Path
ep={ep!r}
def read():
 p=subprocess.run(['setpci','-s',ep,'COMMAND'],capture_output=True,text=True)
 print('read',p.returncode,p.stdout,p.stderr,flush=True)
 assert p.returncode==0 and len(p.stdout.strip())==4
 v=int(p.stdout.strip(),16); assert v!=65535
 return v
read()
subprocess.run(['setpci','-s',ep,'COMMAND=0000:0004'],check=True)
assert read() & 4 == 0
p=Path('/sys/bus/pci/devices')/ep
method=(p/'reset_method').read_text().strip(); print('reset_method',method,flush=True)
assert method=='bus'
assert read() & 4 == 0
(p/'reset').write_text('1\\n')
print('reset_returned',flush=True)
assert read() & 4 == 0
RESET05
"""
        record(directory,'cancel_reset',command,run)
        record(directory,'admission_after_reset',admission_command(plan,'verify'),run)
        v7_program(directory,'qualified_v7_sram',boot)
        value=record(directory,'post_sram_command',f'sudo -n setpci -s {ep} COMMAND',run).decode().strip()
        if len(value)!=4 or int(value,16)==65535 or int(value,16)&4:
            raise RuntimeError('Post SRAM BME readback invalid; no reboot')
        record(directory,'admission_after_sram',admission_command(plan,'verify'),run)
        # program_board itself verifies manifest, status and all parsed vendor stages.
        # Reboot is separately invoked after reviewer checks retained DONE/raw logs.
        save(directory/'next_action.json',dict(status='sram_returned_pending_raw_receipt_review', reboot_executed=False, command='sudo -n systemctl reboot', boot_before=boot, accepted=False))
    finally:
        client.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--dry-run',action='store_true')
    mode.add_argument('--refresh',action='store_true')
    mode.add_argument('--execute',action='store_true')
    p.add_argument('--execution-plan',type=Path)
    p.add_argument('--phase',default='cancel-before-reboot',choices=['cancel-before-reboot','reboot','post-reboot','held-v7','held-candidate','release-sbr'])
    args=p.parse_args()
    if sha(BIT) != EXPECTED_BIT:
        raise RuntimeError('Qualified V7 bit hash drift')
    directory=HERE/('run_'+uuid.uuid4().hex[:12]); directory.mkdir()
    lock=None; lease=None
    try:
        if args.execute:
            if not args.execution_plan:
                raise RuntimeError('--execute requires independently reviewed --execution-plan')
            lock=os.open(HERE/'execution.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.write(lock,str(os.getpid()).encode())
            if args.phase=='cancel-before-reboot': lease=tool_lease(directory)
            execute_phase(args,directory)
            result=dict(status='phase_returned_pending_review',accepted=False)
        else:
            result=recipe(refresh(directory) if args.refresh else None)
        result.update(retained_directory=str(directory),controller_sha256=sha(__file__))
        save(directory/'result.json',result)
        printed = dict(result)
        if printed.get('binding'):
            b=printed.pop('binding')
            printed['live_summary']=dict(boot_before=b['boot_before'], endpoints=[dict(endpoint=e['endpoint'],parent_bdf=e['parent_bdf'],command=e['commands']['endpoint_command']['stdout'].strip(),bridge_control=e['commands']['bridge_control']['stdout'].strip()) for e in b['endpoints']],holders=len(b['holders']),startup_hits=len(b['startup']),admission_persistently_held=False)
        print(json.dumps(printed,ensure_ascii=False,indent=2))
        return 0
    except Exception as e:
        result=dict(status='blocked_or_partial',error_type=type(e).__name__,error=str(e) if isinstance(e,RuntimeError) else 'Inspect retained artifacts',accepted=False,retained_directory=str(directory))
        save(directory/'result.json',result); print(json.dumps(result,ensure_ascii=False)); return 1
    finally:
        if lease:
            k,h=lease; k.ReleaseMutex(h); k.CloseHandle(h)
        if lock is not None:
            os.close(lock);(HERE/'execution.lock').unlink()

if __name__=='__main__':
    sys.exit(main())
