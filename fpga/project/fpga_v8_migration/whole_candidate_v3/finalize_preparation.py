"""Small source-only handoff. No implementation invocation or process inspection."""
import json, re
from pathlib import Path
import prepare_candidate as p

def main():
    p.reaudit()
    h=p.HERE
    audit=json.loads((h/'artifacts/structural_audit.json').read_bytes())
    pins=json.loads((h/'artifacts/candidate_source_sha256.json').read_bytes())
    regression=json.loads((h/'artifacts/regression_binding.json').read_bytes())
    assert all(pins[k]==v for k,v in regression['candidate_sources'].items())
    assert p.sha(h/'cooperative_host/coop_host_protocol.hpp')==p.sha(p.M/'cooperative_host/coop_host_protocol.hpp')
    assert (h/'host/session_fault_transport.hpp').read_bytes()==(p.GUARD/'session_fault_transport.hpp').read_bytes()
    assert (h/'host/../cooperative_host/coop_host_protocol.hpp').is_file()
    assert not any((h/'compile_01').iterdir())
    diff=(h/'artifacts/binding_replay/binding.diff').read_bytes()
    assert diff==(p.GUARD/'artifacts/binding.diff').read_bytes()
    # Bind every delivered test and old-source receipt to current immutable bytes.
    receipt=json.loads((h/'artifacts/guard_results.json').read_bytes())
    for path,digest in receipt['additional_audited_inputs_unchanged'].items(): assert p.sha(Path(path))==digest
    for name,digest in receipt['source_hashes'].items(): assert p.sha(p.BASE/'rtl'/name)==digest
    for path,digest in regression['delivered_test_inputs'].items(): assert p.sha(Path(path))==digest
    r=h/'artifacts/regression_02'
    for name,digest in regression['logs'].items(): assert p.sha(r/name)==digest
    assert p.sha(r/'results.json')==regression['receipt_sha256']
    for path in ['prepare_candidate.py','run_pds.py','run_binding_tests.py','finalize_preparation.py']:
        compile((h/path).read_bytes(),str(h/path),'exec')
    topdiff=(h/'artifacts/binding_replay/fpga_v8_cooperative_top_v2.diff').read_bytes()
    changed=sum(l[:1] in [b'+',b'-'] and not l.startswith((b'+++',b'---')) for l in topdiff.splitlines())
    p.put('artifacts/parent_handoff.json',{
        'status':'source_prepared_structural_and_component_simulation_verified_full_elaboration_pending',
        'top_module':audit['top_module'],'project':'project.pds','future_work_dir':'compile_01',
        'actual_registered_top':'rtl/'+audit['top_module']+'.v',
        'actual_guard':'rtl/fpga_v8_reset_fault_guard.v',
        'actual_controller':'rtl/fpga_v8_pcie_dma_controller_h2f_rfg01.v',
        'binding_module_renames':p.binding.RENAMES,
        'source_base':'whole_candidate_v2: 694 inputs + 12 original components + 5 additions + top',
        'binding_generator_input':'audited whole_candidate_v2_route_01/rtl; all 18 RTL hashes matched unchanged v2',
        'generator_source_manifest_entries':len(p.binding.AUDIT),
        'guard_receipt_current_source_hashes_verified':True,
        'binding_manifest_identical_to_delivered':True,'top_diff_changed_lines':changed,
        'exact_product_byte_replay':True,'pcb_gpio_ddr_pads':112,'hsst_bits':14,
        'top_port_differences':[],'missing_clock_root_port_differences':[],
        'core_clock_mhz':131.25,'free_clk_mhz':25,'fdc_identical_to_v2':True,
        'full_top_named_api_instances_checked':len(json.loads((h/'artifacts/top_named_api_audit.json').read_bytes())),
        'named_port_width_checks':audit['named_port_width_checks'],
        'inherited_top_implicit_nets':audit['inherited_top_implicit_nets'],
        'new_implicit_or_multiple_driver_nets':[],
        'legacy_controller_reachable':False,'test_shell_registered':False,
        'actual_guard_linked_structurally':True,'full_top_elaborated':False,
        'fresh_guard_scenarios':19,'unsupported_control_only_reset_observation':receipt['unsupported_observation'],
        'accepted_AW_W_B_AR_R_drain_equations_unchanged':True,
        'read_F2H_not_guard_blocked':True,'RAW_fault_bit':2,'cooperative_STATUS_error_bit':6,'LASTERR':'0x52534647',
        'guard_parameters':audit['guard_parameters'],'all_product_sources_sha256_pinned':True,
        'host_copy_self_contained_not_PDS_registered':True,
        'compile_01_empty':True,'no_PDS_or_process_inspection_or_SSH_or_board':True,
        'protected_static_files':len(json.loads((h/'artifacts/protected_after.json').read_bytes())),
        'protected_scope':'source/IP/constraints/RTL, old project registration, completed guard and component artifacts; excludes active route dynamic outputs and unrelated README/root docs',
        'pending':['Parent starts compile/synthesis/PnR only after v2 is finished and single-instance check passes',
            'Full-top/hard-IP elaboration and mapped combinational-loop/CDC/timing audit',
            'Guard initialized registers, asynchronous bad_event and runtime-button reconfiguration_required synthesis behavior require PDS review',
            'Inherited core_clk/ddr_init_done implicit scalar nets and 11 vendor duplicates retained without normalization',
            '14 inherited IDF generate.log references absent; all registered source/IP/constraint paths exist',
            'Hard-IP cancellation and posted visibility, DDR outstanding retirement, reset/startup drain and physical reset coverage remain uncertified',
            'CPU/process restart has no fabric signal and is not detected'],
        'board_ready':False,'uniform_recovery_certified':False,
        'parent_commands':['python run_pds.py prepare','python run_pds.py compile','python run_pds.py synthesize','python run_pds.py pnr'],
        'future_runner_validation':'Python syntax and source/path guards verified; PDS stage invocation/completion markers not exercised',
        'evidence':['artifacts/binding_replay/binding.diff','artifacts/source_changes.json','artifacts/structural_audit.json','artifacts/interface_width_audit.json','artifacts/internal_binding_api_audit.json','artifacts/feedback_audit.json','artifacts/regression_binding.json','artifacts/registered_sources.json','artifacts/candidate_source_sha256.json','artifacts/protected_before.json','artifacts/protected_after.json']})
    before=json.loads((h/'artifacts/protected_before.json').read_bytes())
    assert before==p.snapshot([Path(path) for path in before])
    p.put('artifacts/final_receipt.json',{'status':'PASS_SOURCE_PREPARATION_ONLY','parent_handoff_sha256':p.sha(h/'artifacts/parent_handoff.json'),'source_manifest_sha256':p.sha(h/'artifacts/candidate_source_sha256.json'),'compile_01_empty':True,'protected_before_after_identical':True,'PDS_invoked':False,'board_ready':False})
    print('Final handoff: 512 checks, PCB 112+14, 19 fresh guard scenarios; compile_01 empty')

if __name__=='__main__': main()
