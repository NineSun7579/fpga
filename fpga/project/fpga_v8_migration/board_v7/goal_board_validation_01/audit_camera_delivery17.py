"""Cross-check real camera capture artifacts against their SRAM program session."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Timestamp lacks timezone')
    return result


def bound_file(record, expected=None):
    path = Path(record['path']).resolve(strict=True)
    if expected is not None:
        require(path == expected.resolve(strict=True), 'Wrong capture artifact path')
    require(path.stat().st_size == record['bytes'] > 0 and sha(path) == record['sha256'],
            'Missing or changed artifact: ' + str(path))
    return path


def audit(directory):
    directory = directory.resolve(strict=True)
    handoff = json.loads((directory/'checked_bit_handoff.json').read_bytes())
    receipt_path = directory/'sram_program/receipt.json'
    receipt = json.loads(receipt_path.read_bytes())
    require(receipt['status'] == 'success' and receipt['mode'] == 'sram'
            and receipt['stages'] and all(receipt['stages'].values())
            and not receipt['stage_errors'], 'SRAM vendor stages did not succeed')
    require(receipt['bit_sha256'] == handoff['bit_sha256'] == sha(handoff['bit']),
            'SRAM receipt and checked bit disagree')
    require(receipt['handoff_sha256'] == sha(directory/'checked_bit_handoff.json'),
            'SRAM receipt does not bind the checked handoff')
    boot = json.loads((directory/'boot_binding.json').read_bytes())
    require(boot['real_boot_changed'] and boot['before'] != boot['after'] == receipt['boot_id'],
            'Program boot is not the confirmed new boot')
    ended = timestamp(receipt['ended_utc'])
    records = []
    for mode in ['six-camera', 'driving']:
        previous = None
        for number in [1, 2]:
            folder = directory/(mode+'_capture')
            metadata = folder/('screen_%d.json' % number)
            doc = json.loads(metadata.read_bytes())
            require(doc['capture_mode'] == mode, 'Wrong capture mode')
            require(doc['viewer']['boot_id'] == receipt['boot_id'], 'Capture belongs to another boot')
            require(timestamp(doc['captured_utc']) > ended, 'Capture predates successful SRAM program')
            bound_file(doc['inputs']['program_receipt'], receipt_path)
            bit = bound_file(doc['inputs']['bit'], Path(handoff['bit']))
            require(sha(bit) == receipt['bit_sha256'], 'Capture binds another bit')
            require(doc['viewer']['exe'] == '/userdata/detview-driving-demo/detview-driving-demo'
                    and doc['viewer']['exe_sha256'] ==
                    '72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703',
                    'Capture viewer differs from the verified ELF')
            args = doc['viewer']['argv']
            require(not any(arg == '--video' or arg.startswith('--video=') for arg in args),
                    'Video playback is not camera evidence')
            if mode == 'six-camera':
                require('--driving-demo' not in args and '--camera' not in args,
                        'Six-camera overview required')
                index = args.index('--prefer-hdmifull')
                require(args[index+1] == 'off', 'Six-camera mode selects HDMI-full')
            else:
                require('--driving-demo' in args and '--rotate-model' in args,
                        'Driving and model rotation required')
                index = args.index('--rotate-model')
                require(args[index+1] == 'trafficlight-16cls,wb_v4_combo', 'Wrong driving models')
            bound_file(doc['xwd'], folder/('screen_%d.xwd' % number))
            bound_file(doc['png'], folder/('screen_%d.png' % number))
            bound_file(doc['viewer_log'], folder/('viewer_%d.log' % number))
            if previous:
                require(doc['viewer'] == previous['viewer']
                        and doc['viewer_window'] == previous['viewer_window'],
                        'Viewer or window changed between captures')
                require((timestamp(doc['captured_utc']) - timestamp(previous['captured_utc'])).total_seconds() >= 10,
                        'Capture pair lacks the required observation interval')
            previous = doc
            records.append({'mode': mode, 'metadata': str(metadata), 'metadata_sha256': sha(metadata),
                            'png': doc['png'], 'captured_utc': doc['captured_utc']})
    return {'status': 'CAMERA_ARTIFACT_SESSION_BINDINGS_CHECKED', 'boot_id': receipt['boot_id'],
            'bit_sha256': receipt['bit_sha256'], 'program_receipt_sha256': sha(receipt_path),
            'captures': records, 'functional_pass': False, 'goal_complete': False,
            'remaining': 'Review actual images, complete frame/model/error logs, DONE evidence and motion observations.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.directory)
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))
