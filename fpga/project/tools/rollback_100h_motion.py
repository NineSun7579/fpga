"""Independent fixed-baseline SRAM rollback. --check only hashes and renders locally.

Execution requires a live read-only board ownership check; no viewer, driver,
PCIe, SSH configuration, RTL or IP changes are made by this tool.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import time
import types
import uuid

import program_100h_motion as programmer

BASELINE = Path(__file__).resolve().parents[1] / 'bitstream_six_recovery_20261002_192245/top.sbit'
BASELINE_SHA256 = 'c3f07533e37e77ab734d37a5a4ba4ed8ebc8af0841e09fa43f2dcc076f16a44a'
MANIFEST = Path(__file__).resolve().parents[1] / 'motion_100h/baseline_manifest.json'
require = programmer.require


def evidence():
    bit = BASELINE.resolve(strict=True)
    require(bit.is_file() and programmer.sha(bit) == BASELINE_SHA256,
            'Fixed baseline SHA256 mismatch')
    manifest = programmer.load(MANIFEST)
    require(manifest.get('baseline_sha256') == BASELINE_SHA256,
            'Baseline manifest SHA256 mismatch')
    saved = Path(manifest.get('baseline_bitstream', ''))
    require(saved.is_absolute() and saved.resolve(strict=True) == bit,
            'Baseline manifest path mismatch')
    return bit, {'manifest': str(MANIFEST.resolve()),
                 'manifest_sha256': programmer.sha(MANIFEST)}


def script(bit, mode, log):
    require(mode == 'sram', 'Rollback is SRAM only')
    text = programmer.script(bit, mode, log)
    marker = 'cfg_assign_file -file '
    require(text.count(marker) == 1, 'Shared SRAM renderer contract changed')
    guard = ('if {[string first "This device configure situation (done bit): 1" '
             '$motion_scan] < 0} {\n'
             '    error "MOTION_GUARD: initial target DONE is not asserted"\n}\n')
    return text.replace(marker, guard + marker, 1)


def parse_log(text, mode):
    stages, errors = programmer.parse_log(text, mode)
    scan = re.search(r'Executing : cfg_scan_chain\n(.*?)'
                     r'Executing : cfg_scan_chain successfully\.',
                     text.replace('\r\n', '\n'), re.S)
    stages['initial_device_done'] = bool(scan and stages['target_single'] and
        'This device configure situation (done bit): 1' in scan[1])
    return stages, errors


# Reuse the exact owned-process runner with a private globals mapping so the
# stricter rollback renderer/parser cannot change the candidate programmer.
_run_globals = dict(programmer.run.__globals__, script=script, parse_log=parse_log)
run = types.FunctionType(programmer.run.__code__, _run_globals,
                         'run', programmer.run.__defaults__, programmer.run.__closure__)


def board_quiesced():
    from board_host import board_host, ssh_connect
    from motion_board_session import Remote
    client = ssh_connect()
    try:
        remote = Remote(client)
        remote.text('test ! -d /sys/module/pango_pci_driver && '
                    'test ! -e /sys/bus/pci/devices/0002:21:00.0')
        node_present = remote.run('test -e /dev/pango_pci_driver', allowed=(0, 1))[0] == 0
        owners = remote.owners() if node_present else []
        viewers = remote.viewers()
        require(not owners and not viewers,
                'Board must be quiesced: DMA owners=%s viewers=%s' % (owners, viewers))
        return {'host': board_host(), 'device': '/dev/pango_pci_driver',
                'owners': owners, 'viewers': viewers, 'driver_unloaded': True,
                'endpoint_removed': True, 'device_present': node_present,
                'checked_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'method': 'live read-only Remote.owners/Remote.viewers'}
    finally:
        client.close()


def board_lock():
    from motion_board_session import LOG, Operation
    return Operation('baseline_sram_rollback', LOG / 'board_session.lock')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument('--execute', action='store_true')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--log-dir', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'log/100h_motion/rollback')
    args = parser.parse_args(argv)
    args.mode = 'sram'
    require(1 <= args.timeout <= 1800, '--timeout must be 1..1800')
    directory = args.log_dir.resolve() / ('run_' + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex)
    directory.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'blocked', 'operation': 'baseline_sram_rollback',
               'mode': 'sram', 'target': programmer.TARGET, 'port': programmer.PORT,
               'check_only': args.check, 'bit': str(BASELINE),
               'stages': {}, 'stage_errors': [], 'retained_directory': str(directory)}
    try:
        bit, proof = evidence()
        receipt.update(bit_sha256=BASELINE_SHA256, evidence=proof)
        if args.check:
            tcl = directory / 'program.tcl'
            tcl.write_text(script(bit, 'sram', directory / 'log/cfg.log'), encoding='utf-8')
            receipt.update(status='validated_only', tcl=str(tcl))
        else:
            with board_lock() as operation:
                receipt['board_session_receipt'] = str(operation.path)
                receipt['board_quiesce'] = board_quiesced()
                run(args, receipt, directory, bit, BASELINE_SHA256)
                require(receipt.get('status') == 'success' and
                        receipt.get('stages') and all(receipt['stages'].values()),
                        'Runner did not establish definitive rollback success')
    except Exception as error:
        receipt.update(status='blocked', error=str(error))
    finally:
        receipt['updated'] = time.strftime('%Y-%m-%d %H:%M:%S')
        for path in directory.rglob('*'):
            if path.is_file():
                receipt.setdefault('retained_sha256', {})[str(path.relative_to(directory))] = programmer.sha(path)
        (directory / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps(receipt, indent=2), flush=True)
    return 0 if receipt['status'] in ('success', 'validated_only') else 1


if __name__ == '__main__':
    sys.exit(main())
