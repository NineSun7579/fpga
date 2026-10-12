"""Verify the completed delivery; reseal only the documented X-location report edit."""
from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def main():
    prior=json.loads((P/'hashlog.json').read_text(encoding='utf8'))
    documented={'REPORT_ZH.md','seal_delivery.py'}
    changed=[]
    for rel,expected in prior.items():
        actual=sha(P/rel)
        if actual!=expected:
            assert rel in documented,('unexplained delivery drift',rel)
            changed.append(dict(path=rel,before=expected,after=actual))
    contract=json.loads((P/'replacement_contract.json').read_text(encoding='utf8'))
    for variant in ['golden','candidate']:
        assert len(contract[variant])==243
        for row in contract[variant]:
            assert sha(row['source'])==row['sha256']
            assert sha(row['golden_source'])==row['golden_sha256']
    exported=json.loads((P/'src/sourcehash.json').read_text(encoding='utf8'))
    assert len(exported)==2
    for rel,expected in exported.items():assert sha(P/rel)==expected
    results=json.loads((P/'results.json').read_text(encoding='utf8'))
    audit=json.loads((P/'audit.json').read_text(encoding='utf8'))
    assert results['functional_pass'] and not results['pass'] and not results['freeze_pass']
    assert audit['compiled_243_source_closure_unchanged'] and not audit['freeze_pass']
    assert len(audit['external_input_drift'])==5
    assert audit['original_signal_expressions']==976 and audit['extra_signal_expressions']==468
    assert audit['traces']['boolean.trace']['samples']=='SAMPLES 3103251'
    unknown=json.loads((P/'initial_unknown_locations.json').read_text())
    assert unknown['all_unknown_digits_located'] and unknown['early_XZ_digits']==results['boolean.trace']['golden_XZ_digits']==12
    proof=dict(verified_original_manifest_files=len(prior),documented_report_only_changes=changed,compiled_source_closure_still_unchanged=True,src_hashes_verified=True,functional_pass=True,overall_freeze_pass=False,X_locations_verified=True,excluded_observation='source_diagnostics_timing_build_02/STATUS.md',trace_comparison_not_rerun=True,simulation_not_rerun=True)
    (P/'postflight.json').write_text(json.dumps(proof,indent=2),encoding='utf8')
    final={str(f.relative_to(P)):sha(f) for f in sorted(P.rglob('*')) if f.is_file() and not any(x in f.parts for x in ['work','__pycache__']) and f.name not in ['hashlog.json','vsim.wlf','transcript']}
    (P/'hashlog.json').write_text(json.dumps(final,indent=2),encoding='utf8')
    assert all(sha(P/rel)==expected for rel,expected in final.items())
    print('POSTFLIGHT_DELIVERY_HASH_AUDIT_PASS files='+str(len(final))+' functional_pass=True overall_freeze_pass=False',flush=True)
if __name__=='__main__':main()
