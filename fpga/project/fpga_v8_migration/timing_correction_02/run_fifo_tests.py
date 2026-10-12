"""Reuse all 50 production transport scenarios with isolated outputs."""
from pathlib import Path
import sys,importlib.util,json
from build_fifo import transform,main as build
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'pcie_h2f_transport_contract'
sys.path.insert(0,str(OLD))
spec=importlib.util.spec_from_file_location('transport_regression',OLD/'run_tests.py')
reg=importlib.util.module_from_spec(spec);spec.loader.exec_module(reg)
build()
ART=HERE/'artifacts';ART.mkdir(exist_ok=True)
reg.ART=ART
for name in ['candidate_controller.v','tb_transport.sv']:
    (ART/name).write_bytes((OLD/'artifacts'/name).read_bytes())
(ART/'candidate_fifo.v').write_bytes(transform((OLD/'artifacts/candidate_fifo.v').read_bytes()))
before=reg.immutable()
_,cases=reg.suites()
trace=reg.run_design('candidate',cases)
result=reg.audit_candidate(trace,cases)
assert before==reg.immutable(),'Reference inputs changed'
print('PASS',result['cases'],'transport scenarios',flush=True)
