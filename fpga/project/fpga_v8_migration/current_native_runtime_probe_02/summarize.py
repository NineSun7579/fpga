"""Report-only local verification. No board connection or inference."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
def load(name): return json.loads((HERE/name).read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
report=load('runtime_report.json')
audit=load('execution_audit.json')
cases=report['cases']
headers=[]
for name in ['viewer_native_qt.hpp','viewer_native_guard.hpp','raw_dfl_native.h','rknn_api.h']:
    actual=sha(HERE/'src'/name)
    prior=sha(BASE/'viewer_native_runtime_probe/dependencies/src'/name)
    headers.append(dict(name=name,sha256=actual,frozen_prior_sha256=prior,equal=actual==prior))
before=load('board_before.stdout.txt')
after=load('board_after.stdout.txt')
historical=json.loads((BASE/'current_viewer_binding_02/remote_hash_before.json').read_text())
old_hash={row['path']:row.get('sha256') for row in historical}
historical_drift=[row for row in before['files'] if row['path'] in old_hash and row.get('sha256')!=old_hash[row['path']]]
drift=[dict(before=a,after=b) for a,b in zip(before['files'],after['files']) if a!=b]
acquisitions=report['acquisitions']
strict=dict(case_count=len(cases),passed=sum(c['passed'] for c in cases),
    max_score_error=max(c['max_score_error'] for c in cases),
    max_coordinate_error=max(c['max_coordinate_error'] for c in cases),
    ordered_class_differences=sum(c['class_differences_at_index'] for c in cases),
    count_differences=sum(c['count_difference'] for c in cases))
release_exact=all(a['release_calls']==1 and a['released_buffers']==6 and a['release_ret']==0 for a in acquisitions)
summary=dict(strict=strict,runs=report['certification_rknn_run_calls'],successful_gets=report['successful_gets'],
    release_calls=report['release_calls'],released_buffers=report['released_buffers'],active_output_leases=report['active_output_leases'],
    every_acquisition_released_exactly_once=release_exact,prepare_cases=report['prepare_cases'],
    query_accounting=report['query_accounting'],geometry=report['geometry'],mapped_runtime=report['mapped_runtime'],
    api=report['actual_profile']['api'],driver=report['actual_profile']['driver'],headers=headers,
    original_guard_files=len(before['files']),original_guard_changes=drift,historical_hash_drift=historical_drift,
    live_process_before=before['process'],live_process_after=after['process'],audit=audit,
    model=report['model'],remote_stage=load('remote_stage.json'))
summary['current_source_pins']={name:sha(HERE/name) for name in ['src/current_native_gate.hpp','src/current_native_qt.hpp','src/inference_geometry.h','board/current_retained_decoder.inc','candidate_conversion.inc']}
summary['repeat_guard_pure']=dict(return_code=load('repeat_guard_pure.command.json')['return_code'],stdout=(HERE/'repeat_guard_pure.stdout.txt').read_text().strip(),inference_calls=0)
summary['certified']=bool(report['passed'] and len(cases)==120 and strict['passed']==120 and summary['runs']==30 and
    summary['successful_gets']==60 and summary['release_calls']==60 and summary['released_buffers']==360 and
    release_exact and summary['active_output_leases']==0 and all(h['equal'] for h in headers) and
    all(audit[k] for k in ['live_process_equal','original_files_equal','local_inputs_equal','compiled_dependencies_equal']))
(HERE/'certification_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(certified=summary['certified'],strict=strict,runs=summary['runs'],gets=summary['successful_gets'],
    releases=summary['release_calls'],buffers=summary['released_buffers'],header_pins_equal=all(h['equal'] for h in headers),
    guard_changes=len(drift),historical_drift=len(historical_drift)),indent=2))
