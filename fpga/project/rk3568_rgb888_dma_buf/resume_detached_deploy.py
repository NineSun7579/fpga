"""Resume the exact cleanly detached deployment after missing-node gate fix."""
import json
from pathlib import Path
import deploy_candidate as deploy
root=Path(__file__).resolve().parent
folder=root/'deploy_1791567760719372300'
receipt=json.loads((folder/'receipt.json').read_text())
assert receipt['phase'] in ('unloading_original','inserting_candidate'),receipt['phase']
session=deploy.Session(folder,receipt)
try:
    assert session.rpc('boot')['boot_id']==receipt['baseline']['boot_id']
    old=receipt['artifacts']
    updated=deploy.validate_artifacts()
    assert {k:v for k,v in old.items() if k!='helper_sha256'}=={k:v for k,v in updated.items() if k!='helper_sha256'}
    assert session.rpc('hash',path=session.helper)['sha256']==old['helper_sha256']
    receipt['prior_helper_sha256']=old['helper_sha256']
    receipt['artifacts']=updated
    session.upload_helper()
    if receipt['phase']=='unloading_original':
        session.rpc('verify_retired')
        session.rpc('module',operation='unload')
        session.save('inserting_candidate')
    args=receipt['arguments']
    session.rpc('module',operation='insert',module=args['module_remote'],sha256=updated['module_sha256'])
    session.save('candidate_inserted')
    session.rpc('rescan')
    session.launch(receipt['baseline'])
    print(folder/'receipt.json')
finally:
    session.client.close()
