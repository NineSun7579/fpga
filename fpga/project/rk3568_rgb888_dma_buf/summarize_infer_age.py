"""Report source ages for identical inference frames; capture means host RAW DMA."""
import argparse,json,math,re
from pathlib import Path

def summarize(text):
    frames={}
    for line in text.splitlines():
        if not line.startswith('[infer-age] '):continue
        fields=dict(re.findall(r'(\w+)=(\S+)',line))
        key=tuple(int(fields[k]) for k in ('generation','camera','id','tag','captured_ms'))
        event={k:int(fields[k]) for k in ('event_ms','age_ms')}
        if event['age_ms']!=event['event_ms']-key[-1] or event['age_ms']<0:
            raise ValueError('Invalid monotonic source-age evidence')
        stage=fields['stage']
        if stage in frames.setdefault(key,{}):
            raise ValueError('Duplicate same-identity stage: '+stage)
        frames[key][stage]=event
    stages=('publish','request','GUI_submit','RKNN_start','result_accepted')
    matched=[row for row in frames.values() if all(stage in row for stage in stages)]
    def metrics(values):
        values=sorted(values)
        return {'count':len(values),'p50_ms':values[max(0,math.ceil(len(values)*.5)-1)] if values else None,
                'p95_ms':values[max(0,math.ceil(len(values)*.95)-1)] if values else None,
                'max_ms':max(values) if values else None}
    def intervals(stage):
        times=sorted(row[stage]['event_ms'] for row in frames.values() if stage in row)
        gaps=[b-a for a,b in zip(times,times[1:])]
        return {**metrics(gaps),'min_ms':min(gaps) if gaps else None}
    return {'identity_count':len(frames),'matched_completed_frames':len(matched),
            'capture_definition':'Host RAW DMA completion; not exposure or optical latency',
            'matched_source_age':{stage:metrics([row[stage]['age_ms'] for row in matched]) for stage in stages},
            'all_event_source_age':{stage:metrics([row[stage]['age_ms'] for row in frames.values() if stage in row]) for stage in stages},
            'observed_event_intervals':{stage:intervals(stage) for stage in ('request','GUI_submit','RKNN_start')},
            'note':'Matched distributions use only frames with all stages present; sample boundaries can omit completed frames.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('log',type=Path);args=parser.parse_args()
    result=summarize(args.log.read_text(errors='replace'))
    output=json.dumps(result,indent=2)
    args.log.with_suffix('.age_summary.json').write_text(output,encoding='utf-8')
    print(output)
