from pathlib import Path
root=Path(__file__).resolve().parents[1]
for src,dst in [('deploy_rejection_diag.py','deploy_burst_credit.py'),('verify_rejection_board.py','verify_credit_board.py')]:
    data=(root/'tools'/src).read_bytes()
    data=data.replace(b'rejection_diag_evidence',b'burst_credit_evidence').replace(b'flash_rejection_diag.tcl',b'flash_burst_credit.tcl').replace(b'verify_rejection_board.py',b'verify_credit_board.py')
    (root/'tools'/dst).write_bytes(data)
data=(root/'tools/analyze_frame_recovery.py').read_bytes().replace(b'frame_recovery_evidence',b'burst_credit_evidence')
(root/'tools/analyze_burst_credit.py').write_bytes(data)
