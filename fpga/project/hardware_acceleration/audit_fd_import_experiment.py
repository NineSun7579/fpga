"""Recheck downloaded FD-import arrays, tuple records and session retirement."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import numpy as np
import run_rknn


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(directory):
    outer = json.loads((directory/'receipt.json').read_text())
    require(outer['status'] == 'success' and outer.get('artifact_hashes_verified') is True,
            'Complete size/hash-verified download required')
    results = directory/'artifacts/results'
    report_path = results/'report.json'
    report = json.loads(report_path.read_text())
    require(report['status'] == 'isolated_hardware_comparison_complete' and
            report['timing_reference'] == 'native_io_single_copy', 'Incomplete isolated comparison')
    certs = report['certifications'] + report['timing_reference_certifications']
    pairs = report['comparisons']
    require(len(certs) == 8 and len(pairs) == 16, 'Four-fixture/16-pair coverage required')
    manifest = {item['name']: item for row in outer['events'] if row['state'] == 'artifacts'
                for item in row['files']}
    array_cache = {}
    run_cache = {}

    def local_path(remote_path):
        name = remote_path.rsplit('/', 1)[-1]
        require(name not in ('', '.', '..'), 'Invalid retained basename')
        path = results/name
        item = manifest.get('results/'+name)
        require(item is not None and path.is_file() and not path.is_symlink(), 'Missing retained artifact: '+name)
        require(path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], 'Artifact changed: '+name)
        return path

    def load_run(label):
        if label not in run_cache:
            path = local_path(label+'.receipt.json')
            run = json.loads(path.read_text())
            require(run['label'] == label and run['command']['returncode'] == 0, 'Failed benchmark run')
            rows = run['events']
            summary = next(row for row in rows if row['event'] == 'summary')
            frames = [row for row in rows if row['event'] == 'completion']
            output_elements = {row['attr']['index']: row['attr']['n_elems'] for row in rows
                               if row['event'] == 'tensor' and row['query'] == 2}
            require(len(output_elements) == 4 and sum(output_elements.values()) == 536000,
                    'Pinned model logical output sizes differ')
            require(summary['failed'] == 0 and len(frames) == summary['requested'] == summary['completed'],
                    'Incomplete inference accounting')
            snapshots = {}
            for row in rows:
                if row['event'] != 'output_snapshot':
                    continue
                path = local_path(row['path'])
                key = (row['completion'], row['output'])
                require(key not in snapshots, 'Duplicate output snapshot')
                if path not in array_cache:
                    data = path.read_bytes()
                    array = np.frombuffer(data, dtype='<f4')
                    require(row['encoding'] == 'little_endian_fp32' and len(data) == row['bytes'] and
                            len(data) % 4 == 0 and len(array) == output_elements[row['output']] and np.isfinite(array).all(),
                            'Array size/finite check failed')
                    array_cache[path] = (hashlib.sha256(data).hexdigest(), len(array))
                digest, elements = array_cache[path]
                require(digest == row['sha256'] and elements == output_elements[row['output']], 'Array snapshot binding changed')
                snapshots[key] = digest
            run_cache[label] = (run, frames, snapshots)
        return run_cache[label]

    total_values = 0
    for comparison in certs + pairs:
        require(comparison['certified'] and comparison['atol'] == 1e-6 and comparison['rtol'] == 1e-6,
                'Strict certificate missing')
        reference, ref_frames, ref_snapshots = load_run(comparison['reference'])
        candidate, candidate_frames, candidate_snapshots = load_run(comparison['candidate'])
        first = ref_frames[0]['detections']
        for frame in ref_frames + candidate_frames:
            require(frame['count'] == len(first) and frame['detections'] == first, 'Detection tuple changed')
        for run, snapshots in ((reference, ref_snapshots), (candidate, candidate_snapshots)):
            expected = {(metric['completion'], metric['output']) for metric in comparison['arrays']
                        if metric['label'] == run['label']}
            require(set(snapshots) == expected, 'Raw array coverage differs from certificate')
            for completion, output in expected:
                require(snapshots[completion, output] == ref_snapshots[1, output], 'Raw float bits differ')
        require(all(metric['max_abs'] == 0 and metric['bitwise_equal'] and metric['mismatched_elements'] == 0
                    for metric in comparison['arrays']), 'Certificate metrics differ from exact equality')
        total_values += sum(metric['elements'] for metric in comparison['arrays'])

    ns = {'__name__': 'offline_retirement_audit'}
    exec(compile('import json\nfrom pathlib import Path\ndef fd_import_restoration_proof' +
                 run_rknn.REMOTE.split('def fd_import_restoration_proof', 1)[1].split('\ndef acceleration', 1)[0],
                 '<current retirement guard>', 'exec'), ns)
    class Finished:
        def poll(self):
            return 0
    retirement = ns['fd_import_restoration_proof'](
        dict(backend='rknn', phase='experiment', candidates=['native_io_fd_import']), directory/'artifacts', Finished())
    require(retirement['safe'] and retirement['checked_logs'] == 20, 'Retirement coverage failed')
    counts = {key: sum(pair[key]['completed'] for pair in pairs) for key in ('baseline', 'candidate_summary')}
    require(counts == dict(baseline=800, candidate_summary=800), 'Timed successful completion counts differ')
    return dict(status='downloaded_array_tuple_and_retirement_audit_passed', operation=outer['operation'],
                report_sha256=sha(report_path), certificates=len(certs), timing_pairs=len(pairs),
                unique_finite_arrays=len(array_cache), compared_float_values=total_values,
                bitwise_equal=True, max_abs=0, exact_tuples=True, timed_completions=counts,
                retirement=retirement,
                mean_fps={key: statistics.mean(pair[key]['completed_fps'] for pair in pairs) for key in counts},
                median_fps_ratio=statistics.median(pair['completed_fps_ratio'] for pair in pairs),
                live_viewer_gain_proven=False, fpga_gain_proven=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    result = audit(args.directory)
    (args.directory/'downloaded_array_audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
