"""Report complete per-camera display windows, including lows, not just means."""
import argparse,json,re
from pathlib import Path

def summarize(text):
    complete=[];pending=None;discarded=0
    for line in text.splitlines():
        if line.startswith('[display-perf] '):
            if pending is not None:discarded+=1
            fields=dict(re.findall(r'(\w+)=([\d.]+)',line))
            pending={'seconds':float(fields['seconds']),'started_ms':int(fields['started_ms']),
                     'ended_ms':int(fields['ended_ms']),'counts':{}}
        elif line.startswith('[display-upload] ') and pending is not None:
            fields=dict(re.findall(r'(\w+)=(\d+)',line));camera=int(fields['camera'])
            if camera in pending['counts']:raise ValueError('Duplicate camera in display window')
            pending['counts'][camera]=int(fields['count'])
            if set(pending['counts'])==set(range(1,7)):
                if pending['seconds']<=0:raise ValueError('Nonpositive display interval')
                complete.append(pending);pending=None
    if pending is not None:discarded+=1
    duration=sum(row['seconds'] for row in complete)
    cameras={}
    for camera in range(1,7):
        rates=[row['counts'][camera]/row['seconds'] for row in complete]
        cameras[str(camera)]={'weighted_fps':sum(row['counts'][camera] for row in complete)/duration if duration else None,
                              'min_window_fps':min(rates) if rates else None,
                              'max_window_fps':max(rates) if rates else None,
                              'windows_below_29_fps':sum(rate<29 for rate in rates),
                              'windows_below_30_fps':sum(rate<30 for rate in rates)}
    gaps=[b['started_ms']-a['ended_ms'] for a,b in zip(complete,complete[1:])]
    return {'complete_windows':len(complete),'discarded_partial_windows':discarded,
            'measured_seconds':duration,'max_window_gap_ms':max(gaps) if gaps else None,
            'cameras':cameras,'limits':'Fresh texture uploads; does not measure physical screen scanout. Aggregate window boundaries may extend beyond the CPU sample.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('log',type=Path);args=parser.parse_args()
    result=json.dumps(summarize(args.log.read_text(errors='replace')),indent=2)
    args.log.with_suffix('.fresh_display.json').write_text(result,encoding='utf-8');print(result)
