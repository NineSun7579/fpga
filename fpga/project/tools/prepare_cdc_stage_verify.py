"""Prepare board verifier for the CDC stage diagnostic image; does not deploy."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = (root/'tools/verify_credit_board.py').read_bytes()
data = data.replace(b'burst_credit_evidence', b'cdc_stage_evidence')
anchor = b'records=[]'
helper = b'''def stage_snapshot(base):
    for attempt in range(30):
        seq0=d.read32(base+0x1c0)
        counts=[d.read32(base+x) for x in (0x190,0x1a0,0x1b0)]
        seq1=d.read32(base+0x1c0)
        if seq0==seq1 and seq1>=2:
            return dict(seq=seq1,input=counts[0],output=counts[1],drop=counts[2])
    return dict(seq=seq1,input=counts[0],output=counts[1],drop=counts[2],unstable=True,seq_before=seq0)
records=[]'''
assert data.count(anchor)==1
data = data.replace(anchor, helper)
anchor = b'        time.sleep(0.25)'
replacement = b"        rows[-1]['cdc']=[stage_snapshot(base) for base in (0x20000000,0x20000200,0x20000400)]\n" + anchor
assert data.count(anchor)==1
data = data.replace(anchor, replacement)
anchor = b'    a=snap();time.sleep(3);b=snap()'
replacement = b'''    for cam in range(3):
        print('CDC',cam+1,{key:sorted(set(row['cdc'][cam][key] for row in rows)) for key in ('input','output','drop')},flush=True)
''' + anchor
assert data.count(anchor)==1
data = data.replace(anchor, replacement)
target=root/'tools/verify_cdc_stage_board.py'
assert not target.exists(), 'Refuse to overwrite existing verifier'
compile(data,str(target),'exec')
target.write_bytes(data)
print(target)
