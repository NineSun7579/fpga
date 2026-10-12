"""Recover completed final STA offline, retaining unconstrained unscored paths."""
from pathlib import Path
import hashlib, json, re
HERE=Path(__file__).resolve().parent
def write(n,v): (HERE/n).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=HERE/'final_sta/report_timing/v7_sdt_top.rtr'
receipt=json.loads((HERE/'final_sta_receipt.json').read_bytes())
assert receipt['exit_code']==0 and not receipt['errors'] and receipt['route_unchanged'] and receipt['all_original_inputs_verified']
text=report.read_text(encoding='gb18030',errors='replace')
groups=[]
for match in re.finditer(r'^(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):\s*\n(.*?)(?=^=+)',text,re.M|re.S):
    kind,corner,body=match.groups();rows=[]
    for line in body.splitlines():
        fields=line.split();count=5 if kind=='Minimum Pulse Width' else 6
        if len(fields)!=count:continue
        try:w,t,n,total=float(fields[-4]),float(fields[-3]),int(fields[-2]),int(fields[-1])
        except ValueError:continue
        rows.append({'launch_clock':fields[0],'capture_clock':fields[0] if count==5 else fields[1],'worst_slack_ns':w,'total_negative_slack_ns':t,'failing_endpoints':n,'total_endpoints':total})
    assert rows,'Empty final group: '+kind+corner
    groups.append({'check':kind,'corner':corner,'rows':rows,'worst_slack_ns':min(r['worst_slack_ns'] for r in rows),'failing_endpoints':sum(r['failing_endpoints'] for r in rows),'exact_text':body})
assert len(groups)==10
records=[]
for block in re.split(r'(?=^Startpoint\s*:)',text,flags=re.M)[1:]:
    def field(n):
        m=re.search(r'^'+n+r'\s*:\s*(.*)',block,re.M);return m[1].strip() if m else None
    clocks=re.findall(r'^\s*Clock\s+(\S+)\s+\(',block,re.M)
    slack=re.search(r'\bSlack\s*\((MET|VIOLATED)\)\s+(-?\d+(?:\.\d+)?)',block)
    kind=field('Path Type');corner=re.search(r'(slow|fast) corner',kind or '',re.I)
    row={'start':field('Startpoint'),'end':field('Endpoint'),'path_group':field('Path Group'),'kind':kind,'path_class':field('Path Class'),'corner':corner[1].capitalize() if corner else None,'clocks':clocks,'same_clock':len(clocks)>=2 and len(set(clocks))==1,'slack':float(slack[2]) if slack else None,'status':slack[1] if slack else 'UNSCORED'}
    assert row['start'] and row['end'] and row['corner']
    if not slack:assert 'Data arrival time' in block,'Incomplete unscored path'
    records.append(row)
negative=[r for r in records if r['slack'] is not None and r['slack']<0]
assert len(negative)==sum(g['failing_endpoints'] for g in groups),'Negative endpoint coverage mismatch'
route=json.loads((HERE/'provenance.json').read_bytes())['route']
assert sha(Path(route['path']))==route['sha256']
write('final_global10summary.json',{'boundary':'independent final STA on actual build01 route','groups':groups,'route':route,'source':str(report),'sha256':sha(report)})
write('final_negative_paths.json',{'source':str(report),'sha256':sha(report),'records':negative,'record_count':len(records),'unscored_record_count':sum(r['slack'] is None for r in records),'at_max_path_limit':len(records)>=200000,'negative_endpoint_coverage_complete':True,'route':route})
write('final_unscored_paths.json',[r for r in records if r['slack'] is None])
write('queue_status.json',{'phase':'FINAL_STA_EXPORTED','holds_pds_slot':False,'negative_records':len(negative),'offline_parser_recovered':True,'tool_rerun':False})
print(json.dumps({'groups':[(g['check'],g['corner'],g['worst_slack_ns'],g['failing_endpoints']) for g in groups],'negative':negative,'unscored':sum(r['slack'] is None for r in records)},indent=2))
