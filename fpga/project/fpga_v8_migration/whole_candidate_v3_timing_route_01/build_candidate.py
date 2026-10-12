"""Isolated timing correction; frozen prepared v3 is the only build input."""
from pathlib import Path
import sys, json, hashlib, shutil, re, importlib.util, subprocess
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
M=HERE.parent
V3=M/'whole_candidate_v3'
TC=M/'timing_correction_01'
PDS=Path('C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,obj):
    p=HERE/name; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def idle(label):
    data=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,check=True).stdout
    (HERE/('processes_'+label+'.csv')).write_bytes(data)
    live=[x for x in data.splitlines() if re.match(rb'"(?:pds|pds_shell)\.exe"',x,re.I)]
    assert not live,('Global PDS busy; no kill/no wait',live)
def protected():
    paths={Path(p) for p in json.loads((V3/'artifacts/protected_before.json').read_bytes())}
    paths.update(Path(p) for p in json.loads((M/'whole_candidate_v2_route_01/protected_before.json').read_bytes()))
    for root in [V3,TC,M/'whole_candidate_v2_route_01']:
        paths.update(p for p in root.rglob('*') if p.is_file())
    return {str(p):sha(p) for p in sorted(paths)}
def verify_protected():
    before=json.loads((HERE/'protected_before.json').read_bytes())
    after={p:sha(Path(p)) for p in before}
    save('protected_after.json',after)
    changes={p:{'before':h,'after':after[p]} for p,h in before.items() if after[p]!=h}
    save('protected_changes.json',changes)
    assert not changes,changes
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec); spec.loader.exec_module(obj); return obj
def symbolic_schema(a,data):
    header=a.helpers.uncomment(a.audit.pin_header(data))
    schema={}
    for m in re.finditer(rb'\b(input|output|inout)\s+(?:(?:wire|reg|signed)\s+)*(\[[^\]]+\]\s*)?([^;]*?)(?=\binput\b|\boutput\b|\binout\b|\);|;)',header,re.S):
        direction=m[1].decode(); width=re.sub(rb'\s+',b'',m[2] or b'').decode()
        for name in re.findall(rb'\b([A-Za-z_]\w*)\b',m[3]):
            schema[name.decode()]=(direction,width)
    assert schema
    return schema
def main():
    assert not (HERE/'inputs').exists(),'Fresh candidate only'
    idle('before_prepare')
    save('protected_before.json',protected())
    pins=json.loads((V3/'artifacts/candidate_source_sha256.json').read_bytes())
    assert all(sha(V3/p)==h for p,h in pins.items()),'Prepared v3 manifest drift'
    for root in ['inputs','rtl','host','cooperative_host']:
        shutil.copytree(V3/root,HERE/root)
    shutil.copytree(V3/'baseline',HERE/'baseline')
    assert sum(p.is_file() for p in (HERE/'inputs').rglob('*'))==694
    hand=json.loads((TC/'parent_handoff.json').read_bytes())
    changes=[]
    for rule in hand['binding_replacements']:
        original=Path(rule['parent_reference'])
        assert sha(original)==rule['observed_sha256']
        rel=original.relative_to(V3)
        target=HERE/rel if rel.parts[0]=='rtl' else HERE/'rtl'/original.name
        data=original.read_bytes()
        snapshot=HERE/'original_snapshot'/rel
        snapshot.parent.mkdir(parents=True,exist_ok=True); snapshot.write_bytes(data)
        snapshot.chmod(0o444)
        old=rule['old_ascii'].encode(); new=rule['new_ascii'].encode()
        assert data.count(old)==rule['expected_occurrences']==1
        target.write_bytes(data.replace(old,new))
        changes.append({'original_source':str(original),'original_sha256':sha(original),
                        'readonly_original_snapshot':snapshot.relative_to(HERE).as_posix(),
                        'modified_candidate':target.relative_to(HERE).as_posix(),'modified_sha256':sha(target),
                        'exact_replacement':rule})
    for item in hand['add_registered_sources']:
        p=Path(item['file']); assert sha(p)==item['sha256']
        shutil.copyfile(p,HERE/'rtl'/p.name)
    pds=(V3/'project.pds').read_bytes()
    old=b'inputs/source/motion/motion_stream_adapter.v'
    assert pds.count(old)==1
    pds=pds.replace(old,b'rtl/motion_stream_adapter.v')
    anchor=b'                (_file "rtl/fpga_v8_reset_fault_guard.v"'
    assert pds.count(anchor)==1
    extra=b''.join(b'                (_file "rtl/'+Path(x['file']).name.encode()+b'"\n                    (_format verilog)\n                    (_timespec "2026-10-05T00:00:00")\n                )\n' for x in hand['add_registered_sources'])
    pds=pds.replace(anchor,extra+anchor)
    (HERE/'project.pds').write_bytes(pds)
    (HERE/'project_before_options.pds').write_bytes(pds)
    save('source_changes.json',changes)
    finalize(pds,hand)
def finalize(pds,hand):
    # Reuse strong original actual-byte top width / reset-guard chain audit,
    # redirecting every audit output to this candidate only.
    a=load('v3_preparation_audit',V3/'prepare_candidate.py'); a.HERE=HERE
    candidates={n:(HERE/'rtl'/(a.binding.RENAMES[n]+'.v')).read_bytes() for n in a.binding.NAMES}
    a.structural_audit(pds,candidates,{})
    report=json.loads((HERE/'artifacts/structural_audit.json').read_bytes())
    reached=set(report['reachable_modules'])
    assert {'block_motion_detector_tc01','ovreg_axil_decode_tc01','motion_stream_adapter'}<=reached
    assert not {'block_motion_detector','ovreg_axil_decode'}&reached
    # Exact parameter/port schemas must match originals, including adapter API.
    api={}
    for item in hand['add_registered_sources']:
        name=Path(item['file']).name; oldname=name.replace('_tc01','')
        old=next((HERE/'inputs/source').rglob(oldname)).read_bytes()
        new=(HERE/'rtl'/name).read_bytes()
        oldparams=a.parameters(old); newparams=a.parameters(new)
        assert oldparams==newparams
        oldschema=symbolic_schema(a,old)
        newschema=symbolic_schema(a,new)
        assert oldschema==newschema
        api[name]={'identical_parameters':True,'identical_port_schema':True,'ports':newschema}
    original=(HERE/'inputs/source/motion/motion_stream_adapter.v').read_bytes()
    modified=(HERE/'rtl/motion_stream_adapter.v').read_bytes()
    assert symbolic_schema(a,original)==symbolic_schema(a,modified)
    save('corrected_module_api_audit.json',api)
    frozen={p.relative_to(HERE).as_posix():sha(p) for root in ['inputs','rtl','host','cooperative_host','original_snapshot'] for p in sorted((HERE/root).rglob('*')) if p.is_file()}
    save('inputs_before.json',frozen)
    fdc=report['constraints_identical_to_v2']
    assert len([p for p in fdc if p.startswith('inputs/source/constraints/')])==6
    assert all(sha(V3/p)==h for p,h in frozen.items() if p.startswith('inputs/'))
    save('preparation.json',{'origin':str(V3),'frozen_input_files':694,'all_frozen_inputs_identical':True,'fdc_unchanged':fdc,'clock_mhz':131.25,'guard_binding_preserved':True,'protected_files':len(json.loads((HERE/'protected_before.json').read_bytes())),'top_width_checks':report['named_port_width_checks'],'top_bits':126,'pcb_gpio':112,'hsst_bits':14,'original_snapshot_separate_from_modified_source':True,'board_ready':False})
    verify_protected()
    print('Prepared isolated corrected v3:',report['named_port_width_checks'],'width checks; protected files unchanged',flush=True)
if __name__=='__main__':
    if sys.argv[1:]==['--finalize-audit']:
        finalize((HERE/'project.pds').read_bytes(),json.loads((TC/'parent_handoff.json').read_bytes()))
    else: main()
