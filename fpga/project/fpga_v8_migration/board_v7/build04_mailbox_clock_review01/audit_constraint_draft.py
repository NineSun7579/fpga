"""Independent offline check of exact exception inventory and preserved DDR clocks."""
import json,re,sys
from setup_review import HERE,B04,sha,save
sys.dont_write_bytecode=True
sys.path.insert(0,str(HERE/'analysis'))
from derive_new_constraints import coll
def main():
    base=(B04/'inputs/source/constraints/clock.fdc').read_bytes()
    draft=(HERE/'diagnostic_constraint_DRAFT/clock.fdc').read_bytes()
    proof=json.loads((HERE/'diagnostic_constraint_DRAFT/coverageproof.json').read_bytes())
    prefix=b'\n'.join(l for l in base.splitlines() if not l.lstrip().startswith(b'set_clock_groups '))+b'\n'
    assert draft.startswith(prefix)
    added=draft[len(prefix):].decode('ascii').splitlines()
    actual=[l for l in added if l and not l.startswith('#')]
    u={tuple(x) for x in proof['U']};b={tuple(x) for x in proof['carved_camera_to_ddr']}
    assert len(u)==368 and len(b)==4
    expected=[f'set_false_path -from [get_clocks {{{x}}}] -to [get_clocks {{{y}}}]' for x,y in sorted(u-b)]
    pairs=set();counts=[]
    for cam in proof['cameras']:
        cp=set(cam['compile']['leaves']);sp=set(cam['synthesis']['leaves']);mb=set(cam['compile_mailbox']);hp=set(cam['compile_host']);pp={tuple(x) for x in cam['physical_pairs']}
        launch={x for x,y in pp};capture={y for x,y in pp};comp=(cp-mb)|(sp-launch)
        assert comp==set(cam['complement']) and not comp&(mb|launch) and len(pp)==320
        assert not cam['compile']['unknown'] and not cam['synthesis']['unknown']
        pairs|=pp;ack=cam['ack_first']
        expected.extend(['set_false_path -from '+coll(comp)+' -to [get_clocks {ddrphy_sysclk}]','set_max_delay -datapath_only 15.238 -from '+coll(mb|launch)+' -to '+coll(hp|capture),'set_false_path -hold -from '+coll(mb|launch)+' -to '+coll(hp|capture),'set_false_path -from '+coll({ack['launch_CLK']})+' -to '+coll({ack['capture_D']})])
        counts.append({'camera':cam['camera'],'compile_leaves':len(cp),'synthesis_leaves':len(sp),'compile_mailbox_clock_lanes':len(mb),'compile_host_D_lanes':len(hp),'synthesis_unique_pairs':len(pp),'precise_complement':len(comp),'terminal_keepbufs':[x['cell'] for x in cam['compile']['transparent'] if x.get('disposition')=='identity_terminal_no_output_net_no_storage']})
    assert len(pairs)==1280 and actual==expected
    assert not any(x==y for x,y in u-b)
    clean=[l.strip() for l in base.decode('ascii').splitlines() if l.strip() and not l.lstrip().startswith('#')]
    free=next(l for l in clean if l.startswith('create_clock -name {free_clk}'))
    ddr=next(l for l in clean if l.startswith('create_generated_clock -name {ddrphy_sysclk}'))
    period=float(re.search(r'-period \{([^}]+)\}',free)[1]);mult=int(re.search(r'-multiply_by \{(\d+)\}',ddr)[1]);div=int(re.search(r'-divide_by \{(\d+)\}',ddr)[1]);freq=1000/period*mult/div
    assert freq==131.25
    preserved=[l for l in clean if l.startswith(('create_clock','create_generated_clock','set_clock_uncertainty','set_multicycle_path'))]
    assert all(l in draft.decode('ascii') for l in preserved)
    save('constraint_draft_exact_audit.json',{'status':'PASS_OFFLINE_DRAFT_INVENTORY_ONLY','runtime_STA_passed':False,'constraints_qualified':False,'original_clock_sha256':sha(B04/'inputs/source/constraints/clock.fdc'),'draft_clock_sha256':sha(HERE/'diagnostic_constraint_DRAFT/clock.fdc'),'U':368,'B':4,'retained_exact_clock_pairs':364,'new_clock_pair_falsepaths':0,'same_domain_clock_pair_falsepaths':0,'mailbox_budget_ns':15.238,'DDR_MHz_computed':freq,'free_period_ns':period,'DDR_multiply':mult,'DDR_divide':div,'all_original_clock_uncertainty_multicycle_lines_preserved':len(preserved),'exact_added_command_count':len(actual),'cameras':counts})
    print('draft exact audit:U368-B4=364;15.238ns;DDR131.25;no extra clock falsepath')
if __name__=='__main__':main()
