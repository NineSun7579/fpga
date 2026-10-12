"""Local failure/recovery checks for the reversible accelerator supervisor."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, str(Path(__file__).parent))
from viewer.stereo_summary import validate_stereo

SPEC = importlib.util.spec_from_file_location('accelerator_run', Path(__file__).with_name('run_rknn.py'))
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
VIEW_SPEC = importlib.util.spec_from_file_location('accelerator_viewer_trial', Path(__file__).with_name('run_viewer_trial.py'))
VIEW = importlib.util.module_from_spec(VIEW_SPEC)
VIEW_SPEC.loader.exec_module(VIEW)


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        helpers = RUN.load_helpers()
        self.ns = {'__name__': 'test_supervisor'}
        exec(compile(helpers.REMOTE_SOURCE.split("if __name__ == '__main__':", 1)[0] + RUN.REMOTE,
                     '<accelerator supervisor>', 'exec'), self.ns)

    def exercise(self, fail_phase=None, viewer_change=False, extra_owner=False, import_retirement=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            maps = root / 'maps'
            maps.write_text('0 0 0 0 0 /usr/lib/librknnrt.so\n')
            native_path = self.ns['Path']
            def mapped_path(*parts):
                return maps if parts == ('/proc', '17', 'maps') else native_path(*parts)
            viewer = dict(pid=17, starttime='41', exe='/userdata/detview-hdmifull/detview-hdmifull',
                          exe_sha256='v' * 64, argv=['viewer'], cwd=directory,
                          environment={}, uid=0, gid=0, groups=[], boot_id='boot')
            events = []
            def emit(state, **details):
                events.append(dict(state=state, **details))
            child = Mock()
            child.pid = 500
            child.returncode = 2 if fail_phase == 'benchmark' else 0
            child.poll.return_value = child.returncode
            state = {'closed': False}
            def close(*args):
                state['closed'] = True
                if fail_phase == 'close':
                    raise RuntimeError('closure transport failure after normal exit')
            owners = lambda: [] if state['closed'] else [17, 18] if extra_owner else [17]
            restored = Mock()
            def launch(*args, **kwargs):
                if fail_phase == 'launch':
                    raise OSError('launch failure')
                if import_retirement is not None and import_retirement != 'missing':
                    import json
                    log = root/'out/results/native_io_fd_import_fixture_cert_candidate.stdout'
                    log.parent.mkdir(parents=True)
                    normal = import_retirement == 'normal'
                    row = dict(event='dma_heap_retirement', purpose='native_io_fd_import', retirement_branch='normal' if normal else 'uncertain_run_process_teardown',
                               cleanup_ok=normal, context_destroy_attempted=normal, context_destroy_rc=0 if normal else None,
                               process_teardown_only=not normal, runtime_library_retained=not normal,
                               context_retained=not normal, fatal_no_continue=not normal)
                    rows = [dict(event='dma_heap_session_started', purpose='ownership_probe'),
                            dict(row, purpose='ownership_probe', retirement_branch='normal', cleanup_ok=True,
                                 context_destroy_attempted=True, context_destroy_rc=0, process_teardown_only=False,
                                 runtime_library_retained=False, context_retained=False, fatal_no_continue=False),
                            dict(event='dma_heap_session_started', purpose='native_io_fd_import')]
                    if import_retirement not in ('probe_only_interrupted', 'probe_only_with_summary'):
                        rows.append(row)
                    if import_retirement != 'probe_only_interrupted':
                        rows.append(dict(event='summary', mode='native_io_fd_import'))
                    log.write_text('\n'.join(json.dumps(value) for value in rows)+'\n')
                return child
            factory = Mock(side_effect=launch)
            exact = Mock(side_effect=RuntimeError('viewer changed') if viewer_change else None)
            mocks = dict(Path=mapped_path, sha=lambda path: 'm' * 64 if str(path).endswith('model') else 's' * 64,
                         owners=owners, process=lambda pid: None if state['closed'] else viewer,
                         config_for=lambda snap, log: dict(exe=snap['exe'], argv=snap['argv'], env={}),
                         verify_files=Mock(), windows=lambda pid, env: [dict(delete_supported=True)],
                         exact=exact, boot=lambda: 'boot', private_write=Mock(), close_exact=close,
                         original_action=restored, measurement_quiescent=Mock(), wait_for_quiet=Mock())
            request = dict(package=directory, source_sha256={}, phase='experiment', backend='rga',
                           viewer_sha256='v' * 64, viewer_argv=['viewer'], model=str(root / 'model'),
                           model_sha256='m' * 64, operation='op', snapshot=str(root / 'snapshot'),
                           output=str(root / 'out'), restore_log=str(root / 'restore.log'))
            if import_retirement is not None:
                request.update(backend='rknn', candidates=['native_io_fd_import'], binary=str(root/'bench'),
                               binary_sha256='s'*64, native_query=9, iterations=50, rounds=4, dequant_scale='fp16',
                               timing_reference='native_io_single_copy')
            with patch.dict(self.ns, mocks), patch.object(self.ns['subprocess'], 'Popen', factory), \
                 patch.object(self.ns['signal'], 'setitimer', Mock(), create=True), \
                 patch.object(self.ns['signal'], 'ITIMER_REAL', 0, create=True):
                if fail_phase or viewer_change or extra_owner or import_retirement in ('uncertain', 'missing', 'probe_only_interrupted', 'probe_only_with_summary'):
                    with self.assertRaises((RuntimeError, OSError)):
                        self.ns['acceleration'](request, emit)
                else:
                    self.ns['acceleration'](request, emit)
            return events, restored, factory, child

    def test_restores_after_success(self):
        events, restored, _, child = self.exercise()
        restored.assert_called_once()
        self.assertIn('probe_finished', [e['state'] for e in events])
        self.assertIn('restoration_started', [e['state'] for e in events])
        self.assertEqual(child.returncode, 0)

    def test_restores_after_launch_failure(self):
        _, restored, _, _ = self.exercise(fail_phase='launch')
        restored.assert_called_once()

    def test_restores_after_failed_benchmark(self):
        _, restored, _, _ = self.exercise(fail_phase='benchmark')
        restored.assert_called_once()

    def test_restores_after_close_failure_with_exited_viewer(self):
        _, restored, factory, _ = self.exercise(fail_phase='close')
        restored.assert_called_once()
        factory.assert_not_called()

    def test_identity_change_prevents_mutation(self):
        _, restored, factory, _ = self.exercise(viewer_change=True)
        restored.assert_not_called()
        factory.assert_not_called()

    def test_extra_dma_owner_prevents_mutation(self):
        _, restored, factory, _ = self.exercise(extra_owner=True)
        restored.assert_not_called()
        factory.assert_not_called()

    def test_import_normal_retirement_restores(self):
        events, restored, _, _ = self.exercise(import_retirement='normal')
        restored.assert_called_once()
        self.assertIn('import_retirement_checked', [row['state'] for row in events])

    def test_import_uncertainty_holds_restoration(self):
        events, restored, _, _ = self.exercise(import_retirement='uncertain')
        restored.assert_not_called()
        held = next(row for row in events if row['state'] == 'restoration_held')
        self.assertTrue(held['board_lock_must_remain'])
        self.assertFalse(held['hardware_quiescence_proven'])

    def test_import_missing_retirement_holds_restoration(self):
        events, restored, _, _ = self.exercise(import_retirement='missing')
        restored.assert_not_called()
        self.assertIn('restoration_held', [row['state'] for row in events])

    def test_import_probe_retirement_without_terminal_holds_restoration(self):
        events, restored, _, _ = self.exercise(import_retirement='probe_only_interrupted')
        restored.assert_not_called()
        held = next(row for row in events if row['state'] == 'restoration_held')
        self.assertIn('terminal', held['reason'])

    def test_import_probe_retirement_cannot_cover_inference_session(self):
        events, restored, _, _ = self.exercise(import_retirement='probe_only_with_summary')
        restored.assert_not_called()
        held = next(row for row in events if row['state'] == 'restoration_held')
        self.assertIn('coverage', held['reason'])


class NativeProofTests(unittest.TestCase):
    def fixture(self):
        import json
        root = Path(__file__).parent
        proof_path = root/'runs/rknn_experiment_f39aaaf111014a1fb8ac5e6542fe8e21/artifacts/results/report.json'
        report = json.loads(proof_path.read_text())
        experiment = json.loads((proof_path.parents[2]/'receipt.json').read_text())
        pinned = experiment['source_sha256']
        def read(path):
            return report if Path(path).name == 'report.json' else experiment
        diag = Mock(read_json=read, sha_file=lambda path: 'pinned')
        source = {'native_adapter.h': pinned['native_adapter.h']}
        viewer = {'runtime_sha256': report['target']['library_sha256']}
        return proof_path, report, experiment, diag, source, viewer, pinned['prepared/sdk/rknn_api.h']

    def test_real_archived_certificate_binds_original_adapter(self):
        path, _, _, diag, source, viewer, sdk = self.fixture()
        bound = VIEW.native_binding(path, source, viewer, diag, sdk)
        self.assertEqual(bound['target']['machine'], 'aarch64')

    def test_old_certificate_cannot_authorize_revised_adapter(self):
        path, _, _, diag, source, viewer, sdk = self.fixture()
        source['native_adapter.h'] = 'new-unverified-adapter'
        with self.assertRaisesRegex(ValueError, 'different native_adapter'):
            VIEW.native_binding(path, source, viewer, diag, sdk)

    def test_runtime_change_cannot_reuse_certificate(self):
        path, _, _, diag, source, viewer, sdk = self.fixture()
        viewer['runtime_sha256'] = 'new-runtime'
        with self.assertRaisesRegex(ValueError, 'model/runtime differ'):
            VIEW.native_binding(path, source, viewer, diag, sdk)

    def test_relaxed_float_rule_cannot_authorize_viewer(self):
        path, report, _, diag, source, viewer, sdk = self.fixture()
        report['certifications'][0]['atol'] = 0.01
        with self.assertRaisesRegex(ValueError, 'strict parity'):
            VIEW.native_binding(path, source, viewer, diag, sdk)


class PrivateArtifactTests(unittest.TestCase):
    def setUp(self):
        self.ns = {'__name__': 'test_artifact_manifest'}
        exec(compile(RUN.load_helpers().REMOTE_SOURCE.split("if __name__ == '__main__':", 1)[0] + RUN.REMOTE,
                     '<artifact manifest>', 'exec'), self.ns)

    def test_manifest_binds_private_bytes_and_dependency_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'result.json').write_bytes(b'{"completed":3}\n')
            (root/'probe.d').write_bytes(b'probe: source.cpp\n')
            (root/'unretained.cpp').write_bytes(b'int x;\n')
            events = []
            self.ns['emit_private_artifacts']({'output': directory}, lambda state, **values: events.append(dict(state=state, **values)))
            files = events[0]['files']
            self.assertEqual({row['name'] for row in files}, {'result.json', 'probe.d'})
            for row in files:
                self.assertEqual(row['sha256'], RUN.sha(row['path']))
                self.assertEqual(row['bytes'], Path(row['path']).stat().st_size)

    def test_failure_still_emits_partial_artifact_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'error.stderr').write_text('probe failed\n')
            events = []
            with patch.dict(self.ns, {'acceleration': Mock(side_effect=RuntimeError('failed probe'))}):
                with self.assertRaisesRegex(RuntimeError, 'failed probe'):
                    self.ns['action']({'action': 'experiment', 'output': directory}, lambda state, **values: events.append(dict(state=state, **values)))
            self.assertEqual(events[0]['state'], 'artifacts')
            self.assertEqual(events[0]['files'][0]['name'], 'error.stderr')

    def test_manifest_refuses_symlinked_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'target').write_text('data')
            try:
                (root/'alias.json').symlink_to(root/'target')
            except OSError:
                self.skipTest('Host cannot create symlinks')
            with self.assertRaisesRegex(RuntimeError, 'owner/bound/type'):
                self.ns['emit_private_artifacts']({'output': directory}, lambda *args, **values: None)

class SelectedModelLogTests(unittest.TestCase):
    def setUp(self):
        def require(ok, message):
            if not ok:
                raise RuntimeError(message)
        self.ns = dict(action=lambda *args: None, require=require)
        exec(VIEW.EXTRA, self.ns)
        self.selected = ('[rknn-io] model=/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn '
                         'sha256=21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31 '
                         'requested=native actual=native status=experimental')
        self.default = '[rknn-io] model=/other/default.rknn sha256=other requested=native actual=legacy status=baseline'

    def test_default_initialization_before_selected_model_is_allowed(self):
        self.assertEqual(self.ns['selected_io_entries']([self.default, self.selected], 'native'), [self.selected])

    def test_no_selected_model_is_not_ready(self):
        self.assertEqual(self.ns['selected_io_entries']([self.default], 'native'), [])

    def test_selected_runtime_fallback_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'I/O changed'):
            self.ns['selected_io_entries']([self.selected, '[rknn-io] model=wb_v4_combo actual=legacy reason=native_frame_failed'], 'native')

    def test_selected_runtime_unavailable_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'I/O changed'):
            self.ns['selected_io_entries']([self.selected.replace('actual=native', 'actual=unavailable')], 'native')

    def test_other_model_after_selection_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'model changed'):
            self.ns['selected_io_entries']([self.selected, self.default.replace('actual=legacy', 'actual=native')], 'native')


class StereoCoverageTests(unittest.TestCase):
    def line(self, begin, pair=(1,2), ok=9, failed=0):
        return (f'[stereo] window=[{begin},{begin+5000}) window_ms=5000 C{pair[0]}/C{pair[1]} '
                f'pair_compute_ok={ok} pair_compute_failed={failed} no_fresh_pair_polls=0 '
                'compute_mean_ms=250.00 compute_max_ms=290.00')

    def test_continuous_configured_pairs(self):
        text = '\n'.join(self.line(b,pair) for b in range(0,130000,5000) for pair in [(1,2),(3,4)])
        self.assertEqual(len(validate_stereo(text, [[1,2],[3,4]], 1000*1000000, 125000*1000000)['pairs']), 2)

    def test_startup_only_does_not_cover_measurement(self):
        with self.assertRaisesRegex(ValueError, 'cover'):
            validate_stereo(self.line(0), [[1,2]], 10000*1000000, 130000*1000000)

    def test_missing_middle_window_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            validate_stereo(self.line(0)+'\n'+self.line(10000), [[1,2]], 1000*1000000, 14000*1000000)

    def test_failed_or_idle_window_rejected(self):
        for ok, failed in [(0,0),(9,1)]:
            with self.assertRaisesRegex(ValueError, 'stopped or failed'):
                validate_stereo(self.line(0,ok=ok,failed=failed), [[1,2]], 1000*1000000, 4000*1000000)

    def test_missing_configured_pair_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no window'):
            validate_stereo(self.line(0), [[1,2],[3,4]], 1000*1000000, 4000*1000000)



if __name__ == '__main__':
    unittest.main(verbosity=2)
