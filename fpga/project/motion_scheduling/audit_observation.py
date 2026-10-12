"""Summarize recorded observation counters without calling skips throughput."""
import argparse
import json
from pathlib import Path
import re

p = argparse.ArgumentParser()
p.add_argument('receipt', type=Path)
a = p.parse_args()
r = json.loads(a.receipt.read_text())
assert r['status'] == 'success' and r['action'] == 'observe'
text = ''.join(e['text'] for e in r['events'] if e['state'] == 'log_chunk')
def rows(prefix):
    return [dict((k, int(v)) for k,v in re.findall(r'(\w+)=(-?\d+)', line))
            for line in text.splitlines() if prefix in line]
policy = rows('[motion-scheduling]')
traffic = rows('[motion-traffic]')
assert len(policy)>1 and len(traffic)>1
assert len({(x['camera'],x['generation']) for x in policy})==1
def deltas(series, keys):
    result={k:series[-1][k]-series[0][k] for k in keys}
    assert all(v>=0 for v in result.values())
    return result
report=dict(receipt=str(a.receipt), policy_sample_count=len(policy), traffic_sample_count=len(traffic),
    policy_sample_deltas=deltas(policy,['static_deferred_frames','motion_triggered_completed',
                                      'fallback_completed','periodic_completed']),
    traffic_sample_deltas=deltas(traffic,['polls','completed_dma_bytes','errors','sequence_changed']),
    capture_max_us=traffic[-1]['captureduration_max_us'], ioctl_max_us=traffic[-1]['max_ioctl_us'],
    disabled=traffic[-1]['disabled'], camera_one_based=policy[-1]['camera'],
    limitations=['Sample counter deltas exclude edges of the observation window.',
                 'Deferred frames are not completed inferences or extra display frames.',
                 'Full image DMA continues; no ROI bandwidth or throughput gain claimed.',
                 'Fallback includes unavailable hints during DMA mutex contention.'])
assert report['disabled']==0 and report['traffic_sample_deltas']['errors']==0
assert report['traffic_sample_deltas']['sequence_changed']>0
assert all(report['policy_sample_deltas'][k]>0 for k in ['static_deferred_frames','motion_triggered_completed','periodic_completed'])
output=Path(__file__).with_name('live_acceptance.json')
output.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
