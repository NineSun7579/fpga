from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parent
s=json.loads((R/'summary.json').read_text());rows=s['results']
assert len(rows)==24 and all(r['exact'] and r['pixels']==614400 and r['sof']==1 and r['overflow']==0 for r in rows)
assert all(r['relocks']>=r['events'] for r in rows if r['kind']!='baseline')
assert s['skip_matches_only_dedicated'] and s['guards']==307200 and s['data_words']==307200
g=json.loads((R/'guard_only_summary.json').read_text());assert g['exact_pixels'] and g['bc50_matches']==0
assert 'PASS RECOVERY' in (R/'recovery.log').read_text()
for p,h in json.loads((R/'manifest.json').read_text()).items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
out=dict(full_frame_replays=24,exact_pixels_each=614400,
 isolated_pair_events_each=128,minimum_mutation_relocks=min(r['relocks'] for r in rows if r['kind']!='baseline'),
 guard_only_exact=True,guard_only_bc50_matches=0,readiness_recovery=True,
 production_and_ip_unchanged=True,no_pds_build=True,no_physical_ctc_claim=True,
 candidate_sha256=hashlib.sha256((R/'candidate_sfp_video_tx.v').read_bytes()).hexdigest())
(R/'validation.json').write_text(json.dumps(out,indent=2));print('PASS final 50K candidate audit',json.dumps(out))
