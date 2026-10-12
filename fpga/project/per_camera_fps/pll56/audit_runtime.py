"""Offline exact runtime audit; no SSH, DMA or lifecycle actions."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('pll56_offline_compare', ROOT/'project/motion_scheduling/compare_experiment.py')
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    results = {}
    for path in args.directory.glob('*_observe.json'):
        document = json.loads(path.read_text(encoding='utf-8'))
        try:
            results[path.stem] = dict(status='exact_metrics_available', **compare.summarize(document))
        except Exception as exc:
            results[path.stem] = dict(status='exact_metrics_unavailable', reason=str(exc),
                partial=compare.audit.parse_observation(document))
    destination = args.directory/'exact_runtime_audit.json'
    destination.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(str(destination), flush=True)

if __name__ == '__main__':
    main()
