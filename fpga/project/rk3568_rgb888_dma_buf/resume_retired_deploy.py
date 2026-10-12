"""Continue exact trial after clean owner retirement verified independently."""
from pathlib import Path
import json
import deploy_candidate as d
folder=d.ROOT/'deploy_1791596415577888000'
receipt=json.loads((folder/'receipt.json').read_text())
assert receipt['phase']=='stopping_baseline'
session=d.Session(folder,receipt)
try:
    assert session.rpc('boot')['boot_id']==receipt['baseline']['boot_id']
    assert session.rpc('hash',path=session.helper)['sha256']==receipt['artifacts']['helper_sha256']
    session.rpc('verify_lock',remote=session.remote)
    session.rpc('verify_retired')
    session.save('baseline_retired')
    d.pds_preflight()
    session.save('removing_pci')
    session.rpc('remove')
    session.save('pci_removed')
    session.rpc('verify_retired')
    session.save('programming_candidate')
    d.flash(folder)
    session.save('unloading_original')
    session.rpc('module',operation='unload')
    session.save('inserting_candidate')
    session.rpc('module',operation='insert',module=receipt['arguments']['module_remote'],sha256=d.MODULE)
    session.rpc('rescan')
    session.launch(receipt['baseline'])
    print(folder/'receipt.json')
finally:session.client.close()
