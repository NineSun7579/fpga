"""Per-thread checked-reply wall time; not an exclusive wait decomposition."""
import json,re,argparse,collections
from pathlib import Path
def summarize(text):
    groups=collections.defaultdict(list)
    for line in text.splitlines():
        if not line.startswith('xcb_reply_probe tid='):continue
        fields=dict(re.findall(r'(\w+)=([^\s]+)',line))
        bins=[int(v) for v in fields.pop('buckets_lt1_lt5_lt10_lt20_ge20_ms').split(',')]
        row={k:int(v) for k,v in fields.items()}
        assert sum(bins)==row['timed'] and row['calls']==row['timed']+row['invalid_clock']
        row['long_calls']=bins[-1];groups[row['tid']].append(row)
    out={}
    for tid,rows in groups.items():
        wall=sum(r['wall_ns'] for r in rows);total=sum(r['sum_ns'] for r in rows);timed=sum(r['timed'] for r in rows)
        out[str(tid)]={'windows':len(rows),'wall_s':wall/1e9,'calls':sum(r['calls'] for r in rows),
                       'invalid_clock':sum(r['invalid_clock'] for r in rows),
                       'mean_ms':total/timed/1e6 if timed else None,
                       'max_ms':max(r['max_ns'] for r in rows)/1e6,
                       'reply_wall_fraction':total/wall if wall else None,
                       'calls_ge20ms':sum(r['long_calls'] for r in rows)}
    return {'threads':out,'limits':'Approximate per-thread completion windows, includes CPU scheduling; final partial windows omitted. Concurrent EGL/XCB durations can overlap and must not be added.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('log',type=Path);a=p.parse_args()
    result=json.dumps(summarize(a.log.read_text(errors='replace')),indent=2)
    a.log.with_suffix('.xcb_summary.json').write_text(result);print(result)
