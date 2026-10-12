"""Exhaustive registered-parent, device, options and immutable-source byte audit."""
import json
import re
from run_whole import BASE, WORK, HERE, sha, save, plan_binding, baseline_inventory
from accept_regressions import verify_regressions


def option_blocks(data):
    """Compare full options, including multiline values and quoted parentheses."""
    blocks = []
    for match in re.finditer(rb'\(_option\b', data):
        depth, quoted, escaped = 0, False, False
        for index in range(match.start(), len(data)):
            char = data[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == 92:
                    escaped = True
                elif char == 34:
                    quoted = False
            elif char == 34:
                quoted = True
            elif char == 40:
                depth += 1
            elif char == 41:
                depth -= 1
                if depth == 0:
                    blocks.append(data[match.start():index + 1])
                    break
        else:
            raise AssertionError('Unbalanced project option')
    assert blocks, 'Project has no build options'
    return blocks


def main():
    reviewed = verify_regressions(WORK)
    receipt = json.loads((WORK / 'binding_audit.json').read_bytes())
    expected_project, bindings, overrides, contents = plan_binding()
    project = (WORK / 'project.pds').read_bytes()
    assert receipt['parent_bindings'] == bindings and receipt['input_overrides'] == overrides
    pattern = rb'\(_file "([^"]+)"\s*\(_format ([^)]+)\)'
    generated = (b'compile/', b'synthesize/', b'device_map/', b'place_route/', b'report_timing/')
    def registrations(data):
        return [entry for entry in re.findall(pattern, data) if not entry[0].startswith(generated)]
    assert registrations(project) == registrations(expected_project)
    assert option_blocks(project) == option_blocks(expected_project)
    for token in [b'_family', b'_device', b'_speedgrade', b'_package']:
        part = rb'\(' + token + rb'\s+[^)]+\)'
        assert re.findall(part, project) == re.findall(part, expected_project)
    for target, data in contents.items():
        assert (WORK / target).read_bytes() == data and project.count(target.encode()) == 1
    # Every inherited RTL, including now-unregistered TC03 detector and TC04
    # adapter originals, remains byte-identical; only new parent copies differ.
    for folder in ['inputs', 'rtl']:
        for path in (BASE / folder).rglob('*'):
            if path.is_file():
                assert sha(WORK / path.relative_to(BASE)) == sha(path), str(path)
    frozen = {str(p.relative_to(BASE)): sha(p) for p in (BASE / 'inputs').rglob('*') if p.is_file()}
    assert len(frozen) == receipt['unchanged_input_files'] == 694
    assert receipt['unchanged_constraints'] == {p: h for p, h in frozen.items() if p.endswith('.fdc')}
    assert receipt['candidate_hashes'] == {'block_motion_detector_tc05': reviewed['candidate_sha256']}
    assert receipt['tc04_candidate_hashes'] == reviewed['tc04_candidate_sha256']
    assert b'rtl/block_motion_detector_tc03.v' not in project
    assert project.count(b'rtl/block_motion_detector_tc05.v') == 1
    declarations = []
    for token, fmt in registrations(project):
        path = WORK / token.decode('ascii')
        assert path.is_file(), str(path)
        if path.suffix == '.v':
            data = path.read_bytes()
            code = re.sub(rb'/\*.*?\*/|//[^\r\n]*', b'', data, flags=re.S)
            # V6 also registers the unreachable original detector declaration.
            # Preserve that baseline registration, but prohibit old instances.
            code = re.sub(rb'\bmodule\s+block_motion_detector(?:_tc01|_tc03)?\b', b'module unused_legacy_declaration', code)
            assert not re.search(rb'\bblock_motion_detector(?:_tc01|_tc03)?\b', code), str(path)
            if re.search(rb'\bmodule\s+block_motion_detector_tc05\b', data):
                declarations.append(token)
    assert declarations == [b'rtl/block_motion_detector_tc05.v']
    assert baseline_inventory() == json.loads((WORK / 'baseline_before.json').read_bytes())
    save('exact_binding_verification.json', {'passed': True, 'frozen_inputs': len(frozen),
         'candidate_hashes': receipt['candidate_hashes'], 'parent_bindings': bindings,
         'registrations': [(p.decode(), f.decode()) for p, f in registrations(project)],
         'complete_options': [b.decode('ascii') for b in option_blocks(project)],
         'device_and_all_options_verified': True, 'tc04_original_rtl_and_regression_hashes_preserved': True,
         'external_top_api_unchanged': True, 'six_camera_connections_unchanged': True,
         'motion_connections_unchanged': True, 'programming_performed': False})
    print('PASS V7 exhaustive registered binding, TC04 hashes and frozen V6', flush=True)


if __name__ == '__main__':
    main()
