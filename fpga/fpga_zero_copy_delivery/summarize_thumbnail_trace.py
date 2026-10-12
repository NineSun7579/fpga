"""Aggregate diagnostic counters; stage and transport times overlap by design."""
from pathlib import Path
import json
import re
import sys

folder=Path(sys.argv[1])
groups={}
for log in sorted(folder.glob('[0-9]*[AB].log')):
    for line in log.read_text(errors='replace').splitlines():
        marker=re.match(r'\[(dma-lock|thumbnail-stage)\] ',line)
        if not marker: continue
        fields=dict(re.findall(r'(\w+)=([^ ]+)',line))
        key=(log.stem,fields['camera'],fields['path'],marker[1],fields.get('lock_domain','dma'))
        group=groups.setdefault(key,{})
        for field,text in fields.items():
            if field in ('camera','path','t_ns','window_ns','lock_domain'): continue
            value=int(text)
            group[field]=max(group.get(field,0),value) if field.endswith('_max_ns') else group.get(field,0)+value
rows=[]
for (arm,camera,path,kind,lock_domain),values in sorted(groups.items()):
    means={}
    for field,total in values.items():
        if field.endswith('_sum_ns'):
            phase=field[:-7]
            count=values.get(phase+'_count',0)
            means[phase+'_mean_ms']=total/count/1e6 if count else None
    rows.append(dict(arm=arm,camera_index=int(camera),physical_camera=int(camera)+1,path=path,kind=kind,lock_domain=lock_domain,totals=values,means=means))
if not rows: raise RuntimeError('No stage trace evidence found')
report=dict(rows=rows,limits='Diagnostic run, not formal performance A/B. Stage and ioctl timings overlap; never sum across categories. Means are per reported operation/segment, not always per frame. Final incomplete windows may be omitted.')
(folder/'trace_summary.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
