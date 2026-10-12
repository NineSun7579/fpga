"""Aggregate complete EGL diagnostic windows, preserving request success limits."""
import json,re,argparse
from pathlib import Path
def summarize(text):
    rows=[];intervals=[]
    for line in text.splitlines():
        if not line.startswith('egl_swap_probe '):continue
        f=dict(re.findall(r'(\w+)=([^\s]+)',line))
        if 'interval_request' in f:
            intervals.append({k:int(f[k]) for k in ('interval_request','return','success')})
        elif 'wall_s' in f:
            row={k:float(v) for k,v in f.items() if k!='buckets_lt1_lt5_lt10_lt20_ge20'}
            row['buckets']=[int(v) for v in f['buckets_lt1_lt5_lt10_lt20_ge20'].split(',')]
            assert sum(row['buckets'])==row['timed']
            assert row['timed']+row['invalid_clock']==row['calls']
            rows.append(row)
    wall=sum(r['wall_s'] for r in rows);timed=sum(r['timed'] for r in rows)
    total=sum(r['sum_ms'] for r in rows)
    return {'interval_requests':intervals,'windows':len(rows),'wall_s':wall,
            'calls':sum(r['calls'] for r in rows),'invalid_clock':sum(r['invalid_clock'] for r in rows),
            'mean_swap_ms':total/timed if timed else None,
            'max_swap_ms':max((r['max_ms'] for r in rows),default=None),
            'swap_wall_fraction':total/(wall*1000) if wall else None,
            'longswap_ge20ms':sum(r['longswap_ge20ms'] for r in rows),
            'limits':'Successful interval request does not prove effective interval. Swap wall time includes driver, queue and scheduling waits. Preloaded Mali and probe may affect timing; no performance acceptance claim.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('log',type=Path);a=p.parse_args()
    out=json.dumps(summarize(a.log.read_text(errors='replace')),indent=2)
    a.log.with_suffix('.egl_summary.json').write_text(out);print(out)
