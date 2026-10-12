"""Copy immutable compiler inputs once; never copy old qmake output or binaries."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'viewer_build_recovered' / 'inputs'
PIN_MAIN = 'f91893ec34c014eb4f14a9631dc2ed4d2c248eb69a9e4411b307a05d3261516f'
PIN_DECODER = '02e52a2c828229d65637e84dffed0b97e662cf2a6db07bbd328f108508c6e4e4'
PIN_SDK = 'c48e11a6f41b451a5fd1e4ad774ea60252d3d94f78bee9b21ea3d21b21deba9a'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    paths = sorted(p for p in BASE.rglob('*') if p.is_file())
    frozen = {str(p.relative_to(BASE)): sha(p) for p in paths}
    assert len(paths) == 61, len(paths)
    assert frozen['main.cpp'] == PIN_MAIN
    assert frozen['rknn_api.h'] == PIN_SDK
    src = HERE / 'src'
    # Refuse to overwrite a previously prepared/edited source tree.
    assert not src.exists(), 'src already exists; use audit_native_candidate.py for validation'
    selected = [p for p in paths if p.suffix in ('.cpp', '.h', '.pro') and
                not p.name.startswith('moc_')]
    for path in selected:
        destination = src / path.relative_to(BASE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
    decoder = HERE.parent / 'host_acceleration' / 'raw_dfl_native.h'
    assert sha(decoder) == PIN_DECODER
    (src / decoder.name).write_bytes(decoder.read_bytes())
    assert frozen == {str(p.relative_to(BASE)): sha(p) for p in paths}
    (HERE / 'frozen_inputs_sha256.json').write_text(json.dumps(frozen, indent=2) + '\n')
    (HERE / 'copied_sources.json').write_text(json.dumps(
        {'base': str(BASE), 'source_files': [str(p.relative_to(BASE)) for p in selected],
         'native_decoder_sha256': PIN_DECODER, 'rknn_api_sha256': PIN_SDK}, indent=2) + '\n')
    print('COPIED', len(selected), 'compiler inputs; FROZEN', len(frozen), 'files unchanged')

if __name__ == '__main__':
    main()
