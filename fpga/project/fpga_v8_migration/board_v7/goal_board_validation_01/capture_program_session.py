"""Actual programSession/v1 boundaries; default check is local and read-only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
from new_program_candidate import ALLOWED_BUILDS, VENDOR, load, require, sha, verify
from new_validate_board import vendor_parser

HERE = Path(__file__).resolve().parent
HELPER = HERE.parents[2] / 'tools' / 'board_host.py'
BOOT_COMMAND = "cat /proc/sys/kernel/random/boot_id && hostname && date -u +%Y-%m-%dT%H:%M:%S.%NZ"


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def inventory(root):
    return {p.resolve() for p in root.iterdir() if p.is_dir() and p.name.startswith('candidate_run_')}


def capture_boot(directory):
    # Lazy import: --check never loads SSH/device dependencies.
    sys.path.insert(0, str(HELPER.parent))
    from board_host import board_host, ssh_connect
    helper_digest = sha(HELPER)
    begin, tick = utc(), time.monotonic()
    client = ssh_connect()
    try:
        _, stdout, stderr = client.exec_command(BOOT_COMMAND, timeout=20)
        raw, err = stdout.read(), stderr.read()
        code = stdout.channel.recv_exit_status()
    finally:
        client.close()
    end, elapsed = utc(), time.monotonic() - tick
    (directory / 'program_boot_ssh.stdout').write_bytes(raw)
    (directory / 'program_boot_ssh.stderr').write_bytes(err)
    rows = raw.decode('utf-8').splitlines(keepends=True)
    evidence = dict(command=BOOT_COMMAND, local_started_utc=begin, local_completed_utc=end,
                    monotonic_elapsed_seconds=elapsed, uncertainty_seconds=elapsed,
                    exit_code=code, helper_sha256=helper_digest,
                    stdout_sha256=sha(directory / 'program_boot_ssh.stdout'),
                    stderr_sha256=sha(directory / 'program_boot_ssh.stderr'))
    save(directory / 'program_boot_transport.json', evidence)
    require(code == 0 and not err and len(rows) == 3, 'Boot SSH capture failed')
    import re
    require(re.fullmatch(r'[0-9a-fA-F-]{36}', rows[0].strip()) and rows[1].strip(), 'Invalid boot/hostname')
    remote = datetime.fromisoformat(rows[2].strip().replace('Z', '+00:00'))
    a, b = datetime.fromisoformat(begin).timestamp(), datetime.fromisoformat(end).timestamp()
    require(remote.utcoffset().total_seconds() == 0 and a - elapsed <= remote.timestamp() <= b + elapsed,
            'Remote/local UTC synchronization outside measured uncertainty')
    require(sha(HELPER) == helper_digest, 'SSH helper changed')
    (directory / 'program_boot_raw.txt').write_bytes(rows[0].encode('utf-8'))
    boot = dict(contract='programBootCapture/v1', collector=str(Path(__file__).resolve()),
                collector_sha256=sha(__file__), host=rows[1].strip(), ssh_host=board_host(),
                boot_id=rows[0].strip(), captured_utc=end, remote_utc=rows[2].strip(),
                raw_sha256=sha(directory / 'program_boot_raw.txt'), **evidence)
    save(directory / 'program_boot.json', boot)
    return boot


def bind_receipt(output, root, before, manifest, mdigest, pdigest):
    decoder, receipts = json.JSONDecoder(), []
    for index, line in enumerate(output.splitlines(keepends=True)):
        if line.lstrip().startswith('{'):
            try:
                obj, _ = decoder.raw_decode(''.join(output.splitlines(keepends=True)[index:]).lstrip())
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and 'retained_directory' in obj:
                receipts.append(obj)
    require(len(receipts) == 1, 'Exactly one stdout receipt required')
    receipt = receipts[0]
    directory = Path(receipt['retained_directory']).resolve(strict=True)
    require(inventory(root) - before == {directory} and directory.parent == root.resolve(),
            'Exactly one new candidate directory required')
    path = directory / 'receipt.json'
    digest = sha(path)
    require(load(path) == receipt, 'Stdout/original receipt mismatch')
    require(receipt.get('status') == 'success' and receipt.get('target') == 'PG2L100H' and
            receipt.get('mode') == 'sram' and receipt.get('check_only') is False and
            receipt.get('board_operation_verified') is False, 'Not an actual SRAM success receipt')
    expected = dict(candidate_id=manifest['candidate_id'], bit=manifest['bitstream']['path'],
                    bit_sha256=manifest['bitstream']['sha256'], bit_bytes=manifest['bitstream']['bytes'],
                    delivery_manifest_sha256=mdigest, owner_preflight_sha256=pdigest,
                    programmer_sha256=sha(VENDOR), limitations=manifest['limitations'])
    require(all(receipt.get(k) == v for k, v in expected.items()), 'Receipt binding mismatch')
    require(sha(manifest['bitstream']['path']) == expected['bit_sha256'] and
            Path(manifest['bitstream']['path']).stat().st_size == expected['bit_bytes'], 'Bit changed')
    require(sha(directory / 'validated_delivery.json') == mdigest, 'Retained delivery mismatch')
    logs = [Path(p).resolve(strict=True) for p in receipt['logs']]
    require(len(logs) == 3 and len(set(logs)) == 3 and all(p.is_relative_to(directory) for p in logs),
            'Original log provenance invalid')
    log_hashes = {str(p): sha(p) for p in logs}
    cfg = [p for p in logs if p.suffix.lower() == '.log' and 'cfg' in p.name.lower()]
    require(len(cfg) == 1, 'Unique cfg log required')
    parse, errors = vendor_parser()
    stages, failures = parse(cfg[0].read_bytes().decode('gb18030').replace('\r\n', '\n'), 'sram')
    require(stages and not failures and stages == receipt.get('stages') and
            all(v is True for v in stages.values()) and not receipt.get('stage_errors'), 'Raw stages incomplete')
    require(all(not errors.search(p.read_bytes().decode('gb18030')) for p in logs if p != cfg[0]),
            'Raw programmer log error')
    require(sha(path) == digest, 'Receipt changed while reading')
    require(log_hashes == {str(p): sha(p) for p in logs}, 'Logs changed while reading')
    return path, digest, log_hashes


def execute(manifest_path, preflight_path, root=HERE, boot_reader=capture_boot, runner=subprocess.run):
    manifest_path, preflight_path = manifest_path.resolve(strict=True), preflight_path.resolve(strict=True)
    manifest = load(manifest_path)
    require(manifest.get('candidate_id') in ALLOWED_BUILDS, 'Unexpected candidate ID')
    mdigest, pdigest = sha(manifest_path), sha(preflight_path)
    directory = root / ('program_session_run_' + uuid.uuid4().hex)
    directory.mkdir()
    command = [sys.executable, str(HERE / 'new_program_candidate.py'), '--execute',
               '--manifest', str(manifest_path), '--owner-preflight', str(preflight_path)]
    state = dict(collector=str(Path(__file__).resolve()), collector_sha256=sha(__file__),
                 recipe=command, delivery_manifest_sha256=mdigest, owner_preflight_sha256=pdigest)
    raw = directory / 'program_session_raw.txt'
    journal = directory / 'program_session_events.jsonl'
    def event(kind, **values):
        with journal.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(event=kind, **values)) + '\n')
    try:
        boot = boot_reader(directory)
        before = inventory(root)
        state.update(started_utc=utc(), started_monotonic=time.monotonic(), exit_code=None)
        require(0 <= (datetime.fromisoformat(state['started_utc']) -
                      datetime.fromisoformat(boot['captured_utc'])).total_seconds() <= 60, 'Stale boot capture')
        event('launch_boundary', **state)
        try:
            result = runner(command, cwd=HERE, capture_output=True,
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'})
            state['exit_code'] = result.returncode
            (directory / 'consumer.stdout').write_bytes(result.stdout)
            (directory / 'consumer.stderr').write_bytes(result.stderr)
        finally:
            state.update(completed_utc=utc(), completed_monotonic=time.monotonic())
            event('exit_boundary', **state)
        require(state['exit_code'] == 0, 'Consumer failed')
        path, digest, logs = bind_receipt(result.stdout.decode('utf-8'), root, before, manifest, mdigest, pdigest)
        state.update(receipt_sha256=digest, receipt_path=str(path), log_sha256=logs)
        require(sha(manifest_path) == mdigest and sha(preflight_path) == pdigest and sha(path) == digest,
                'Input/receipt changed')
        require(datetime.fromisoformat(state['started_utc']) < datetime.fromisoformat(state['completed_utc']) and
                state['completed_monotonic'] >= state['started_monotonic'], 'Invalid real boundaries')
        require(0 <= datetime.fromisoformat(state['started_utc']).timestamp() -
                load(preflight_path)['captured_unix'] <= 300, 'Invalid actual preflight chronology')
        raw.write_text('\n'.join(f'{k}={v}' for k, v in state.items()) + '\n', encoding='utf-8')
        state.update(contract='programSession/v1', raw_sha256=sha(raw), raw_source_sha256=sha(journal))
        save(directory / 'program_session.json', state)
        return 0, directory
    except Exception as error:
        state.update(contract='programSessionFailure/v1', error_type=type(error).__name__, error=str(error))
        event('collection_failure', **state)
        raw.write_text('\n'.join(f'{k}={v}' for k, v in state.items()) + '\n', encoding='utf-8')
        save(directory / 'program_session_failure.json', state)
        return 1, directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--owner-preflight', type=Path)
    args = parser.parse_args()
    if args.execute:
        if not args.manifest or not args.owner_preflight:
            parser.error('--execute requires explicit --manifest and --owner-preflight')
        code, directory = execute(args.manifest, args.owner_preflight)
        print(json.dumps(dict(exit_code=code, retained_directory=str(directory))))
        return code
    if args.manifest:
        verify(args.manifest.resolve(strict=True))
    print(json.dumps(dict(status='offline_check_only', programming_performed=False)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
