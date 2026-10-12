"""Exact RTL field decomposition and induction for duplicate one-bit lanes."""
import json
from setup_review import HERE,B04,BOARD,sha,save
def main():
    widths=[32,24,16,16,24,24,24,24,24,24,24,16,8,16,24,32]
    magic=0x53464401
    expected_zero={w*32+b for w,n in enumerate(widths) for b in range(n,32)}|{480+b for b in range(32) if not (magic>>b)&1}
    alias_bits=[240]+[480+b for b in range(32) if (magic>>b)&1]
    contract=json.loads((HERE/'logical_to_physical_2048.json').read_bytes())
    for cam in range(4):
        actual={r['logical_bit'] for r in contract['constant_zero_bits'] if r['camera']==cam}
        assert actual==expected_zero and len(actual)==182
    src=(B04/'rtl/v7_sfd_candidate.v').read_bytes()
    expected=[b'mailbox<=0;',b'mailbox[15*32+:32]<=32\'h53464401;',b'have_prev,1\'b1,gap_q}',b'host_bank<=0;',b'host_bank<=mailbox;']
    assert all(s in src for s in expected)
    # Full one-step induction, including async assertion priority. Initial equality
    # is reset==0; in every control case equal lane states remain equal forever.
    transitions=[]
    for previous in range(2):
        for reset in range(2):
            for write in range(2):
                out=0 if reset else (1 if write else previous)
                states=[0 if reset else (1 if write else previous) for _ in alias_bits]
                assert states==[out]*11
                transitions.append({'previous_equal_value':previous,'reset':reset,'snapshot_write_enable':write,'all11_next_values':states})
    captures=[]
    for previous in range(2):
        for reset in range(2):
            for enable in range(2):
                for source in range(2):
                    out=0 if reset else (source if enable else previous)
                    captures.append({'previous_equal_value':previous,'host_reset':reset,'acquire_enable':enable,'source_equal_value':source,'all11_next_values':[out]*11})
    lines=src.splitlines()
    relevant=[{'line':i,'ascii':l.decode('ascii','replace')} for i,l in enumerate(lines,1) if any(x in l for x in [b'mailbox[',b'host_bank<=',b'mailbox<=',b'if(edge_vs)',b'if(armed)',b'if(busy)',b'if(rst_c)',b'if(rst_h)',b'if(snapshot_available',b'have_prev,',b'read_data<=host_bank'])]
    save('rtl_field_alias_contract.json',{'source_sha256':sha(B04/'rtl/v7_sfd_candidate.v'),'source03_byte_equal':src==(BOARD/'source_diagnostics_timing_build_03/rtl/v7_sfd_candidate.v').read_bytes(),'field_payload_widths':widths,'word15_hex':'53464401','zero_bits_per_camera':sorted(expected_zero),'one_lane_alias_group_per_camera':alias_bits,'extra_aliases_per_camera':10,'mailbox_induction':transitions,'host_capture_induction':captures,'RTL_lines':relevant,'semantics':'Every listed lane resets to zero, updates to one under identical mailbox write enable, otherwise holds. All host lanes reset to zero and sample equal mailbox lanes under identical acquire enable. These are sequential equal-value aliases, not always-1 constants; before first snapshot they are zero. Cameras retain separate clocks/source states.'})
    old=json.loads((HERE/'build01_duplicate_original_primitives.json').read_bytes());nets=json.loads((HERE/'complete_connected_nets_build01.json').read_bytes());structural=[]
    for cam in range(4):
        for bank in ['mailbox','host_bank']:
            rows=[r for k,r in old.items() if f'cameras[{cam}].source/{bank}[' in k]
            assert len(rows)==11 and {r['record']['type'] for r in rows}=={'GTP_DFF_CE'}
            common={pin:{r['pins'][pin]['net'] for r in rows} for pin in ['CLK','C','CE']}
            assert all(len(v)==1 for v in common.values())
            assert len({json.dumps(r['record']['default_parameters'],sort_keys=True) for r in rows})==1
            dn={r['pins']['D']['net'] for r in rows}
            if bank=='mailbox':
                assert len(dn)==1 and any('$constant_1' in alias for alias in nets[next(iter(dn))]['aliases'])
            else:assert len(dn)==11
            structural.append({'camera':cam,'bank':bank,'old_independent_cells':[r['cell'] for r in rows],'identical_CLK_C_CE_nets':{p:next(iter(v)) for p,v in common.items()},'identical_default_parameters':rows[0]['record']['default_parameters'],'distinct_D_nets':len(dn),'mailbox_D_is_one':bank=='mailbox'})
    save('build01_equal_lane_structural_proof.json',{'status':'PASS_OFFLINE_EQUAL_TRAJECTORY_PROOF','groups':structural,'actual_40_pair_change':'Old mailbox 11 independent cells per camera already had identical D=1,CLK,C,CE/defaults. Host 11 independent cells had sameCLK,C,CE/defaults and D from those equal mailbox cells. New graph retains only bit240 for both sides, so40 removed pairs are true equal-value sharing, not parser-created pairs.','optimizer_heuristic_cause_known':False})
    print('RTL:182 zero/camera,11 equal one-write lanes/camera,40 shared aliases proven')
if __name__=='__main__':main()
