from pathlib import Path
root=Path(__file__).resolve().parents[1]
data=(root/'tools/deploy_burst_credit.py').read_bytes()
data=data.replace(b'burst_credit_evidence',b'cdc_stage_evidence').replace(b'flash_burst_credit.tcl',b'flash_cdc_stage.tcl').replace(b'verify_credit_board.py',b'verify_cdc_stage_board.py')
target=root/'tools/deploy_cdc_stage.py'
assert not target.exists()
compile(data,str(target),'exec')
target.write_bytes(data)
