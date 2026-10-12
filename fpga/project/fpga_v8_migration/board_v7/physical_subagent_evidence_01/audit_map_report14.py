"""Require real mapped 1280-pair max-delay coverage and literal 15.238 budget."""
from pathlib import Path
import re,json,hashlib,sys
BASE=Path(__file__).resolve().parent/'fixed_06/map_audit14'
def main():
    directory=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else BASE
    if len(sys.argv)>1:
        identity=json.loads((directory/'launch.json').read_bytes())
        expected={tuple(p) for p in identity['expected_pairs']}
        reports=list(directory.rglob('*.rtr'))
    else:
        exact=json.loads((BASE/'actual/analysis/exact_complement.json').read_bytes())
        expected={tuple(p) for c in exact['cameras'] for p in c['bundle_pairs']}
        assert not exact['errors']
        reports=list((BASE/'timing').rglob('*.rtr'))
    assert len(expected)==1280 and len(reports)==1,(len(expected),reports)
    raw=reports[0].read_bytes()
    text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf8',errors='replace')
    rows=[]
    for block in re.split(r'(?=^\s*Startpoint\s*:)',text,flags=re.M)[1:]:
        def field(pattern):
            m=re.search(pattern,block,re.M|re.I);return m.group(1).strip() if m else None
        start=field(r'^\s*Startpoint\s*:\s*(.*?)\s+\(')
        end=field(r'^\s*Endpoint\s*:\s*(.*?)\s+\(')
        kind=field(r'^\s*Path Type\s*:\s*([^\n]+)')
        exception=field(r'^\s*Timing Exception\s*:\s*([^\n]+)')
        slack=field(r'Slack\s*\((?:MET|VIOLATED)\)\s+([-0-9.]+)')
        corner='Slow' if re.search(r'slow\s+corner',block,re.I) else 'Fast' if re.search(r'fast\s+corner',block,re.I) else None
        rows.append({'start':start,'end':end,'kind':kind,'exception':exception,'corner':corner,'slack':float(slack) if slack else None,'detail':block})
    details={}
    for corner in ['Slow','Fast']:
        subset=[r for r in rows if r['corner']==corner and r['exception'] and 'MaxDelay Path' in r['exception']]
        covered={(r['start'],r['end']) for r in subset}
        bad_budget=[r['exception'] for r in subset if not re.search(r'15\.238\s*ns',r['exception']) or '-datapath_only' not in r['exception']]
        details[corner]={'records':len(subset),'covered':len(expected&covered),'missing':sorted(expected-covered),'unexpected':sorted(covered-expected),'bad_budget':bad_budget,'worst_slack':min((r['slack'] for r in subset if r['slack'] is not None),default=None)}
    passed=all(d['covered']==1280 and not d['missing'] and not d['unexpected'] and not d['bad_budget'] and d['worst_slack'] is not None and d['worst_slack']>=0 for d in details.values())
    result={'report':str(reports[0]),'report_sha256':hashlib.sha256(raw).hexdigest(),'expected_pairs':1280,'corners':details,'passed':passed,'pnr_permitted':passed,'bit_permitted':False,'records':rows}
    (directory/'mailbox_coverage.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'passed':passed,'corners':{c:{k:v for k,v in d.items() if k not in ('missing','unexpected','bad_budget')} for c,d in details.items()}},indent=2))
    assert passed,'Actual mapped maxdelay coverage is incomplete; no PNR'
if __name__=='__main__':main()
