"""MPW uses scored table rows, not Startpoint/Slack records in this PDS version."""
import re
from preflight import HERE,load,sha,require
from physical_flow import record

def main(label='reset_clock_mpw'):
    out=HERE/'route_attempt_03/evidence'
    proof=load(out/'coverageproof_physical_receivers.json')
    targets={r['physical'].rsplit('/',1)[0]+'/CLK':r for r in proof['reset_bindings']}
    report=out/label/'report_timing/v7_sdt_top.rtr'
    corner=None;clock=None;rows=[]
    with report.open(encoding='gb18030',errors='strict') as stream:
        for number,line in enumerate(stream,1):
            m=re.fullmatch(r'\s*(Slow|Fast) Corner\s*',line)
            if m:corner=m[1];clock=None
            m=re.match(r'^\s*\{([^}]+)\} Minimum Pulse Width\s*:',line)
            if m:clock=m[1]
            m=re.match(r'^\s*(-?\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(High|Low) Pulse Width\s+(\S+)\s+(\S+)\s*$',line)
            if m and m[6] in targets:
                require(corner and clock,'MPW row lacks explicit corner/clock section')
                rows.append({'corner':corner,'clock':clock,'slack':float(m[1]),'actual_width':float(m[2]),
                    'require_width':float(m[3]),'check':m[4]+' Pulse Width','location':m[5],'physical':m[6],'line':number})
    details={}
    for c in ['Slow','Fast']:
        for kind in ['High Pulse Width','Low Pulse Width']:
            selected=[r for r in rows if r['corner']==c and r['check']==kind]
            covered={r['physical'] for r in selected}
            logical={m['logical'] for pin in covered for m in targets[pin]['logical_mappings']}
            details[c+'_'+kind]={'physical_covered':len(covered),'logical_mapped':len(logical),
                'missing':sorted(set(targets)-covered),'worst_slack':min((r['slack'] for r in selected),default=None)}
    passed=all(not d['missing'] and d['logical_mapped']==32 and d['worst_slack'] is not None and d['worst_slack']>=0 for d in details.values())
    import physical_flow as flow
    flow.EVIDENCE=out
    record('evidence/reset_mpw_routed_audit.json',{'passed':passed,'details':details,'records':rows,
        'report_sha256':sha(report),'route_sha256':proof['route_sha256'],
        'method':'Actual MPW table rows with explicit corner sections and exactly bound physical clocks',
        'global_MPW_table_not_filtered_by_to':True,'physical_clocks':len(targets),'logical_reset_stages':32,
        'independent_internal_stage_checks_claimed':False})
    require(passed,'Actual physical reset-clock MPW row coverage/slack incomplete')
    print('ACTUAL PHYSICAL MPW HIGH/LOW BOTH CORNERS PASS',details)

if __name__=='__main__':main()
