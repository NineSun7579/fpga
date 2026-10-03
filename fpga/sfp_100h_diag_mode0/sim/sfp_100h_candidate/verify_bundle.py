from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parent
for row in json.loads((R/'manifest.json').read_text()).values():
    assert hashlib.sha256(Path(row['source']).read_bytes()).hexdigest()==row['sha256'],row['source']
checks={'e2e.log':'PASS E2E','old_default.log':'PASS OLD',
 'tb_sfp_diag.log':'SFP_DIAG_PASS','tb_cdc_host_map.log':'PASS HOST MAP',
 'tb_diagnostics.log':'PASS DIAGNOSTICS'}
for file,marker in checks.items():
    t=(R/file).read_text();assert marker in t and '** Fatal:' not in t,file
assert json.loads((R/'top_audit.json').read_text())['new_errors']==0
boundary=json.loads((R.parent/'sfp_payload_probe/boundary_summary.json').read_text())
assert len(boundary)==36 and all(row['exact'] and row['sof']==1 and row['overflow']==0 for row in boundary)
result=dict(production_and_vendor_ip_unchanged=True,pds_launched=False,
 end_to_end_exact_full_frames=5,cam_pixels_each=307200,old_default_exact_baseline=True,
 bc50_payload_deletion_detected=True,boundary_cases=36,
 abi_and_host_route_tests=True,diagnostics_cdc_tests=True,full_top_compile=False,
 baseline_top_diagnostics=174,new_top_diagnostics=0,synthesis_timing_verified=False,
 candidate_hashes={p.relative_to(R/'candidate').as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
  for p in (R/'candidate').rglob('*') if p.is_file()})
(R/'validation.json').write_text(json.dumps(result,indent=2))
print('PASS bundle audit: tests, hashes and explicit build/physical limitations recorded')
