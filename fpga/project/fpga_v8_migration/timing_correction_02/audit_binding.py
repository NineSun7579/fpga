"""Static audit independent of the running PDS phase; byte-safe source reads."""
from pathlib import Path
import re,json
from run_whole import WORK,BASE,sha,save,inventory
def main():
    before=json.loads((WORK/'inputs_before.json').read_bytes())
    assert inventory()==before
    unchanged_inputs={str(p.relative_to(BASE)):sha(p) for p in (BASE/'inputs').rglob('*') if p.is_file()}
    assert all(sha(WORK/n)==h for n,h in unchanged_inputs.items())
    topname='rtl/fpga_v8_cooperative_top_v2_rfg01.v'
    original=(BASE/topname).read_bytes();candidate=(WORK/topname).read_bytes()
    expected=original
    changes={}
    for old,new,count in [(b'fpga_v8_pcie_fifo_h2f_rfg01',b'fpga_v8_pcie_fifo_h2f_tc02',1),
                           (b'fpga_v8_reset_fault_guard',b'fpga_v8_reset_fault_guard_02',1),
                           (b'axi_dma_write',b'axi_dma_write_tc02',7)]:
        pattern=rb'\b'+old+rb'(?=\s*(?:#\s*\(|\w+\s*\())'
        expected,n=re.subn(pattern,new,expected);assert n==count,(old,n)
        changes[old.decode()]={'replacement':new.decode(),'instances':n}
    assert candidate==expected,'Unexpected top delta'
    # Entire top delta is instance type only: parameters, ports, addresses,
    # source clocks and all six camera/motion connections are byte-identical.
    prep=json.loads((WORK/'preparation.json').read_bytes())
    for name,h in prep['corrected_sources'].items():
        p=Path(name);assert sha(p)==h and sha(WORK/'rtl'/p.name)==h
    unchanged_rtl=[]
    for p in (BASE/'rtl').glob('*.v'):
        if p.name==Path(topname).name:continue
        assert sha(p)==sha(WORK/'rtl'/p.name)
        unchanged_rtl.append(p.name)
    constraints={n:h for n,h in unchanged_inputs.items() if n.endswith('.fdc')}
    save('binding_audit.json',{'exact_top_instance_replacements_only':True,'changes':changes,
         'unchanged_input_files':len(unchanged_inputs),'unchanged_rtl':unchanged_rtl,
         'unchanged_constraints':constraints,'candidate_sources_match_tested_hashes':True,
         'external_top_api_unchanged':True,'six_camera_connections_unchanged':True,
         'motion_connections_unchanged':True,'routed_timing_claimed':False,
         'scope':'Static byte preservation; actual elaboration and physical verification still required'})
    print('Binding audit PASS; unchanged inputs',len(unchanged_inputs),flush=True)
if __name__=='__main__':main()
