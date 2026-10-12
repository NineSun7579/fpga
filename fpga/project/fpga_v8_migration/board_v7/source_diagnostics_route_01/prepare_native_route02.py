from prepare_route import *

def main():
    out=HERE.parent/'source_diagnostics_route_02'
    assert not out.exists()
    out.mkdir()
    for folder in ['inputs','rtl','compile']:
        shutil.copytree(HERE/folder,out/folder)
    original=HERE/'synthesis_export/synthesis_dump.txt'
    (out/'synthesis_export').mkdir()
    shutil.copy2(original,out/'synthesis_export/synthesis_dump.txt')
    recovered=HERE/'physical_03/route01_recovered_syn.adf'
    assert recovered.exists() and not recovered.with_suffix('.adf.lock').exists()
    (out/'synthesize').mkdir()
    shutil.copy2(recovered,out/'synthesize/v7_sdt_top_syn.adf')
    g=json.loads((HERE/'actual/graph.json').read_bytes())
    exact=json.loads((HERE/'actual/exact_complement.json').read_bytes())
    assert not exact['errors']
    native={}
    def convert(pin):
        cell,port=pin.rsplit('/',1)
        assert cell in g['primitives'] and port in g['primitives'][cell]['ports'],pin
        native[pin]=cell.replace('/','.')+'/'+port
        return native[pin]
    def collection(pins):
        assert pins and len(pins)==len(set(pins))
        return '[get_pins -hierarchical {'+' '.join(convert(p) for p in sorted(pins))+'}]'
    lines=[];camera_manifest=[]
    for c in exact['cameras']:
        assert len(c['bundle_pairs'])==320
        launches=c['mailbox_launch_pins'];captures=c['capture_D'];complement=c['complement_launch_pins']
        assert len(launches)==len(captures)==320 and complement
        lines += ['set_false_path -from '+collection(complement)+' -to [get_clocks {ddrphy_sysclk}]',
                  'set_max_delay -datapath_only 15.238 -from '+collection(launches)+' -to '+collection(captures),
                  'set_false_path -hold -from '+collection(launches)+' -to '+collection(captures)]
        camera_manifest.append({'camera':c['camera'],'bundle_pairs':[[convert(a),convert(b)] for a,b in c['bundle_pairs']], 'complement_launch_pins':[convert(p) for p in complement]})
    constraints=out/'physical_constraints';constraints.mkdir()
    for p in (HERE/'physical_constraints').glob('*.fdc'):
        raw=p.read_bytes()
        if p.name=='clock.fdc':
            prefix=raw.split(b'# Exact real-object CDC complement and mailbox absolute budget',1)[0]
            raw=prefix+b'# Exact real-object CDC complement and mailbox absolute budget\n'+'\n'.join(lines).encode('ascii')+b'\n'
        (constraints/p.name).write_bytes(raw)
    project=(HERE/'project.pds').read_bytes()
    project=re.sub(rb'\(_gci_state \(_integer \d+\)\)',b'(_gci_state (_integer 0))',project)
    project=project.replace(b'(_command cmd_devmap',b'(_command cmd_devmap\n            (_option top_module (_string "v7_sdt_top"))')
    assert b'physical_03/route01_recovered_syn.adf' in project
    project=project.replace(b'physical_03/route01_recovered_syn.adf',b'recovered_actual_syn.adf')
    (out/'project.pds').write_bytes(project)
    manifest={'source_dump_sha256':sha(original),'copied_dump_sha256':sha(out/'synthesis_export/synthesis_dump.txt'),'recovered_db_source':str(recovered),'recovered_db_sha256':sha(recovered),'mapping':native,'cameras':camera_manifest,'pair_count':sum(len(c['bundle_pairs']) for c in camera_manifest),'native_syntax':'FDC dotted instance hierarchy, slash final port, get_pins -hierarchical; official UCE guide pp 72-73,106-107; runtime acceptance pending', 'runtime_validated':False,'protected_build01_manifest':str(HERE/'build01_guard.json')}
    assert manifest['pair_count']==1280
    assert len(native)==len(set(native.values()))
    (out/'native_constraint_manifest.json').write_text(json.dumps(manifest,indent=2))
    (out/'prepared_hashes.json').write_text(json.dumps({str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},indent=2))
    # Record the earlier conversion from archived bytes without pretending it was validated.
    old=HERE/'failed_attempt_01/physical_constraints/clock.fdc'
    curr=HERE/'physical_constraints/clock.fdc'
    (HERE/'physical_flow_audit_05/prior_conversion_manifest.json').write_text(json.dumps({'before_sha256':sha(old),'after_current_sha256':sha(curr),'conversion_script_sha256':sha(HERE/'repair_fdc_paths.py'),'runtime_validated':False,'new_derivation':str(out/'native_constraint_manifest.json')},indent=2))
    print(out,flush=True)

if __name__=='__main__':main()
