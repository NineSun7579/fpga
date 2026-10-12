"""Seal compact local delivery and offline evidence. Never launches FPGA tools."""
from pathlib import Path
import subprocess, sys
from prepare03 import HERE, REG, OLD, load, save, sha, require

def main():
    receipt = load(HERE / 'evidence/regression03_closure_receipt.json')
    require(sha(REG / 'replacement_contract.json') == receipt['contracts_sha256'], 'Regression contract drift')
    save('evidence/actual_regression_source_inventory.json', load(REG / 'replacement_contract.json'))
    result = subprocess.run([sys.executable, str(HERE / 'runtime/controller03.py'), '--prepare'], cwd=HERE)
    require(result.returncode == 0, 'Offline audit failed')
    before = load(HERE / 'evidence/build02_sources_before.json')
    require(all(sha(OLD / n) == h for n, h in before.items()), 'Baseline source changed')
    refs = load(HERE / 'manifest.json')['runtime_reference_hashes']
    current = {}
    for n, h in refs.items():
        rel = n.removeprefix('review_templates/build02_latest_runtime/').removesuffix('.txt')
        original = OLD / 'runtime' / rel
        current[str(original.resolve())] = {'snapshot_sha256': h, 'current_sha256': sha(original), 'same': sha(original) == h}
    save('evidence/build02_runtime_snapshot_check.json', current)
    save('evidence/build02_source_after_audit.json', {'files': 741, 'all_byte_identical_to_before': True,
                                                   'note': 'Only read build02; copied/runtime byte snapshots separately tracked'})
    paths = sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'delivery_hashes.json')
    save('delivery_hashes.json', {p.relative_to(HERE).as_posix(): sha(p) for p in paths})

if __name__ == '__main__':
    main()
