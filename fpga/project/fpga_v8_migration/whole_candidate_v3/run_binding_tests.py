"""Run delivered component scenarios against pinned v3 inputs, in v3 only."""
import sys, json, importlib.util
from pathlib import Path
sys.dont_write_bytecode=True
import prepare_candidate as prep
HERE=prep.HERE
OUT=HERE/'artifacts/regression_02'

def main():
    assert not OUT.exists(),'Never overwrite regression evidence'
    pins=json.loads((HERE/'artifacts/candidate_source_sha256.json').read_bytes())
    protected=json.loads((HERE/'artifacts/protected_before.json').read_bytes())
    assert prep.snapshot([Path(p) for p in protected])==protected
    binding=prep.binding
    binding.OUT=OUT
    sys.modules['build_binding']=binding
    tests=prep.load_module('delivered_guard_tests',prep.GUARD/'run_tests.py')
    tests.OUT=OUT
    tests.SOURCE=HERE/'rtl'
    original_audited=binding.audited_bytes
    def audited(path):
        if path.is_relative_to(HERE):
            data=path.read_bytes(); rel=path.relative_to(HERE).as_posix()
            if rel in pins: assert prep.digest(data)==pins[rel]
            else:
                assert path.parent==OUT and path.name.startswith('compat_')
                assert path.name in ['compat_'+binding.RENAMES[binding.NAMES[i]]+'.v' for i in [1,4]]
            return data
        return original_audited(path)
    tests.audited_bytes=audited
    original_build=binding.build
    def build():
        candidates=original_build()
        for n,b in candidates.items(): assert (HERE/'rtl'/(binding.RENAMES[n]+'.v')).read_bytes()==b
        assert (prep.GUARD/'fpga_v8_reset_fault_guard.v').read_bytes()==(HERE/'rtl/fpga_v8_reset_fault_guard.v').read_bytes()
        return candidates
    tests.build=build
    executed=[prep.GUARD/'run_tests.py',prep.GUARD/'build_binding.py',prep.GUARD/'fpga_v8_reset_fault_guard.v',prep.GUARD/'test_transport.cpp',prep.GUARD/'session_fault_transport.hpp']
    executed+=list(prep.GUARD.glob('tb_*.sv'))
    executed+=[HERE.parent/'pcie_retirement_contract/tests/pango_pcie_top_stub.sv']
    testpins=prep.snapshot(executed)
    tests.main()
    assert testpins==prep.snapshot(executed)
    assert prep.snapshot([Path(p) for p in protected])==protected
    assert all(prep.sha(HERE/p)==h for p,h in pins.items())
    receipt=json.loads((OUT/'results.json').read_bytes())
    assert receipt['enforced_scenarios']==19 and receipt['transport_precheck_pass']
    prep.put('artifacts/regression_binding.json',{'fresh_v3_execution':True,'enforced_scenarios':19,'unsupported_observation':receipt['unsupported_observation'],'candidate_sources':pins,'delivered_test_inputs':testpins,'receipt_sha256':prep.sha(OUT/'results.json'),'logs':{p.name:prep.sha(p) for p in OUT.glob('*.log')},'compatibility_only_in_simulation':True,'full_top_elaborated':False,'protected_source_unchanged':True})
    print('Fresh v3: 19 expected scenarios + 1 explicit unsupported observation; pinned candidate sources unchanged')

if __name__=='__main__': main()
