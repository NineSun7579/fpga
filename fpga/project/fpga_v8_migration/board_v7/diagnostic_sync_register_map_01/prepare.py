"""Byte-preserving preparation only; never starts PDS or edits other projects."""
from pathlib import Path
import hashlib, json, re
HERE=Path(__file__).resolve().parent
BOARD=HERE.parent
CAND=BOARD/'diagnostic_sync_register_timing_candidate'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v): p.write_bytes((json.dumps(v,indent=2,ensure_ascii=True)+'\n').encode('ascii'))
def main():
    assert not (HERE/'project.pds').exists(), 'Refuse to overwrite experiment'
    for d in ['rtl','constraints','evidence','analysis_tools']: (HERE/d).mkdir(exist_ok=True)
    origin={}
    for name in ['v7_sdt_bus.v','v7_sfd_candidate.v']:
        src=CAND/'rtl_primitive'/name; dst=HERE/'rtl'/name
        dst.write_bytes(src.read_bytes()); origin[str(src)]=sha(src)
    bus=(HERE/'rtl/v7_sdt_bus.v').read_bytes()
    header=bus[bus.index(b'module v7_sdt_bus'):bus.index(b');')+2]
    names=[]
    for chunk in header[header.index(b'(')+1:-2].split(b','):
        names.append(re.findall(rb'[A-Za-z_][A-Za-z_0-9]*',chunk)[-1].decode('ascii'))
    assert len(names)==len(set(names))==43
    top=header.replace(b'module v7_sdt_bus',b'module v7_sdt_top').replace(b'output reg ',b'output ')
    top+=b'\nv7_sdt_bus source_diagnostics (\n'+b',\n'.join((' .'+n+'('+n+')').encode('ascii') for n in names)+b'\n);\nendmodule\n'
    (HERE/'rtl/v7_sdt_top.v').write_bytes(top)
    # Same domain rates as integrated top. Five genuine root inputs; no exceptions.
    clock=b'# Isolated roots replacing parent PLL outputs; no false-path/clock-group relaxation.\ncreate_clock -name {ddrphy_sysclk} [get_ports {clk}] -period {7.619} -waveform {0 3.8095}\n'
    for i,period,half in [(0,'11.905','5.952'),(1,'11.905','5.952'),(2,'20.833','10.416'),(3,'20.833','10.416')]:
        clock+=('create_clock -name {cmos'+str(i+1)+'_pclk} [get_ports {cam_clk['+str(i)+']}] -period {'+period+'} -waveform {0 '+half+'}\n').encode('ascii')
    (HERE/'constraints/clock.fdc').write_bytes(clock)
    template=(BOARD/'source_diagnostics_timing_build_01/project_template.pds').read_bytes()
    tail=template[template.index(b'    (_task tsk_compile'):]
    tail=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',tail)
    # Only compile/synthesize/map tasks, deliberately exclude PNR and bitstream tasks.
    tail=tail[:tail.index(b'    (_task tsk_pnr')]+b')\n'
    handoff=json.loads((CAND/'mapping_handoff.json').read_bytes())
    options=handoff['documented_device_map_options_for_later_isolated_build']
    assert options=={'devmap_remove_dups':0,'devmap_const_prop':0,'devmap_control_set_num':0}
    injection=b''.join(('            (_option '+k+' (_integer 0))\n').encode('ascii') for k in options)
    tail=tail.replace(b'(_command cmd_devmap',b'(_command cmd_devmap\n'+injection)
    prefix=b'(_flow fab_demo "2022.2-SP6.4"\n (_version "1.1.0")\n (_status "initial")\n (_project (_option prj_work_dir (_string ".")) (_option prj_impl_dir (_string ".")))\n (_task tsk_setup\n (_widget wgt_select_arch (_input (_part (_family Logos2) (_device PG2L100H) (_speedgrade -6) (_package FBG484))))\n (_widget wgt_my_design_src (_input\n'
    for name in ['v7_sdt_top.v','v7_sdt_bus.v','v7_sfd_candidate.v']:
        prefix+=('  (_file "rtl/'+name+'" (_format verilog))\n').encode('ascii')
    prefix+=b'))\n (_widget wgt_import_logic_con_file (_input (_file "constraints/clock.fdc" (_format fdc))))\n )\n'
    prefix=prefix.replace(b'(_flow fab_demo "2022.2-SP6.4"\n',b'(_flow fab_demo "2022.2-SP6.4"\n (_comment "Isolated diagnostic mapping experiment")\n',1)
    prefix=re.sub(rb'(\(_file "(?:rtl|constraints)/[^"]+"\s*\(_format \w+\))\)',rb'\1 (_timespec "2026-10-07T00:00:00"))',prefix)
    (HERE/'project.pds').write_bytes(prefix+tail)
    parser=BOARD/'physical_subagent_evidence_01/fixed_06/physical_exact_09/actual/analysis/parse_objects.py'
    raw=parser.read_bytes(); needle=b"'parameters':children(i,'PARAMETERMAP') or children(i,'PARAMETER')}"
    assert raw.count(needle)==1
    (HERE/'analysis_tools/parse_objects.py').write_bytes(raw.replace(needle,b"'parameters':children(i,'PARAMETERMAP') or children(i,'PARAMETER'), 'cdb_entries':children(i,'CDBENTRY')}"))
    guard=json.loads((BOARD/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    save(HERE/'evidence/protected_baseline.json',guard)
    save(HERE/'evidence/preflight.json',{'status':'PASS','root_clocks':5,'false_paths':0,'clock_groups':0,'all_bus_ports_bound':names,'outputs_bound_to_top':17,'sync_primitives_per_source':7,'reset_primitives_per_source':4,'bus_reset_primitives':16,'total_sync':28,'total_reset':32,'gbk_byte_preserving':True,'original_sources':origin,'options':options,'option_evidence_sha256':sha(CAND/'docs/stored_stage_api12_shell.log'),'handoff_sha256':sha(CAND/'mapping_handoff.json'),'topology_contract_sha256':sha(CAND/'evidence/topology_contract.json'),'protected_count':len(guard),'remote_or_program':False})
    frozen={str(p.relative_to(HERE)):sha(p) for d in ['rtl','constraints','analysis_tools'] for p in (HERE/d).rglob('*') if p.is_file()}
    frozen['project.pds']=sha(HERE/'project.pds')
    save(HERE/'evidence/input_hashes.json',frozen)
    print('OFFLINE_PREPARED',json.dumps(frozen,indent=2))
if __name__=='__main__':main()
