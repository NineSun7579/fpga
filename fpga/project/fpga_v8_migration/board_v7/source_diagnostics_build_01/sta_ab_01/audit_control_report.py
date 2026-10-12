from pathlib import Path
import json,re,sys
HERE=Path(__file__).resolve().parent
def main():
    kind=sys.argv[1];out=HERE/sys.argv[2];text=(out/(kind+'.snr')).read_text(errors='replace')
    c=json.loads((HERE/'classification.json').read_bytes());records=[]
    for block in re.split(r'(?=Startpoint\s*:)',text)[1:]:
        def f(p):
            match=re.search(p,block);return match.group(1).strip() if match else None
        records.append({'start':f(r'^Startpoint\s*:\s*(.*?) \('),'end':f(r'Endpoint\s*:\s*(.*?) \('),'path_type':f(r'Path Type\s*:\s*([^\n]+)'), 'path_class':f(r'Path Class\s*:\s*([^\n]+)'), 'check':'recovery' if 'Recovery time' in block else 'removal' if 'Removal time' in block else 'setup' if 'Setup time' in block else 'hold' if 'Hold time' in block else 'unknown', 'exception':f(r'Timing Exception\s*:\s*([^\n]+)'), 'required':f(r'Data required time\s+([-0-9.]+)'), 'slack':f(r'Slack \((?:MET|VIOLATED)\)\s+([-0-9.]+)')})
    result={'kind':kind,'records':records,'limits':['Synthesis Slow estimate only; Fast and routed verification remain open. The synthesis API rejects explicit -delay_type, but its default query returns applicable max and min paths.']}
    if kind=='ordinary':
        expected={(r['launch_CLK'],r['capture_D']) for r in c['ordinary_pairs']};covered={(r['start'],r['end']) for r in records}
        result.update({'expected':len(expected),'covered':len(expected&covered),'missing':sorted(expected-covered),'unexpected':sorted(covered-expected)})
    if kind=='negedge':
        expected={r['cell']+'/CLK' for r in c['negedge']};covered={r['start'] for r in records}
        result.update({'expected_starts':len(expected),'covered_starts':len(expected&covered),'missing_starts':sorted(expected-covered)})
    (out/(kind+'_audit.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2));print('records',len(records),'exceptions',sum(bool(r['exception']) for r in records))
if __name__=='__main__':main()
