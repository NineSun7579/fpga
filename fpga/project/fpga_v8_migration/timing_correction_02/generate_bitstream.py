"""Generate a local bitstream only after routed checks. Never programs hardware."""
import json,subprocess,re
from pathlib import Path
from run_whole import WORK,M,PDS,idle,inventory,save,sha
def main():
    receipt=json.loads((WORK/'parent_handoff.json').read_bytes())
    assert receipt['scored_timing_closed'] and receipt['structural_checks_passed'],'Routed timing / structure gate failed'
    assert receipt['pin_rows_match_previous'],'Pin mapping gate failed'
    phy=json.loads((WORK/'evidence/hsst_actual_phy_audit.json').read_bytes())
    assert phy['sites_identical_to_baseline'] and phy['dedicated_connections_identical_to_baseline'],'HSST physical mapping gate failed'
    sta=json.loads((WORK/'evidence/final_sta_summary.json').read_bytes())
    sections=sta['all_corner_summaries']
    expected={(s,c) for s in ['Setup','Hold','Recovery','Removal','Minimum Pulse Width'] for c in ['Slow','Fast']}
    assert len(sections)==10 and {(s['section'],s['corner']) for s in sections}==expected,'Incomplete timing summaries'
    assert all(s['rows'] and s['sum_failing_endpoints']==0 for s in sections),'Empty or failing timing summary'
    assert sta['negative_paths_match_summary_endpoint_total'] and sta['negative_slack_paths']==0
    assert json.loads((WORK/'actual_elaboration.json').read_bytes())['passed']
    tests=Path(__file__).resolve().parent
    transport=json.loads((tests/'artifacts/results.json').read_bytes())
    assert transport['cases']==50 and transport['fault_cases']==4
    cases=transport['case_results']
    assert len(cases)==50
    faults=[c for c in cases if c['result']=='PENDING_FAULT_NO_MSI']
    assert len(faults)==4 and all(c['msi']==0 and c['final_b_credits']==0 for c in faults)
    assert all(c['result'] in ['PASS','PENDING_FAULT_NO_MSI'] for c in cases)
    fifo_binding=json.loads((tests/'binding.json').read_bytes())
    assert sha(WORK/'rtl/fpga_v8_pcie_fifo_h2f_tc02.v')==fifo_binding['candidate_sha256']
    dma=json.loads((tests/'dma_artifacts/results.json').read_bytes())
    assert dma['cases']==160 and dma['wait_for_data_modes']==[0,1] and dma['public_outputs_and_internal_beat_count_match']
    assert sha(WORK/'rtl/axi_dma_write_tc02.v')==dma['candidate_sha256']
    guarded=json.loads((tests/'guarded_artifacts/results.json').read_bytes())
    assert len(guarded['passed'])==5 and guarded['source_unchanged']
    assert all(sha(Path(p))==h for p,h in guarded['source_hashes'].items())
    guard=json.loads((M/'reset_fault_guard_02/artifacts/results.json').read_bytes())
    assert guard['passed_cases']==9
    assert sha(WORK/'rtl/fpga_v8_reset_fault_guard_02.v')==guard['source_sha256']
    ram=json.loads((WORK/receipt['motion_ram_proof']).read_bytes())
    assert ram['routed_history_DRM36K_total']==32 and ram['logical_total_bits']==614400
    assert inventory()==json.loads((WORK/'inputs_before.json').read_bytes())
    route=WORK/'place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf'
    exported=json.loads((WORK/'final_export_result.json').read_bytes())
    assert sha(route)==exported['route_sha256_after']
    out=WORK/'bitstream_01';assert not out.exists(),'No bitstream attempt overwrite'
    idle('before_bitstream');out.mkdir()
    template=M.parent/'motion_100h/run_20261003_212303/bitgen.tcl'
    script=out/'bitgen.tcl'
    script.write_text('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG484\n'
        'gen_bit_stream -input_db_file {'+route.as_posix()+'} -force_to_run -create_bit_file TRUE\n',encoding='ascii')
    before=sha(route)
    command=[str(PDS),'-file',str(script),'-work_dir',str(out),'-project_name','cooperative_v4_bitstream']
    with (out/'bitgen.log').open('xb') as log:
        p=subprocess.run(command,cwd=out,stdout=log,stderr=subprocess.STDOUT)
    bits=list(out.rglob('*.sbit'))+list(out.rglob('*.bit'))
    logtext=(out/'bitgen.log').read_bytes().decode('ascii','backslashreplace')
    declared=re.findall(r'The bitstream file is "([^"]+)"',logtext)
    declared_paths={Path(n).resolve() for n in declared}
    generated_ok='Process "Generate Bitstream" done.' in logtext and 'Generating Programming File done.' in logtext
    companion_masks=list(out.rglob('*.smsk'))
    result={'exit_code':p.returncode,'command':command,'template':str(template),'template_sha256':sha(template),
            'route_sha256':before,'route_unchanged':sha(route)==before,
            'bitstreams':[{'path':str(f),'bytes':f.stat().st_size,'sha256':sha(f)} for f in bits],
            'generator_completed':generated_ok,'declared_bitstream_paths':declared,
            'companion_masks':[{'path':str(f),'bytes':f.stat().st_size,'sha256':sha(f)} for f in companion_masks],
            'programming_performed':False,'board_verified':False,
            'unscored_io_paths':receipt['unscored_io_paths']}
    save('bitstream_result.json',result)
    assert p.returncode==0 and generated_ok and bits and all(f.stat().st_size>0 for f in bits)
    assert declared_paths=={f.resolve() for f in bits},'Generated files must match PDS log'
    assert sha(route)==before and inventory()==json.loads((WORK/'inputs_before.json').read_bytes())
    receipts=WORK/'regression_receipts';receipts.mkdir()
    receipt_inputs={'transport.json':tests/'artifacts/results.json',
                    'fifo_binding.json':tests/'binding.json',
                    'dma.json':tests/'dma_artifacts/results.json',
                    'guarded_fifo.json':tests/'guarded_artifacts/results.json',
                    'reset_guard.json':M/'reset_fault_guard_02/artifacts/results.json'}
    for name,source in receipt_inputs.items():
        (receipts/name).write_bytes(source.read_bytes())
    evidence_paths=[WORK/'parent_handoff.json',WORK/'actual_elaboration.json',WORK/'binding_audit.json',
                    WORK/'structural_gate.json',WORK/'baseline_guard.json',WORK/'flow_result.json',
                    WORK/'evidence/final_sta_summary.json',WORK/'evidence/all_reported_failing_paths.json',
                    WORK/'evidence/motion_routed_resource_proof.json',WORK/'evidence/hsst_actual_phy_audit.json',
                    WORK/'final_export_result.json',WORK/'bitstream_result.json',out/'bitgen.log']
    evidence_paths.extend(receipts/name for name in receipt_inputs)
    save('delivery_manifest.json',{'device':'PG2L100H-6FBG484','top':'fpga_v8_cooperative_top_v2_rfg01',
          'bitstreams':result['bitstreams'],'routed_adf_sha256':before,
          'evidence':{str(f.relative_to(WORK)):sha(f) for f in evidence_paths},
          'sources':inventory(),'programming_performed':False,'board_verified':False,
          'remaining_unscored_io_paths':receipt['unscored_io_paths']})
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
