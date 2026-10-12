from prepare_route import *
def records(path):
    text=path.read_text(errors='replace');items=[]
    for block in re.split(r'(?=Startpoint\s*:)',text)[1:]:
        def field(pattern):
            m=re.search(pattern,block,re.M);return m.group(1).strip() if m else None
        start=field(r'^Startpoint\s*:\s*(.*?) \(');end=field(r'^Endpoint\s*:\s*(.*?) \(')
        kind=field(r'^Path Type\s*:\s*([^\n]+)');exc=field(r'^Timing Exception\s*:\s*([^\n]+)')
        corner='Slow' if 'Slow' in block else 'Fast' if 'Fast' in block else None
        slack=field(r'Slack \((?:MET|VIOLATED)\)\s+([-0-9.]+)')
        items.append({'start':start,'end':end,'kind':kind,'corner':corner,'exception':exc,'slack':float(slack) if slack else None,'detail':block})
    return items

def main():
    target=json.loads((HERE/'routed_mailbox/targets.json').read_bytes());expected={tuple(x) for x in target['pairs']}
    rows=records(HERE/'routed_mailbox/report_timing/v7_sdt_top.rtr')
    bundle=[x for x in rows if x['exception'] and 'MaxDelay Path' in x['exception']]
    corners={}
    for corner in ['Slow','Fast']:
        subset=[x for x in bundle if x['corner']==corner];covered={(x['start'],x['end']) for x in subset}
        corners[corner]={'records':len(subset),'covered':len(expected&covered),'missing':sorted(expected-covered),'unexpected':sorted(covered-expected),'worst_slack':min((x['slack'] for x in subset if x['slack'] is not None),default=None)}
    save('evidence/mailbox_routed_audit.json',{'expected_pairs':1280,'corners':corners,'records':bundle})
    resets=json.loads((HERE/'routed_reset/targets.json').read_bytes())['ends']
    reset_rows=records(HERE/'routed_reset/report_timing/v7_sdt_top.rtr')
    coverage={}
    for corner in ['Slow','Fast']:
        for kind in ['Recovery','Removal']:
            subset=[x for x in reset_rows if x['corner']==corner and x['kind'] and kind.lower() in x['kind'].lower()]
            covered={x['end'] for x in subset}
            coverage[corner+'_'+kind]={'covered_targets':sorted(covered&set(resets)),'missing_targets':sorted(set(resets)-covered),'reported_records':len(subset)}
    save('evidence/reset_routed_audit.json',{'targets':resets,'coverage':coverage,'records':reset_rows,'empty_reports_are_not_pass':True})
    assert all(x['covered']==1280 and not x['unexpected'] and x['worst_slack'] is not None and x['worst_slack']>=0 for x in corners.values()),'Mailbox two-corner routed coverage gate open'
    assert all(not x['missing_targets'] for x in coverage.values()),'Reset recovery/removal coverage gate open; no new false paths permitted'
if __name__=='__main__':main()
