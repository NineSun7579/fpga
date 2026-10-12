"""Isolated native candidate build and audited synthetic Qt tests."""
import sys, json, hashlib, importlib.util, shlex, uuid, re, tarfile, posixpath, difflib
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
CAND = BASE/'current_viewer_native_candidate_02'
SRC = CAND/'src'
TARGET = 'detview-native-current-candidate'
spec = importlib.util.spec_from_file_location('exact', BASE/'current_viewer_rebuild_02/rebuild.py')
exact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exact)
w = exact.workflow
w.HERE = HERE
exact.HERE = HERE
save, run, remote_python, digest = w.save, w.run, w.remote_python, w.digest

def inventory(root):
    return {p.relative_to(root).as_posix():{'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}

def protected(label):
    roots = ['current_viewer_native_candidate_02','current_viewer_binding_02','current_viewer_rebuild_02']
    value = {n:inventory(BASE/n) for n in roots}
    save('protected_'+label+'.json',value)
    if label != 'before' and value != json.loads((HERE/'protected_before.json').read_text()):
        raise RuntimeError('Protected owner inputs changed externally')

def prepare(cli):
    if (HERE/'state.json').exists(): raise RuntimeError('No stage reuse')
    protected('before')
    exact.guard(cli,'before')
    exact.remote_original(cli,'before')
    authored = inventory(SRC)
    manifest = json.loads((CAND/'manifest.json').read_text())
    checks=[]
    for n,h in manifest['originals'].items():
        n=n.replace('\\','/')
        checks.append({'path':n,'equal':authored[n]['sha256']==h,'expected_main_delta':n=='main.cpp'})
    for n,h in manifest['byteexact_old_headers'].items():
        checks.append({'path':n,'equal':authored[n]['sha256']==h})
    save('manifest_checks.json',checks)
    if not all(c['equal'] or c.get('expected_main_delta') for c in checks): raise RuntimeError('Manifest mismatch')
    if authored['detview.pro']['sha256'] != digest(exact.SOURCE/'detview.pro'):raise RuntimeError('Project changed')
    save('candidate_source_manifest.json',authored)
    root='/userdata/linaro/fpga_v8_viewer_binding_20261005_native_build_02_'+uuid.uuid4().hex[:12]
    exact.guard(cli,'before_stage_write')
    run(cli,'mkdir '+shlex.quote(root))
    save('state.json',{'remote_root':root,'target':TARGET,'reused_objects':0,'device_opens':0,'deployments':0})
    audit=(BASE/'viewer_rebuild_evidence/remote_audit.py').read_text().replace("'detview'",repr(TARGET))
    (HERE/'remote_audit.py').write_text(audit)
    script=(BASE/'viewer_rebuild_evidence/build_isolated.sh').read_text().replace('/usr/lib/qt5/bin/qmake -o Makefile detview.pro','/usr/lib/qt5/bin/qmake -o Makefile detview.pro -after TARGET='+TARGET)
    (HERE/'build_isolated.sh').write_text(script,newline='\n')
    sftp=cli.open_sftp()
    for n in authored:
        parent=posixpath.dirname(n)
        if parent:
            try:sftp.mkdir(root+'/'+parent)
            except OSError:pass
        sftp.put(str(SRC/n),root+'/'+n)
    for n in ['remote_audit.py','build_isolated.sh']:sftp.put(str(HERE/n),root+'/'+n)
    sftp.close()
    save('uploaded_sources.json',[{'path':n,**v} for n,v in authored.items()])
    actual=json.loads(remote_python(cli,w.VERIFY_REMOTE,root))
    save('upload_verification.json',{'files':len(authored),'all_equal':all(actual[n]==v for n,v in authored.items()),'actual':actual})
    if not all(actual[n]==v for n,v in authored.items()):raise RuntimeError('Upload mismatch')
    exact.guard(cli,'before_preflight_write')
    remote_python(cli,'import os; os.chdir('+repr(root)+'); exec('+repr(exact.REMOTE_PREFLIGHT)+')',timeout=900)
    print(json.dumps({'stage':root,'source_files':len(authored)}))

def build(cli):
    protected('before_build')
    exact.guard(cli,'before_build_write')
    versions={'gcc':run(cli,'g++ -dumpfullversion').strip(),'qt':run(cli,'/usr/lib/qt5/bin/qmake -v').strip()}
    save('required_toolchain_check.json',versions)
    if versions['gcc']!='12.2.0' or 'Qt version 5.15.8' not in versions['qt']:raise RuntimeError('Toolchain drift')
    w.build(cli)

def repair_script(cli):
    exact.guard(cli,'before_script_repair')
    root=json.loads((HERE/'state.json').read_text())['remote_root']
    p=HERE/'build_isolated.sh'
    p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
    sftp=cli.open_sftp();sftp.put(str(p),root+'/build_isolated.sh');sftp.close()
    save('script_repair.json',{'reason':'Windows CRLF shell script rejected before qmake/build; normalized own script to LF','sha256':digest(p),'prepared_source_edits':0})

def collect(cli):
    root=json.loads((HERE/'state.json').read_text())['remote_root']
    exact.guard(cli,'before_collect_write')
    result=json.loads(run(cli,'cd '+shlex.quote(root)+' && python3 remote_audit.py collect',timeout=900))
    save('remote_result.json',result)
    after=json.loads(remote_python(cli,'import os; os.chdir('+repr(root)+'); exec('+repr(exact.REMOTE_AFTER)+')',timeout=900))
    save('dependency_checks_summary.json',after)
    extra=['header_inventory_before.json','stage_authored_before.json','qmake_pkgconfig_snapshot_manifest.json','dependency_before_after.json','qmake_pkgconfig_snapshots.tar.gz','qmake_pkgconfig_archive_identity.json','actual_baseline_elf.json']
    sftp=cli.open_sftp()
    for n in result['download_files']+extra:
        dest=HERE/n;dest.parent.mkdir(parents=True,exist_ok=True);sftp.get(root+'/'+n,str(dest))
    sftp.close()
    if result['build_return_code']:raise RuntimeError('Compile failed: see compile_link.log')
    w.supplement(cli)
    verify()

def verify():
    state=json.loads((HERE/'state.json').read_text())
    old=exact.assignments((exact.SOURCE/'Makefile').read_text());new=exact.assignments((HERE/'Makefile.fresh').read_text())
    keys=['CC','CXX','DEFINES','CFLAGS','CXXFLAGS','INCPATH','LINK','LFLAGS','LIBS','QMAKE','SOURCES','OBJECTS']
    flags={k:{'old':old.get(k),'new':new.get(k),'equal':old.get(k)==new.get(k)} for k in keys}
    save('qmake_flags_comparison.json',flags)
    normalized_old=(exact.SOURCE/'Makefile').read_text().replace('/userdata/linaro/detview-driving-demo-src','<STAGE>')
    normalized_new=(HERE/'Makefile.fresh').read_text().replace(state['remote_root'],'<STAGE>').replace(TARGET,'detview').replace(' -after TARGET=detview','')
    (HERE/'qmake_makefile_normalized.diff').write_text(''.join(difflib.unified_diff(normalized_old.splitlines(True),normalized_new.splitlines(True),fromfile='baseline',tofile='candidate-normalized')))
    save('qmake_semantics.json',{'pro_unchanged':digest(SRC/'detview.pro')==digest(exact.SOURCE/'detview.pro'),'baseline_target':old.get('TARGET'),'candidate_target':new.get('TARGET'),'target_override':'qmake -after TARGET='+TARGET,'optimization_flags_unchanged':flags['CXXFLAGS']['equal'],'normalized_diff':'qmake_makefile_normalized.diff'})
    objects=new['OBJECTS'].split()
    rows=[{'path':n,'sha256':digest(HERE/'rebuilt'/n),'baseline_sha256':digest(exact.SOURCE/n),'equal':digest(HERE/'rebuilt'/n)==digest(exact.SOURCE/n)} for n in objects]
    save('binary_comparison.json',rows)
    generated=[{'path':n,'equal':(HERE/n).read_bytes()==(exact.SOURCE/n).read_bytes(),'sha256':digest(HERE/n),'baseline_sha256':digest(exact.SOURCE/n)} for n in ['main.moc','moc_predefs.h','moc_calibration_capture.cpp','moc_vision_pipeline.cpp','.qmake.stash']]
    save('generated_comparison.json',generated)
    deps={x['path']:x for x in json.loads((HERE/'compiler_dependency_snapshot_manifest.json').read_text())}
    authored=json.loads((HERE/'candidate_source_manifest.json').read_text())
    confirmed=[{'path':n,'equal':deps[state['remote_root']+'/'+n]['sha256']==v['sha256']} for n,v in authored.items() if state['remote_root']+'/'+n in deps]
    save('compiled_authored_input_verification.json',confirmed)
    save('source_object_counts.json',{'uploaded_authored_files':len(authored),'original_files':35,'old_native_headers':3,'new_headers':2,'qmake_source_units':len(new['SOURCES'].split()),'objects':len(objects),'compiled_authored_files':len(confirmed),'not_compiler_inputs':sorted(set(authored)-{r['path'] for r in confirmed}),'object_order':objects})
    needed=lambda text:re.findall(r'\(NEEDED\).*?\[(.*?)\]',text)
    baseline=json.loads((HERE/'actual_baseline_elf.json').read_text())
    save('elf_baseline_comparison.json',{'needed_equal':needed(baseline['dynamic']['stdout'])==needed((HERE/'elf_dynamic.txt').read_text()),'needed':needed((HERE/'elf_dynamic.txt').read_text()),'comment_equal':baseline['comment']['stdout']==(HERE/'elf_comment.txt').read_text(),'baseline_build_id':re.findall(r'Build ID: (\w+)',baseline['notes']['stdout']),'candidate_build_id':re.findall(r'Build ID: (\w+)',(HERE/'elf_notes.txt').read_text())})
    archives=[]
    for archive,identity,prefixes in [('dependency_snapshots.tar.gz','snapshot_archive_identity.json',['toolchain_snapshot','compiler_dependency_snapshot','linker_input_snapshot','runtime_library_snapshot']),('qmake_pkgconfig_snapshots.tar.gz','qmake_pkgconfig_archive_identity.json',['qmake_pkgconfig_snapshot']),('supplement_snapshots.tar.gz','supplement_archive_identity.json',['qmake_config_snapshot','live_runtime_library_snapshot'])]:
        ident=json.loads((HERE/identity).read_text());assert digest(HERE/archive)==ident['sha256'];count=0
        with tarfile.open(HERE/archive) as tar:
            for prefix in prefixes:
                for f in json.loads((HERE/(prefix+'_manifest.json')).read_text()):
                    member=posixpath.normpath(prefix+'/'+f['path'].lstrip('/'));stream=tar.extractfile(member);h=hashlib.sha256()
                    for block in iter(lambda:stream.read(1048576),b''):h.update(block)
                    assert h.hexdigest()==f['sha256'];count+=1
        archives.append({'path':archive,'sha256':ident['sha256'],'verified_entries':count})
    save('archive_verification.json',archives)
    state.update({'build_return_code':0,'executable_sha256':digest(HERE/'rebuilt'/TARGET),'source_files':len(authored),'compiled_authored_files':len(confirmed),'objects_total':len(objects),'objects_equal':sum(r['equal'] for r in rows),'different_objects':[r['path'] for r in rows if not r['equal']],'semantic_flags_equal':all(v['equal'] for v in flags.values()),'generated_outputs_equal':all(r['equal'] for r in generated)})
    save('state.json',state)
    assert len(objects)==17 and state['different_objects']==['main.o']
    assert state['semantic_flags_equal'] and all(r['equal'] for r in confirmed)
    print(json.dumps(state))

def tests(cli):
    root=json.loads((HERE/'state.json').read_text())['remote_root']
    exact.guard(cli,'before_selftests')
    owners(cli,'before_selftests')
    audit={'dispatch_before_model_scan':True,'qapplication_offscreen':True,'inference_thread_constructor':'QThread(parent) only; thread never started; m_ctx=0, native session pointer=null','commands':['--dfl-selftest','--trafficlight-selftest'],'geometry_dispatch':'no standalone geometry flag; included in trafficlight selftest','source_main_sha256':digest(SRC/'main.cpp')}
    text=(SRC/'main.cpp').read_text(encoding='utf8')
    assert 'InferenceThread(QObject *parent = nullptr) : QThread(parent) {}' in text
    assert text.index('if (app.arguments().contains("--dfl-selftest"))') < text.index('const QVector<ModelInfo> models = scanModels();')
    assert text.index('if (app.arguments().contains("--trafficlight-selftest"))') < text.index('const QVector<ModelInfo> models = scanModels();')
    fixture=text[text.index('static bool selfTestDfl('):text.index('void submit(',text.index('static bool selfTestDfl('))]
    assert not any(x in fixture for x in ['rknn_init(', 'rknn_run(', '.start(', 'ioctl(', 'mmap('])
    audit['fixture_source']=fixture
    audit['geometry_source_sha256']=digest(SRC/'inference_geometry_selftest.cpp')
    save('selftest_source_audit.json',audit)
    code="""import subprocess,os,json,sys,pathlib
root=sys.argv[1];target=sys.argv[2]
env=os.environ.copy();env['QT_QPA_PLATFORM']='offscreen'
for key,folder in [('XDG_RUNTIME_DIR','qt-runtime'),('XDG_CACHE_HOME','qt-cache'),('XDG_CONFIG_HOME','qt-config')]:
 path=pathlib.Path(root)/folder;path.mkdir(mode=0o700,exist_ok=True);env[key]=str(path)
rows=[]
for flag in ['--dfl-selftest','--trafficlight-selftest']:
 p=subprocess.run([root+'/'+target,flag],env=env,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
 rows.append({'argv':[root+'/'+target,flag],'environment':{key:env[key] for key in ['QT_QPA_PLATFORM','XDG_RUNTIME_DIR','XDG_CACHE_HOME','XDG_CONFIG_HOME']},'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'ok_diagnostics':p.stderr.count('[ok]'),'fail_diagnostics':p.stderr.count('[FAIL]')})
print(json.dumps(rows))
"""
    save('selftest_results.json',json.loads(remote_python(cli,code,root,TARGET,timeout=150)))
    exact.guard(cli,'after_selftests')
    owners(cli,'after_selftests')

def owners(cli,label):
    code=r'''import pathlib,os,json,hashlib,stat
rows=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  exe=os.readlink(p/'exe');fds={}
  for f in (p/'fd').iterdir():
   try:
    dest=os.readlink(f);s=f.stat()
    if stat.S_ISCHR(s.st_mode) or (dest.startswith('/dev/') and dest!='/dev/null'):fds[f.name]=dest
   except OSError:pass
  if fds or 'detview' in exe:
   s=(p/'stat').read_text().rsplit(')',1)[1].split()
   rows.append({'pid':int(p.name),'start_ticks':int(s[19]),'exe':exe,'fds':fds,'maps':(p/'maps').read_text()})
 except OSError:pass
print(json.dumps({'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'owners':sorted(rows,key=lambda x:x['pid'])}))
'''
    rc,out,err=w.board_ssh.run(cli,'python3 -c '+shlex.quote(code),sudo=True)
    if rc:raise RuntimeError('Read-only all-owner audit failed')
    save('all_device_owners_'+label+'.json',json.loads(out))

def owners_before(cli):owners(cli,'before_build')

def finalize(cli):
    exact.guard(cli,'final')
    original=exact.remote_original(cli,'final')
    protected('final')
    owners(cli,'final')
    root=json.loads((HERE/'state.json').read_text())['remote_root']
    code="""import pathlib,json,hashlib,sys
root=pathlib.Path(sys.argv[1]);result={}
for prefix in ['toolchain_snapshot','qmake_pkgconfig_snapshot','compiler_dependency_snapshot','linker_input_snapshot','runtime_library_snapshot','qmake_config_snapshot','live_runtime_library_snapshot']:
 rows=[]
 for f in json.loads((root/(prefix+'_manifest.json')).read_text()):
  h=hashlib.sha256()
  with pathlib.Path(f['path']).open('rb') as stream:
   for block in iter(lambda:stream.read(1048576),b''):h.update(block)
  rows.append({'path':f['path'],'equal':h.hexdigest()==f['sha256'],'sha256':h.hexdigest()})
 result[prefix]=rows
print(json.dumps(result))
"""
    dependencies=json.loads(remote_python(cli,code,root,timeout=900))
    save('dependency_final_recheck.json',dependencies)
    state=json.loads((HERE/'state.json').read_text())
    before=json.loads((HERE/'process_guard_before.json').read_text());after=json.loads((HERE/'process_guard_final.json').read_text())
    state.update({'original_remote_unchanged':original==json.loads((HERE/'original_remote_before.json').read_text()),'owners_identity_unchanged':[(p['pid'],p['start_ticks'],p['image']) for p in before['processes']]==[(p['pid'],p['start_ticks'],p['image']) for p in after['processes']],'tests':json.loads((HERE/'selftest_results.json').read_text())})
    state['all_dependency_snapshots_unchanged_final']=all(r['equal'] for rows in dependencies.values() for r in rows)
    state['dependency_counts']={n:len(rows) for n,rows in dependencies.items()}
    def owner_changes(first,last):
        a=json.loads((HERE/first).read_text());b=json.loads((HERE/last).read_text())
        x={(p['pid'],p['start_ticks']):p for p in a['owners']};y={(p['pid'],p['start_ticks']):p for p in b['owners']}
        return {'boot_equal':a['boot_id']==b['boot_id'],'added':[list(k) for k in y.keys()-x.keys()],'removed':[list(k) for k in x.keys()-y.keys()],'common':[{'pid':k[0],'start_ticks':k[1],'exe_equal':x[k]['exe']==y[k]['exe'],'fds_equal':x[k]['fds']==y[k]['fds'],'maps_equal':x[k]['maps']==y[k]['maps']} for k in sorted(x.keys()&y.keys())]}
    save('all_owner_comparison.json',{'selftests':owner_changes('all_device_owners_before_selftests.json','all_device_owners_after_selftests.json'),'build_observation_to_final':owner_changes('all_device_owners_before_build.json','all_device_owners_final.json')})
    save('state.json',state)
    save('workflow_input_binding.json',{str(p.relative_to(BASE)):{'sha256':digest(p),'bytes':p.stat().st_size} for p in [BASE/'current_viewer_rebuild_02/rebuild.py',BASE/'viewer_rebuild_evidence/rebuild_binding.py',BASE/'viewer_rebuild_evidence/remote_audit.py',BASE/'viewer_rebuild_evidence/build_isolated.sh',CAND/'manifest.json']})
    save('artifact_manifest.json',{'excludes':['artifact_manifest.json'],'files':{n:v for n,v in inventory(HERE).items() if n!='artifact_manifest.json'}})
    print(json.dumps(state))

if __name__=='__main__':
    phase=sys.argv[1]
    if phase=='verify':verify()
    else:
        cli=w.board_ssh.connect()
        try:globals()[phase](cli)
        finally:cli.close()
