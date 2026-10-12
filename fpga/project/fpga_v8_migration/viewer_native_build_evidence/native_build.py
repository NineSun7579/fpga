"""Build the immutable prepared viewer in a new isolated board directory."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import shlex
import shutil
import sys
import tarfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
MIGRATION = HERE.parent
PREPARED = MIGRATION/'viewer_native_candidate'
BASELINE = MIGRATION/'viewer_rebuild_evidence'
sys.path.insert(0,str(BASELINE))
# Read-only use of the previously audited SSH/process helpers; no prior save/build
# function is called, and bytecode writes are disabled before importing them.
import rebuild_binding as binding


def save(name, value):
    (HERE/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def identity(path):
    return {'bytes':Path(path).stat().st_size,'sha256':sha(path)}


def local_prepared_hashes():
    # Freeze both the source manifest and the metadata establishing copied inputs.
    names = ['candidate_manifest.json','copied_sources.json','frozen_inputs_sha256.json',
             'build_prepared_viewer.sh','patch.diff']
    out = {name:identity(PREPARED/name) for name in names}
    out.update({'src/'+p.relative_to(PREPARED/'src').as_posix():identity(p)
                for p in sorted((PREPARED/'src').rglob('*')) if p.is_file()})
    return out


READ_HASHES = r'''
import hashlib,json,pathlib,sys
paths=json.loads(sys.argv[1]); out={}
for name in paths:
    p=pathlib.Path(name)
    if not p.is_file(): out[name]={'missing':True}; continue
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    out[name]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
print(json.dumps(out))
'''


def baseline_system_reference():
    expected = {}
    for name in ['toolchain_snapshot_manifest.json','compiler_dependency_snapshot_manifest.json',
                 'linker_input_snapshot_manifest.json','runtime_library_snapshot_manifest.json',
                 'qmake_config_snapshot_manifest.json','live_runtime_library_snapshot_manifest.json']:
        for f in json.loads((BASELINE/name).read_text()):
            if f['path'].startswith('/userdata/'): continue
            expected[f['path']] = {'bytes':f['bytes'],'sha256':f['sha256']}
    return expected


def check_board_baseline(cli, phase):
    expected = baseline_system_reference()
    current = json.loads(binding.remote_python(cli,READ_HASHES,json.dumps(list(expected)),timeout=300))
    diff = {name:{'old':f,'current':current.get(name)} for name,f in expected.items() if f!=current.get(name)}
    save('board_dependencies_'+phase+'.json',{'checked_files':len(expected),'files':current,'differences':diff})
    if diff: raise RuntimeError('Board compiler/header/library baseline drift: '+', '.join(diff))
    original_manifest = json.loads((MIGRATION/'viewer_build_recovered'/'manifest.json').read_text())
    original = json.loads(binding.remote_python(cli,binding.VERIFY_REMOTE,original_manifest['remote_root']))
    expected_sources = {f['path']:{'bytes':f['bytes'],'sha256':f['sha256']} for f in original_manifest['files']}
    save('original_remote_'+phase+'.json',original)
    # Other sessions may update the retained board source after the completed
    # baseline rebuild. It is not an input to this candidate build. Preserve the
    # observed delta and assess stability against this task's own before audit.
    save('original_remote_baseline_delta_'+phase+'.json',{
        'changed':{name:{'frozen':f,'current':original.get(name)} for name,f in expected_sources.items()
                   if original.get(name)!=f},
        'extra_files':sorted(set(original)-set(expected_sources)),
        'missing_files':sorted(set(expected_sources)-set(original))})
    return len(expected)


def prepare(cli):
    if (HERE/'state.json').exists(): raise RuntimeError('Refusing to reuse local evidence state')
    manifest = json.loads((PREPARED/'candidate_manifest.json').read_text())
    expected = {'src/'+name.replace('\\','/'):{'bytes':f['bytes'],'sha256':f['sha256']}
                for name,f in manifest['source_files'].items()}
    before = local_prepared_hashes()
    source_map = {n:f for n,f in before.items() if n.startswith('src/')}
    save('prepared_inputs_before.json',before)
    if source_map != expected or len(expected)!=29: raise RuntimeError('Prepared source manifest mismatch')
    frozen_manifest = json.loads((MIGRATION/'viewer_build_recovered'/'manifest.json').read_text())
    frozen = {f['path']:{'bytes':f['bytes'],'sha256':f['sha256']} for f in frozen_manifest['files']}
    current_frozen = {name:identity(MIGRATION/'viewer_build_recovered'/'inputs'/name) for name in frozen}
    save('frozen_inputs_before.json',current_frozen)
    if current_frozen != frozen: raise RuntimeError('Immutable recovered inputs changed')
    count = check_board_baseline(cli,'before')
    guard = binding.process_guard(cli)
    save('process_guard_before.json',guard)
    # Both a local source snapshot and remote upload retain exact prepared bytes.
    for name in before:
        dest = HERE/'prepared_snapshot'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(PREPARED/name,dest)
    root = binding.run(cli,'base=/userdata/linaro/fpga_v8_viewer_native_build_20261005; '
                            'dest="$base"; i=0; while [ -e "$dest" ]; do i=$((i+1)); dest="${base}_$i"; done; '
                            'mkdir "$dest" && printf "%s" "$dest"').strip()
    state = {'remote_root':root,'status':'staged_source_only','source_files':len(expected),
             'candidate_manifest_sha256':before['candidate_manifest.json']['sha256'],
             'baseline_system_files_checked':count,'build_return_code':None,
             'viewer_executions':0,'selftest_executions':0,'driver_opens':0}
    save('state.json',state)
    sftp = cli.open_sftp()
    sftp.mkdir(root+'/src')
    sftp.mkdir(root+'/src/stereo_demo')
    for name in source_map:
        sftp.put(str(HERE/'prepared_snapshot'/name),root+'/'+name)
    sftp.put(str(HERE/'prepared_snapshot'/'build_prepared_viewer.sh'),root+'/build_prepared_viewer.sh')
    for name in ['remote_native_audit.py','make_evidence.sh','run_build.sh']:
        sftp.put(str(HERE/name),root+'/'+name)
    sftp.chmod(root+'/make_evidence.sh',0o755)
    sftp.close()
    uploaded = json.loads(binding.remote_python(cli,binding.VERIFY_REMOTE,root+'/src'))
    if uploaded != {name[4:]:f for name,f in expected.items()}: raise RuntimeError('Remote upload differs')
    save('remote_uploaded_source_hashes.json',uploaded)
    output = binding.run(cli,'cd '+shlex.quote(root)+' && python3 remote_native_audit.py preflight',timeout=300)
    save('preflight_status.json',json.loads(output))
    print(json.dumps({'status':'prepared','remote_root':root,'source_files':len(expected),
                      'board_baseline_files_unchanged':count,'reused_objects':0,
                      'viewer_processes':[{k:p[k] for k in ['pid','start_ticks','exe','image']} for p in guard['processes']]}))


def build(cli):
    state = json.loads((HERE/'state.json').read_text())
    print(binding.run(cli,'cd '+shlex.quote(state['remote_root'])+' && bash run_build.sh',timeout=900).strip())


def retry_target(cli):
    state=json.loads((HERE/'state.json').read_text());root=state['remote_root']
    sftp=cli.open_sftp()
    first=HERE/'attempt1';first.mkdir(exist_ok=True)
    for name in ['compile_link.log','commands.txt','build_return_code.txt','build_start_epoch.txt','build_end_epoch.txt']:
        sftp.get(root+'/'+name,str(first/name))
    sftp.get(root+'/artifacts/viewer_build/Makefile',str(first/'Makefile'))
    text=(first/'compile_link.log').read_text(errors='replace')
    print(json.dumps({'attempt1_diagnostics':[line for line in text.splitlines() if 'warning' in line.lower() or 'error' in line.lower()],
                      'attempt1_link_command':[line for line in text.splitlines() if ' -o detview ' in line]}))
    for name in ['remote_native_audit.py','qmake_evidence.sh','run_retry_target.sh']:
        sftp.put(str(HERE/name),root+'/'+name)
    sftp.chmod(root+'/qmake_evidence.sh',0o755)
    sftp.close()
    print(binding.run(cli,'cd '+shlex.quote(root)+' && bash run_retry_target.sh',timeout=900).strip())


def collect(cli):
    state = json.loads((HERE/'state.json').read_text())
    root = state['remote_root']
    result = json.loads(binding.run(cli,'cd '+shlex.quote(root)+' && python3 remote_native_audit.py collect',timeout=900))
    save('remote_collection.json',result)
    sftp = cli.open_sftp()
    for name in result['download_files']:
        dest = HERE/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        sftp.get(root+'/'+name,str(dest))
    sftp.close()
    state['build_return_code'] = result['build_return_code']
    state['status'] = 'built_and_linked_not_executed' if result['build_return_code']==0 else 'build_failed'
    state['products'] = result['products']
    save('state.json',state)
    check_board_baseline(cli,'after')
    after = local_prepared_hashes()
    save('prepared_inputs_after.json',after)
    if after != json.loads((HERE/'prepared_inputs_before.json').read_text()): raise RuntimeError('Prepared inputs changed during build')
    remote_sources = json.loads(binding.remote_python(cli,binding.VERIFY_REMOTE,root+'/src'))
    save('remote_source_hashes_after.json',remote_sources)
    if remote_sources!=json.loads((HERE/'remote_uploaded_source_hashes.json').read_text()): raise RuntimeError('Remote source changed')
    guard = binding.process_guard(cli)
    save('process_guard_after.json',guard)
    prior = json.loads((HERE/'process_guard_before.json').read_text())
    state['installed_executable_unchanged'] = prior['installed']==guard['installed']
    state['boot_unchanged'] = prior['boot_id']==guard['boot_id']
    state['live_process_identity_unchanged'] = [(p['pid'],p['start_ticks'],p['image']) for p in prior['processes']] == [(p['pid'],p['start_ticks'],p['image']) for p in guard['processes']]
    state['prepared_sources_unchanged'] = True
    state['original_sources_unchanged'] = json.loads((HERE/'original_remote_before.json').read_text()) == json.loads((HERE/'original_remote_after.json').read_text())
    state['board_toolchain_headers_libraries_unchanged'] = True
    save('state.json',state)
    print(json.dumps({'status':state['status'],'build_return_code':state['build_return_code'],
                      'candidate':result['products'].get('detview-native-candidate'),
                      'warnings':result['warning_lines'],'preservation':{k:v for k,v in state.items() if k.endswith('_unchanged')}}))


def verify_local():
    state = json.loads((HERE/'state.json').read_text())
    before = json.loads((HERE/'prepared_inputs_before.json').read_text())
    if local_prepared_hashes()!=before: raise RuntimeError('Prepared inputs changed')
    if {name:identity(HERE/'prepared_snapshot'/name) for name in before}!=before: raise RuntimeError('Local prepared snapshot differs')
    frozen_before=json.loads((HERE/'frozen_inputs_before.json').read_text())
    frozen_after={name:identity(MIGRATION/'viewer_build_recovered'/'inputs'/name) for name in frozen_before}
    save('frozen_inputs_after.json',frozen_after)
    if frozen_after!=frozen_before:raise RuntimeError('Local frozen inputs changed')
    collection = json.loads((HERE/'remote_collection.json').read_text())
    for name,f in collection['products'].items():
        if identity(HERE/'rebuilt'/name)!={'bytes':f['bytes'],'sha256':f['sha256']}: raise RuntimeError('Downloaded product differs: '+name)
    manifest = json.loads((HERE/'dependency_archive_identity.json').read_text())
    if sha(HERE/'dependency_snapshots.tar.gz')!=manifest['sha256']: raise RuntimeError('Archive hash mismatch')
    count = 0
    with tarfile.open(HERE/'dependency_snapshots.tar.gz','r:gz') as tar:
        members = {m.name:m for m in tar.getmembers() if m.isfile()}
        for prefix in ['compiler_dependency_snapshot','linker_input_snapshot','runtime_library_snapshot','toolchain_snapshot','qmake_config_snapshot']:
            for f in json.loads((HERE/(prefix+'_manifest.json')).read_text()):
                name = posixpath.normpath(prefix+'/'+f['path'].lstrip('/'))
                member = members[name]
                stream = tar.extractfile(member)
                h = hashlib.sha256()
                for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
                if h.hexdigest()!=f['sha256'] or member.size!=f['bytes']: raise RuntimeError('Dependency snapshot mismatch '+name)
                count+=1
    deps = {f['path']:f for f in json.loads((HERE/'compiler_dependency_snapshot_manifest.json').read_text())}
    authored = []
    for name,f in before.items():
        if not name.startswith('src/'): continue
        actual = deps.get(state['remote_root']+'/'+name)
        if actual:
            if actual['sha256']!=f['sha256']: raise RuntimeError('Compiled source differs: '+name)
            authored.append(name)
    compared = []
    for p in sorted((HERE/'rebuilt').glob('*.o')):
        old = BASELINE/'rebuilt'/p.name
        compared.append({'path':p.name,'candidate_sha256':sha(p),'baseline_sha256':sha(old),
                         'equal':p.read_bytes()==old.read_bytes()})
    save('objects_compared_to_baseline.json',compared)
    # Out-of-source include/project paths and the target name are expected to
    # change. Optimization, definitions, linker flags and library order must not.
    flags={}
    for key in ['CC','CXX','DEFINES','CFLAGS','CXXFLAGS','LINK','LFLAGS','LIBS','QMAKE']:
        def setting(path):
            for line in path.read_text().splitlines():
                if line.split('=',1)[0].strip()==key:return line.split('=',1)[1].strip()
        old=setting(BASELINE/'Makefile.fresh')
        new=setting(HERE/'generated'/'Makefile')
        flags[key]={'equal':old==new,'baseline':old,'candidate':new}
    save('qmake_flags_compared.json',flags)
    if not all(f['equal'] for f in flags.values()):raise RuntimeError('Candidate qmake compiler/link semantics drift')
    sdk_path=state['remote_root']+'/src/rknn_api.h'
    sdk=deps[sdk_path]
    if sdk['sha256']!=before['src/rknn_api.h']['sha256']:raise RuntimeError('SDK input changed')
    native_headers=['raw_dfl_native.h','viewer_native_guard.hpp','viewer_native_qt.hpp']
    for name in native_headers:
        if state['remote_root']+'/src/'+name not in deps:raise RuntimeError('Native header absent from compiler dependency trace')
    runtime=json.loads((HERE/'runtime_library_snapshot_manifest.json').read_text())
    actual=[f for f in runtime if f['realpath']=='/usr/lib/librknnrt.so']
    expected_runtime='73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885'
    if len(actual)!=1 or actual[0]['sha256']!=expected_runtime:raise RuntimeError('Candidate loader RKNN fingerprint mismatch')
    versions=json.loads((HERE/'toolchain_versions.json').read_text())
    baseline_versions=json.loads((BASELINE/'toolchain_versions.json').read_text())
    comparisons={}
    for candidate_key,baseline_key in [('qmake_version','qmake_version'),('qmake_query','qmake_query'),
                                       ('gxx_version','gxx_version'),('gxx_search_dirs','gxx_search_dirs'),
                                       ('gxx_specs','gxx_specs'),('opencv_version','pkg_opencv_version'),
                                       ('opencv_flags','pkg_opencv_flags'),('ld_version','ld_version'),
                                       ('make_version','make_version')]:
        candidate=versions[candidate_key];base=baseline_versions[baseline_key]
        comparisons[candidate_key]={'equal':all(candidate[k]==base[k] for k in ['rc','stdout','stderr'])}
    save('toolchain_versions_compared.json',comparisons)
    if not all(x['equal'] for x in comparisons.values()):raise RuntimeError('Toolchain version/configuration changed')
    live_maps=json.loads((HERE/'process_guard_after.json').read_text())
    save('live_rknn_mappings_after.json',{'candidate_executed':False,
         'processes':[{'pid':p['pid'],'start_ticks':p['start_ticks'],
                       'rknn_map_lines':[line for line in p['maps'].splitlines() if 'librknnrt' in line]}
                      for p in live_maps['processes']]})
    save('local_verification.json',{'all_downloaded_products_verified':True,'archive_sha256':manifest['sha256'],
                                   'dependency_entries_verified':count,'compiled_authored_inputs_verified':authored,
                                   'prepared_source_snapshot_matches':True,'objects_compared':compared,
                                   'qmake_semantic_flags_match_baseline':True,
                                   'frozen_sdk_header_used':sdk,'native_headers_compiled':native_headers,
                                   'candidate_loader_rknn_fingerprint':actual[0],
                                   'toolchain_versions_match_baseline':True})
    print(json.dumps({'downloaded_products_verified':len(collection['products']),
                      'dependency_entries_verified':count,'compiled_authored_inputs_verified':len(authored),
                      'objects_equal_to_baseline':sum(f['equal'] for f in compared),'objects_total':len(compared)}))


def finalize(cli):
    check_board_baseline(cli,'final')
    state = json.loads((HERE/'state.json').read_text())
    final = binding.process_guard(cli)
    save('process_guard_final.json',final)
    before = json.loads((HERE/'process_guard_before.json').read_text())
    state['installed_executable_unchanged_final']=before['installed']==final['installed']
    state['boot_unchanged_final']=before['boot_id']==final['boot_id']
    state['live_process_identity_unchanged_final']=[(p['pid'],p['start_ticks'],p['image']) for p in before['processes']]==[(p['pid'],p['start_ticks'],p['image']) for p in final['processes']]
    state['prepared_inputs_unchanged_final']=local_prepared_hashes()==json.loads((HERE/'prepared_inputs_before.json').read_text())
    state['original_sources_unchanged_final']=json.loads((HERE/'original_remote_before.json').read_text())==json.loads((HERE/'original_remote_final.json').read_text())
    remote_sources=json.loads(binding.remote_python(cli,binding.VERIFY_REMOTE,state['remote_root']+'/src'))
    save('remote_source_hashes_final.json',remote_sources)
    state['staged_candidate_sources_unchanged_final']=remote_sources==json.loads((HERE/'remote_uploaded_source_hashes.json').read_text())
    state['build_attempts']=[{'attempt':1,'compile_link':'succeeded_as_detview','script_return_code':1,
                              'failure':'Final sha256sum expected candidate target; project reset early TARGET assignment.'},
                             {'attempt':2,'script_return_code':state['build_return_code'],
                              'target_override':'QMAKE wrapper appends -after TARGET=detview-native-candidate',
                              'reused_objects':0}]
    state['validation_scope']='Full RK3568 compile/link only; candidate runtime/head/semantic/failure validation pending.'
    save('state.json',state)
    files=[{'path':p.relative_to(HERE).as_posix(),**identity(p)} for p in sorted(HERE.rglob('*'))
           if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts]
    save('artifact_manifest.json',{'excludes':['artifact_manifest.json','__pycache__'],'files':files})
    sftp=cli.open_sftp()
    for name in ['README.md','state.json','artifact_manifest.json','local_verification.json','objects_compared_to_baseline.json']:
        sftp.put(str(HERE/name),state['remote_root']+'/'+name)
    sftp.close()
    print(json.dumps({'status':state['status'],'remote_candidate':state['remote_root']+'/artifacts/viewer_build/detview-native-candidate',
                      'artifact_files':len(files),'preservation':{k:v for k,v in state.items() if k.endswith('_final')}}))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['prepare','build','retry-target','collect','verify-local','finalize'])
    args=parser.parse_args()
    if args.phase=='verify-local': verify_local(); return
    cli=binding.board_ssh.connect()
    try: {'prepare':prepare,'build':build,'retry-target':retry_target,'collect':collect,'finalize':finalize}[args.phase](cli)
    finally: cli.close()


if __name__=='__main__': main()
