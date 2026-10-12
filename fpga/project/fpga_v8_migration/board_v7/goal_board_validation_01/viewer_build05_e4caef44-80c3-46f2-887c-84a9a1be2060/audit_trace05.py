"""Finish split strace records and bind actual read inputs; read-only follow-up."""
import ast
import hashlib
import json
import os
import re
import stat
from pathlib import Path

ROOT = Path('/userdata/linaro/fpga-goal-viewer-build05-e4caef44-80c3-46f2-887c-84a9a1be2060')
SRC, ART = ROOT/'src', ROOT/'artifacts05'
system = {r['realpath']: r for r in json.loads((ART/'system_before05.json').read_text())['files']}
sources = {r['realpath']: r for r in json.loads((ART/'source_begin05.json').read_text())}
reads, executions, dev, unresolved, changes = set(), [], [], [], []
completed_split = 0
for label in ['qmake', 'make']:
    waiting = {}
    cwd_by_pid = {}
    for original in (ART/(label+'.strace05.txt')).read_text(errors='replace').splitlines():
        line = original
        match = re.match(r'\s*(\d+)\s+(.*)', line)
        if not match:
            unresolved.append(line)
            continue
        pid, body = match.groups()
        if '<unfinished ...>' in body:
            call = body.split('(', 1)[0]
            waiting[(pid, call)] = body.replace('<unfinished ...>', '')
            continue
        resumed = re.match(r'<\.\.\. (\w+) resumed>(.*)', body)
        if resumed:
            call, tail = resumed.groups()
            head = waiting.pop((pid, call), None)
            if head is None:
                unresolved.append(line)
                continue
            body = head+tail
            completed_split += 1
        if body.startswith('chdir(') and body.endswith('= 0'):
            changes.append(dict(pid=pid, line=body))
            destination = ast.literal_eval(body[len('chdir('):body.rfind(')')])
            previous = cwd_by_pid.get(pid, SRC)
            cwd_by_pid[pid] = Path(destination) if destination.startswith('/') else previous/destination
        if body.startswith('execve('):
            m = re.match(r'execve\(("(?:[^"\\]|\\.)*")', body)
            if m and not re.search(r'= -1\b', body):
                p = ast.literal_eval(m.group(1))
                executions.append(dict(pid=pid, path=p, line=body))
                reads.add(p if p.startswith('/') else str(cwd_by_pid.get(pid,SRC)/p))
        if not body.startswith(('openat(', 'open(')) or not re.search(r'= \d+(?:<|\s|$)', body):
            continue
        m = re.match(r'(?:openat\([^,]+, |open\()' + r'("(?:[^"\\]|\\.)*")', body)
        if not m:
            unresolved.append(line)
            continue
        p = ast.literal_eval(m.group(1))
        if p.startswith('/dev/'):
            dev.append(dict(pid=pid, path=p, line=body))
        if 'O_RDONLY' not in body and 'O_RDWR' not in body:
            continue
        if not p.startswith('/'):
            if not body.startswith(('openat(AT_FDCWD,', 'open(')):
                unresolved.append(line)
                continue
            p = str(cwd_by_pid.get(pid,SRC)/p)
        reads.add(p)
    unresolved.extend(dict(pid=k[0],call=k[1],line=v) for k,v in waiting.items())

records, missing, changed = [], [], []
for p in sorted(reads):
    real = os.path.realpath(p)
    try:
        st = os.stat(real)
        if not stat.S_ISREG(st.st_mode):
            continue
        # Proc/sys observations do not constitute compiler header/library inputs.
        if real.startswith(('/proc/', '/sys/')):
            records.append(dict(path=p,realpath=real,classification='volatile_host_observation'))
            continue
        h = hashlib.sha256()
        with open(real,'rb') as f:
            for b in iter(lambda:f.read(1048576),b''):
                h.update(b)
        after = dict(path=p,realpath=real,bytes=st.st_size,sha256=h.hexdigest())
    except OSError as e:
        records.append(dict(path=p,realpath=real,error=str(e)))
        continue
    before = system.get(real) or sources.get(real)
    generated = real.startswith(str(SRC)+'/') and real not in sources
    if generated:
        category = 'generated_build_file'
    elif '/include/' in real or real.endswith(('.h','.hpp','.hxx','.tcc','.inc')):
        category = 'header_input'
    elif '.so' in Path(real).name or real.endswith(('.a','.o','.lds')):
        category = 'library_crt_or_linker_input'
    elif real in sources:
        category = 'restored_source_input'
    else:
        category = 'tool_or_build_configuration_input'
    matched = bool(before and before['sha256']==after['sha256'])
    record = dict(path=p,realpath=real,classification=category,before=before,after=after,start_end_matched=matched)
    if not before and not generated:
        missing.append(record)
    if before and not matched:
        changed.append(record)
    records.append(record)
result = dict(files=records,completed_split_records=completed_split,unresolved_trace_lines=unresolved,
              successful_chdir=changes,missing_begin_hash=missing,changed_inputs=changed,
              device_opens=dev,executions=executions,
              viewer_or_selftest_executed=any(x['path'].startswith(str(SRC)) for x in executions),
              path_resolution_assumption='Track successful chdir per PID, otherwise the recorded initial build src cwd. The captured qmake children explicitly enter features or src; no other successful cwd changes are present.')
(ART/'actual_read_inputs_final05.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(dict(files=len(records),split_records=completed_split,unresolved=len(unresolved),
    chdir=changes,missing_begin_hash=[x['path'] for x in missing],changed_inputs=[x['path'] for x in changed],
    device_paths=sorted({x['path'] for x in dev}),viewer_or_selftest_executed=result['viewer_or_selftest_executed']),indent=2))
