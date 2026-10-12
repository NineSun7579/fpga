"""Compare verified cumulative six-camera trials with identical execution configuration."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
from viewer.acceptance_summary import observed_window
from viewer.stereo_summary import latest_stereo_endpoint, validate_stereo


def load(path):
    receipt = json.loads(path.read_text())
    if receipt['status'] != 'success' or not receipt.get('restoration_verified'):
        raise ValueError('Trial or restoration failed: ' + str(path))
    configs = [e for e in receipt['events'] if e['state'] == 'comparison_configuration']
    windows = [e['result'] for e in receipt['events'] if e['state'] == 'acceptance_window']
    if len(configs) != 1 or len(windows) != 1:
        raise ValueError('One pinned configuration and accepted window required')
    summary = windows[0]
    log = path.parent/'candidate.redacted.log'
    if hashlib.sha256(log.read_bytes()).hexdigest() != receipt['log_sha256']:
        raise ValueError('Retained raw log changed')
    text = log.read_text()
    pairs = configs[0]['stereo_configuration']['pairs']
    endpoint = latest_stereo_endpoint(text, pairs)
    snapshots = [json.loads(line.split('[acceptance] ', 1)[1]) for line in text.splitlines() if line.startswith('[acceptance] ')]
    selected = [row for row in snapshots if row['epoch'] == summary['epoch'] and
                int(row['sample_begin_ns']) >= summary['first_sample_bounds_ns'][0] and
                int(row['sample_end_ns']) <= min(summary['last_sample_bounds_ns'][1], endpoint)]
    if len(selected) < 2:
        raise ValueError('No counter endpoints covered by stereo windows')
    original = summary
    summary = observed_window(selected[0], selected[-1], 120)
    summary['stereo'] = validate_stereo(text, pairs, summary['first_sample_bounds_ns'][0], summary['last_sample_bounds_ns'][1])
    summary['original_snapshot_range'] = [original['first_snapshot'], original['last_snapshot']]
    if summary['seconds_bounds'][0] < 120 or summary['delta']['failed'] or not summary['all_six_cameras_painted']:
        raise ValueError('Incomplete six-camera inference interval')
    return receipt, configs[0]['sha256'], summary


def compare(paths):
    trials = [load(path) for path in paths]
    if len({r['binary_sha256'] for r, _, _ in trials}) != 1 or len({c for _,c,_ in trials}) != 1:
        raise ValueError('Executable, camera/stereo/model configuration or environment differs')
    legacy = [(r,s) for r,_,s in trials if r['mode'] == 'legacy']
    native = [(r,s) for r,_,s in trials if r['mode'] == 'native']
    if not legacy or len(legacy) != len(native):
        raise ValueError('Equal numbers of verified legacy and native trials required')
    pairs = []
    for (a, x), (b, y) in zip(legacy, native):
        lo = y['completed_fps_bounds']['minimum_fps'] / x['completed_fps_bounds']['maximum_fps']
        hi = y['completed_fps_bounds']['maximum_fps'] / x['completed_fps_bounds']['minimum_fps']
        pairs.append(dict(legacy_operation=a['operation'], native_operation=b['operation'],
                          completed_fps_ratio_bounds=[lo,hi], legacy=x, native=y))
    ratios = [(p['completed_fps_ratio_bounds'][0]+p['completed_fps_ratio_bounds'][1])/2 for p in pairs]
    return dict(status='matched_observed_windows', pairs=pairs, median_completed_fps_ratio=statistics.median(ratios),
                every_pair_improved=all(p['completed_fps_ratio_bounds'][0] > 1 for p in pairs),
                binary_sha256=trials[0][0]['binary_sha256'], configuration_sha256=trials[0][1],
                six_camera_target_fps=[40,40,30,30,40,40],
                native_all_camera_targets_met=all(s['per_camera_paint_fps_bounds'][i]['minimum_fps'] >= target
                    for _,s in native for i,target in enumerate([40,40,30,30,40,40])),
                dma_metric='requested pixel/tag bytes only; excludes motion/control and total DDR traffic',
                scene_limitation='Same retained execution configuration; live scene changes are not automatically detectable.',
                 statistical_significance_claim=False)


def compare_stereo_worker(paths):
    trials = [load(path) for path in paths]
    def require(ok, reason):
        if not ok:
            raise ValueError(reason)
    require(len({receipt['binary_sha256'] for receipt, _, _ in trials}) == 1,
            'Stereo trials must use one frozen executable')
    require(len({receipt['mode'] for receipt, _, _ in trials}) == 1,
            'Stereo comparison must hold RKNN I/O mode fixed')
    configs = [next(row for row in receipt['events'] if row['state'] == 'comparison_configuration')
               for receipt, _, _ in trials]
    require(all('stereo_worker_configuration_sha256' in config for config in configs),
            'Stereo comparison configuration binding missing')
    require(len({config['stereo_worker_configuration_sha256'] for config in configs}) == 1,
            'Stereo/model/camera/environment configuration differs beyond worker mode')
    for (receipt, _, _), config in zip(trials, configs):
        require(receipt.get('stereo_worker') in ('sync', 'async'), 'Explicit stereo worker trial required')
        require(config['stereo_worker'] == ('1' if receipt['stereo_worker'] == 'async' else '0'),
                'Stereo worker environment differs from requested mode')
    controls = [(receipt, summary) for receipt, _, summary in trials if receipt['stereo_worker'] == 'sync']
    candidates = [(receipt, summary) for receipt, _, summary in trials if receipt['stereo_worker'] == 'async']
    require(bool(controls) and len(controls) == len(candidates), 'Equal numbers of sync and async trials required')
    pairs = []
    for (control, x), (candidate, y) in zip(controls, candidates):
        bounds = [y['completed_fps_bounds']['minimum_fps']/x['completed_fps_bounds']['maximum_fps'],
                  y['completed_fps_bounds']['maximum_fps']/x['completed_fps_bounds']['minimum_fps']]
        pairs.append(dict(sync_operation=control['operation'], async_operation=candidate['operation'],
                          completed_fps_ratio_bounds=bounds, sync=x, async_worker=y))
    return dict(status='matched_stereo_worker_observed_windows', pairs=pairs,
                median_completed_fps_ratio=statistics.median(sum(pair['completed_fps_ratio_bounds'])/2 for pair in pairs),
                every_pair_improved=all(pair['completed_fps_ratio_bounds'][0] > 1 for pair in pairs),
                binary_sha256=trials[0][0]['binary_sha256'], rknn_io_mode=trials[0][0]['mode'],
                configuration_sha256=configs[0]['stereo_worker_configuration_sha256'],
                acceleration_scope='stereo scheduling; separate from NPU allocator and FPGA/RGA gains',
                async_all_camera_targets_met=all(summary['per_camera_paint_fps_bounds'][i]['minimum_fps'] >= target
                    for _, summary in candidates for i, target in enumerate([40,40,30,30,40,40])),
                dma_metric='requested pixel/tag bytes only; excludes motion/control and total DDR traffic',
                statistical_significance_claim=False,
                scene_limitation='Same retained execution configuration; live scene variation remains.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipts', type=Path, nargs='+')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--comparison', choices=('npu_io', 'stereo_worker'), default='npu_io')
    args = parser.parse_args()
    result = compare_stereo_worker(args.receipts) if args.comparison == 'stereo_worker' else compare(args.receipts)
    text = json.dumps(result, indent=2) + '\n'
    if args.out:
        with args.out.open('x') as stream:
            stream.write(text)
    print(text)


if __name__ == '__main__':
    main()
