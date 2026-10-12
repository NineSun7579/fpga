"""Local exhaustive mapping proof and staged phase-aware FDC; no PDS calls."""
from pathlib import Path
import json, collections, subprocess, sys
import continue_fixed as cf
from run_native_fixed08 import OUT, ROOT, HERE, sha
from resume_exact09 import proof

def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2), encoding='utf8')

def main():
    analysis=OUT/'actual/analysis'
    baseline=ROOT/'native_probe_07/synthesize_actual/analysis'
    inputs=json.loads((OUT/'input_hashes.json').read_bytes())
    guard=json.loads((cf.BASE/'source_diagnostics_route_01/build01_guard.json').read_bytes())
    assert all(sha(HERE/p)==h for p,h in inputs.items())
    assert all(sha(Path(p))==h for p,h in guard.items())
    db=HERE/'synthesize/v7_sdt_top_syn.adf'
    dump=OUT/'actual/synthesis_export/synthesis_dump.txt'
    pending=json.loads((OUT/'new_synthesis_pending.json').read_bytes())
    export=json.loads((OUT/'export_new_syn_result.json').read_bytes())
    assert export['exit_code']==0 and not export['errors']
    current_db_verified=db.exists() and sha(db)==pending['after']
    # A different serial controller may already be rebuilding this work directory.
    # The historical export remains useful for local proof but cannot authorize PNR.
    m=json.loads((analysis/'manifest.json').read_bytes())
    o=json.loads((analysis/'objects.json').read_bytes())
    assert sha(dump)==m['source_dump_sha256']==o['dump_sha256']
    assert len(m['resolved'])==len(m['checks'])==2048 and not m['errors']
    assert {(r['camera'],r['logical_bit']) for r in m['resolved']}=={(c,b) for c in range(4) for b in range(512)}
    equivalence=proof(analysis,baseline)
    save('canonical_equivalence.json',equivalence)
    with (OUT/'repair_derive_exact_complement.log').open('wb') as log:
        r=subprocess.run([sys.executable,str(analysis/'derive_exact_complement.py')],stdout=log,stderr=subprocess.STDOUT)
    assert r.returncode==0, 'Inspect repair_derive_exact_complement.log'
    exact=json.loads((analysis/'exact_complement.json').read_bytes())
    assert not exact['errors']
    g=json.loads((analysis/'graph.json').read_bytes())
    oldg=json.loads((baseline/'graph.json').read_bytes())
    oldm=json.loads((baseline/'manifest.json').read_bytes())
    olde=json.loads((baseline/'exact_complement.json').read_bytes())
    cg=json.loads((ROOT/'native_probe_07/compile_actual/analysis/graph.json').read_bytes())
    phase=json.loads((OUT/'native_phase_mapping.json').read_bytes())
    rows=[];lines=[];mapping={}
    def native(pin):
        cell,port=pin.rsplit('/',1); value=cell.replace('/','.')+'/'+port
        mapping[pin]=value
        return value
    def coll(pins):
        assert pins
        return '[get_pins -hierarchical {'+' '.join(native(p) for p in sorted(pins))+'}]'
    for cam,c in enumerate(exact['cameras']):
        pre=f'source_diagnostics/cameras[{cam}].source/'
        rr=[r for r in m['resolved'] if r['camera']==cam]
        assert collections.Counter(r['mapping']['kind'] for r in rr)=={'register':330,'constant_zero':182}
        assert len(c['bundle_pairs'])==330 and not c['unknown_clock_sinks']
        cp=m['clock_provenance'][cam]
        assert cp==oldm['clock_provenance'][cam], 'Clock provenance changed'
        assert cp['launch'][-1]['top_ports']==[f'cmos{cam+1}_pclk']
        assert cp['capture'][-1]['drivers']==['ddr3/u_ddrphy_top/ddrphy_gpll/u_gpll/CLKOUT0']
        ph=phase['cameras'][cam]
        cl=set(ph['compile_mailbox_clock_pins']);cc=set(ph['compile_complement_clock_pins'])
        cd={ip+'/'+p for ip,r in cg['primitives'].items() if ip.startswith(pre+'host_bank[') for p,v in r['ports'].items() if p.startswith('D[') and v['direction']=='INPUT'}
        assert len(cl)==17 and len(cd)==512 and cc and not cl&cc
        launch=set(c['mailbox_launch_pins'])|cl; capture=set(c['capture_D'])|cd
        comp=set(c['complement_launch_pins'])|cc
        assert not launch&comp
        for selected,expected in [(launch,c['mailbox_launch_pins']),(capture,c['capture_D']),(comp,c['complement_launch_pins'])]:
            assert {p for p in selected if p.rsplit('/',1)[0] in g['primitives']}==set(expected)
        lines.extend(['set_false_path -from '+coll(comp)+' -to [get_clocks {ddrphy_sysclk}]',
            'set_max_delay -datapath_only 15.238 -from '+coll(launch)+' -to '+coll(capture),
            'set_false_path -hold -from '+coll(launch)+' -to '+coll(capture)])
        def cells(graph,leaf):return {n for n in graph['primitives'] if n.startswith(pre+leaf+'[')}
        def regs(graph,leaf):return {n for n in cells(graph,leaf) if graph['primitives'][n]['type'].startswith('GTP_DFF')}
        rows.append({'camera':cam,'logical_bits':512,'register_bits':330,'constant_zero_bits':182,
            'old_pairs':len(olde['cameras'][cam]['bundle_pairs']),'pairs':len(c['bundle_pairs']),
            'old_mailbox':len(cells(oldg,'mailbox')),'mailbox':len(cells(g,'mailbox')),
            'old_host':len(cells(oldg,'host_bank')),'host':len(cells(g,'host_bank')),
            'old_mailbox_dff':len(regs(oldg,'mailbox')),'mailbox_dff':len(regs(g,'mailbox')),
            'old_host_dff':len(regs(oldg,'host_bank')),'host_dff':len(regs(g,'host_bank')),
            'old_complement':len(olde['cameras'][cam]['complement_launch_pins']),
            'complement':len(c['complement_launch_pins']), 'all_launch':len(c['all_launch_pins']),
            'added_complement':sorted(set(c['complement_launch_pins'])-set(olde['cameras'][cam]['complement_launch_pins'])),
            'removed_complement':sorted(set(olde['cameras'][cam]['complement_launch_pins'])-set(c['complement_launch_pins'])),
            'retained_extra_mailbox':sorted(cells(g,'mailbox')-cells(oldg,'mailbox')),
            'mailbox_host_attributes':dict(collections.Counter(str(g['primitives'][p]['attributes']) for p in cells(g,'mailbox')|cells(g,'host_bank'))),
            'clock_provenance_unchanged':True,'compile_mailbox':17,'compile_capture':512})
    staged=OUT/'staged_actualmapping_constraints';staged.mkdir(exist_ok=True)
    for p in (HERE/'physical_constraints_native_08').glob('*.fdc'):
        raw=p.read_bytes()
        if p.name=='clock.fdc':
            marker=b'# Exact real-object CDC complement and mailbox absolute budget'
            assert raw.count(marker)==1
            raw=raw.split(marker)[0]+marker+b'\n'+'\n'.join(lines).encode('ascii')+b'\n'
        (staged/p.name).write_bytes(raw)
    original_inputs=json.loads((ROOT/'input_hashes.json').read_bytes())
    source_changes=[p for p,h in inputs.items() if p.startswith(('rtl','inputs')) and original_inputs.get(p)!=h]
    assert not source_changes, source_changes
    receipt={'syn_db_sha256':pending['after'],'current_syn_db_verified':current_db_verified,
        'dump_sha256':sha(dump),'map_db_sha256':json.loads((OUT/'dev_map_artifact.json').read_bytes())['sha256'],
        'export_reused':True,'export_success_receipt':export,'manifest_sha256':sha(analysis/'manifest.json'),
        'graph_sha256':sha(analysis/'graph.json'),'source_changes_since_fixed06':source_changes,
        'protected_count':len(guard),'protected_mismatches':[], 'cameras':rows,'physical_pairs':1320,
        'canonical_pairs':1280,'logical_bits':2048,'mapping':mapping,
        'staged_constraint_hashes':{p.name:sha(p) for p in staged.glob('*.fdc')},'runtime_validated':False}
    save('actualmapping_local_audit.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k in ['cameras','logical_bits','physical_pairs','syn_db_sha256','export_reused']},indent=2),flush=True)
    return receipt

if __name__=='__main__':main()
