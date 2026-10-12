"""Read-only production audit; every generated artifact stays next to this file."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
MIG = HERE.parent
PROJECT = MIG.parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('live_hwc16', MIG / 'hwc16_layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


def independent_pack(w):
    co, ci, kh, kw = w.shape
    data = bytearray()
    for ob in range((co + 15) // 16 * 8):
        for ib in range((ci + 15) // 16):
            for y in range(kh):
                for x in range(kw):
                    for o in range(2):
                        for i in range(16):
                            oc, ic = ob * 2 + o, ib * 16 + i
                            data.append(int(w[oc, ic, y, x]) & 255 if oc < co and ic < ci else 0)
    return bytes(data)


def main():
    manifest = json.loads((MIG / 'legacy_hwc16/manifest.json').read_text())
    numeric = json.loads((MIG / 'numeric_layer/numeric.json').read_text())
    ops = {x['task_id']: x for x in numeric['operations'] if x['op'] == 'Conv'}
    sampled = {}
    frames = sorted((MIG / 'integer_evaluation30').glob('frame_*/report.json'))
    for f in frames:
        for t in json.loads(f.read_text())['trace']:
            if 'raw_accumulator_min' in t:
                r = sampled.setdefault(t['task_id'], [t['raw_accumulator_min'], t['raw_accumulator_max']])
                r[0] = min(r[0], t['raw_accumulator_min'])
                r[1] = max(r[1], t['raw_accumulator_max'])
    assets, bounds = [], []
    for c in manifest['convolutions']:
        tid = c['task_id']
        with np.load(MIG / 'numeric_layer' / ops[tid]['asset']) as n:
            w = n['weight'].astype(np.int64)
            bias = n['folded_bias_q16']
            pack = independent_pack(w)
            wf = MIG / 'legacy_hwc16' / c['files']['weight']['path']
            bf = MIG / 'legacy_hwc16' / c['files']['bias']['path']
            b = bf.read_bytes()
            expected_b = b''.join((int(bias[o]) & 0xffffffff).to_bytes(4, 'little') + bytes(4)
                                  if o < len(bias) else bytes(8)
                                  for o in range((len(bias) + 15) // 16 * 16))
            assets.append(dict(task_id=tid, shape=list(w.shape), weight_bytes=len(pack),
                               weight_matches=wf.read_bytes() == pack,
                               packer_matches=layout.pack_weights(w.astype(np.int8)) == pack,
                               bias_matches=b == expected_b,
                               weight_sha256=hashlib.sha256(wf.read_bytes()).hexdigest()))
            pos = np.maximum(w, 0).sum((1, 2, 3))
            neg = np.minimum(w, 0).sum((1, 2, 3))
            lo, hi = int(255 * neg.min()), int(255 * pos.max())
            abs_bound = int(255 * np.abs(w).sum((1, 2, 3)).max())
            # Exact extrema over independent u8 inputs to a full interior window.
            # Prefix ranges are also safe: partial sums contain subsets of terms.
            co, ci, kh, kw = w.shape
            generic_low, generic_high = -255*128*ci*kh*kw, 255*127*ci*kh*kw
            block_ranges = []
            for ib in range((ci + 15) // 16):
                block = w[:, ib * 16:(ib + 1) * 16]
                block_ranges.append([int(255 * np.minimum(block, 0).sum((1, 2, 3)).min()),
                                     int(255 * np.maximum(block, 0).sum((1, 2, 3)).max())])
            observed = sampled.get(tid)
            bounds.append(dict(task_id=tid, shape=list(w.shape), model_abs_bound=ops[tid]['raw_accumulator_abs_bound_max'],
                               recomputed_abs_bound=abs_bound, u8_exact_min=lo, u8_exact_max=hi,
                               exceeds_signed={str(bits): lo < -(1 << (bits-1)) or hi > (1 << (bits-1))-1
                                               for bits in (24,25,26)},
                               abs_bound_exceeds_signed={str(bits): abs_bound > (1 << (bits-1))-1 for bits in (24,25,26)},
                               arbitrary_int8_shape_min=generic_low,arbitrary_int8_shape_max=generic_high,
                               arbitrary_int8_shape_exceeds_signed={str(bits): generic_low < -(1 << (bits-1)) or generic_high > (1 << (bits-1))-1 for bits in (24,25,26)},
                               input16_block_min=min(r[0] for r in block_ranges),
                               input16_block_max=max(r[1] for r in block_ranges),
                               observed_30frames_min=observed[0] if observed else None,
                               observed_30frames_max=observed[1] if observed else None))
    hashes = {}
    for f in (PROJECT / 'source/npu').rglob('*.v'):
        if f.parent.name in {'conv', 'conv11_16', 'common', 'npu_top'}:
            hashes[str(f.relative_to(PROJECT)).replace('\\', '/')] = hashlib.sha256(f.read_bytes()).hexdigest()
    result = dict(scope='packing, independent u8 arithmetic bounds, sampled CPU trace ranges; no board acceptance',
                  assets=assets, bounds=bounds, sampled_frames=len(frames), source_sha256=hashes,
                  exact_exceed_layers={str(bits): [r['task_id'] for r in bounds if r['exceeds_signed'][str(bits)]] for bits in (24,25,26)},
                  conservative_exceed_layers={str(bits): [r['task_id'] for r in bounds if r['abs_bound_exceeds_signed'][str(bits)]] for bits in (24,25,26)},
                  arbitrary_int8_shape_exceed_layers={str(bits): [r['task_id'] for r in bounds if r['arbitrary_int8_shape_exceeds_signed'][str(bits)]] for bits in (24,25,26)})
    (HERE / 'asset_bounds.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Assets:', len(assets), 'all match:', all(x['weight_matches'] and x['packer_matches'] and x['bias_matches'] for x in assets))
    print('Exact range exceeds:', result['exact_exceed_layers'])
    print('Conservative abs bound exceeds:', result['conservative_exceed_layers'])
    print('Observed frames:', len(frames), 'range:', min(r[0] for r in sampled.values()), max(r[1] for r in sampled.values()))
    if not all(x['weight_matches'] and x['packer_matches'] and x['bias_matches'] for x in assets):raise SystemExit(1)


if __name__ == '__main__':
    main()
