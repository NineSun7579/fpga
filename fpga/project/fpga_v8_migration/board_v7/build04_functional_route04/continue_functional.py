"""Fresh official full-crossing budget build, then physical qualification."""
import controller as f
from pathlib import Path
import sys,json,re,shutil

def run():
    r=f.r;w=f.E/'functional_candidate01';r.W=w
    w.mkdir()
    for name in ['rtl','inputs','constraints_live']:
        shutil.copytree(f.REBUILD/'candidate02'/name,w/name)
    shutil.copy2(f.REBUILD/'candidate02/project.pds',w/'project.pds')
    hashes=json.loads((f.REBUILD/'sourcehash.json').read_bytes())
    assert hashes['count']==741 and hashes['registered']==186
    for path,hv in hashes['hashes'].items():assert r.sha(w/path)==hv
    f.save('functional_source_binding.json',hashes)
    # Original official compile derivation includes all 17 mailbox words and 512 D bits.
    deriv=json.loads((f.OLD/'compile02_constraint_derivation.json').read_bytes())
    base=[l for l in (r.F/'constraints/clock.fdc').read_text('ascii').splitlines() if 'get_pins -hierarchical' not in l]
    for row in deriv['rows']:
        ack=row['ack']
        base+=['set_false_path -from '+f.coll(row['complement'])+' -to [get_clocks {ddrphy_sysclk}]',
            'set_max_delay -datapath_only 15.238 -from '+f.coll(row['mailbox'])+' -to '+f.coll(row['host']),
            'set_false_path -hold -from '+f.coll(row['mailbox'])+' -to '+f.coll(row['host']),
            'set_false_path -from '+f.coll({ack['launch_CLK']})+' -to '+f.coll({ack['capture_D']})]
    (w/'constraints_live/clock.fdc').write_text('\n'.join(base)+'\n',encoding='ascii')
    f.save('full_compile_constraint_binding.json',dict(derivation_sha256=r.sha(f.OLD/'compile02_constraint_derivation.json'),clock_sha256=r.sha(w/'constraints_live/clock.fdc'),budget_ns=15.238,all_signature_included=True,U364=deriv['U364'],no_new_setup_falsepath=True))
    r.tool('functional_compile',r.ARCH+r.constraints()+'compile -force_to_run -top_module v7_sdt_top\n',w,'compile')
    cg=r.export('functional_compile_native',w/'compile/v7_sdt_top_comp.adf')
    old=json.loads((f.REBUILD/'compile_native/analysis/graph.json').read_bytes())
    for key in ['pin_net','netpins','net_aliases']:assert cg[key]==old[key]
    r.tool('functional_syn',r.ARCH+r.constraints()+'synthesize -force_to_run -ads\n',w,'synthesize')
    sg=r.export('functional_syn_native',w/'synthesize/v7_sdt_top_syn.adf')
    pairs=f.actual_pairs(sg)
    # Fresh compile owns timing CDB; no CDB/phase rewriting or late replacement.
    r.tool('functional_map',r.ARCH+'add_constraint {'+(w/'constraints_live/production60.lcf').as_posix()+'}\ndev_map -force_to_run -input_db_file {'+(w/'synthesize/v7_sdt_top_syn.adf').as_posix()+'} -override_pcf TRUE -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0\n',w)
    mg=r.export('functional_map_native',w/'device_map/v7_sdt_top_map.adf')
    mp=f.actual_pairs(mg)
    f.save('functional_complete_physical_graph.json',dict(logical_mailbox_bits=2048,actual_physical_pairs=len(mp),rows=mp,graph_sha256=r.sha(f.E/'functional_map_native/analysis/graph.json'),note='Complete exported graph retained; constant sharing is checked against source signature semantics, no fixed pair count qualification.'))
    result=f.route(w,mg,'functional_route01',True)
    if result['status']!='PASS_FUNCTIONAL_ROUTE':
        f.save('functional_route01/FAIL_PRESERVED.json',dict(result=result,bit=False,program=False))
        assert result['retention_pass'] and result['coverage_complete'] and result['DDR131_25'] and not result['old_camera_async'], 'Functional engineering coverage/retention failure requires source/constraint diagnosis'
        helpfile=f.E.parent.parent/'whole_candidate_v3_timing_route_01/pnr_help.log'
        helpraw=helpfile.read_bytes()
        flags=['-gplace_seed','-groute_seed','-enable_route_constraint_iterate','-route_constraint_iterate_times','-route_constraint_slack','-route_constraint_max_timing_path']
        assert all(option.encode() in helpraw for option in flags)
        for seed in range(2,5):
            options=f'-gplace_seed {seed} -groute_seed {seed} -enable_route_constraint_iterate -route_constraint_iterate_times 3 -route_constraint_slack 0 -route_constraint_max_timing_path 32'
            label=f'functional_route{seed:02d}'
            f.save(label+'_physical_correction.json',dict(previous_route=result['route'],previous_minima=result['minima_ns'],critical_paths=result['critical_paths'],rationale='Native negative slack; change placement/route seeds and enable vendor route-constraint optimization with unchanged clocks, sites and 15.238 budget',options=options,official_help_sha256=r.sha(helpfile)))
            result=f.route(w,mg,label,True,options)
            if result['status']=='PASS_FUNCTIONAL_ROUTE':break
        if result['status']!='PASS_FUNCTIONAL_ROUTE':
            f.save('FUNCTIONAL_FAIL.json',dict(result=result,next='Remaining critical paths require targeted local placement/source correction',bit=False,program=False))
            return
    # Official project genbit stage already used by the native build03 delivery.
    official=f.E.parent/'source_diagnostics_timing_build_03/runtime/prepare_local_delivery.py'
    assert "'-run', 'gen_bit_stream'" in official.read_text('utf-8')
    assert not (w/'place_route').exists() and not (w/'generate_bitstream').exists()
    shutil.copytree(Path(result['route']).parent,w/'place_route')
    route=w/'place_route/v7_sdt_top_pnr.adf'
    assert r.sha(route)==result['route_sha256']
    f.save('official_genbit_entry_binding.json',dict(reference=str(official),reference_sha256=r.sha(official),stage='gen_bit_stream',route_sha256=r.sha(route),qualified_result_sha256=r.sha(Path(result['route']).parents[2]/'RESULT.json')))
    r.tool('functional_genbit',r.ARCH,w,'gen_bit_stream')
    assert r.sha(route)==result['route_sha256']
    for path,hv in hashes['hashes'].items():assert r.sha(w/path)==hv
    bits=list((w/'generate_bitstream').rglob('*.sbit'))
    assert bits and all(p.stat().st_size>0 for p in bits)
    f.save('BIT_MANIFEST.json',dict(status='PASS_FUNCTIONAL_SBIT',source_binding=hashes,route=str(route),route_sha256=r.sha(route),controller_sha256=r.sha(f.E/'controller.py'),continuation_sha256=r.sha(__file__),bits=[dict(path=str(p),sha256=r.sha(p),size=p.stat().st_size) for p in bits],program=False))

if __name__=='__main__':run()
