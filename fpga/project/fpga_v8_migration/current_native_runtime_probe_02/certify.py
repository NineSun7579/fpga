"""Isolated current-native certification. Never rerun a started workload."""
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import sys
import uuid

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OLD = BASE / 'viewer_native_runtime_probe'
CAND = BASE / 'current_viewer_native_candidate_02'
def digest(data): return hashlib.sha256(data).hexdigest()
def write(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
def connect():
    spec = importlib.util.spec_from_file_location('board', BASE.parent / 'board_ssh.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, module.connect()
def call(label, command, timeout=60, sudo=False):
    helper, client = connect()
    try: rc, out, err = helper.run(client, command, timeout=timeout, sudo=sudo)
    finally: client.close()
    write(label + '.command.json', dict(command=command, return_code=rc, timeout=timeout, sudo=sudo))
    (HERE / (label+'.stdout.txt')).write_text(out, encoding='utf-8')
    (HERE / (label+'.stderr.txt')).write_text(err, encoding='utf-8')
    print(label, rc, flush=True)
    if rc: raise RuntimeError(label + ' failed; see retained stderr')
    return out
def local_guard():
    roots = [CAND/'src', BASE/'current_viewer_binding_02/inputs']
    paths = [p for root in roots for p in root.rglob('*') if p.is_file()]
    paths += [BASE/'current_viewer_binding_02/current_retained_decoder.inc', OLD/'prepared_inputs.json', BASE/'pipeline_board_runtime_compatible/pipeline_source.json']
    return {str(p): digest(p.read_bytes()) for p in sorted(paths)}

def prepare():
    write('local_guard_before.json', local_guard())
    rows = []
    def snapshot(source, relative, payload=None):
        original = source.read_bytes()
        data = original if payload is None else payload
        target = HERE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        rows.append(dict(original=str(source), original_sha256=digest(original), relative=relative,
                         sha256=digest(data), bytes=len(data), whole_file=payload is None))
    for name in ['current_native_gate.hpp','current_native_qt.hpp','viewer_native_qt.hpp','viewer_native_guard.hpp','raw_dfl_native.h','rknn_api.h','inference_geometry.h']:
        snapshot(CAND/'src'/name, 'src/'+name)
    for name in ['raw_dfl_reference.h','raw_dfl_native.h']:
        snapshot(BASE/'host_acceleration'/name, 'host_acceleration/'+name)
    decoder = BASE/'current_viewer_binding_02/current_retained_decoder.inc'
    main = (CAND/'src/main.cpp').read_bytes()
    assert decoder.read_bytes() in main
    snapshot(decoder, 'board/current_retained_decoder.inc')
    adapter = (BASE/'host_acceleration/legacy_production_adapter.h').read_bytes()
    adapter = adapter.replace(b'bool m_xyxy = false;', b'bool m_xyxy = false;\n    bool m_trafficlight = false;\n    tdm::InferenceGeometry m_geometry;')
    adapter = adapter.replace(b'../board/board_production_decoder.inc', b'../board/current_retained_decoder.inc')
    snapshot(BASE/'host_acceleration/legacy_production_adapter.h','host_acceleration/legacy_production_adapter.h',adapter)
    types = (CAND/'src/vision_types.h').read_bytes()
    start = types.index(b'struct Detection {'); end = types.index(b'\n};',start)+4
    snapshot(CAND/'src/vision_types.h','viewer_detection.inc',types[start:end])
    start = main.index(b'                for (uint32_t i = 0; i < m_nOutput; ++i)\n',main.index(b'if (nativeDecode) {',main.index(b'QImage laneMask;')))
    end = main.index(b'            } catch (const std::exception& e)',start)
    snapshot(CAND/'src/main.cpp','candidate_conversion.inc',main[start:end])
    snapshot(OLD/'prepare_inputs.cpp','prepare_inputs.cpp')
    snapshot(OLD/'capture_dependencies.py','capture_dependencies.py')
    pipeline = (BASE/'host_acceleration/pipeline_bench.cpp').read_bytes()
    start = pipeline.index(b'cv::Mat prepare(const cv::Mat& bgr) {'); end = pipeline.index(b'\n}\n', start)+2
    snapshot(BASE/'host_acceleration/pipeline_bench.cpp','pipeline_prepare.inc',pipeline[start:end])
    snapshot(OLD/'input_expectations.json','input_expectations.json')
    snapshot(OLD/'board_inventory.py','board_inventory.py')
    source = (OLD/'runtime_probe.cpp').read_text(encoding='utf-8')
    prefix = '''#include "src/rknn_api.h"
static unsigned query_attrs=0, query_sdk=0, query_counts=0;
static int tracked_query(rknn_context c, rknn_query_cmd cmd, void* p, uint32_t size) {
    if(cmd==RKNN_QUERY_INPUT_ATTR || cmd==RKNN_QUERY_OUTPUT_ATTR) ++query_attrs;
    if(cmd==RKNN_QUERY_SDK_VERSION) ++query_sdk;
    if(cmd==RKNN_QUERY_IN_OUT_NUM) ++query_counts;
    return rknn_query(c,cmd,p,size);
}
#define rknn_query tracked_query
#include "src/inference_geometry.h"
'''
    source = prefix + source.replace('src/viewer_native_qt.hpp','src/current_native_qt.hpp')
    source = source.replace('    return dets;\n}', '    tdm::InferenceGeometry geometry;\n    tdm::restoreCanonicalDetections(dets, geometry);\n    return dets;\n}',1)
    source = source.replace('auto session = viewer_native::prepare(owner.context, supplied, model_path, io.n_output, 3, false, ++serial);', '''const auto aq=query_attrs, sq=query_sdk;
        auto session = viewer_native::prepare_current(owner.context, supplied, model_path, io.n_input, io.n_output, 3, false, false, 640, 640, input, attrs, ++serial);
        require(query_attrs==aq, "prepare_current queried cached attributes");
        require(query_sdk-sq==(expected ? 1u : 0u), "unexpected prepare SDK query count");''')
    source = source.replace('    result.insert("prepare_cases", preparations);', '''    auto fallback_geometry = [&](const char* label, bool traffic, int w, int h, rknn_tensor_attr cached) {
        const auto aq=query_attrs, sq=query_sdk;
        auto s=viewer_native::prepare_current(owner.context,model,model_path,io.n_input,io.n_output,3,false,traffic,w,h,cached,attrs,++serial);
        const bool ok=!s.enabled && s.attrs.empty() && !s.decoder && s.context_serial==serial && query_attrs==aq && query_sdk==sq;
        ++prepare_checks; if(!ok) ++failed_checks;
        preparations.append(QJsonObject{{"case",label},{"passed",ok},{"attribute_queries",int(query_attrs-aq)},{"sdk_queries",int(query_sdk-sq)}});
    };
    fallback_geometry("trafficlight actual cache",true,640,640,input);
    fallback_geometry("rectangular 640x480 actual cache",false,640,480,input);
    auto channel_mismatch=input;
    channel_mismatch.dims[input.fmt==RKNN_TENSOR_NHWC ? 3 : 1]=1;
    fallback_geometry("RGB channel mismatch derived actual cache",false,640,640,channel_mismatch);
    for(const char* name : {"traffic.rknn","wbv4.rknn"}) {
        const auto supplied=bytes(stage+"/model/"+name);
        prepare_case(QString("actual rotated model ")+name,supplied,false,"model SHA256 is outside pinned V8 profile");
    }
    tdm::InferenceGeometry geometry;
    require(tdm::queryInputGeometry(input,geometry) && geometry.width==640 && geometry.height==640 && geometry.canonicalTop()==0,"current geometry mismatch");
    result.insert("geometry",QJsonObject{{"width",geometry.width},{"height",geometry.height},{"canonical_top",geometry.canonicalTop()},{"actual_restore_function",true}});
    result.insert("query_accounting",QJsonObject{{"attribute_queries",int(query_attrs)},{"sdk_queries",int(query_sdk)},{"io_queries",int(query_counts)},{"prepare_attribute_queries",0}});
    result.insert("prepare_cases", preparations);''')
    source = source.replace('const auto reference = production.decode(outputs, attrs);','auto reference = production.decode(outputs, attrs);\n                tdm::restoreCanonicalDetections(reference, production.m_geometry);')
    source = source.replace('require(cases.size() == 120 && failed_checks == 0,', 'require(query_attrs==7 && query_counts==1, "cached query accounting changed during inference");\n    require(cases.size() == 120 && failed_checks == 0,')
    (HERE/'runtime_probe.cpp').write_text(source, encoding='utf-8')
    write('source_dependencies.json',rows)
    makefile=BASE/'current_viewer_rebuild_02/Makefile'
    text=makefile.read_text()
    flags=re.search(r'^CXXFLAGS\s*=\s*(.*)$',text,re.M).group(1)
    actual=flags.replace('$(DEFINES)','-DQT_NO_DEBUG -DQT_CORE_LIB -DQT_GUI_LIB')+' -fno-fast-math'
    assert '-O2' in actual and '-std=gnu++1z' in actual and 'fast-math' not in flags
    write('compiler_flag_binding.json',dict(makefile=str(makefile),sha256=digest(makefile.read_bytes()),original=flags,probe=actual,parallel_jobs=2))
    return actual

def audit(stage,label):
    command='python3 '+shlex.quote(stage+'/audit_board.py')
    return json.loads(call(label,command,timeout=120,sudo=True))

def main():
    if (HERE/'remote_stage.json').exists():
        raise RuntimeError('Existing stage: use report-only collection; this orchestrator refuses repeats')
    flags=prepare()
    stage='/userdata/linaro/current_native_runtime_probe_02_'+uuid.uuid4().hex
    call('create_stage','mkdir -m 700 '+shlex.quote(stage))
    write('remote_stage.json',dict(remote_root=stage))
    remote_paths=[row['path'] for row in json.loads((BASE/'current_viewer_binding_02/remote_hash_before.json').read_text())]
    inventory=json.loads((OLD/'prepared_inputs.json').read_text())
    audit_source='''import json,hashlib,sys
from pathlib import Path
from board_inventory import identity
paths=json.loads(Path(__file__).with_name('audit_paths.json').read_text())
rows=[]
for p in paths:
 try:
  f=Path(p); rows.append(dict(path=p,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size))
 except Exception as e: rows.append(dict(path=p,error=str(e)))
print(json.dumps(dict(process=identity(),files=rows),indent=2))
'''
    (HERE/'audit_board.py').write_text(audit_source,encoding='utf-8')
    remote_paths += [row['board_path'] for row in inventory['inputs']]+[row['prepared_path'] for row in inventory['inputs']]
    remote_paths += ['/userdata/detview-driving-demo/detview-driving-demo','/usr/lib/librknnrt.so']
    write('audit_paths.json',sorted(set(remote_paths)))
    helper,client=connect()
    try:
        with client.open_sftp() as sftp:
            for folder in ['src','host_acceleration','board','model']: sftp.mkdir(stage+'/'+folder)
            for row in json.loads((HERE/'source_dependencies.json').read_text()):
                sftp.put(str(HERE/row['relative']),stage+'/'+row['relative'])
            for name in ['runtime_probe.cpp','audit_board.py','audit_paths.json']:
                sftp.put(str(HERE/name),stage+'/'+name)
    finally: client.close()
    before=audit(stage,'board_before')
    models=json.loads((BASE/'current_viewer_binding_02/elf_sdk_model_metadata.json').read_text())['models']
    selected={}
    for row in models:
        for key,prefix in [('traffic','f96'),('wbv4','21451'),('pinned','be7ee8')]:
            if row.get('sha256','').startswith(prefix): selected[key]=row
    assert len(selected)==3
    script='import hashlib,json,shutil\nfrom pathlib import Path\n'
    for key,row in selected.items():
        script+=f'p=Path({row["path"]!r}); data=p.read_bytes(); assert hashlib.sha256(data).hexdigest()=={row["sha256"]!r}; Path({(stage+"/model/"+key+".rknn")!r}).write_bytes(data)\n'
    (HERE/'stage_models.py').write_text(script,encoding='utf-8')
    helper,client=connect()
    try:
        with client.open_sftp() as sftp: sftp.put(str(HERE/'stage_models.py'),stage+'/stage_models.py')
    finally: client.close()
    call('model_snapshot','python3 '+shlex.quote(stage+'/stage_models.py'),sudo=True)
    helper,client=connect()
    try:
        with client.open_sftp() as sftp:
            for key,row in selected.items():
                target=HERE/'model'/f'{key}.rknn'
                target.parent.mkdir(exist_ok=True)
                sftp.get(stage+'/model/'+key+'.rknn',str(target))
                assert digest(target.read_bytes())==row['sha256']
    finally: client.close()
    write('model_snapshot_manifest.json',selected)
    finish(stage,flags,before)

def finish(stage,flags,before):
    common='g++ '+flags+' $(pkg-config --cflags Qt5Core Qt5Gui) -I'+shlex.quote(stage)+' -I'+shlex.quote(stage+'/src')
    commands={}
    for binary in ['runtime_probe','prepare_inputs']:
        extra=' -I/usr/include/opencv4' if binary=='prepare_inputs' else ''
        libs=' -lrknnrt' if binary=='runtime_probe' else ' -lopencv_core -lopencv_imgcodecs -lopencv_imgproc'
        commands[binary]='timeout 300s '+common+extra+' -MD -MF '+stage+'/'+binary+'.d -c '+stage+'/'+binary+'.cpp -o '+stage+'/'+binary+'.o && g++ -Wl,-O1 -o '+stage+'/'+binary+' '+stage+'/'+binary+'.o'+libs+' $(pkg-config --libs Qt5Core Qt5Gui) -lpthread'
    write('compiler_commands.json',commands)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(call,key+'_build',cmd,330) for key,cmd in commands.items()]
        for f in futures: f.result()
    call('prepare_inputs','timeout 60s '+stage+'/prepare_inputs '+stage,90,sudo=True)
    call('dependency_before','python3 '+stage+'/capture_dependencies.py '+stage)
    call('binary_identity','sha256sum '+stage+'/runtime_probe '+stage+'/prepare_inputs\nldd '+stage+'/runtime_probe\nreadelf -d '+stage+'/runtime_probe')
    # mkdir is an atomic permanent attempt lock. It remains even after failure.
    command='if ! mkdir '+stage+'/workload_started 2>/dev/null; then echo REFUSE_REPEAT; exit 73; fi\n'+stage+'/runtime_probe '+stage+'/model/pinned.rknn '+stage+'/prepared_inputs.json '+stage+' > '+stage+'/runtime_probe.stdout.txt 2> '+stage+'/runtime_probe.stderr.txt\nrc=$?\nprintf "%s\\n" "$rc" > '+stage+'/runtime_return_code.txt\nif [ "$rc" -eq 0 ]; then touch '+stage+'/workload_success; fi\nexit "$rc"'
    error=None
    try: call('workload_once',command,timeout=600,sudo=True)
    except Exception as e: error=str(e)
    after=audit(stage,'board_after')
    call('dependency_after','cp '+stage+'/compiled_dependency_hashes.json '+stage+'/compiled_dependency_hashes_before.json\npython3 '+stage+'/capture_dependencies.py '+stage)
    helper,client=connect()
    try:
        with client.open_sftp() as sftp:
            for name in ['runtime_report.json','runtime_return_code.txt','runtime_probe.stdout.txt','runtime_probe.stderr.txt','prepared_inputs.json','probe_runtime_maps.txt','actual_guard_profile.txt','compiled_dependency_hashes.json','compiled_dependency_hashes_before.json','runtime_probe.d','prepare_inputs.d']:
                try: sftp.get(stage+'/'+name,str(HERE/name))
                except FileNotFoundError: pass
    finally: client.close()
    write('local_guard_after.json',local_guard())
    process_equal=before['process']['boot_id']==after['process']['boot_id'] and before['process']['viewers']==after['process']['viewers']
    files_equal=before['files']==after['files']
    local_equal=json.loads((HERE/'local_guard_before.json').read_text())==local_guard()
    dep_equal=(HERE/'compiled_dependency_hashes_before.json').read_bytes()==(HERE/'compiled_dependency_hashes.json').read_bytes()
    report=json.loads((HERE/'runtime_report.json').read_text())
    write('execution_audit.json',dict(error=error,remote_root=stage,live_process_equal=process_equal,expected_pid_2740_present=any(v['pid']==2740 for v in before['process']['viewers']),original_files_equal=files_equal,local_inputs_equal=local_equal,compiled_dependencies_equal=dep_equal,live_parallel_cpu_build_jobs=2,report_passed=report.get('passed'),runs=report.get('certification_rknn_run_calls'),limitations='Standalone current adapter; not full Viewer::runOnce orchestration, not viewer FPS. Concurrent live viewer workload exists. Existing component/selftest lease semantics are separate evidence.'))
    if error: raise RuntimeError(error)

def resume_before_workload():
    stage=json.loads((HERE/'remote_stage.json').read_text())['remote_root']
    call('resume_no_workload_proof','test ! -e '+stage+'/workload_started && test ! -e '+stage+'/runtime_report.json')
    selected={}
    for row in json.loads((BASE/'current_viewer_binding_02/elf_sdk_model_metadata.json').read_text())['models']:
        for key,prefix in [('traffic','f96'),('wbv4','21451'),('pinned','be7ee8')]:
            if row.get('sha256','').startswith(prefix): selected[key]=row
    helper,client=connect()
    try:
        with client.open_sftp() as sftp:
            for key,row in selected.items():
                target=HERE/'model'/f'{key}.rknn'
                target.parent.mkdir(exist_ok=True)
                sftp.get(stage+'/model/'+key+'.rknn',str(target))
                assert digest(target.read_bytes())==row['sha256']
    finally: client.close()
    write('model_snapshot_manifest.json',selected)
    flags=json.loads((HERE/'compiler_flag_binding.json').read_text())['probe']
    before=json.loads((HERE/'board_before.stdout.txt').read_text())
    finish(stage,flags,before)

if __name__=='__main__':
    if sys.argv[1:]==['resume-before-workload']: resume_before_workload()
    else: main()
