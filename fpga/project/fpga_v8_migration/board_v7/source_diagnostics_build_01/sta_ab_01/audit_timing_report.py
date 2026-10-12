from pathlib import Path
import json,re,sys
HERE=Path(__file__).resolve().parent
def main():
    out=HERE/sys.argv[1];report=sys.argv[2] if len(sys.argv)>2 else 'v7_sdt_top.snr';text=(out/report).read_text(errors='replace')
    m=json.loads((HERE/'manifest.json').read_bytes())
    expected={(r['mapping']['launch_CLK'],r['mapping']['capture_D']) for r in m['resolved'] if r['mapping']['kind']=='register'}
    records=[]
    for block in re.split(r'(?=Startpoint\s*:)',text)[1:]:
        def field(pattern):
            match=re.search(pattern,block);return match.group(1).strip() if match else None
        start=field(r'^Startpoint\s*:\s*(.*?) \(')
        end=field(r'Endpoint\s*:\s*(.*?) \(')
        exception=field(r'Timing Exception\s*:\s*([^\n]+)')
        if not exception or 'MaxDelay Path' not in exception:continue
        required=field(r'Data required time\s+([-0-9.]+)')
        arrival=field(r'Data arrival time\s+([-0-9.]+)')
        slack=field(r'Slack \((?:MET|VIOLATED)\)\s+([-0-9.]+)')
        records.append({'start':start,'end':end,'path_type':field(r'Path Type\s*:\s*([^\n]+)'), 'exception':exception,'required':float(required) if required else None,'arrival':float(arrival) if arrival else None,'slack':float(slack) if slack else None,'tco_present':'tco' in block,'setup_present':'Setup time' in block})
    covered={(r['start'],r['end']) for r in records}
    missing=sorted(expected-covered);unexpected=sorted(covered-expected)
    result={'report':report,'expected_actual_pairs':len(expected),'maxdelay_records':len(records),'covered_actual_pairs':len(covered&expected),'missing':missing,'unexpected':unexpected,'records':records,'report_has_all_constraints_met':'All Constraints Met' in text,'limits':['Synthesis estimate only; routed timing and corner/reset/ordinary-path gates are separate.']}
    (out/'timing_audit.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('records','missing','unexpected')},indent=2))
    print('missing',len(missing),'unexpected',len(unexpected),'slack range', [min(r['slack'] for r in records),max(r['slack'] for r in records)] if records and all(r['slack'] is not None for r in records) else None)
if __name__=='__main__':main()
