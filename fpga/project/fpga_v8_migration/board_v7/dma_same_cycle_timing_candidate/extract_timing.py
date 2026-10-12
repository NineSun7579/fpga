"""Read-only extraction from existing exact09 report. Never starts PDS."""
from pathlib import Path
import re, json, hashlib
HERE=Path(__file__).resolve().parent
source=HERE.parent/'physical_subagent_evidence_01/fixed_06/physical_exact_09/final_export/report_timing/v7_sdt_top.rtr'
raw=source.read_bytes()
text=raw.decode('gbk',errors='replace').replace('\r','')
starts=list(re.finditer(r'^Startpoint\s*:\s*(.+)$',text,re.M))
paths=[]
for i,m in enumerate(starts):
    block=text[m.start():starts[i+1].start() if i+1<len(starts) else len(text)]
    endpoint=re.search(r'^Endpoint\s*:\s*(.+)$',block,re.M)
    slack=re.search(r'^\s*Slack\s*\([^)]*\)\s+(-?\d+\.\d+)',block,re.M)
    group=re.search(r'^Path Group\s*:\s*(.+)$',block,re.M)
    typ=re.search(r'^Path Type\s*:\s*(.+)$',block,re.M)
    if not all([endpoint,slack,group,typ]): continue
    start,end=m[1].strip(),endpoint[1].strip()
    if 'axi_dma_write/' not in start and 'axi_dma_write/' not in end: continue
    paths.append(dict(start=start,end=end,slack_ns=float(slack[1]),group=group[1].strip(),type=typ[1].strip(),block=block))
setup=[p for p in paths if p['type'].startswith('max')]
negative=[p for p in setup if p['slack_ns']<0]
lenwd=[p for p in setup if '/len[' in p['start'] and '/wd_cnt[' in p['end']]
worst=sorted(lenwd,key=lambda p:p['slack_ns'])[:5]
out=HERE/'evidence'
out.mkdir(exist_ok=True)
for i,p in enumerate(worst):
    (out/f'exact09_len_wdcnt_{i}.txt').write_text(p['block'],encoding='utf-8')
result=dict(source=str(source),source_sha256=hashlib.sha256(raw).hexdigest(),
            reported_dma_paths=len(paths),reported_dma_setup_paths=len(setup),negative_dma_setup_paths=len(negative),
            dma_setup_wns_ns=min(p['slack_ns'] for p in setup),
            reported_len_wdcnt_setup_paths=len(lenwd),worst_len_wdcnt=[{k:v for k,v in p.items() if k!='block'} for p in worst],
            limitations='Counts cover paths present in existing report; no new timing run or candidate slack measurement.')
(out/'exact09_timing_cones.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
