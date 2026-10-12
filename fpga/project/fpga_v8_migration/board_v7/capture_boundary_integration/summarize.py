from pathlib import Path
import csv,re,collections
here=Path(__file__).resolve().parent
text=(here/'modelsim/simulation.log').read_text(errors='replace')
rows=[dict(re.findall(r'(\w+)=(-?[\d.]+)',s)) for s in text.splitlines() if 'RESULT ' in s]
with (here/'results.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
lines=[f'Cases: {len(rows)}',f'Normal cases: {sum(r["normal"]=="1" for r in rows)}',
       f'Short cases: {sum(int(r["short"])>0 for r in rows)}',
       'Trailing blank sweep, 32x4 / cp=12ns / hb=64 / head=32 / pulse=16:',
       'video period | tested tail range | smallest tail where all sampled phases publish']
for vp in sorted(set(r['vp'] for r in rows),key=float):
 a=[r for r in rows if r['vp']==vp and r['w']=='32' and r['head']=='32' and int(r['tail'])<=40]
 if not a: continue
 good=[b for b in sorted(set(int(r['tail']) for r in a)) if all(r['publish']=='1' for r in a if int(r['tail'])==b)]
 lines.append(f'{vp} | {min(int(r["tail"]) for r in a)}..{max(int(r["tail"]) for r in a)} | {min(good) if good else "none"}')
lines += ['Startup sweep (vp, received_initial_marker, accepted, short):']
lines += [str(x) for x in collections.Counter((r['vp'],r.get('sof_count','?'),r['accepted'],r['short']) for r in rows if r['pulse']=='1').items()]
lines += ['Full-size results:']
lines += [' '.join(f'{k}={v}' for k,v in r.items()) for r in rows if r['w']=='640']
(here/'summary.txt').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
