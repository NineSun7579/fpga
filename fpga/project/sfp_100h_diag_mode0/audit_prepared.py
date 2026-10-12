from pathlib import Path
import ast, hashlib, json, re
import build
H=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
# Freeze final local constraint/runner revisions before handing off; never touch originals.
manifest=json.loads((H/'input_sha256.json').read_text())
for n in ('source/constraints/clock.fdc','prepare.py','build.py','build.ps1','README.md','audit_prepared.py'):
    manifest[n]=sha(H/n)
(H/'input_sha256.json').write_text(json.dumps(manifest,indent=2))
for n in ('prepare.py','build.py','audit_prepared.py'): ast.parse((H/n).read_text())
pins=build.auditpins(H/'baseline/top_prr.prt')
for n in ('top.v','sfp/sfp_rx_link.v','preprocess/prep_regs.v','sfp/rx_symbol_candidate.sv','sfp/sfp_rx_diagnostics.sv'):
    assert sha(H/'source'/n)==sha(H/'sim/sfp_100h_candidate/candidate'/n),n
pds=(H/'work/project.pds').read_bytes()
refs=re.findall(rb'\(_file\s+"(\.\./source/[^"]+)"',pds)
names={}
for ref in refs:
    p=(H/'work'/ref.decode()).resolve()
    for x in re.findall(rb'^\s*module\s+(\w+)',p.read_bytes(),re.M):
        names.setdefault(x.decode(),[]).append(str(p))
for n in ('rx_symbol_candidate','sfp_rx_diagnostics'): assert len(names[n])==1,(n,names[n])
assert pds.count(b'_format systemverilog')==2
same=sha(H.parent/'project_build/place_route/top_timing_summary_after_hold_fix.txt')==sha(H/'baseline/top_timing_summary_after_hold_fix.txt')
assert same,'Retained route timing does not match 192245 final timing'
build.check()
proof={'status':'ready_for_sequential_launch_physical_validation_pending','mode':0,
       'pds_launched':False,'vendor_ip_edited':False,'hardlinked_inputs':False,
       'pin_baseline_audit':pins,'baseline_matches_192245_final_timing':same,
       'registered_new_modules_unique':True,'systemverilog_entries':2,
       'private_regression_bundle':json.loads((H/'sim/sfp_100h_candidate/validation.json').read_text()),
       'physical_constraints_vendor_validated':False,'original_hashes_checked':True}
(H/'readiness.json').write_text(json.dumps(proof,indent=2))
(H/'status.json').write_text(json.dumps({k:v for k,v in proof.items() if k!='private_regression_bundle'},indent=2))
print('PASS readiness: regression, hashes, pin baseline, source registration; NO PDS launch')
