
import ast, hashlib, json, os, re, stat, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path('/userdata/linaro/fpga-goal-viewer-build05-e4caef44-80c3-46f2-887c-84a9a1be2060')
SRC=ROOT/'src'
ART=ROOT/'artifacts05'
ART.mkdir()
def utc(): return datetime.now(timezone.utc).isoformat()
def save(name,data): (ART/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
def identity(p):
    try:
        real=os.path.realpath(p)
        st=os.stat(real)
        if not stat.S_ISREG(st.st_mode): return {'path':str(p),'regular':False}
        h=hashlib.sha256()
        with open(real,'rb') as f:
            for b in iter(lambda:f.read(1048576),b''): h.update(b)
        return dict(path=str(p),realpath=real,bytes=st.st_size,sha256=h.hexdigest())
    except OSError as e: return dict(path=str(p),error=str(e))
def run(label,argv,cwd=SRC,trace=False):
    started=utc()
    actual=argv
    if trace:
        actual=['/usr/bin/strace','-f','-qq','-s','4096','-o',str(ART/(label+'.strace05.txt')),
                '-e','trace=openat,open,execve,chdir']+argv
    with open(ART/(label+'.stdout05.txt'),'wb') as out,open(ART/(label+'.stderr05.txt'),'wb') as err:
        result=subprocess.run(actual,cwd=str(cwd),stdout=out,stderr=err)
    rec=dict(label=label,argv=argv,executed_argv=actual,cwd=str(cwd),started_utc=started,
             ended_utc=utc(),exit_code=result.returncode,
             stdout_file=label+'.stdout05.txt',stderr_file=label+'.stderr05.txt')
    operations.append(rec)
    save('operations05.json',operations)
    print(label,result.returncode,flush=True)
    return result.returncode
operations=[]
upload=json.loads((ROOT/'source_upload_receipt05.json').read_text())
source_begin=[identity(SRC/r['relative']) for r in upload['source_files']]
assert all(x.get('sha256')==r['sha256'] for x,r in zip(source_begin,upload['source_files']))
save('source_begin05.json',source_begin)
protected=['/userdata/detview-driving-demo/detview-driving-demo',
           '/userdata/detview-driving-demo/run_driving_demo.sh',
           '/userdata/linaro/detview-driving-demo-src/run_driving_demo.sh']
protected += [r['historical_remote'] for r in upload['source_files']]
protected_begin=[identity(p) for p in protected]
save('protected_begin05.json',protected_begin)
tool_paths=['/usr/bin/gcc','/usr/bin/g++','/usr/bin/ld','/usr/bin/as','/usr/bin/make',
 '/usr/bin/strace','/usr/bin/pkg-config','/usr/lib/qt5/bin/qmake','/usr/lib/qt5/bin/moc',
 '/usr/lib/gcc/aarch64-linux-gnu/12/cc1plus','/usr/lib/gcc/aarch64-linux-gnu/12/collect2']
save('tools_begin05.json',[identity(p) for p in tool_paths])
for label,argv in [('qmake_version',['/usr/lib/qt5/bin/qmake','-v']),
 ('qmake_query',['/usr/lib/qt5/bin/qmake','-query']),('compiler_version',['g++','-v']),
 ('linker_version',['ld','--version']),('make_version',['make','--version']),
 ('opencv_flags',['pkg-config','--cflags','--libs','opencv4']),
 ('packages',['dpkg-query','-W','g++','gcc','binutils','qt5-qmake','qtbase5-dev','libopencv-dev'])]:
    run(label,argv)
print('snapshotting readonly system inputs before build',flush=True)
started=utc()
system={}
roots=['/usr/include','/usr/bin','/usr/lib/aarch64-linux-gnu',
       '/usr/lib/gcc/aarch64-linux-gnu/12','/usr/lib/qt5','/usr/share/qt5',
       '/usr/lib/pkgconfig','/usr/share/pkgconfig','/usr/libexec']
for root in roots:
    if not os.path.isdir(root): continue
    for base,dirs,names in os.walk(root,followlinks=False):
        for name in names:
            p=os.path.join(base,name)
            real=os.path.realpath(p)
            if real in system: continue
            row=identity(p)
            if row.get('sha256'): system[real]=row
for p in ['/usr/lib/librknnrt.so','/etc/ld.so.cache','/etc/ld.so.conf',
          '/lib/ld-linux-aarch64.so.1','/usr/lib/aarch64-linux-gnu/qt5/mkspecs/linux-g++/qmake.conf']:
    row=identity(p)
    if row.get('sha256'): system[row['realpath']]=row
save('system_before05.json',dict(started_utc=started,ended_utc=utc(),roots=roots,files=list(system.values())))
print('system input snapshot complete',len(system),flush=True)
qmake_rc=run('qmake',['/usr/lib/qt5/bin/qmake','-o','Makefile','detview.pro'],trace=True)
make_rc=run('make',['/usr/bin/make','-j1'],trace=True) if qmake_rc==0 else None
source_end=[identity(SRC/r['relative']) for r in upload['source_files']]
save('source_end05.json',source_end)
save('tools_end05.json',[identity(p) for p in tool_paths])
protected_end=[identity(p) for p in protected]
save('protected_end05.json',protected_end)
source_unchanged=source_begin==source_end
protected_unchanged=protected_begin==protected_end
save('build_result05.json',dict(qmake_exit_code=qmake_rc,make_exit_code=make_rc,
     source_unchanged=source_unchanged,protected_unchanged=protected_unchanged,
     elf=identity(SRC/'detview'),viewer_executed=False,selftests_executed=False,
     old_objects_uploaded=False,hardware_access_requested=False))
reads=set(); executions=[]; device_opens=[]; changes=[]; unresolved=[]
for label in ['qmake','make']:
    trace=ART/(label+'.strace05.txt')
    if not trace.exists(): continue
    for line in trace.read_text(errors='replace').splitlines():
        if 'chdir(' in line: changes.append(line)
        if 'execve(' in line:
            match=re.search(r'execve\(("(?:[^"\\]|\\.)*")',line)
            if match:
                try: p=ast.literal_eval(match.group(1))
                except Exception: continue
                executions.append(dict(trace=label,line=line,path=p))
                if not re.search(r'= -1\b',line): reads.add(p if p.startswith('/') else str(SRC/p))
        if not ('openat(' in line or 'open(' in line): continue
        if not re.search(r'= [0-9]+(?:<|\s|$)',line): continue
        match=re.search(r'(?:openat\([^,]+, |open\()' + r'("(?:[^"\\]|\\.)*")',line)
        if not match:
            if '<unfinished ...>' in line or 'resumed>' in line: unresolved.append(line)
            continue
        try: p=ast.literal_eval(match.group(1))
        except Exception:
            unresolved.append(line); continue
        if p.startswith('/dev/'):
            device_opens.append(dict(trace=label,line=line,path=p))
        if 'O_RDONLY' not in line and 'O_RDWR' not in line: continue
        if not p.startswith('/'):
            if 'openat(AT_FDCWD,' not in line and 'open(' not in line:
                unresolved.append(line);continue
            p=str(SRC/p)
        reads.add(p)
actual=[];missing=[];mismatch=[]
for p in sorted(reads):
    after=identity(p)
    if not after.get('sha256'): continue
    real=after['realpath']
    before=system.get(real)
    source_match=next((x for x in source_begin if x.get('realpath')==real),None)
    if before is None and source_match is not None: before=source_match
    generated=real.startswith(str(SRC)+'/') and source_match is None
    row=dict(path=p,realpath=real,classification='generated_build_file' if generated else 'external_or_source_input',
             before=before,after=after,start_end_matched=bool(before and before['sha256']==after['sha256']))
    if not generated and not before: missing.append(p)
    if before and before['sha256']!=after['sha256']: mismatch.append(p)
    actual.append(row)
save('actual_read_inputs05.json',dict(files=actual,missing_begin_hash=missing,changed_inputs=mismatch,
     chdir_trace=changes,unresolved_trace_lines=unresolved,
     scope='successful read/read-write opens and execve from strace; generated build files classified separately'))
save('executions_device_audit05.json',dict(executions=executions,device_opens=device_opens,
     viewer_or_selftest_executed=any(x['path'].startswith(str(SRC)) for x in executions)))
print('actual input audit',len(actual),'missing',len(missing),'changed',len(mismatch),flush=True)
if make_rc==0:
    run('elf_cmp',['cmp','/userdata/detview-driving-demo/detview-driving-demo',str(SRC/'detview')])
    run('elf_readelf',['readelf','-n','-S','-d',str(SRC/'detview')])
    run('elf_nm',['nm','-S','--size-sort','-C',str(SRC/'detview')])
    run('deployed_nm',['nm','-S','--size-sort','-C','/userdata/detview-driving-demo/detview-driving-demo'])
    run('elf_size',['size',str(SRC/'detview'),'/userdata/detview-driving-demo/detview-driving-demo'])
generated=[]
for p in SRC.iterdir():
    if p.is_file() and p.name not in {r['relative'] for r in upload['source_files']}:
        generated.append(identity(p))
save('generated_manifest05.json',generated)
save('environment05.json',dict(captured_utc=utc(),uname=list(os.uname()),
    relevant_environment={k:os.environ.get(k) for k in ['PATH','LANG','LC_ALL','CXX','CC','CFLAGS','CXXFLAGS','LDFLAGS','LIBRARY_PATH','CPATH','CPLUS_INCLUDE_PATH','QTDIR','QT_SELECT','PKG_CONFIG_PATH','LD_LIBRARY_PATH']},
    remote_root=str(ROOT)))
print('BUILD_CAPTURE_FINISHED',qmake_rc,make_rc,flush=True)
