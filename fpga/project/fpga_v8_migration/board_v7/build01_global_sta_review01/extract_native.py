"""Read-only build01 native report extraction; writes only this review directory."""
from pathlib import Path
import importlib.util
import json
import hashlib
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / 'source_diagnostics_timing_build_01'
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''): h.update(b)
    return h.hexdigest()
def write(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

receipt = json.loads((BUILD / 'evidence/pnr_artifact.json').read_bytes())
route = Path(receipt['path'])
assert sha(route) == receipt['sha256'], 'Actual route hash mismatch'
spec = importlib.util.spec_from_file_location('original_summary', HERE.parent.parent / 'whole_candidate_v2_route_01/summarize_route.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)
summary.EVIDENCE = HERE / 'native_tables'
summary.EVIDENCE.mkdir(exist_ok=True)
db = BUILD / 'place_route/prr.db'
before = sha(db)
tables = summary.extract(db, 'pnr')
write('native_tables.json', tables)
write('provenance.json', {'boundary':'PNR embedded STA, not independent final STA', 'route':receipt,
    'native_report':{'path':str(db),'sha256':before},
    'input_hashes':json.loads((BUILD/'evidence/input_hashes.json').read_bytes()),
    'route_unchanged':sha(route)==receipt['sha256'], 'report_unchanged':sha(db)==before})
textfile = BUILD / 'place_route/v7_sdt_top_timing_summary_after_hold_fix.txt'
text = textfile.read_text(encoding='ascii')
groups = []
for match in re.finditer(r'^(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):\s*\n(.*?)(?=^=+)', text, re.M|re.S):
    kind, corner, body = match.groups()
    rows = []
    for line in body.splitlines():
        m = re.match(r'^\s*(\S+)\s+(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$', line)
        if m:
            a,b,w,t,n,total = m.groups()
            rows.append({'launch_clock':a,'capture_clock':b,'same_clock':a==b,'worst_slack_ns':float(w),'total_negative_slack_ns':float(t),'failing_endpoints':int(n),'total_endpoints':int(total)})
    groups.append({'check':kind,'corner':corner,'rows':rows,'worst_slack_ns':min((r['worst_slack_ns'] for r in rows),default=None),'failing_endpoints':sum(r['failing_endpoints'] for r in rows),'coverage':'no rows in native report' if not rows else 'native PNR summary rows'})
assert len(groups)==10
write('global10summary.json', {'boundary':'PNR embedded after hold fix; not independent final STA','source':str(textfile),'sha256':sha(textfile),'prr_db_contains_sta_tables':False,'groups':groups,'negative_clock_groups':[dict(check=g['check'],corner=g['corner'],**r) for g in groups for r in g['rows'] if r['worst_slack_ns']<0], 'negative_endpoint_names_available':False})
print(json.dumps(groups, indent=2))
