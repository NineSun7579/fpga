"""Read-only final source/runtime audit plus compact review receipt; no tool launch."""
from pathlib import Path
import json, sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'runtime'))
from preflight import load,sha,require,verify
from controller03 import immutable_runtime_guard

def main():
    immutable_runtime_guard();m=verify();e=HERE/'evidence/runtime'
    before=load(HERE/'evidence/build02_sources_before.json');old=HERE.parent/'source_diagnostics_timing_build_02'
    require(all(sha(old/n)==h for n,h in before.items()),'Build02 source changed externally; retain evidence')
    ledger=load(e/'runtime_hash_append.json')
    launched=load(e/'controller_launch.json')
    require(launched['ledger_sha256']==sha(e/'runtime_hash_append.json'),'Actual controller launch not bound to frozen runtime')
    require(launched['controller_sha256']==sha(HERE/'runtime/controller03.py'),'Actual launched controller changed')
    stable=[HERE/'manifest.json',HERE/'sourcehash.json',HERE/'source03hash.json',HERE/'project_template.pds',HERE/'REPORT_ZH.md',
            e/'runtime_hash_append.json',e/'offline_runtime_checks.json',e/'identity_adapter_review.json',e/'controller_launch.json']
    receipt={'status':'SOURCE_AND_RUNTIME_DELIVERY_AUDIT_PASS_ONLY','source_files':741,'registered_sources':186,
             'source_set_sha256':load(HERE/'source03hash.json')['source_set_sha256'],
             'runtime_files':len(ledger['runtime_hash_append']),'runtime_ledger_sha256':sha(e/'runtime_hash_append.json'),
             'controller_pid':launched['pid'],'controller_launch_sha256':sha(e/'controller_launch.json'),
             'source03hash_sha256':sha(HERE/'source03hash.json'),'build02_sources_unchanged':True,
             'main_consumer_not_modified_by_this_task':True,'physical_signoff':False,
             'note':'This receipt proves local preparation and launch provenance only; actual map gate/stage DB/STA results remain authoritative.',
             'stable_review_hashes':{str(p.relative_to(HERE)):sha(p) for p in stable}}
    p=HERE/'runtime_delivery_review03.json'
    require(not p.exists(),'Review receipt already exists; refuse overwrite')
    p.write_text(json.dumps(receipt,indent=2)+'\n',encoding='ascii')
    print(json.dumps({k:v for k,v in receipt.items() if k!='stable_review_hashes'},indent=2))

if __name__=='__main__':main()
