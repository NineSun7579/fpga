"""Verify and record already-launched performance owner after stale identity race."""
import json,shlex
import deploy_candidate as d
folder=d.ROOT/'deploy_1791596415577888000'
receipt=json.loads((folder/'receipt.json').read_text())
assert receipt['phase']=='parity_retired'
session=d.Session(folder,receipt)
try:
    identity_path=session.remote+'/candidate.identity.json'
    code='import json, pathlib; p=pathlib.Path('+repr(identity_path)+'); print(p.read_text())'
    rc,out,err=session.board.run(session.client,'python3 -c '+shlex.quote(code),timeout=20,sudo=True)
    assert rc==0,err
    current=json.loads(out)
    assert current['sha256']==receipt['arguments']['viewer_sha256']
    check_code='import pathlib,subprocess; p=pathlib.Path("/proc/'+str(current['pid'])+'/environ"); e=p.read_bytes().split(b"\\0"); assert b"DETVIEW_FPGA_INFER_RGB=1" in e; assert b"DETVIEW_FPGA_INFER_VERIFY=1" not in e; assert subprocess.check_output(["fuser","/dev/pango_pci_driver"],stderr=subprocess.DEVNULL).split()==['+repr(str(current['pid']).encode())+']; print("verified")'
    rc,out,err=session.board.run(session.client,'python3 -c '+shlex.quote(check_code),timeout=20,sudo=True)
    assert rc==0,err
    candidate=receipt['candidate'];candidate['identity']=current
    candidate['env'].pop('DETVIEW_FPGA_INFER_VERIFY',None)
    session.save('candidate_running',candidate=candidate,performance_mode=True)
    print(current)
finally:session.client.close()
