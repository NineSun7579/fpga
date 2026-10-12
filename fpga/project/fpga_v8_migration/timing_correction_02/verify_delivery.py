"""Independent final file/evidence verification. No PDS or hardware access."""
from pathlib import Path
import json,re
from run_whole import WORK,sha
def main():
    manifest=json.loads((WORK/'delivery_manifest.json').read_bytes())
    assert manifest['device']=='PG2L100H-6FBG484'
    assert manifest['programming_performed'] is False
    for name,h in manifest['evidence'].items():
        assert sha(WORK/name)==h,('Evidence drift',name)
    for name,h in manifest['sources'].items():
        assert sha(WORK/name)==h,('Source drift',name)
    bits=manifest['bitstreams'];assert bits
    for record in bits:
        path=Path(record['path']);assert path.is_relative_to(WORK)
        assert path.stat().st_size==record['bytes'] and record['bytes']>0
        assert sha(path)==record['sha256']
    route=WORK/'place_route/fpga_v8_cooperative_top_v2_rfg01_pnr.adf'
    assert sha(route)==manifest['routed_adf_sha256']
    sta=json.loads((WORK/'evidence/final_sta_summary.json').read_bytes())
    assert sta['routed_db_sha256']==sha(route)
    sections=sta['all_corner_summaries']
    expected={(s,c) for s in ['Setup','Hold','Recovery','Removal','Minimum Pulse Width'] for c in ['Slow','Fast']}
    assert {(s['section'],s['corner']) for s in sections}==expected and len(sections)==10
    assert all(s['rows'] and s['sum_failing_endpoints']==0 for s in sections)
    assert sta['negative_paths_match_summary_endpoint_total'] and sta['negative_slack_paths']==0
    assert json.loads((WORK/'evidence/all_reported_failing_paths.json').read_bytes())==[]
    assert sha(Path(sta['report']))==sta['report_sha256']
    handoff=json.loads((WORK/'parent_handoff.json').read_bytes())
    assert handoff['scored_timing_closed'] and handoff['structural_checks_passed'] and handoff['pin_rows_match_previous']
    checks=handoff['checks']
    assert all(checks[k]=='0' for k in ['loops','latchs','latch_loops','no_clock','unexpandable_clocks'])
    phy=json.loads((WORK/'evidence/hsst_actual_phy_audit.json').read_bytes())
    assert phy['sites_identical_to_baseline'] and phy['dedicated_connections_identical_to_baseline']
    ram=json.loads((WORK/'evidence/motion_routed_resource_proof.json').read_bytes())
    assert ram['routed_history_DRM36K_total']==32 and ram['logical_total_bits']==614400
    assert sha(WORK/'final_export/routed_dump.txt')==phy['dump_sha256']==ram['dump_sha256']
    assert sha(WORK/'final_export/routed_dump.v')==ram['verilog_sha256']
    assert json.loads((WORK/'actual_elaboration.json').read_bytes())['passed']
    bitgen=json.loads((WORK/'bitstream_result.json').read_bytes())
    assert bitgen['exit_code']==0 and bitgen['generator_completed'] and bitgen['route_unchanged']
    assert bitgen['route_sha256']==sha(route) and bitgen['bitstreams']==bits
    log=(WORK/'bitstream_01/bitgen.log').read_text(encoding='ascii',errors='backslashreplace')
    assert not re.search(r'^E:',log,re.M),'Bit generation errors'
    assert 'Process "Generate Bitstream" done.' in log
    result={'verified':True,'bitstreams':bits,'device':manifest['device'],
            'all_scored_slow_fast_timing_checks_passed':True,'structural_checks_passed':True,
            'source_and_route_and_evidence_hashes_verified':True,'programming_performed':False,
            'remaining_unscored_io_paths':sta['unscored_io_paths'],'board_operation_verified':False}
    (WORK/'delivery_verification.json').write_text(json.dumps(result,indent=2))
    lines=['# FPGA cooperative V4 bitstream','',
           'Device: PG2L100H-6FBG484. PDS 2022.2-SP6.4. Core clock: 131.25 MHz.','',
           'Generated locally and verified against the routed ADF and retained source hashes. No programming was performed.','']
    for record in bits:
        lines += ['File: '+record['path'],'Bytes: '+str(record['bytes']),'SHA256: '+record['sha256'],'']
    lines += ['All scored slow/fast setup, hold, recovery, removal and minimum-pulse checks pass.',
              'Whole-design loops, latches and no_clock checks pass. Physical pins and motion histories are retained.','',
              'Unscored IO paths: '+str(sta['unscored_io_paths'])+'. These remain outside scored timing acceptance.',
              'Physical board operation has not been tested; the user requested generation without programming.','',
              'Evidence: delivery_manifest.json, delivery_verification.json, parent_handoff.json and evidence/final_sta_summary.json.']
    (WORK/'BITSTREAM_DELIVERY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
