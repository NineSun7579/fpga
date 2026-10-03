"""Attribute injected loss to source A/B words using actual TX word positions."""
from pathlib import Path
import json
R=Path(__file__).resolve().parent
words=[tuple(int(t,16) for t in l.split()) for l in (R/'actual.vec').read_text().splitlines()]
golden=[int(l,16) for l in (R/'input.hex').read_text().splitlines()]
summary=json.loads((R/'summary.json').read_text())
summary['attribution']=[]
for row in summary['results']:
    n=row['pixels']; q,r=divmod(n,1280)
    row['splitter_count5']=q*640+min(r,640)
    row['splitter_count6']=q*640+max(r-640,0)
payload=0;before_b=[];bc50=[]
for i,(d,k) in enumerate(words):
    if k==0:
        if payload%1280==640 and payload//1280%4==0:before_b.extend([payload,payload+1])
        if i and words[i-1][1]==9 and d&255==0x50:bc50.extend([payload,payload+1])
        payload+=2
for name,missing in [('delete_BC28_before_B',before_b),('delete_BC50_matches',bc50)]:
    observed=[int(l,16) for l in (R/(name+'.pixels')).read_text().splitlines()]
    mask=set(missing)
    result=dict(case=name,missing_A=sum(i%1280<640 for i in missing),missing_B=sum(i%1280>=640 for i in missing),
                exact_survivors=observed==[p for i,p in enumerate(golden) if i not in mask])
    summary.setdefault('attribution',[]).append(result)
    print(result)
(R/'summary.json').write_text(json.dumps(summary,indent=2))
