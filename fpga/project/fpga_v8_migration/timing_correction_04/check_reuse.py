"""Check inherited-script substitutions without executing flow or generation."""
import ast
from run_whole import HERE, M


def main():
    cases = [
        ('export_whole.py', 'export_whole.py', 'edits'),
        ('generate_bitstream.py', 'generate_bitstream.py', 'replacements'),
        ('verify_delivery.py', 'audit_acceptance.py', 'replacements'),
    ]
    for wrapper, inherited, variable in cases:
        tree = ast.parse((HERE / wrapper).read_bytes())
        assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == variable
                               for target in node.targets)]
        assert len(assignments) == 1, wrapper
        replacements = ast.literal_eval(assignments[0].value)
        path = M / 'timing_correction_02' / inherited
        source = path.read_bytes()
        for old, new in replacements:
            assert source.count(old) == 1, (wrapper, old)
            source = source.replace(old, new)
        compile(source, str(path), 'exec')
        print('PASS exact substitutions and transformed syntax:', wrapper, flush=True)


if __name__ == '__main__':
    main()
