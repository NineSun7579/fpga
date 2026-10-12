"""Gracefully switch the parity-approved candidate to uninstrumented inference."""
import json
import argparse
import deploy_candidate as d
parser=argparse.ArgumentParser()
parser.add_argument('trial',nargs='?',default='deploy_1791596415577888000')
args=parser.parse_args()
folder=(d.ROOT/args.trial).resolve()
folder.relative_to(d.ROOT)
receipt=json.loads((folder/'receipt.json').read_text())
assert receipt['phase']=='candidate_running'
log=(folder/'candidate_runtime.log').read_text()
assert 'OUTPUT_COUNT_REACHED count=12 required=12 input_and_native_exact=1' in log
session=d.Session(folder,receipt)
try:
    candidate=receipt['candidate']
    session.rpc('stop',identity=candidate['identity'],env=candidate['env'],status=candidate['status'])
    session.save('parity_retired',parity_candidate=candidate)
    receipt['arguments']['verify']=False
    receipt['baseline']['env'].pop('DETVIEW_FPGA_INFER_VERIFY',None)
    session.launch(receipt['baseline'])
    print(folder/'receipt.json')
finally:session.client.close()
