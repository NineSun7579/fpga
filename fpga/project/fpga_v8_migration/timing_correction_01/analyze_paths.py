"""Extract exact v2 path evidence and installed vendor documentation, no PDS."""
from pathlib import Path
from collections import Counter, defaultdict
import csv, difflib, hashlib, json, re
import xml.etree.ElementTree as ET
import pymupdf

HERE=Path(__file__).resolve().parent
V2=HERE.parent/'whole_candidate_v2_route_01'
E=HERE/'evidence'
E.mkdir(exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x): (E/n).write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
source=V2/'evidence/all_reported_failing_paths.json'
paths=json.loads(source.read_bytes())
rows=[]
for p in paths:
    detail=p['full_detail']
    kind='removal' if 'Removal time' in detail else 'setup' if p['Path Type'].startswith('max') else 'hold'
    corner='slow' if 'slow' in p['Path Type'] else 'fast'
    clocks=re.findall(r'Clock (\S+) \((?:rising|falling) edge\)',detail)
    assert len(clocks)==2,(p['number'],clocks)
    skew=float(re.search(r'Clock Skew\s*:\s*([-\d.]+)',detail)[1])
    r={'number':p['number'],'check':kind,'corner':corner,'group':p['Path Group'],
       'launch_clock':clocks[0],'capture_clock':clocks[1],
       'slack_ns':p['Slack'],'clock_skew_ns':skew,
       'startpoint':p['Startpoint'],'endpoint':p['Endpoint']}
    route=re.search(r'Logic: ([\d.]+)ns\(([\d.]+)%\), Route: ([\d.]+)ns\(([\d.]+)%\)',detail)
    if route:
        r.update(logic_ns=float(route[1]),route_ns=float(route[3]),route_percent=float(route[4]))
    rows.append(r)
with (E/'all_611_classified.csv').open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
    writer.writeheader(); writer.writerows(rows)
groups=defaultdict(list)
for r in rows: groups[(r['corner'],r['check'],r['launch_clock'],r['capture_clock'])].append(r)
summary=[]
for k,rs in groups.items():
    worst=min(rs,key=lambda r:r['slack_ns'])
    summary.append({'corner':k[0],'check':k[1],'launch':k[2],'capture':k[3],
        'count':len(rs),'worst_ns':worst['slack_ns'],
        'worst_startpoint':worst['startpoint'],'worst_endpoint':worst['endpoint'],
        'min_clock_skew_ns':min(r['clock_skew_ns'] for r in rs),
        'max_clock_skew_ns':max(r['clock_skew_ns'] for r in rs)})
assert len(rows)==611
assert Counter((r['corner'],r['check']) for r in rows)=={
    ('slow','setup'):39,('slow','hold'):336,('slow','removal'):11,('fast','hold'):225}
save('path_cluster_summary.json',summary)
setup=[r for r in rows if r['check']=='setup']
save('exact_setup_paths.json',setup)
representatives={}
for label,predicate in [('address_decode',lambda r:r['check']=='setup' and '/ov5640_reg/' in r['endpoint']),
    ('motion_reduce',lambda r:r['check']=='setup' and '/u_detector/' in r['endpoint']),
    ('core_hold',lambda r:r['check']=='hold' and r['group']=='ddrphy_sysclk'),
    ('pcie_hold',lambda r:r['check']=='hold' and r['group']=='pclk_div2'),
    ('camera_removal',lambda r:r['check']=='removal' and 'cam3' in r['endpoint'])]:
    subset=[r for r in rows if predicate(r)]
    worst=min(subset,key=lambda r:r['slack_ns'])
    original=next(p for p in paths if p['number']==worst['number'])
    (E/(label+'.txt')).write_text(original['full_detail'],encoding='utf-8')
    representatives[label]={'count':len(subset),**worst}
save('representatives.json',representatives)
save('cross_clock_failures.json',[r for r in rows if r['launch_clock']!=r['capture_clock']])

# Datapath nets only, excluding clocks. Report counts are occurrence counts,
# not design-wide fanout or all-positive-path statistics.
hot=[]
for p in paths:
    d=p['full_detail']
    # Strip first and second clock trees at the launch FF tco and arrival line.
    m=re.search(r'\n[^\n]*\btco\s+[^\n]*\n',d)
    if not m: continue
    data=d[m.end():d.find('Data arrival time')]
    for fan,incr,name in re.findall(r'net \(fanout=(\d+)\)\s+([\d.]+)\s+[\d.]+\s+([^\r\n]+)',data):
        hot.append({'number':p['number'],'fanout':int(fan),'delay_ns':float(incr),'net':name.strip()})
save('datapath_hot_nets.json',sorted(hot,key=lambda r:(r['delay_ns'],r['fanout']),reverse=True)[:80])
route_summary=V2/'evidence/route_summary.json'
rt=json.loads(route_summary.read_bytes())['stage_reports']['place_route']['tables']['pnr_resource_utilization']
selected=[]
def walk_resource(rs,parent=''):
    for r in rs:
        name=r['data'][0]
        hierarchy=parent+'/'+name if parent else name
        if any(n in name.lower() for n in ('motion','ov5640_reg','ovreg_axil','cooperative','output_packer','h2f')):
            selected.append({'hierarchy':hierarchy,'values':dict(zip(rt['headers'],r['data']))})
        walk_resource(r.get('children',[]),hierarchy)
walk_resource(rt['rows'])
save('v2_relevant_mapped_resources.json',{'source':str(route_summary),'sha256':sha(route_summary),'rows':selected})

baseline=HERE.parent.parent/'motion_100h/run_20261003_212303/final_sta_proof.json'
b=json.loads(baseline.read_bytes())
baseline_report=baseline.parent/'final_sta/report_timing/top.rtr'
assert sha(baseline_report)==b['report_sha256']
assert b'Design Summary : All Constraints Met.' in baseline_report.read_bytes()
save('baseline_final_sta_comparison.json',{'source':str(baseline),'source_sha256':sha(baseline),
    'actual_final_report':str(baseline_report),'actual_report_sha256_verified':True,
    'baseline_route_sha256':b['route_sha256'],'baseline_report_sha256':b['report_sha256'],
    'baseline_negative_rows':[r for r in b['rows'] if r['slack']<0],
    'baseline_all_clock_rows':b['rows'],
    'v2_failing_clock_rows':summary,
    'interpretation':'These RTL subsystems existed in baseline; the final frozen baseline has no negative rows. Failures are not proven pre-existing baseline violations.'})
v2_final_report=V2/'final_export/report_timing/fpga_v8_cooperative_top_v2.rtr'
actual=v2_final_report.read_bytes().decode('ascii',errors='replace')
start=actual.index('Clock Groups:')
end=actual.index('Performance Summary:',start)
(E/'effective_v2_clock_groups.txt').write_text(actual[start:end],encoding='ascii')
tables=V2/'evidence/final_sta_tables.json'
ft=json.loads(tables.read_bytes())
save('effective_v2_clock_evidence.json',{'source_report':str(v2_final_report),'sha256':sha(v2_final_report),
    'clock_summary':ft['report_timing_clock_summary'],
    'clock_interaction':ft['report_clock_interaction'],
    'check_timing':ft['check_timing_summary']})

doc=Path(r'C:\pango\PDS_2022.2-SP6.4\doc\Pango_Design_Suite_User_Guide.pdf')
d=pymupdf.open(doc)
pages=[110,111,112,118,184,252,253]
text='\n\n'.join(f'PDF PAGE {n}\n'+d[n-1].get_text() for n in pages)
(E/'vendor_route_and_clock_docs.txt').write_text(text,encoding='utf-8')
save('vendor_doc_identity.json',{'source':str(doc),'sha256':sha(doc),'pdf_pages':pages})

# Keep exact v2 flow settings as evidence, rather than assuming defaults.
prr=V2/'place_route/prr.db'
settings=None
for event,elem in ET.iterparse(prr,events=['end']):
    if elem.tag=='general_container' and elem.attrib.get('id')=='pnr_settings':
        settings=ET.tostring(elem,encoding='unicode')
        break
assert settings, 'Missing exact v2 PRR settings'
(E/'v2_route_settings.txt').write_text(re.sub(r'<[^>]+>',' ',settings),encoding='utf-8')

fdcs=list((V2/'inputs/source/constraints').glob('*.fdc'))
protected=[source,baseline,prr,*fdcs]
for old,new in [('motion/block_motion_detector.v','block_motion_detector_tc01.v'),
                ('ov5640/ovreg_axil_decode.v','ovreg_axil_decode_tc01.v')]:
    original=V2/'inputs/source'/old
    candidate=HERE/'rtl'/new
    protected.append(original)
    diff=''.join(difflib.unified_diff(original.read_bytes().decode('ascii',errors='replace').splitlines(True),
        candidate.read_text().splitlines(True),fromfile=str(original),tofile=str(candidate)))
    (E/(new+'.diff')).write_text(diff,encoding='utf-8')
save('source_hashes.json',{str(p):sha(p) for p in protected+list((HERE/'rtl').glob('*.v'))})
print(json.dumps({'total':len(rows),'counts':{str(k):v for k,v in Counter((r['corner'],r['check']) for r in rows).items()},
    'cross_clock':len([r for r in rows if r['launch_clock']!=r['capture_clock']]),
    'setup_clusters':{n:r['count'] for n,r in representatives.items()},
    'baseline_negative_rows':len([r for r in b['rows'] if r['slack']<0])},indent=2))
