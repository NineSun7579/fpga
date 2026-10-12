"""Summarize submitted-frame wall phases; includes scheduler/transport waits."""
import argparse,json,re,math
from pathlib import Path

def summarize(text):
    stages=('arm','claim','hold_command','hold_validated','release','publish','request')
    rows=[];identities=set()
    for line in text.splitlines():
        if not line.startswith('[fpga-prefetch-timing] '):continue
        fields={key:int(value) for key,value in re.findall(r'(\w+)=(-?\d+)',line)}
        identity=tuple(fields[key] for key in ('generation','camera','frame','tag'))
        if identity in identities:raise ValueError('Duplicate submitted identity')
        identities.add(identity)
        values=[fields[key] for key in stages]
        if fields.get('ordered')!=1 or any(value<=0 for value in values) or values!=sorted(values):
            raise ValueError('Invalid monotonic phase ordering')
        rows.append(fields)
    def metric(values):
        values=sorted(values);n=len(values)
        return {'count':n,'mean_ms':sum(values)/n if n else None,
                'p50_ms':values[math.ceil(n*.5)-1] if n else None,
                'p95_ms':values[math.ceil(n*.95)-1] if n else None,
                'max_ms':max(values) if n else None}
    pairs=list(zip(stages,stages[1:]))+[('arm','publish'),('arm','request'),('hold_command','release')]
    return {'submitted_frames':len(rows),'phases':{a+'_to_'+b:metric([row[b]-row[a] for row in rows]) for a,b in pairs},
            'limits':'Only completed submitted frames; cancelled captures excluded. Millisecond wall intervals include CPU scheduling and DMA admission waits; not hardware cycle durations.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('log',type=Path);args=parser.parse_args()
    output=json.dumps(summarize(args.log.read_text(errors='replace')),indent=2)
    args.log.with_suffix('.prefetch_summary.json').write_text(output,encoding='utf-8');print(output)
