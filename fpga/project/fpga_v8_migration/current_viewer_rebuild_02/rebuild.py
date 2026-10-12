"""Independent build-only reconstruction; never execute the viewer or selftests."""
from __future__ import annotations
import argparse
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import posixpath
import re
import shlex
import sys
import tarfile
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
FROZEN = BASE / 'current_viewer_binding_02'
SOURCE = FROZEN / 'inputs/userdata/linaro/detview-driving-demo-src'
OLD = BASE / 'viewer_rebuild_evidence'
EXPECTED = 'f1fd98042a6f87c410cc44fbff574fc01f42e63a3f08827574cff3e51b6433b4'
spec = importlib.util.spec_from_file_location('previous_build_workflow', OLD/'rebuild_binding.py')
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)
workflow.HERE = HERE
board_ssh = workflow.board_ssh
save, run, remote_python, digest = workflow.save, workflow.run, workflow.remote_python, workflow.digest

def frozen_check(label):
    records = json.loads((FROZEN/'retrieval_manifest.json').read_text())
    result = []
    for rec in records:
        if 'local' not in rec: continue
        p = FROZEN / rec['local']
        h = digest(p)
        result.append({'path':rec['local'], 'bytes':p.stat().st_size, 'sha256':h,
                       'equal':h == rec['local_sha256'] and p.stat().st_size == rec['bytes']})
    save('frozen_'+label+'.json', result)
    if not all(x['equal'] for x in result): raise RuntimeError('Frozen input changed')
    return records

def guard(cli, label):
    g = workflow.process_guard(cli)
    # Audit the actual installed current image as well as /proc identity.
    extra = json.loads(remote_python(cli, "import pathlib,hashlib,json; p=pathlib.Path('/userdata/detview-driving-demo/detview-driving-demo'); d=p.read_bytes(); print(json.dumps({'sha256':hashlib.sha256(d).hexdigest(),'bytes':len(d)}))"))
    g['current_installed'] = extra
    save('process_guard_'+label+'.json', g)
    live = [p for p in g['processes'] if p['pid'] == 2740]
    ok = (g['boot_id'] == '12803068-a3fb-4341-b05e-4f31921cfb1b' and
          len(live) == 1 and live[0]['start_ticks'] == 152164 and
          live[0]['exe'] == '/userdata/detview-driving-demo/detview-driving-demo' and
          live[0]['image']['sha256'] == EXPECTED and extra['sha256'] == EXPECTED)
    if (HERE/'original_remote_before.json').exists():
        original=json.loads(remote_python(cli,workflow.VERIFY_REMOTE,'/userdata/linaro/detview-driving-demo-src'))
        save('original_guard_'+label+'.json',original)
        ok = ok and original == json.loads((HERE/'original_remote_before.json').read_text())
    if not ok:
        save('external_change_stop.json', {'label':label,'reason':'Current live identity changed; no subsequent remote writes authorized by this workflow',
                                         'frozen_source_binding_remains_possible':True})
        raise RuntimeError('External identity change: stopped before subsequent remote writes')
    return g

REMOTE_PREFLIGHT = r'''
import hashlib,json,pathlib,subprocess,os
import remote_audit as a
a.preflight()
root=pathlib.Path.cwd()
def hashes(paths):
    return {str(p):a.info(p) for p in sorted(set(paths)) if p.is_file()}
include_roots=[pathlib.Path('/usr/include'),pathlib.Path('/usr/lib/gcc/aarch64-linux-gnu/12/include')]
headers=hashes(p for base in include_roots for p in base.rglob('*') if p.is_file())
a.dump('header_inventory_before.json',headers)
paths=set()
for base in ['/usr/lib/aarch64-linux-gnu/qt5/mkspecs','/usr/lib/aarch64-linux-gnu/pkgconfig','/usr/share/pkgconfig']:
    paths.update(p for p in pathlib.Path(base).rglob('*') if p.is_file())
paths.update([pathlib.Path('/usr/bin/qtchooser')])
a.copy_snapshot(paths,'qmake_pkgconfig_snapshot')
a.dump('stage_authored_before.json',hashes(p for p in root.rglob('*') if p.suffix in ['.cpp','.h','.pro'] and not p.name.startswith('moc_')))
'''

REMOTE_AFTER = r'''
import json,pathlib,tarfile
import remote_audit as a
root=pathlib.Path.cwd()
checks={}
for name in ['toolchain_snapshot','qmake_pkgconfig_snapshot','compiler_dependency_snapshot','linker_input_snapshot','runtime_library_snapshot']:
    entries=json.loads((root/(name+'_manifest.json')).read_text())
    checks[name]=[{'path':f['path'],'before_sha256':f['sha256'],'after_sha256':a.info(f['path'])['sha256'],'equal':a.info(f['path'])['sha256']==f['sha256']} for f in entries]
before=json.loads((root/'header_inventory_before.json').read_text())
before_real={v['realpath']:v for v in before.values()}
direct=json.loads((root/'direct_accelerator_libraries_before.json').read_text())
checks['direct_accelerator_before_vs_after']=[{'path':f['path'],'equal':a.info(f['path'])['sha256']==f['sha256']} for f in direct.values()]
checks['headers_before_vs_used']=[]
authored=json.loads((root/'stage_authored_before.json').read_text())
for f in json.loads((root/'compiler_dependency_snapshot_manifest.json').read_text()):
    old=before.get(f['path']) or before_real.get(f['realpath']) or authored.get(f['path'])
    if old: checks['headers_before_vs_used'].append({'path':f['path'],'equal':old['sha256']==f['sha256']})
    elif not f['realpath'].startswith(str(root)+'/'):
        checks['headers_before_vs_used'].append({'path':f['path'],'equal':False,'reason':'External compiler input not covered by pre-build inventory'})
a.dump('dependency_before_after.json',checks)
baseline={}
for key,args in {'comment':['readelf','-p','.comment','/userdata/detview-driving-demo/detview-driving-demo'],'dynamic':['readelf','-dW','/userdata/detview-driving-demo/detview-driving-demo'],'notes':['readelf','-nW','/userdata/detview-driving-demo/detview-driving-demo']}.items():baseline[key]=a.command(args)
a.dump('actual_baseline_elf.json',baseline)
with tarfile.open(root/'qmake_pkgconfig_snapshots.tar.gz','w:gz') as tar:
    tar.add(root/'qmake_pkgconfig_snapshot',arcname='qmake_pkgconfig_snapshot')
a.dump('qmake_pkgconfig_archive_identity.json',a.info(root/'qmake_pkgconfig_snapshots.tar.gz'))
print(json.dumps({'all_unchanged':all(x['equal'] for rows in checks.values() for x in rows),'counts':{k:len(v) for k,v in checks.items()}}))
'''

def remote_original(cli, label):
    data=json.loads(remote_python(cli, workflow.VERIFY_REMOTE, '/userdata/linaro/detview-driving-demo-src'))
    save('original_remote_'+label+'.json',data)
    return data

def prepare(cli):
    if (HERE/'state.json').exists(): raise RuntimeError('Refusing to reuse stage')
    records=frozen_check('before')
    g=guard(cli,'before')
    original=remote_original(cli,'before')
    expected={r['path'].split('/detview-driving-demo-src/',1)[1]:{'bytes':r['bytes'],'sha256':r['sha256']} for r in records if '/detview-driving-demo-src/' in r['path']}
    differences={n:{'expected':v,'actual':original.get(n)} for n,v in expected.items() if original.get(n)!=v}
    save('original_input_check.json',{'frozen_source_files':len(expected),'differences':differences,'extra_remote_files':sorted(set(original)-set(expected))})
    if differences: raise RuntimeError('Retained current source differs from frozen binding')
    root='/userdata/linaro/fpga_v8_viewer_binding_20261005_current_rebuild_02_'+uuid.uuid4().hex[:12]
    authored=[p for p in SOURCE.rglob('*') if p.is_file() and p.suffix in {'.cpp','.h','.pro'} and not p.name.startswith('moc_')]
    save('source_path_literals.json',[{'path':p.relative_to(SOURCE).as_posix(),'lines':[{'line':i,'text':l} for i,l in enumerate(p.read_text(errors='replace').splitlines(),1) if '__FILE__' in l or '/userdata/linaro/detview-driving-demo-src' in l]} for p in authored if '__FILE__' in p.read_text(errors='replace') or '/userdata/linaro/detview-driving-demo-src' in p.read_text(errors='replace')])
    guard(cli,'before_stage_write')
    run(cli,'mkdir '+shlex.quote(root))
    save('state.json',{'remote_root':root,'expected_executable_sha256':EXPECTED,'reused_objects':0,'viewer_or_selftest_executions':0,'device_opens':0})
    sftp=cli.open_sftp()
    uploaded=[]
    for p in authored:
        rel=p.relative_to(SOURCE).as_posix()
        parent=posixpath.dirname(rel)
        if parent:
            try:sftp.mkdir(root+'/'+parent)
            except OSError:pass
        sftp.put(str(p),root+'/'+rel)
        uploaded.append({'path':rel,'bytes':p.stat().st_size,'sha256':digest(p)})
    for name in ['remote_audit.py','build_isolated.sh']: sftp.put(str(OLD/name),root+'/'+name)
    sftp.close()
    save('uploaded_sources.json',uploaded)
    guard(cli,'before_preflight_write')
    remote_python(cli,"import os; os.chdir("+repr(root)+"); exec("+repr(REMOTE_PREFLIGHT)+")",timeout=900)
    print(json.dumps({'remote_root':root,'frozen_records':sum('local' in r for r in records),'authored_uploaded':len(uploaded),'reused_objects':0}))

def build(cli):
    frozen_check('before_build')
    guard(cli,'before_build_write')
    versions={'gcc':run(cli,'g++ -dumpfullversion').strip(),'qt':run(cli,'/usr/lib/qt5/bin/qmake -v').strip()}
    save('required_toolchain_check.json',versions)
    if versions['gcc']!='12.2.0' or 'Qt version 5.15.8' not in versions['qt']:raise RuntimeError('Required compiler/Qt baseline changed')
    workflow.build(cli)

def collect(cli):
    state=json.loads((HERE/'state.json').read_text()); root=state['remote_root']
    guard(cli,'before_collect_write')
    result=json.loads(run(cli,'cd '+shlex.quote(root)+' && python3 remote_audit.py collect',timeout=900))
    save('remote_result.json',result)
    after=json.loads(remote_python(cli,"import os; os.chdir("+repr(root)+"); exec("+repr(REMOTE_AFTER)+")",timeout=900))
    save('dependency_checks_summary.json',after)
    sftp=cli.open_sftp()
    extra=['header_inventory_before.json','stage_authored_before.json','qmake_pkgconfig_snapshot_manifest.json','dependency_before_after.json','qmake_pkgconfig_snapshots.tar.gz','qmake_pkgconfig_archive_identity.json','actual_baseline_elf.json']
    for name in result['download_files']+extra:
        dest=HERE/name; dest.parent.mkdir(parents=True,exist_ok=True)
        sftp.get(root+'/'+name,str(dest))
    sftp.close()
    original=remote_original(cli,'after')
    g=guard(cli,'after')
    frozen_check('after')
    state.update({'build_return_code':result['build_return_code'],'original_remote_unchanged':original==json.loads((HERE/'original_remote_before.json').read_text()),'dependency_files_unchanged':after['all_unchanged'],'live_identity_unchanged':True})
    save('state.json',state)
    verify()

def supplement(cli):
    guard(cli,'before_supplement_write')
    workflow.supplement(cli)
    guard(cli,'after_supplement')

def early_compare(cli):
    state=json.loads((HERE/'state.json').read_text())
    code="""import pathlib,hashlib,json,sys
root=pathlib.Path(sys.argv[1])
paths=list(root.glob('*.o'))+[root/'detview']
print(json.dumps({p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in paths}))
"""
    values=json.loads(remote_python(cli,code,state['remote_root']))
    rows=[{'path':name,'new_sha256':value['sha256'],'old_sha256':digest(SOURCE/name),'equal':value['sha256']==digest(SOURCE/name),'bytes':value['bytes']} for name,value in sorted(values.items())]
    save('early_binary_comparison.json',rows)
    print(json.dumps({'executable_sha256':values['detview']['sha256'],'objects_equal':sum(r['equal'] for r in rows if r['path'].endswith('.o')),'objects_total':sum(r['path'].endswith('.o') for r in rows),'all_products_equal':all(r['equal'] for r in rows)}))

def assignments(text):
    text=text.replace('\\\n',' ')
    return {m.group(1):m.group(2).strip() for m in re.finditer(r'^([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.*)$',text,re.M)}

def verify():
    frozen_check('final')
    state=json.loads((HERE/'state.json').read_text())
    old=assignments((SOURCE/'Makefile').read_text()); new=assignments((HERE/'Makefile.fresh').read_text())
    flags={k:{'old':old.get(k),'new':new.get(k),'equal':old.get(k)==new.get(k)} for k in ['CC','CXX','DEFINES','CFLAGS','CXXFLAGS','INCPATH','LINK','LFLAGS','LIBS','QMAKE','SOURCES','OBJECTS']}
    save('qmake_flags_comparison.json',flags)
    sources=new['SOURCES'].split(); objects=new['OBJECTS'].split()
    products=[]
    for name in ['detview']+objects:
        a=HERE/'rebuilt'/name; b=SOURCE/name
        products.append({'path':name,'new_sha256':digest(a),'old_sha256':digest(b),'new_bytes':a.stat().st_size,'old_bytes':b.stat().st_size,'byte_for_byte_equal':a.read_bytes()==b.read_bytes()})
    save('binary_comparison.json',products)
    generated=[]
    for name in ['main.moc','moc_predefs.h','moc_calibration_capture.cpp','moc_vision_pipeline.cpp','.qmake.stash']:
        generated.append({'path':name,'equal':(HERE/name).read_bytes()==(SOURCE/name).read_bytes(),'new_sha256':digest(HERE/name),'old_sha256':digest(SOURCE/name)})
    save('generated_comparison.json',generated)
    normalized_old=(SOURCE/'Makefile').read_text().replace('/userdata/linaro/detview-driving-demo-src','<STAGE>')
    normalized_new=(HERE/'Makefile.fresh').read_text().replace(state['remote_root'],'<STAGE>')
    strip_stash=lambda t:'\n'.join(l for l in t.splitlines() if l.strip() not in {'.qmake.stash \\', '.qmake.stash:'})
    save('qmake_makefile_normalized_comparison.json',{'path_normalization':{'old':'/userdata/linaro/detview-driving-demo-src','new':state['remote_root'],'replacement':'<STAGE>'},'equal':normalized_old==normalized_new,'equal_except_preexisting_stash_dependency_lines':strip_stash(normalized_old)==strip_stash(normalized_new),'reason':'A cold qmake invocation regenerates .qmake.stash but does not list it as a preexisting Makefile dependency; frozen Makefile lists it in DIST, Makefile prerequisites and an empty dependency rule. No build settings or recipes differ.','old_normalized_sha256':hashlib.sha256(normalized_old.encode()).hexdigest(),'new_normalized_sha256':hashlib.sha256(normalized_new.encode()).hexdigest()})
    (HERE/'qmake_makefile_normalized.diff').write_text(''.join(difflib.unified_diff(normalized_old.splitlines(True),normalized_new.splitlines(True),fromfile='frozen_Makefile_normalized',tofile='fresh_Makefile_normalized')),encoding='utf8')
    baseline=json.loads((HERE/'actual_baseline_elf.json').read_text())
    needed=lambda t:re.findall(r'\(NEEDED\).*?\[(.*?)\]',t)
    save('elf_baseline_comparison.json',{'needed_equal':needed(baseline['dynamic']['stdout'])==needed((HERE/'elf_dynamic.txt').read_text()),'needed':needed((HERE/'elf_dynamic.txt').read_text()),'comment_equal':baseline['comment']['stdout']==(HERE/'elf_comment.txt').read_text(),'baseline_build_id':re.findall(r'Build ID: (\w+)',baseline['notes']['stdout']),'rebuilt_build_id':re.findall(r'Build ID: (\w+)',(HERE/'elf_notes.txt').read_text())})
    counts={'pro_authored_sources':len(re.findall(r'\S+\.cpp', (SOURCE/'detview.pro').read_text().split('HEADERS')[0])), 'qmake_sources':len(sources),'objects_expected':len(objects),'objects_built':len(list((HERE/'rebuilt').glob('*.o'))),'objects_equal':sum(p['byte_for_byte_equal'] for p in products[1:]),'source_order':sources,'object_order':objects}
    save('source_object_counts.json',counts)
    deps={f['path']:f for f in json.loads((HERE/'compiler_dependency_snapshot_manifest.json').read_text())}
    authored=[]
    for f in json.loads((HERE/'uploaded_sources.json').read_text()):
        actual=deps.get(state['remote_root']+'/'+f['path'])
        if actual: authored.append({'path':f['path'],'matches_frozen':actual['sha256']==f['sha256'],'sha256':actual['sha256']})
    save('compiled_authored_input_verification.json',authored)
    save('relative_source_artifact_binding.json',{'frozen_source_root':'../current_viewer_binding_02/inputs/userdata/linaro/detview-driving-demo-src','stage_root':state['remote_root'],'uploaded_authored_files':json.loads((HERE/'uploaded_sources.json').read_text()),'compiler_confirmed_authored_files':authored,'relative_products':[p['path'] for p in products],'reused_objects':0,'path_literals':json.loads((HERE/'source_path_literals.json').read_text()),'pro':{'sha256':digest(SOURCE/'detview.pro'),'lines':(SOURCE/'detview.pro').read_text().splitlines()},'baseline_makefile_sha256':digest(SOURCE/'Makefile'),'baseline_executable_sha256':digest(SOURCE/'detview')})
    archives=[]
    archive_specs=[('dependency_snapshots.tar.gz','snapshot_archive_identity.json',['toolchain_snapshot','compiler_dependency_snapshot','linker_input_snapshot','runtime_library_snapshot']),('qmake_pkgconfig_snapshots.tar.gz','qmake_pkgconfig_archive_identity.json',['qmake_pkgconfig_snapshot'])]
    if (HERE/'supplement_snapshots.tar.gz').exists():archive_specs.append(('supplement_snapshots.tar.gz','supplement_archive_identity.json',['qmake_config_snapshot','live_runtime_library_snapshot']))
    for filename,identity,prefixes in archive_specs:
        ident=json.loads((HERE/identity).read_text()); count=0
        if digest(HERE/filename)!=ident['sha256']: raise RuntimeError('Archive hash mismatch')
        with tarfile.open(HERE/filename,'r:gz') as tar:
            members={m.name:m for m in tar.getmembers() if m.isfile()}
            for prefix in prefixes:
                for f in json.loads((HERE/(prefix+'_manifest.json')).read_text()):
                    name=posixpath.normpath(prefix+'/'+f['path'].lstrip('/')); m=members[name]
                    h=hashlib.sha256(); stream=tar.extractfile(m)
                    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
                    if h.hexdigest()!=f['sha256'] or m.size!=f['bytes']:raise RuntimeError('Snapshot member mismatch '+name)
                    count+=1
        archives.append({'path':filename,'sha256':ident['sha256'],'verified_entries':count})
    save('archive_verification.json',archives)
    state.update({'actual_executable_sha256':products[0]['new_sha256'],'source_build_binding':'exact_executable_reproduction' if products[0]['byte_for_byte_equal'] else 'requires_delta_analysis','objects_equal':counts['objects_equal'],'objects_total':len(objects),'semantic_flags_equal':all(x['equal'] for x in flags.values()),'generated_outputs_equal':all(x['equal'] for x in generated),'compiled_authored_inputs_verified':len(authored),'frozen_records_verified':len(json.loads((HERE/'frozen_final.json').read_text()))})
    save('state.json',state)
    if not all(p['byte_for_byte_equal'] for p in products):
        diff=[]
        for p in products:
            if p['byte_for_byte_equal']:continue
            a=(HERE/'rebuilt'/p['path']).read_bytes();b=(SOURCE/p['path']).read_bytes()
            offsets=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
            diff.append({'path':p['path'],'differing_byte_count':len(offsets)+abs(len(a)-len(b)),'first_different_offsets':offsets[:128]})
        save('code_bytes_diff.json',diff)
    print(json.dumps(state))

def finalize(cli):
    guard(cli,'final')
    original=remote_original(cli,'final')
    verify()
    state=json.loads((HERE/'state.json').read_text()); state['original_remote_unchanged_final']=original==json.loads((HERE/'original_remote_before.json').read_text())
    frozen_check('final')
    code="""import pathlib,json,hashlib,sys
root=pathlib.Path(sys.argv[1]);result={}
for prefix in ['toolchain_snapshot','qmake_pkgconfig_snapshot','compiler_dependency_snapshot','linker_input_snapshot','runtime_library_snapshot','qmake_config_snapshot','live_runtime_library_snapshot']:
    rows=[]
    for f in json.loads((root/(prefix+'_manifest.json')).read_text()):
        p=pathlib.Path(f['path']);h=hashlib.sha256()
        with p.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
        actual=h.hexdigest();rows.append({'path':f['path'],'snapshot_sha256':f['sha256'],'final_sha256':actual,'equal':actual==f['sha256']})
    result[prefix]=rows
print(json.dumps(result))
"""
    dependencies=json.loads(remote_python(cli,code,state['remote_root'],timeout=900))
    save('dependency_final_recheck.json',dependencies)
    state['all_dependency_snapshots_unchanged_final']=all(r['equal'] for rows in dependencies.values() for r in rows)
    state['dependency_final_recheck_counts']={name:len(rows) for name,rows in dependencies.items()}
    workflow_inputs=[OLD/'rebuild_binding.py', OLD/'remote_audit.py', OLD/'build_isolated.sh', FROZEN/'retrieval_manifest.json', SOURCE/'detview.pro',SOURCE/'Makefile']
    save('workflow_input_binding.json',[{'path':p.relative_to(BASE).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)} for p in workflow_inputs])
    save('state.json',state)
    inventory=[{'path':p.relative_to(HERE).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts]
    save('artifact_manifest.json',{'excludes':['artifact_manifest.json','__pycache__'],'files':inventory})
    guard(cli,'before_final_report_write')
    # Refresh inventory after the final guard records are saved.
    inventory=[{'path':p.relative_to(HERE).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts]
    save('artifact_manifest.json',{'excludes':['artifact_manifest.json','__pycache__'],'files':inventory})
    sftp=cli.open_sftp()
    for p in sorted(HERE.iterdir()):
        if p.is_file() and p.suffix in {'.json','.md','.py'}:sftp.put(str(p),state['remote_root']+'/'+p.name)
    sftp.close()
    print(json.dumps({'artifact_files':len(inventory),**state}))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','build','collect','supplement','early_compare','verify','finalize']);args=parser.parse_args()
    if args.phase=='verify':verify();return
    cli=board_ssh.connect()
    try:globals()[args.phase](cli)
    finally:cli.close()

if __name__=='__main__':main()
