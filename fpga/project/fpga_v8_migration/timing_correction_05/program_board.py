"""Program the independently accepted V7 into SRAM using retained vendor guards."""
import importlib.util
import json
import time
import uuid
from types import SimpleNamespace
from run_whole import WORK, M, sha


def main():
    from verify_delivery import main as verify
    verify()
    manifest = json.loads((WORK / 'delivery_manifest.json').read_bytes())
    assert manifest['candidate_revision'] == 'V7'
    assert len(manifest['bitstreams']) == 1
    from pathlib import Path
    entry = manifest['bitstreams'][0]
    bit = Path(entry['path'])
    assert sha(bit) == entry['sha256'] and bit.stat().st_size == entry['bytes']
    path = M.parent / 'tools/program_100h_motion.py'
    spec = importlib.util.spec_from_file_location('vendor_programmer', path)
    vendor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vendor)
    directory = M / 'board_v7' / ('run_' + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True)
    receipt = {'status': 'started', 'target': 'PG2L100H', 'mode': 'sram',
               'bit': str(bit), 'bit_sha256': entry['sha256'],
               'delivery_manifest_sha256': sha(WORK / 'delivery_manifest.json'),
               'programmer_sha256': sha(path), 'board_operation_verified': False}
    try:
        vendor.run(SimpleNamespace(mode='sram', timeout=300), receipt, directory, bit, entry['sha256'])
        assert receipt['status'] == 'success' and all(receipt['stages'].values())
    except Exception as error:
        receipt['status'] = 'failed'
        receipt['error'] = str(error)
        raise
    finally:
        receipt['retained_directory'] = str(directory)
        (directory / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
