from pathlib import Path
import re,csv,hashlib,difflib
here=Path(__file__).resolve().parent
rows=[]
for mode in ('baseline','candidate','long_baseline','long_candidate'):
 text=(here/mode/'simulation.log').read_text(errors='replace')
 count=3 if mode.startswith('long_') else 29
 assert f'CANDIDATE_DONE cases={count} errors=0' in text and 'FAIL' not in text
 if mode.startswith('long_'):
  print(mode,*[l for l in text.splitlines() if 'LONG_LEVEL' in l],sep='\n')
 for line in text.splitlines():
  if 'RESULT ' in line:
   rows.append(dict(mode=mode,**dict(re.findall(r'(\w+)=([^\s]+)',line))))
with (here/'results.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for mode in ('baseline','candidate'):
 selected=[r for r in rows if r['mode']==mode]
 narrow=[r for r in selected if r['pulse']=='1']
 print(mode,'cases',len(selected),'narrow published',sum(int(r['publish']) for r in narrow),'/',len(narrow))
 for r in selected:
  if r['case'] in ('1','4'):print(mode,r['case'],{k:r[k] for k in ('source','drop','accepted','publish','short','window','ddrwin')})
assert 'CONTRACT_DONE errors=0' in (here/'contract/simulation.log').read_text(errors='replace')
assert 'CANDIDATE_DONE cases=2 errors=0' in (here/'extra/simulation.log').read_text(errors='replace')
original=here.parents[1]/'whole_candidate_v7_route_01/rtl/ov5640_cdc_tc04.v'
(here/'candidate.diff').write_text(''.join(difflib.unified_diff(
 original.read_text().splitlines(True),(here/'cdc_order_candidate.v').read_text().splitlines(True),
 fromfile='frozen/ov5640_cdc_tc04.v',tofile='candidate/cdc_order_candidate.v')))
files=[*here.glob('*.v'),*here.glob('*.vh'),*here.glob('*.sv'),*here.glob('*.py')]
(here/'candidate_hashes.txt').write_text('\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}' for p in sorted(files))+'\n')
