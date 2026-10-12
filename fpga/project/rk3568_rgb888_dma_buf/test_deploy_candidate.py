"""Local-only lifecycle tests. No SSH, X display, JTAG or board execution."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import deploy_candidate as deploy
import deploy_remote_helper as remote


class LocalContract(unittest.TestCase):
    def test_artifact_receipts(self):
        artifacts = deploy.validate_artifacts()
        self.assertEqual(artifacts['image_sha256'], deploy.IMAGE)
        self.assertEqual(artifacts['module_sha256'], deploy.MODULE)

    def test_default_and_explicit_deploy_are_local_plans(self):
        for argv in ([], ['--deploy'], ['--deploy', '--verify', '--seconds', '10']):
            with patch.object(deploy, 'Session', side_effect=AssertionError('SSH forbidden')), \
                 patch.object(deploy, 'pds_preflight', side_effect=AssertionError('JTAG forbidden')), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(deploy.main(argv), 0)
                self.assertIn('LOCAL PLAN ONLY', output.getvalue())

    def test_execution_requires_reviewed_paths_and_flags(self):
        args = deploy.parser().parse_args(['--execute', '--deploy'])
        with self.assertRaisesRegex(RuntimeError, 'viewer-remote'):
            deploy.validate_args(args)
        args = deploy.parser().parse_args([
            '--execute', '--deploy', '--viewer-remote', '/userdata/production/viewer',
            '--module-remote', '/userdata/linaro/ov56401-test/pango_zc.ko',
            '--viewer-sha256', 'a' * 64, '--feature-env', 'REVIEWED_FLAG'])
        with self.assertRaisesRegex(RuntimeError, 'isolated'):
            deploy.validate_args(args)

    def test_unknown_owner_cannot_send_q(self):
        q = {'identity': {'pid': 10}, 'env': {}}
        with patch.object(remote, 'same_process', return_value=True), \
             patch.object(remote, 'owners', return_value=[10, 11]), \
             patch.object(remote, 'send_q') as send:
            with self.assertRaisesRegex(RuntimeError, 'Unknown'):
                remote.stop(q)
            send.assert_not_called()

    def test_stale_pid_cannot_send_q(self):
        with patch.object(remote, 'same_process', return_value=False), \
             patch.object(remote, 'send_q') as send:
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                remote.stop({'identity': {'pid': 10}, 'env': {}})
            send.assert_not_called()

    def test_q_timeout_never_removes_or_signals(self):
        with patch.object(remote, 'same_process', return_value=True), \
             patch.object(remote, 'owners', return_value=[10]), \
             patch.object(remote, 'send_q') as send, \
             patch.object(remote, 'remove') as remove:
            with self.assertRaisesRegex(RuntimeError, 'Graceful q timeout'):
                remote.stop({'identity': {'pid': 10}, 'env': {}, 'timeout': 0})
            send.assert_called_once()
            remove.assert_not_called()

    def test_quarantine_reference_blocks_retirement(self):
        with tempfile.TemporaryDirectory() as folder:
            module = Path(folder)
            (module / 'refcnt').write_text('1\n')
            with patch.object(remote, 'MODULE', module), patch.object(remote, 'no_owner'):
                with self.assertRaisesRegex(RuntimeError, 'uncertain'):
                    remote.retired()
                (module / 'refcnt').write_text('0\n')
                remote.retired()

    def test_exit_transient_and_zombie_wait_for_clean_supervisor(self):
        expected = {'pid': 10, 'starttime': '123', 'sha256': 'hash', 'exe': '/viewer'}
        with tempfile.TemporaryDirectory() as folder:
            module = Path(folder)
            (module / 'refcnt').write_text('0')
            status = module / 'exit.json'
            calls = []
            def pause(_):
                calls.append(1)
                status.write_text(json.dumps({'identity': expected, 'returncode': 0}))
            with patch.object(remote, 'MODULE', module), \
                 patch.object(remote, 'same_process', return_value=True), \
                 patch.object(remote, 'owners', side_effect=[[10], [], []]), \
                 patch.object(remote, 'send_q'), \
                 patch.object(remote, 'process_state', side_effect=[
                     {'state': 'R', 'starttime': '123'}, {'state': 'Z', 'starttime': '123'}, None]), \
                 patch.object(remote, 'identity', side_effect=FileNotFoundError), \
                 patch.object(remote.time, 'sleep', side_effect=pause):
                self.assertTrue(remote.stop({'identity': expected, 'env': {},
                                             'status': str(status)})['retired'])
                self.assertTrue(calls)

    def test_true_pid_reuse_after_q_blocks_retirement(self):
        with patch.object(remote, 'same_process', return_value=True), \
             patch.object(remote, 'owners', return_value=[10]), \
             patch.object(remote, 'send_q'), \
             patch.object(remote, 'process_state', return_value={'state': 'Z', 'starttime': '456'}), \
             patch.object(remote, 'retired') as retired:
            with self.assertRaisesRegex(RuntimeError, 'PID reused'):
                remote.stop({'identity': {'pid': 10, 'starttime': '123'}, 'env': {}})
            retired.assert_not_called()

    def test_exit_missing_or_failed_status_cannot_retire(self):
        expected = {'pid': 10, 'starttime': '123'}
        with tempfile.TemporaryDirectory() as folder:
            status = Path(folder) / 'exit.json'
            for rc in (None, 1):
                if rc is not None:
                    status.write_text(json.dumps({'identity': expected, 'returncode': rc}))
                with patch.object(remote, 'same_process', return_value=True), \
                     patch.object(remote, 'owners', return_value=[10]), \
                     patch.object(remote, 'send_q'), \
                     patch.object(remote, 'process_state', return_value=None), \
                     patch.object(remote.time, 'sleep'), \
                     patch.object(remote.time, 'monotonic', side_effect=[0, 0, 2]), \
                     patch.object(remote, 'retired') as retired:
                    with self.assertRaisesRegex(RuntimeError, 'timeout|not clean'):
                        remote.stop({'identity': expected, 'env': {}, 'status': str(status), 'timeout': 1})
                    retired.assert_not_called()

    def test_launch_archives_stale_identity_before_supervisor(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            q = {'exe': '/viewer', 'sha256': 'new', 'uid': 1, 'gid': 1}
            for key in ('config', 'identity_file', 'status', 'supervisor_log'):
                q[key] = str(root / key)
            old = {'pid': 10, 'starttime': 'old', 'sha256': 'old', 'exe': '/viewer'}
            fresh = {**old, 'pid': 11, 'starttime': 'fresh', 'sha256': 'new'}
            for key in ('config', 'identity_file', 'status'):
                Path(q[key]).write_text(json.dumps(old))
            def start(*a, **kw):
                self.assertFalse(Path(q['identity_file']).exists())
                self.assertFalse(Path(q['status']).exists())
                Path(q['identity_file']).write_text(json.dumps(fresh))
            with patch.object(remote, 'no_owner'), patch.object(remote, 'digest', return_value='new'), \
                 patch.object(remote.os, 'chown', create=True), patch.object(remote.os, 'chmod'), \
                 patch.object(remote.subprocess, 'Popen', side_effect=start), \
                 patch.object(remote, 'same_process', side_effect=lambda x: x == fresh), \
                 patch.object(remote, 'owners', return_value=[11]):
                self.assertEqual(remote.launch(q), fresh)
            self.assertEqual(len(list(root.glob('*.previous-*'))), 3)

    def test_launch_refuses_to_archive_when_device_owned(self):
        with patch.object(remote, 'no_owner', side_effect=RuntimeError('Device owned')), \
             patch.object(remote.subprocess, 'Popen') as start:
            with self.assertRaisesRegex(RuntimeError, 'owned'):
                remote.launch({})
            start.assert_not_called()

    def test_retirement_revalidation_requires_matching_clean_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            status = Path(folder) / 'status.json'
            status.write_text(json.dumps({'identity': {'pid': 11}, 'returncode': 0}))
            with patch.object(remote, 'retired') as retired:
                with self.assertRaisesRegex(RuntimeError, 'not clean'):
                    remote.dispatch({'action': 'verify_retired', 'identity': {'pid': 10}, 'status': str(status)})
                retired.assert_not_called()

    def module_receipt(self, root):
        source = root / 'source'
        source.mkdir()
        sources = {}
        for name in ('pango_zc.c', 'pango_zc_uapi.h', 'Makefile'):
            (source / name).write_bytes(name.encode())
            sources[name] = deploy.digest(source / name)
        (root / 'pango_zc.ko').write_bytes(b'new module')
        sha = deploy.digest(root / 'pango_zc.ko')
        (root / 'build.log').write_text('  [ 42]  vermagic=6.1-rockchip SMP\n' + sha + '  pango_zc.ko\n')
        manifest = root / 'manifest.json'
        manifest.write_text(json.dumps({'return_code': 0, 'source': str(source), 'sources': sources,
                                        'module_sha256': sha, 'remote': '/userdata/linaro/ov56401-build-test'}))
        return manifest

    def test_dynamic_module_receipt_and_tampering(self):
        with tempfile.TemporaryDirectory(dir=deploy.ROOT) as folder:
            root = Path(folder)
            manifest = self.module_receipt(root)
            artifacts = deploy.validate_artifacts(manifest)
            self.assertNotEqual(artifacts['module_sha256'], deploy.MODULE)
            receipt = {'schema': 2, 'artifacts': artifacts}
            self.assertEqual(deploy.validate_restore_receipt(receipt), artifacts)
            (root / 'build.log').write_text('  [ 42]  vermagic=6.1-rockchip SMP\n' + '0' * 64 + '  pango_zc.ko\n')
            with self.assertRaisesRegex(RuntimeError, 'remote module hash'):
                deploy.validate_module_build(manifest)

    def test_module_receipt_source_change_and_outside_root_rejected(self):
        with tempfile.TemporaryDirectory(dir=deploy.ROOT) as folder:
            root = Path(folder)
            manifest = self.module_receipt(root)
            (root / 'source/pango_zc.c').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError, 'source changed'):
                deploy.validate_module_build(manifest)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                deploy.validate_module_build(Path(folder) / 'manifest.json')

    def test_schema1_restore_accepts_preserved_helper_identity(self):
        artifacts = deploy.validate_artifacts()
        artifacts['helper_sha256'] = 'a' * 64
        artifacts['entry_sha256'] = 'b' * 64
        self.assertEqual(deploy.validate_restore_receipt({'schema': 1, 'artifacts': artifacts}), artifacts)

    def test_wrong_kernel_module_fails_before_stopping_viewer(self):
        class Kernel:
            release = '6.1.99'
        with patch.object(remote, 'digest', return_value='reviewed'), \
             patch.object(remote.subprocess, 'check_output', return_value='  [  42]  vermagic=6.1.98 SMP\n'), \
             patch.object(remote.os, 'uname', return_value=Kernel(), create=True):
            with self.assertRaisesRegex(RuntimeError, 'release mismatch'):
                remote.module_compatible({'module': 'candidate.ko', 'sha256': 'reviewed'})

    def test_readelf_metadata_fields(self):
        text = "String dump of section '.modinfo':\n  [     0]  license=GPL v2\n  [   1aF]  srcversion=ABC123DEF456\n  [  200]  vermagic=6.1.99 SMP preempt mod_unload aarch64\n"
        self.assertEqual(remote.parse_modinfo(text, 'srcversion'), 'ABC123DEF456')
        self.assertEqual(remote.parse_modinfo(text, 'vermagic'),
                         '6.1.99 SMP preempt mod_unload aarch64')
        for field in ('srcversion', 'vermagic'):
            for invalid in ('', '  [ 0]  ' + field + '=\n',
                            '  [ 0]  ' + field + '=one\n  [ 10]  ' + field + '=one\n',
                            '  [ 0]  other=' + field + '=one\n'):
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaisesRegex(RuntimeError, 'Missing, empty or duplicate'):
                        remote.parse_modinfo(invalid, field)

    def test_matching_kernel_and_readelf_command(self):
        class Kernel:
            release = '6.1.99'
        with patch.object(remote, 'digest', return_value='reviewed'), \
             patch.object(remote.subprocess, 'check_output',
                          return_value='  [  42]  vermagic=6.1.99 SMP\n') as readelf, \
             patch.object(remote.os, 'uname', return_value=Kernel(), create=True):
            result = remote.module_compatible({'module': 'candidate.ko', 'sha256': 'reviewed'})
            self.assertEqual(result['kernel_release'], '6.1.99')
            self.assertEqual(readelf.call_args.args[0], ['readelf', '-p', '.modinfo', 'candidate.ko'])
            self.assertEqual(readelf.call_args.kwargs['env']['LC_ALL'], 'C')

    def make_session(self, phase='candidate_running'):
        session = object.__new__(deploy.Session)
        session.remote = '/userdata/linaro/ov56401-deploy-test'
        session.helper = session.remote + '/deploy_remote_helper.py'
        session.evidence = deploy.ROOT
        session.receipt = {'phase': phase, 'artifacts': {'helper_sha256': 'helper'},
                           'baseline': {'boot_id': 'boot', 'identity': {'exe': 'active'}},
                           'candidate': {'identity': {'pid': 10}, 'env': {}, 'status': 'exit'},
                           'original_module': {'module': 'original', 'sha256': 'old'}}
        return session

    def test_restore_orders_unload_before_program_and_insert_before_rescan(self):
        session = self.make_session()
        events = []
        def rpc(action, **values):
            events.append((action, values))
            if action == 'boot': return {'boot_id': 'boot'}
            if action == 'hash':
                return {'sha256': {'active': deploy.ACTIVE, 'original': 'old', session.helper: 'helper'}[values['path']]}
            return {}
        def save(phase, **values):
            session.receipt['phase'] = phase
        with patch.object(session, 'rpc', side_effect=rpc), \
             patch.object(session, 'save', side_effect=save), \
             patch.object(session, 'launch', side_effect=lambda *a, **k: events.append(('launch', k))), \
             patch.object(deploy, 'pds_preflight'), \
             patch.object(deploy, 'flash', side_effect=lambda *a, **k: events.append(('flash', k))):
            session.restore()
        actions = [item[0] for item in events]
        self.assertLess(actions.index('stop'), actions.index('remove'))
        modules = [(i, values['operation']) for i, (action, values) in enumerate(events) if action == 'module']
        self.assertEqual([x[1] for x in modules], ['unload', 'insert'])
        self.assertLess(modules[0][0], actions.index('flash'))
        self.assertLess(actions.index('flash'), modules[1][0])
        self.assertLess(modules[1][0], actions.index('rescan'))
        self.assertLess(actions.index('rescan'), actions.index('launch'))

    def test_restore_stop_failure_never_touches_pci_or_jtag(self):
        session = self.make_session()
        events = []
        def rpc(action, **values):
            events.append(action)
            if action == 'boot': return {'boot_id': 'boot'}
            if action == 'hash': return {'sha256': 'helper'}
            if action == 'verify_lock': return {'lock_owned': True}
            if action == 'stop': raise RuntimeError('consumer uncertain')
            raise AssertionError('Unexpected mutation ' + action)
        with patch.object(session, 'rpc', side_effect=rpc), \
             patch.object(session, 'save'), patch.object(deploy, 'flash') as flash:
            with self.assertRaisesRegex(RuntimeError, 'uncertain'):
                session.restore()
            self.assertNotIn('remove', events)
            flash.assert_not_called()

    def test_unknown_receipt_phase_cannot_restore(self):
        session = self.make_session('programming_candidate')
        with patch.object(session, 'rpc') as rpc:
            with self.assertRaisesRegex(RuntimeError, 'known'):
                session.restore()
            rpc.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
