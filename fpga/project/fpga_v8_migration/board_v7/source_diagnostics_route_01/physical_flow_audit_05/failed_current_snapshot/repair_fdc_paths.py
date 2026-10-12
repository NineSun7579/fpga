"""Archive the failed attempt and translate dump hierarchy to native FDC hierarchy."""
from prepare_route import *
from collections import Counter

def main():
    idle('repair_fdc_paths')
    guard = json.loads((HERE/'build01_guard.json').read_bytes())
    assert all(sha(Path(p)) == h for p,h in guard.items())
    archive = HERE/'failed_attempt_01'
    assert not archive.exists()
    archive.mkdir()
    hashes = {}
    for f in list(HERE.rglob('*')):
        if not f.is_file() or archive in f.parents or '__pycache__' in f.parts:
            continue
        rel = f.relative_to(HERE)
        target = archive/rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        hashes[str(rel)] = sha(f)
        assert sha(target) == hashes[str(rel)]
    (archive/'archive_hashes.json').write_text(json.dumps(hashes,indent=2))
    log = (HERE/'pnr_shell.log').read_bytes()
    errors = [l.decode('ascii','backslashreplace') for l in log.splitlines() if l.startswith(b'E:')]
    missing = [l.decode('ascii','backslashreplace') for l in log.splitlines() if b'Timing-4003' in l]
    assert not (HERE/'place_route').exists()
    save('failed_attempt_diagnosis.json', {'archive':str(archive),'log_bytes':len(log),'log_sha256':sha(HERE/'pnr_shell.log'),'errors':errors,'missing_pin_messages':missing,'route_generated':False,'timing_verified':False,'root_cause_candidate':'Exported slash hierarchy used in native FDC; native FDC uses dot hierarchy with final /port. Actual PDS rerun must validate every object.'})
    graph = json.loads((HERE/'actual/graph.json').read_bytes())
    mapping = {}
    fdc = HERE/'physical_constraints/clock.fdc'
    raw = fdc.read_bytes()
    def translate(match):
        names = match.group(1).decode('ascii').split()
        converted = []
        for pin in names:
            cell,port = pin.rsplit('/',1)
            assert cell in graph['primitives'], pin
            assert port in graph['primitives'][cell]['ports'],pin
            native = cell.replace('/','.')+'/'+port
            mapping[pin] = native
            converted.append(native)
        assert len(converted) == len(set(converted))
        return ('[get_pins {'+' '.join(converted)+'}]').encode('ascii')
    prefix,suffix = raw.split(b'# Exact real-object CDC complement and mailbox absolute budget',1)
    fixed = prefix+b'# Exact real-object CDC complement and mailbox absolute budget'+re.sub(rb'\[get_pins \{([^}]+)\}\]',translate,suffix)
    assert len(set(mapping.values())) == len(mapping)
    assert fixed.count(b'set_max_delay -datapath_only 15.238') == 4
    fdc.write_bytes(fixed)
    save('native_fdc_path_translation.json', {'source_sha256':hashes[str(Path('physical_constraints/clock.fdc'))],'fixed_sha256':sha(fdc),'mapping':mapping,'clock_groups_and_budget_unchanged':True,'rtl_and_ip_unchanged':True})
    for folder in ['compile','synthesize','device_map','place_route','constraint_check']:
        path = HERE/folder
        if path.exists():shutil.rmtree(path)
    for n in ['pnr_shell.log','pnr_result.json','pnr_launch.json','pnr_input_hashes.json']:
        (HERE/n).unlink(missing_ok=True)
    assert all(sha(Path(p)) == h for p,h in guard.items())
    print('Archived failure; translated',len(mapping),'actual pin names; fresh PNR required',flush=True)

if __name__ == '__main__':main()
