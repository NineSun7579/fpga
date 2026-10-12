from pathlib import Path
import re,json,collections
ROOT=Path(__file__).resolve().parent/'fixed_06/physical_exact_09'
report=ROOT/'routed_mailbox/report_timing/v7_sdt_top.rtr'
analysis=ROOT/'actual/analysis'
m=json.loads((analysis/'manifest.json').read_bytes())
expected=set((r['mapping']['launch_CLK'],r['mapping']['capture_D']) for r in m['resolved'] if r['mapping']['kind']=='register')
c=json.loads((analysis/'classification.json').read_bytes())
sync=set((r['launch_CLK'],r['capture_D']) for r in c['ordinary_pairs'])
resetcells=set(q.rsplit('/',1)[0] for r in c['reset'] for q in r['actual_Q'])
def canonical(pin):
    cell,port=pin.rsplit('/',1)
    if '/opit_' in cell:cell=cell.split('/opit_',1)[0]
    return cell+'/'+port
found=collections.defaultdict(dict);resets=collections.defaultdict(dict);counter=collections.Counter();block=[]
def process(lines):
    s=''.join(lines)
    def field(k):
        match=re.search(r'^'+re.escape(k)+r'\s*:\s*(.*)$',s,re.M);return match[1].strip() if match else ''
    a=field('Startpoint');b=field('Endpoint');typ=field('Path Type');corner='Slow' if 'slow' in typ else 'Fast' if 'fast' in typ else 'Unknown'
    match=re.search(r'Slack \((?:MET|VIOLATED)\)\s+([-\d.]+)',s)
    if not match:return
    slack=float(match[1]);pair=(canonical(a),canonical(b));counter[corner]+=1
    if pair in expected or pair in sync:
        group='mailbox' if pair in expected else 'sync_later'
        key=(group,corner); prior=found[key].get(pair)
        if prior is None or slack<prior['slack']:found[key][pair]={'start':a,'end':b,'slack':slack,'exception':field('Timing Exception'),'type':typ}
    cell=canonical(b).rsplit('/',1)[0]
    if cell in resetcells and canonical(b).rsplit('/',1)[1] in ('RS','P','C','R','S'):
        kind='Recovery' if 'Recovery' in s else 'Removal' if 'Removal' in s else 'Other'
        key=(corner,kind);prior=resets[key].get(cell)
        if prior is None or slack<prior['slack']:resets[key][cell]={'start':a,'end':b,'slack':slack,'type':typ}
with report.open(errors='replace') as f:
    for line in f:
        if line.startswith('Startpoint'):
            if block:process(block)
            block=[line]
        elif block:block.append(line)
    if block:process(block)
result={'source_report':str(report),'streamed_paths':dict(counter),'coverage':{},'reset':{}}
for group,exp in [('mailbox',expected),('sync_later',sync)]:
    for corner in ['Slow','Fast']:
        rows=found[group,corner];covered=set(rows);result['coverage'][group+'_'+corner]={'expected':len(exp),'covered':len(covered),'missing':sorted(exp-covered),'worst_slack':min((v['slack'] for v in rows.values()),default=None),'records':list(rows.values())}
for (corner,kind),rows in resets.items():result['reset'][corner+'_'+kind]={'covered':len(rows),'expected_cells':len(resetcells),'missing_cells':sorted(resetcells-set(rows)),'worst_slack':min((v['slack'] for v in rows.values()),default=None),'records':list(rows.values())}
(ROOT/'evidence/streamed_routed_coverage.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'coverage':{k:{a:b for a,b in v.items() if a!='records' and not a.startswith('missing')} for k,v in result['coverage'].items()},'reset':{k:{a:b for a,b in v.items() if a!='records' and not a.startswith('missing')} for k,v in result['reset'].items()}},indent=2))
