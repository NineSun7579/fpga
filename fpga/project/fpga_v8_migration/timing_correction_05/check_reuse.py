"""Read-only syntax, exact nested reuse and frozen V6 binding-plan checks."""
import ast
from run_whole import HERE, M, BASE, plan_binding, TC04_MODULES, sha
from reuse import EDITS, transformed, load, OLD_DETECTOR_HASH
import json
import re
from audit_binding import option_blocks


def main():
    for path in sorted(HERE.glob('*.py')):
        compile(path.read_bytes(), str(path), 'exec')
        print('PASS syntax:', path.name)
    for name in EDITS:
        path, source = transformed(name)
        assert OLD_DETECTOR_HASH not in source
        scope = load(name)
        assert callable(scope['main'])
        tree = ast.parse(source)
        # Check the second-level TC02 substitutions without invoking main(),
        # importing simulators or opening any PDS process.
        for variable, inherited in [('edits', 'export_whole.py'), ('replacements', 'generate_bitstream.py' if name == 'generate_bitstream.py' else 'audit_acceptance.py')]:
            assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == variable for t in node.targets)]
            if not assignments:
                continue
            assert len(assignments) == 1
            source2 = (M / 'timing_correction_02' / inherited).read_bytes()
            for old, new in ast.literal_eval(assignments[0].value):
                assert source2.count(old) == 1, (name, old)
                source2 = source2.replace(old, new)
            compile(source2, inherited, 'exec')
        print('PASS exact TC04 and nested TC02 reuse:', name)
    project, bindings, overrides, contents = plan_binding()
    assert option_blocks(project) == option_blocks((BASE / 'project.pds').read_bytes())
    # Also compile the untouched lower-level verifier and process-event adapter.
    for name in ['verify_delivery.py', 'finish_when_ready.py']:
        path = M / 'timing_correction_02' / name
        compile(path.read_bytes(), str(path), 'exec')
    assert bindings and len(bindings) == len(overrides) == len(contents)
    reviewed = json.loads((M / 'timing_correction_04/regression_acceptance.json').read_bytes())
    assert set(reviewed['candidate_sha256']) == TC04_MODULES
    assert all(sha(BASE / 'rtl' / (name + '.v')) == digest for name, digest in reviewed['candidate_sha256'].items())
    assert b'rtl/block_motion_detector_tc03.v' not in project
    assert project.count(b'rtl/block_motion_detector_tc05.v') == 1
    for token in re.findall(rb'\(_file "([^"]+\.v)"', project):
        relative = token.decode('ascii')
        data = (HERE / relative).read_bytes() if relative == 'rtl/block_motion_detector_tc05.v' else contents.get(relative)
        if data is None:
            data = (BASE / relative).read_bytes()
        code = re.sub(rb'/\*.*?\*/|//[^\r\n]*', b'', data, flags=re.S)
        code = re.sub(rb'\bmodule\s+block_motion_detector(?:_tc01|_tc03)?\b', b'module unused_legacy_declaration', code)
        assert not re.search(rb'\bblock_motion_detector(?:_tc01|_tc03)?\b', code), relative
    print('PASS frozen V6 plan, original TC04 six hashes, only TC05 detector instantiated; parents:', sorted(bindings))
    print('No PDS, regression, build-directory creation or acceptance claim performed.')


if __name__ == '__main__':
    main()
