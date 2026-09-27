from pathlib import Path
root=Path(__file__).resolve().parents[1]
data=(root/'tools/deploy_frame_recovery.py').read_bytes()
data=data.replace(b'frame_recovery_evidence',b'rejection_diag_evidence').replace(b'flash_frame_recovery.tcl',b'flash_rejection_diag.tcl').replace(b'verify_recovery_board.py',b'verify_rejection_board.py')
(root/'tools/deploy_rejection_diag.py').write_bytes(data)
data=(root/'tools/verify_recovery_board.py').read_bytes().replace(b'frame_recovery_evidence',b'rejection_diag_evidence')
old=b"    a=snap();time.sleep(3);b=snap()"
new=b"""    rows=[]
    for sample in range(81):
        rows.append(dict(t=time.monotonic(),cams=[{hex(x):d.read32(base+x) for x in range(0,256,16)} for base in (0x20000000,0x20000200,0x20000400)]))
        time.sleep(0.25)
    (out/'registers.json').write_text(json.dumps(rows,indent=2))
    for cam in range(3):
        start=rows[0]['cams'][cam];end=rows[-1]['cams'][cam]
        dt=rows[-1]['t']-rows[0]['t']
        print('CAM',cam+1,'success/s',((end['0xf0']-start['0xf0'])&0xffffffff)/dt,
              'offered_pixels',sorted(set(r['cams'][cam]['0x30'] for r in rows)),
              'faults',sorted(set(hex(r['cams'][cam]['0x0']) for r in rows)),
              'overflow_count_delta',((end['0xa0']>>16)-(start['0xa0']>>16))&65535,
              'short_count_delta',((end['0xa0']&65535)-(start['0xa0']&65535))&65535,flush=True)
    a=snap();time.sleep(3);b=snap()"""
assert data.count(old)==1
(root/'tools/verify_rejection_board.py').write_bytes(data.replace(old,new))
