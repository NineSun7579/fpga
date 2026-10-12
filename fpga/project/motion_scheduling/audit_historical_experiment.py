import importlib.util
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('performance_audit',HERE.parent/'performance_100h/audit_performance.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
inputs=json.loads((HERE/'historical_experiment_receipts.json').read_text())
report={}
for label in ('historical','current'):
    receipt=json.loads(Path(inputs[label+'_observe']).read_text())
    assert receipt['status']=='success'
    begin=[e for e in receipt['events'] if e['state']=='observation_started'][0]
    end=[e for e in receipt['events'] if e['state']=='observed'][0]
    assert end['monotonic']-begin['monotonic']>=120
    metrics=audit.parse_observation(receipt)
    assert not metrics['parse_errors'],metrics['parse_errors']
    display=metrics['display']
    assert display['window_count']>0
    text=''.join(e.get('text','') for e in receipt['events'] if e['state']=='log_chunk')
    peaks=[float(v) for v in re.findall(r'paint_new_fps=([\d.]+)',text)]
    captures=metrics['capture']
    report[label]={'observation_seconds':end['seconds'],'new_display_fps':display['fresh_paint_fps'],
        'complete_display_seconds':display['seconds'],'stats_short_sample_peak_fps':max(peaks,default=None),
        'successful_image_dma_MB_per_second':sum(v['dma_bytes_per_second'] for v in captures.values())/1e6,
        'read_errors':sum(v['read_errors'] for v in captures.values()),
        'inference':metrics['inference'],
        'notes':'Historical binary may lack precise inference counters; absent inference metrics cannot be compared.'}
old=report['historical']['new_display_fps'];new=report['current']['new_display_fps']
report['display_percent_change']=(new/old-1)*100
report['limits']='Sequential live scenes; both arms retain stereo, motion gating/HUD batching off, DET_BENCH=0. Scene variation prevents causal attribution.'
(HERE/'historical_experiment_comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('historical','current')},indent=2))
for label in ('historical','current'):
    print(label,json.dumps({k:v for k,v in report[label].items() if k!='inference'},indent=2))
