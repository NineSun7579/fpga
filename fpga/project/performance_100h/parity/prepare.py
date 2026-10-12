"""Local-only generation of isolated RKNN parity harnesses. Never connects to SSH."""
import hashlib
import json
from pathlib import Path
import shutil
from PIL import Image

HERE = Path(__file__).resolve().parent
PERF = HERE.parent
ROOT = PERF.parents[1]
PIN = 'f340608065fdb16c94d46b1160612aed597981b50b30f3e9b497ebd367cb5dc1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inventory(source):
    return {p.relative_to(source).as_posix(): sha(p.read_bytes())
            for p in sorted(source.rglob('*')) if p.is_file()}


def snapshot(files):
    # Same digest recipe as parent build_host.py.
    return sha(json.dumps(files, sort_keys=True).encode())


def main():
    candidate = PERF / 'candidate/detview/src'
    if sha((candidate / 'main.cpp').read_bytes()) != PIN:
        raise ValueError('Candidate no longer matches frozen f340 main.cpp')
    receipt = json.loads((PERF / 'builds/053c691e05d07408/receipt.json').read_text())
    if inventory(candidate) != receipt['source_sha256']:
        raise ValueError('Candidate differs from frozen 053c source inventory')
    manifest = {'schema': 1, 'status': 'prepared_only', 'board_actions': False,
                'candidate_original_build': receipt['snapshot_sha256'],
                'sdk_include': '/userdata/linaro/detview-todo-work/sdk',
                'completions_per_scene_per_harness': 3,
                'coordinate_space': '640x640 model input (gray114 pad y=80)',
                'assets': json.loads((PERF / 'model_assets.json').read_text()),
                'harnesses': {}, 'scenes': {}}
    block = (HERE / 'parity_block.cpp.inc').read_bytes()
    anchor = b'    const int rotateTest = args.indexOf("--rotate-selftest");'
    for kind in ('baseline', 'candidate'):
        original = PERF / kind / 'detview/src'
        files = inventory(original)
        dest = HERE / kind / 'src'
        if dest.exists():
            raise ValueError('Harness already exists; refusing to overwrite ' + str(dest))
        shutil.copytree(original, dest)
        data = (dest / 'main.cpp').read_bytes()
        if data.count(anchor) != 1:
            raise ValueError('Expected unique selftest insertion anchor')
        preparation = b''
        if kind == 'baseline':
            preparation = b'''        // Exact original DetViewController inferenceRequested padding loop.
        QImage infer(MODEL_W, MODEL_H, QImage::Format_RGB888);
        infer.fill(QColor(114, 114, 114));
        for (int y = 0; y < IMG_H; ++y)
            memcpy(infer.scanLine(y + 80), image.constScanLine(y), IMG_W * 3);
        image = infer;
'''
        generated = block.replace(b'        // PARITY_PREPARATION\n', preparation)
        (dest / 'main.cpp').write_bytes(data.replace(anchor, generated + b'\n' + anchor))
        harness_files = inventory(dest)
        manifest['harnesses'][kind] = {'source': str(dest.relative_to(HERE)),
            'original_source_sha256': files, 'source_sha256': harness_files,
            'original_snapshot_sha256': snapshot(files),
            'snapshot_sha256': snapshot(harness_files),
            'input_path': 'controller padded square' if kind == 'baseline' else 'raw RGB888 640x480'}
    scenes = [('candidate_cam1', PERF / 'candidate_ring1_unpaced.png', (0, 68, 640, 548)),
              ('bright_baseline_cam1', ROOT / 'log/100h_motion/baseline.png', (0, 60, 640, 540))]
    for name, source, box in scenes:
        if not source.exists():
            continue
        target = HERE / (name + '.png')
        with Image.open(source) as image:
            image.crop(box).convert('RGB').save(target)
        manifest['scenes'][name] = {'path': target.name, 'sha256': sha(target.read_bytes()),
            'source': str(source.relative_to(ROOT)), 'source_sha256': sha(source.read_bytes()),
            'crop_xyxy': box, 'dimensions': [640, 480],
            'limitation': 'Screenshot crop retains camera label / display overlays; identical bytes for both harnesses.'}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Prepared local harnesses and scenes; no board connection or build.')


if __name__ == '__main__':
    main()
