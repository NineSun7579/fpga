"""Plan locally by default. --execute enables a parent-reviewed SRAM trial.

Never automatically restore after failure. --restore uses an exact deployment
receipt, with the same graceful retirement gates as deployment.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'hardware_baseline'
ACTIVE = '73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100'
MODULE = '2631405b7bb1f8f0cabb5e219fbbef85ca72def7b4077f2dce16a53c6161462c'
ROLLBACK = 'fcb2e44d5b97d9857e72610d543300e747dcc4a822e8797bbf5d5418ddd01122'
IMAGE = '81eb0c05b40eff2887f1b81770fece6beafedc25f77fd1bbfbebe487e9dbb192'


def check(value, message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contained(path, root=ROOT):
    path = Path(path).resolve()
    path.relative_to(root.resolve())
    return path


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_module_build(receipt_path):
    """Bind a successful local build receipt to sources, ELF metadata and remote hash."""
    path = contained(receipt_path)
    build = json.loads(path.read_text())
    check(build.get('return_code') == 0, 'Module build did not succeed')
    source = contained(build['source'])
    check(set(build['sources']) >= {'pango_zc.c', 'pango_zc_uapi.h', 'Makefile'},
          'Module source receipt incomplete')
    for name, expected in build['sources'].items():
        check(digest(contained(source / name, source)) == expected, 'Module source changed: ' + name)
    module = contained(path.parent / 'pango_zc.ko')
    sha = digest(module)
    check(sha == build['module_sha256'], 'Module build hash mismatch')
    remote = build['remote'] + '/pango_zc.ko'
    check(re.fullmatch(r'/userdata/linaro/ov56401-[A-Za-z0-9_-]+/pango_zc\.ko', remote),
          'Module build remote path invalid')
    log = contained(path.parent / 'build.log').read_text()
    helper = load_module(ROOT / 'deploy_remote_helper.py', 'module_receipt_metadata')
    magic = helper.parse_modinfo(log, 'vermagic')
    check(re.search(r'^' + sha + r'\s+\*?pango_zc\.ko\s*$', log, re.MULTILINE),
          'Build log remote module hash mismatch')
    return {'receipt': str(path), 'receipt_sha256': digest(path),
            'module_sha256': sha, 'module_remote': remote, 'vermagic': magic,
            'sources': build['sources'], 'build_log_sha256': digest(path.parent / 'build.log')}


def validate_artifacts(module_build=None):
    identities = json.loads((BASE / 'copied_identity.json').read_text())['files']
    # Verify copied artifacts against their copy receipt without mutating them.
    for relative, expected in identities.items():
        path = contained(BASE / Path(relative.replace('\\', '/')), BASE)
        check(digest(path) == expected, 'Copied artifact changed: ' + relative)
    generated = json.loads((BASE / 'six_batch_bitstream_manifest.json').read_text())
    build = json.loads((BASE / 'six_batch_pds_manifest.json').read_text())
    for receipt in (generated, build):
        check(receipt.get('status') == 'finished' and receipt.get('return_code') == 0,
              'Hardware build/generation receipt is not successful')
    image = BASE / 'integrated_six_batch/project/generate_bitstream/top.sbit'
    timing = BASE / 'integrated_six_batch/project/place_route/top_timing_summary_after_hold_fix.txt'
    check(digest(image) == IMAGE == generated['sha256'], 'Candidate image identity mismatch')
    check(digest(timing) == generated['timing_sha256'], 'Timing receipt mismatch')
    check(b'All Constraints Met' in timing.read_bytes(), 'Timing constraints not met')
    for relative, expected in build['inputs'].items():
        if Path(relative.replace('\\', '/')).name == 'project.pds':
            continue  # PDS rewrites output metadata; copy receipt still verifies it.
        check(digest(contained(BASE / relative.replace('\\', '/'), BASE)) == expected,
              'Build input identity mismatch: ' + relative)
    check(digest(BASE / 'rollback/top.sbit') == ROLLBACK, 'Rollback image mismatch')
    selected = validate_module_build(module_build) if module_build else None
    if selected is None:
        local_module = ROOT / 'driver_build_1791563854046563100/pango_zc.ko'
        check(digest(local_module) == MODULE, 'Reviewed ARM64 module mismatch')
    artifacts = {'image_sha256': IMAGE, 'rollback_sha256': ROLLBACK,
            'module_sha256': selected['module_sha256'] if selected else MODULE, 'active_sha256': ACTIVE,
            'helper_sha256': digest(ROOT / 'deploy_remote_helper.py'),
            'entry_sha256': digest(ROOT / 'deploy_candidate.py'),
            'flash_helper_sha256': digest(BASE / 'flash_repo_latest.py')}
    if selected:
        artifacts['module_build'] = selected
    return artifacts


def validate_restore_receipt(receipt):
    check(receipt.get('schema') in (1, 2), 'Restore receipt schema invalid')
    stored = receipt['artifacts']
    selected = stored.get('module_build')
    current = validate_artifacts(selected['receipt'] if selected else None)
    # Restore executes the preserved remote helper, whose hash is checked on-board.
    # Local entry/helper revisions must not invalidate historical schema-1 receipts.
    for key in ('helper_sha256', 'entry_sha256'):
        check(re.fullmatch('[0-9a-f]{64}', stored.get(key, '')), 'Invalid stored helper/entry identity')
        current[key] = stored[key]
    check(stored == current, 'Local artifact identities mismatch with restore receipt')
    return current


def pds_preflight():
    check(os.name == 'nt', 'JTAG execution requires Windows/PDS')
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True,
                            text=True, check=True)
    names = {row[0].lower() for row in csv.reader(result.stdout.splitlines()) if row}
    conflicts = names & {'pds.exe', 'pds_shell.exe', 'cdt_cfg.exe'}
    check(not conflicts, 'PDS/programmer conflict: ' + ', '.join(sorted(conflicts)))
    check(Path(r'C:\pango\PDS_2022.2-SP6.4\bin\cdt_js.exe').is_file(), 'PDS JTAG server absent')


def flash(evidence, restore=False, module_build=None):
    pds_preflight()  # helper kills cdt_js only AFTER this conflict gate.
    validate_artifacts(module_build)
    image = BASE / ('rollback/top.sbit' if restore else
                    'integrated_six_batch/project/generate_bitstream/top.sbit')
    # Copy the verified image into this run's evidence; never alter archived files.
    import shutil
    prefix = 'restore' if restore else 'candidate'
    copy = evidence / (prefix + '.sbit')
    shutil.copyfile(image, copy)
    check(digest(copy) == (ROLLBACK if restore else IMAGE), 'Programming copy mismatch')
    tcl = evidence / (prefix + '.tcl')
    tcl.write_text('cfg_scan_chain\ncfg_assign_file -file {' + copy.as_posix() +
                   '} -device_index 0\ncfg_program -device_index 0\n', encoding='ascii')
    helper = load_module(BASE / 'flash_repo_latest.py', 'isolated_flash')
    helper.TCL = str(tcl)
    helper.LOG = str(evidence / (prefix + '.jtag.log'))
    helper.JSLOG = str(evidence / (prefix + '.jtag-server.log'))
    check(helper.main() == 0, 'SRAM programming failed; endpoint remains removed')


class Session:
    def __init__(self, evidence, receipt):
        self.evidence = evidence
        self.receipt = receipt
        # No board imports or connections occur on the plan path.
        self.board = load_module(BASE / 'board_ssh.py', 'deploy_board')
        self.client = self.board.connect()
        self.remote = receipt['remote']
        self.helper = self.remote + '/deploy_remote_helper.py'

    def save(self, phase, **fields):
        self.receipt.update(fields)
        self.receipt['phase'] = phase
        self.receipt.setdefault('history', []).append({'phase': phase, 'time_ns': time.time_ns()})
        target = self.evidence / 'receipt.json'
        tmp = target.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.receipt, indent=2), encoding='utf-8')
        tmp.replace(target)

    def rpc(self, action, **values):
        payload = json.dumps({'action': action, **values})
        command = 'python3 ' + shlex.quote(self.helper) + ' ' + shlex.quote(payload)
        rc, out, err = self.board.run(self.client, command, timeout=90, sudo=True)
        # Do not dump captured baseline environment into console/command logs.
        if rc:
            raise RuntimeError('Remote ' + action + ' failed: ' + err[-2000:])
        return json.loads(out)

    def upload_helper(self):
        with self.client.open_sftp() as sftp:
            sftp.put(str(ROOT / 'deploy_remote_helper.py'), self.helper)
        check(self.rpc('hash', path=self.helper)['sha256'] == self.receipt['artifacts']['helper_sha256'],
              'Remote lifecycle helper identity mismatch')

    def launch(self, baseline, restore=False):
        args = self.receipt['arguments']
        prefix = 'active' if restore else 'candidate'
        exe = baseline['identity']['exe'] if restore else args['viewer_remote']
        sha = ACTIVE if restore else args['viewer_sha256']
        env = dict(baseline['env'])
        argv = list(baseline['argv'])
        if not restore:
            argv[0] = exe
            if args['viewer_args_json'] is not None:
                argv = [exe] + json.loads(args['viewer_args_json'])
            env.update(json.loads(args['env_json']))
            env[args['feature_env']] = '1'
            if args['verify']:
                env[args['verify_env']] = '1'
        run = prefix + '-' + uuid.uuid4().hex
        paths = {key: self.remote + '/' + run + suffix for key, suffix in
                 {'config': '.launch.json', 'log': '.viewer.log', 'supervisor_log': '.supervisor.log',
                  'identity_file': '.identity.json', 'status': '.exit.json'}.items()}
        current = self.rpc('launch', exe=exe, sha256=sha, argv=argv, env=env,
                           cwd=baseline['cwd'], uid=baseline['uid'], gid=baseline['gid'],
                           groups=baseline['groups'], candidate=not restore, **paths)
        self.save(prefix + '_running', **{prefix: {'identity': current, 'env': env, **paths}})

    def restore(self):
        check(self.receipt['phase'] in ('candidate_running', 'smoke_stopped'),
              'Restore accepts only a known running or cleanly stopped candidate receipt')
        check(self.rpc('boot')['boot_id'] == self.receipt['baseline']['boot_id'],
              'Board rebooted; receipt is stale')
        check(self.rpc('hash', path=self.helper)['sha256'] == self.receipt['artifacts']['helper_sha256'],
              'Remote helper changed')
        self.rpc('verify_lock', remote=self.remote)
        candidate = self.receipt['candidate']
        if self.receipt['phase'] == 'candidate_running':
            self.save('stopping_candidate')
            self.rpc('stop', identity=candidate['identity'], env=candidate['env'], status=candidate['status'])
            self.save('candidate_retired')
        else:
            # Revalidate retirement on a later explicit smoke restore invocation.
            self.rpc('verify_retired', identity=candidate['identity'], status=candidate['status'])
        check(self.rpc('hash', path=self.receipt['original_module']['module'])['sha256'] ==
              self.receipt['original_module']['sha256'], 'Saved original module changed')
        check(self.rpc('hash', path=self.receipt['baseline']['identity']['exe'])['sha256'] == ACTIVE,
              'ACTIVE on-disk executable changed; no restore launch')
        pds_preflight()
        self.save('restore_removing_pci')
        self.rpc('remove')
        self.save('restore_unloading_candidate')
        self.rpc('module', operation='unload')
        self.save('restore_programming')
        selected = self.receipt['artifacts'].get('module_build')
        flash(self.evidence, restore=True, module_build=selected['receipt'] if selected else None)
        self.save('restore_inserting_original')
        self.rpc('module', operation='insert', **self.receipt['original_module'])
        self.rpc('rescan')
        self.launch(self.receipt['baseline'], restore=True)
        self.rpc('release_lock', remote=self.remote)
        self.save('restored')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--deploy', action='store_true')
    mode.add_argument('--restore', type=Path, metavar='RECEIPT')
    p.add_argument('--execute', action='store_true', help='Only use after parent review/authorization')
    p.add_argument('--viewer-remote')
    p.add_argument('--module-remote')
    p.add_argument('--module-build', type=Path, help='Reviewed local driver build manifest.json within this root')
    p.add_argument('--viewer-sha256', help='Full SHA256 from parent viewer build receipt')
    p.add_argument('--baseline-owner-pid', type=int, default=5650)
    p.add_argument('--feature-env', help='Exact viewer feature flag name from parent review')
    p.add_argument('--verify', action='store_true')
    p.add_argument('--verify-env', help='Exact verification flag name from parent review')
    p.add_argument('--env-json', default='{}', help='Explicit model/MVP environment overrides')
    p.add_argument('--viewer-args-json', help='JSON argument array; default reuses ACTIVE fullscreen/MVP args')
    p.add_argument('--seconds', type=int, help='1..300 second smoke, graceful q then leave stopped for explicit restore')
    return p


def validate_args(args):
    check(args.seconds is None or 1 <= args.seconds <= 300, '--seconds must be 1..300')
    env = json.loads(args.env_json)
    check(isinstance(env, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()),
          '--env-json must be a string-to-string object')
    if args.viewer_args_json is not None:
        argv = json.loads(args.viewer_args_json)
        check(isinstance(argv, list) and all(isinstance(x, str) for x in argv), '--viewer-args-json must be string array')
    if args.restore:
        check(args.module_build is None, 'Restore selects module build from stored receipt')
        contained(args.restore)
        return
    if args.execute:
        check(args.deploy, 'Execution requires explicit --deploy or --restore')
        for key in ('viewer_remote', 'module_remote', 'viewer_sha256', 'feature_env'):
            check(getattr(args, key), 'Execution requires --' + key.replace('_', '-'))
        check(re.fullmatch('[0-9a-f]{64}', args.viewer_sha256), 'Expected full candidate viewer SHA256')
        check(args.viewer_sha256 != ACTIVE, 'Candidate viewer must differ from ACTIVE')
        for path in (args.viewer_remote, args.module_remote):
            check(path.startswith('/userdata/linaro/ov56401-') and '..' not in Path(path).parts,
                  'Candidate paths must be isolated /userdata/linaro/ov56401-* paths')
        check(args.baseline_owner_pid > 1, 'Invalid baseline PID')
        for name in (args.feature_env, args.verify_env if args.verify else None):
            check(name is None or re.fullmatch('[A-Z][A-Z0-9_]*', name), 'Invalid environment flag')
        check(not args.verify or args.verify_env, '--verify requires --verify-env')


def main(argv=None):
    args = parser().parse_args(argv)
    validate_args(args)
    receipt = json.loads(contained(args.restore).read_text()) if args.restore else None
    artifacts = validate_restore_receipt(receipt) if receipt else validate_artifacts(args.module_build)
    if args.module_build and args.module_remote:
        check(args.module_remote == artifacts['module_build']['module_remote'], 'Module remote differs from build receipt')
    if not args.execute:
        if args.restore:
            check(receipt['phase'] in ('candidate_running', 'smoke_stopped'),
                  'Restore plan requires a known candidate state')
        print(json.dumps({'mode': 'LOCAL PLAN ONLY; no SSH/JTAG', 'artifacts': artifacts,
                          'operation': 'restore' if args.restore else 'deploy',
                          'arguments': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                          'sequence': ['verify identities and sole owner; back up original module on userdata',
                                       'X11 PID-owned q; wait exit, no owner and module refcnt=0',
                                       ('unbind/remove PCI; unload candidate; program rollback SRAM' if args.restore else
                                        'unbind/remove PCI; program verified SRAM image; unload old module'),
                                       'insert selected module BEFORE rescan; bind if probe did not auto-bind',
                                       'launch isolated candidate; record real PID/device owner',
                                       'optional smoke stops gracefully; explicit receipt-based restore only'],
                          'failure': 'Stop at failed gate; no signal or automatic restoration'}, indent=2))
        return 0
    pds_preflight()
    stamp = str(time.time_ns())
    evidence = ROOT / ('deploy_' + stamp)
    evidence.mkdir()
    lock = ROOT / 'deploy.execute.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    session = None
    try:
        if args.restore:
            receipt = json.loads(contained(args.restore).read_text())
            check(receipt.get('schema') in (1, 2) and
                  re.fullmatch('/userdata/linaro/ov56401-deploy-[0-9]+', receipt.get('remote', '')),
                  'Restore receipt schema/remote path invalid')
            check(receipt['artifacts'] == artifacts, 'Local artifact/helper identity changed since receipt')
            session = Session(evidence, receipt)
            session.restore()
        else:
            receipt = {'schema': 2, 'remote': '/userdata/linaro/ov56401-deploy-' + stamp,
                       'artifacts': artifacts,
                       'arguments': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                       'phase': 'preflight'}
            session = Session(evidence, receipt)
            session.save('preflight')
            # Bootstrap read-only snapshot/helper from stdin without any staging mutation.
            helper_source = (ROOT / 'deploy_remote_helper.py').read_text()
            def bootstrap(action, **values):
                code = helper_source.split("if __name__ == '__main__':", 1)[0] + '\nprint(json.dumps(dispatch(' + repr({'action': action, **values}) + ')))\n'
                command = 'python3 -c ' + shlex.quote(code)
                rc, out, err = session.board.run(session.client, command, timeout=30, sudo=True)
                check(rc == 0, 'Bootstrap ' + action + ' failed: ' + err[-2000:])
                return json.loads(out)
            baseline = bootstrap('snapshot', pid=args.baseline_owner_pid, active_sha=ACTIVE)
            module_sha = artifacts['module_sha256']
            check(bootstrap('hash', path=args.module_remote)['sha256'] == module_sha, 'Remote candidate module mismatch')
            check(bootstrap('hash', path=args.viewer_remote)['sha256'] == args.viewer_sha256, 'Remote viewer mismatch')
            compatibility = bootstrap('module_compatible', module=args.module_remote, sha256=module_sha)
            if args.module_build:
                check(compatibility['vermagic'] == artifacts['module_build']['vermagic'],
                      'Remote module vermagic differs from build receipt')
            original = bootstrap('stage', remote=receipt['remote'])
            session.save('original_backed_up', baseline=baseline, original_module=original,
                         module_compatibility=compatibility)
            session.upload_helper()
            session.save('stopping_baseline')
            session.rpc('stop', identity=baseline['identity'], env=baseline['env'])
            session.save('baseline_retired')
            pds_preflight()
            session.save('removing_pci')
            session.rpc('remove')
            session.save('pci_removed')
            session.rpc('verify_retired')
            session.save('programming_candidate')
            flash(evidence, module_build=args.module_build)
            session.save('unloading_original')
            session.rpc('module', operation='unload')
            session.save('inserting_candidate')
            session.rpc('module', operation='insert', module=args.module_remote, sha256=module_sha)
            session.rpc('rescan')
            session.launch(baseline)
            if args.seconds:
                for _ in range(args.seconds):
                    time.sleep(1)
                candidate = receipt['candidate']
                session.save('stopping_smoke')
                session.rpc('stop', identity=candidate['identity'], env=candidate['env'], status=candidate['status'])
                session.save('smoke_stopped')
        print('Receipt:', evidence / 'receipt.json')
    except Exception as exc:
        if session:
            # Preserve the failing phase so an unknown state cannot pass restore gates.
            session.save(session.receipt['phase'], failure=str(exc))
        print('Stopped without automatic recovery:', str(exc), file=sys.stderr)
        print('Inspect receipt and state; uncertain lease requires separate recovery review.', file=sys.stderr)
        return 1
    finally:
        if session:
            session.client.close()
        lock.unlink()
    return 0


if __name__ == '__main__':
    sys.exit(main())
