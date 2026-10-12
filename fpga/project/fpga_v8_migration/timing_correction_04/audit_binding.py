"""Independent byte audit of V6 candidates and registered parent overrides."""
import json
import re
from run_whole import BASE, WORK, HERE, MODULES, sha, save, replace_instances


def main():
    receipt = json.loads((WORK / 'binding_audit.json').read_bytes())
    project = (WORK / 'project.pds').read_bytes()
    expected_project = (BASE / 'project.pds').read_bytes()
    for old, (new, oldpath) in MODULES.items():
        assert expected_project.count(oldpath.encode()) == 1
        expected_project = expected_project.replace(oldpath.encode(), ('rtl/' + new + '.v').encode())
    for oldpath, newpath in receipt['input_overrides'].items():
        assert expected_project.count(oldpath.encode()) == 1
        expected_project = expected_project.replace(oldpath.encode(), newpath.encode())
    # PDS rewrites timestamps and stage status. Compare every registered file,
    # its format, all build options and the target part independently of those.
    file_pattern = rb'\(_file "([^"]+)"\s*\(_format ([^)]+)\)'
    generated = (b'compile/', b'synthesize/', b'device_map/', b'place_route/', b'report_timing/')
    registrations = lambda data: [entry for entry in re.findall(file_pattern, data)
                                   if not entry[0].startswith(generated)]
    assert registrations(project) == registrations(expected_project)
    assert re.findall(rb'\(_option[^\r\n]*', project) == re.findall(rb'\(_option[^\r\n]*', expected_project)
    for token in [b'_family', b'_device', b'_speedgrade', b'_package']:
        pattern = rb'\(' + token + rb'\s+[^)]+\)'
        assert re.findall(pattern, project) == re.findall(pattern, expected_project)
    for relative, entry in receipt['parent_bindings'].items():
        data = (BASE / relative).read_bytes()
        assert sha(BASE / relative) == entry['before_sha256']
        counts = {}
        for old, (new, oldpath) in MODULES.items():
            data, count = replace_instances(data, old.encode(), new.encode())
            if count:
                counts[old] = count
        target = WORK / entry['target']
        assert target.read_bytes() == data and counts == entry['counts']
        assert sha(target) == entry['after_sha256']
        assert project.count(entry['target'].encode()) == 1
    frozen = {str(p.relative_to(BASE)): sha(p) for p in (BASE / 'inputs').rglob('*') if p.is_file()}
    assert len(frozen) == 694
    assert all(sha(WORK / p) == digest for p, digest in frozen.items())
    changed = {entry['target'] for entry in receipt['parent_bindings'].values()}
    assert all(sha(WORK / p.relative_to(BASE)) == sha(p)
               for p in (BASE / 'rtl').rglob('*') if p.is_file()
               and str(p.relative_to(BASE)).replace('\\', '/') not in changed)
    for old, (new, oldpath) in MODULES.items():
        target = 'rtl/' + new + '.v'
        assert sha(WORK / target) == sha(HERE / target) == receipt['candidate_hashes'][new]
        assert project.count(target.encode()) == 1
        assert oldpath.encode() not in project
    save('exact_binding_verification.json', {'passed': True, 'frozen_inputs': len(frozen),
         'candidate_hashes': receipt['candidate_hashes'], 'parent_bindings': receipt['parent_bindings'],
         'external_top_api_unchanged': True, 'six_camera_connections_unchanged': True,
         'motion_connections_unchanged': True, 'programming_performed': False})
    print('PASS exact V6 registered parent substitutions and frozen inputs', flush=True)


if __name__ == '__main__':
    main()
