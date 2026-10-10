#!/usr/bin/env python3
"""Hermetic launcher contract tests; never dispatch an installed backend."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import native_containment as module

HERE = Path(__file__).resolve().parent

class PlanTests(unittest.TestCase):
    def setUp(self):
        # No installed runtime or user manager is consulted by the hermetic suite.
        self.real_manifest = module.runtime_manifest
        root_patch = patch.object(module, 'SCRATCH_ROOT', Path(tempfile.gettempdir()))
        runtime_patch = patch.object(module, 'runtime_manifest', return_value={'/usr/bin/true': '/usr/bin/true'})
        root_patch.start()
        runtime_patch.start()
        self.addCleanup(root_patch.stop)
        self.addCleanup(runtime_patch.stop)

    def test_plan_is_narrow_and_environment_is_empty(self):
        self.assertTrue((HERE / 'native_containment.py').exists(), 'containment launcher is missing')
        with tempfile.TemporaryDirectory() as tmp:
            plan = module.build_plan(['/usr/bin/true'], Path(tmp), runtime_mounts=['/usr/bin/true'])
        args = plan['sandbox_argv']
        self.assertIn('--unshare-net', args)
        self.assertIn('--unshare-pid', args)
        self.assertIn('--unshare-user', args)
        self.assertIn('--clearenv', args)
        self.assertNotIn('/', [args[i+1] for i, x in enumerate(args) if x == '--ro-bind'])
        self.assertIn('/home/sandbox', args)
        self.assertEqual(plan['live_model_execution'], 'NOT_RUN')
        self.assertEqual(plan['configured_controls']['KillMode'], 'control-group')

    def test_controller_socket_is_single_readonly_bind(self):
        import socket
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = root / 'job'
            job.mkdir()
            with socket.socket(socket.AF_UNIX) as server:
                endpoint = root / 'controller.sock'
                server.bind(str(endpoint))
                plan = module.build_plan(['/usr/bin/true'], job,
                    runtime_mounts=['/usr/bin/true'], controller_socket=endpoint)
                default = module.build_plan(['/usr/bin/true'], job, runtime_mounts=['/usr/bin/true'])
                args = plan['sandbox_argv']
                index = args.index(str(endpoint))
                self.assertEqual(args[index-1:index+2], ['--ro-bind', str(endpoint), '/controller.sock'])
                self.assertEqual(args.count('/controller.sock'), 1)
                self.assertEqual(args[:index-1] + args[index+2:], default['sandbox_argv'])

    def test_controller_socket_rejects_noncanonical_unowned_and_worker_paths(self):
        import socket
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = root / 'job'
            job.mkdir()
            file = root / 'ordinary'
            file.write_text('fixture')
            with socket.socket(socket.AF_UNIX) as server, socket.socket(socket.AF_UNIX) as inside:
                endpoint = root / 'controller.sock'
                server.bind(str(endpoint))
                inside.bind(str(job / 'inside.sock'))
                link = root / 'link'
                link.symlink_to(endpoint)
                directory_link = root / 'linked-job'
                directory_link.symlink_to(job, target_is_directory=True)
                cases = [file, root, root / 'absent', link, job / 'inside.sock',
                         str(root) + '/./controller.sock', 'controller.sock',
                         directory_link / 'inside.sock']
                for path in cases:
                    with self.subTest(path=str(path)), self.assertRaises(ValueError):
                        module.build_plan(['/usr/bin/true'], job,
                            runtime_mounts=['/usr/bin/true'], controller_socket=path)
                original = Path.stat
                def stat(path, *args, **kwargs):
                    observed = original(path, *args, **kwargs)
                    if path == endpoint:
                        return SimpleNamespace(st_uid=module.os.getuid() + 1, st_mode=observed.st_mode)
                    return observed
                with patch.object(Path, 'stat', stat), self.assertRaises(ValueError):
                    module.build_plan(['/usr/bin/true'], job,
                        runtime_mounts=['/usr/bin/true'], controller_socket=endpoint)

    def test_refuses_invalid_bounds_paths_and_broad_mounts(self):
        import native_containment as module
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            link = scratch / 'link'
            link.symlink_to(scratch, target_is_directory=True)
            cases = [dict(runtime_sec=0), dict(runtime_sec=6), dict(runtime_sec=float('nan')),
                     dict(runtime_sec=True), dict(memory_bytes=0), dict(tasks=0),
                     dict(cpu_percent=101), dict(runtime_mounts=['/']),
                     dict(runtime_mounts=['/home']), dict(runtime_mounts=['/usr']),
                     dict(runtime_mounts=['/etc']), dict(runtime_mounts=['/usr/bin']),
                     dict(runtime_mounts=['/usr/bin/python3']), dict(scratch=link),
                     dict(scratch=Path.home()), dict(scratch=str(scratch) + '/../escape')]
            for overrides in cases:
                kwargs = dict(scratch=scratch, runtime_mounts=['/usr/bin/true'])
                kwargs.update(overrides)
                with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                    module.build_plan(['/usr/bin/true'], **kwargs)
            with self.assertRaises(ValueError):
                module.build_plan(['/bin/sh'], scratch, runtime_mounts=['/usr/bin/true'])

    def test_manifest_omits_distribution_config_and_site_packages(self):
        import native_containment as module
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            stdlib = Path(tmp)
            for name in ('encodings', 'json', 'collections', 're', 'importlib',
                         'lib-dynload', 'urllib', 'dist-packages', 'config-3.12'):
                (stdlib / name).mkdir()
            (stdlib / 'os.py').write_text('# trusted fixture\n')
            (stdlib / 'sitecustomize.py').symlink_to('/etc/synthetic-sitecustomize.py')
            libraries = stdlib / 'libraries'
            libraries.mkdir()
            for name in module.SONAMES:
                (libraries / name).write_text('library fixture')
            with patch.object(module, 'STDLIB', str(stdlib)), patch.object(module, 'LIBRARY_ROOT', libraries):
                manifest = self.real_manifest()
            self.assertNotIn(str(stdlib / 'dist-packages'), manifest)
            self.assertNotIn(str(stdlib / 'config-3.12'), manifest)
            self.assertNotIn(str(stdlib / 'sitecustomize.py'), manifest)
            self.assertIn(str(stdlib / 'encodings'), manifest)
            self.assertIn(str(stdlib / 'os.py'), manifest)

    def test_cli_help_is_available_without_backend_dispatch(self):
        import contextlib
        import io
        import native_containment as module
        from unittest.mock import patch
        self.assertTrue(callable(getattr(module, 'main', None)), 'executable CLI is missing')
        with patch.object(module, 'command') as backend, contextlib.redirect_stdout(io.StringIO()) as out:
            with self.assertRaises(SystemExit) as exit_info:
                module.main(['--help'])
            self.assertEqual(exit_info.exception.code, 0)
            self.assertIn('--runtime-sec', out.getvalue())
            backend.assert_not_called()

    def test_refuses_runtime_library_symlink_escape(self):
        import native_containment as module
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            libraries = root / 'libraries'
            libraries.mkdir()
            outside = root / 'synthetic-outside'
            outside.write_text('fixture')
            for name in module.SONAMES:
                (libraries / name).symlink_to(outside)
            self.assertTrue(hasattr(module, 'LIBRARY_ROOT'), 'library confinement root is missing')
            with patch.object(module, 'LIBRARY_ROOT', libraries), patch.object(module, 'STDLIB', str(root)), \
                 self.assertRaises(ValueError):
                self.real_manifest()

    def test_unavailable_controls_refuse_without_any_dispatch_or_fallback(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = root / 'job'
            job.mkdir()
            with patch.object(module, 'trusted_runtime', side_effect=RuntimeError('bwrap unavailable')), \
                 patch.object(module, 'command') as backend:
                receipt = module.launch(['/usr/bin/true'], job, receipt_path=root / 'refused.json')
            self.assertEqual(receipt['execution_status'], 'REFUSED')
            self.assertEqual(receipt['live_model_execution'], 'NOT_RUN')
            self.assertEqual(receipt['verified_controls'], {})
            self.assertEqual(json.loads((root / 'refused.json').read_text()), receipt)
            backend.assert_not_called()
            self.assertEqual(receipt['cleanup'].get('status'), 'NOT_NEEDED',
                             'non-dispatch cleanup status is missing')

    def test_disappearing_cgroup_is_observed_as_absent_not_an_error(self):
        from unittest.mock import Mock
        group = Mock()
        group.exists.return_value = True
        entry = Mock()
        entry.read_text.side_effect = FileNotFoundError('owned cgroup removed during read')
        group.rglob.return_value = [entry]
        self.assertEqual(module.cgroup_pids(group), [])

class SyntheticLaunchTests(unittest.TestCase):
    """Real launcher with synthetic manager/kernel observations, no dispatch."""
    setUp = PlanTests.setUp

    def run_fixture(self, *, cancel_phase=None, stop_ok=True, absent=True,
                    observation_error=False, dispatch_lost=False, controls=None, cgroup_error=False,
                    lingering_pid=False, controller=False, launch_options=None, evidence_name=None):
        import contextlib
        import json
        import threading
        from types import SimpleNamespace
        event = threading.Event()
        if cancel_phase == 'preset':
            event.set()
        calls = []
        stopped = False
        original_read = Path.read_text
        original_exists = Path.exists
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            root = Path(tmp)
            job = root / 'job'
            job.mkdir()
            options = dict(launch_options or {})
            if controller:
                import socket
                server = stack.enter_context(socket.socket(socket.AF_UNIX))
                endpoint = root / 'controller.sock'
                server.bind(str(endpoint))
                options['controller_socket'] = endpoint
            if callable(options.get('before_release')):
                hook = options['before_release']
                def before_release(observation):
                    self.assertTrue(list(job.glob('.ready-*')))
                    self.assertFalse(list(job.glob('.release-*')))
                    self.assertTrue(calls)
                    result = hook(observation)
                    if cancel_phase == 'registration':
                        event.set()
                    return result
                options['before_release'] = before_release
            state = {'ControlGroup': '', 'RuntimeMaxUSec': '2s', 'TimeoutStopUSec': '1s',
                     'KillMode': 'control-group', 'NoNewPrivileges': 'yes', 'RemainAfterExit': 'yes',
                     'MemoryMax': '134217728', 'TasksMax': '16', 'CPUQuotaPerSecUSec': '1s',
                     'ActiveState': 'active', 'SubState': 'exited', 'ExecMainCode': '1',
                     'ExecMainStatus': '0', 'Result': 'success', 'LoadState': 'loaded'}
            state.update(controls or {})
            for key, value in (controls or {}).items():
                if value is None:
                    state.pop(key, None)
            def command(args):
                nonlocal stopped
                calls.append(args)
                if args[0] == '/usr/bin/systemd-run':
                    unit = next(a.split('=', 1)[1] for a in args if a.startswith('--unit='))
                    state['ControlGroup'] = (controls or {}).get('ControlGroup', '/synthetic/' + unit)
                    nonce = unit.removeprefix('native-containment-').removesuffix('.service')
                    if cancel_phase == 'readiness':
                        event.set()
                    else:
                        (job / ('.ready-' + nonce)).write_text(json.dumps({
                            'namespaces': {n: 'isolated-' + n for n in ('user', 'pid', 'net', 'mnt')},
                            'environment': {'HOME': '/home/sandbox', 'PATH': '/usr/bin', 'LANG': 'C', 'PWD': '/job'},
                            'home_entries': [], 'manager_paths_present': False}))
                    if dispatch_lost:
                        raise TimeoutError('dispatch acknowledgement lost')
                if 'stop' in args:
                    stopped = stop_ok
                    return SimpleNamespace(returncode=0 if stop_ok else 1, stdout='', stderr='synthetic stop')
                return SimpleNamespace(returncode=0, stdout='Version=synthetic', stderr='')
            def unit_state(unit):
                if observation_error:
                    raise RuntimeError('synthetic observation failed')
                return {**state, 'LoadState': 'not-found' if stopped and absent else 'loaded'}
            def read(path, *args, **kwargs):
                if str(path).startswith('/sys/fs/cgroup/synthetic/'):
                    return {'memory.max': '134217728', 'pids.max': '16', 'cpu.max': '100000 100000'}[path.name]
                if str(path) == '/proc/999999/status':
                    return 'NSpid:\t999999\t1\n'
                return original_read(path, *args, **kwargs)
            def identity(pid):
                if cancel_phase == 'before-release':
                    event.set()
                return None if stopped and not lingering_pid else 'synthetic-starttime'
            def pids(group):
                if cgroup_error:
                    raise PermissionError('synthetic cgroup observation failed')
                return [] if any('stop' in c for c in calls) or group is None else [999999]
            for name, value in [('trusted_runtime', lambda mounts: None), ('command', command),
                                ('unit_state', unit_state), ('cgroup_pids', pids),
                                ('host_pid_identity', identity)]:
                stack.enter_context(patch.object(module, name, value))
            stack.enter_context(patch.object(module.os, 'access', return_value=True))
            stack.enter_context(patch.object(module.os, 'readlink', side_effect=lambda p:
                ('host-' if '/self/' in p else 'isolated-') + p.rsplit('/', 1)[1]))
            stack.enter_context(patch.object(Path, 'read_text', read))
            stack.enter_context(patch.object(Path, 'exists', lambda p:
                not (stopped and absent) if str(p).startswith('/sys/fs/cgroup/synthetic/') else original_exists(p)))
            receipt_path = ((Path.home() / '.hermes/cache/scratch/executable-safeguards/controller-bridge/containment')
                            / (evidence_name + '.json')) if evidence_name else root / 'receipt.json'
            receipt = module.launch(['/usr/bin/true'], job, receipt_path=receipt_path, cancel_event=event, **options)
            self.assertEqual(json.loads(receipt_path.read_text()), receipt)
            released = bool(list(job.glob('.release-*')))
        return receipt, calls, released

    def test_trusted_registration_observes_exact_identity_before_release(self):
        seen = []
        def register(observation):
            seen.append(observation)
            return True
        receipt, calls, released = self.run_fixture(controller=True,
            launch_options={'before_release': register}, evidence_name='synthetic-registered')
        self.assertEqual(seen, [{'unit': receipt['unit'], 'control_group': receipt['control_group'],
                               'namespace_host_pids': [999999]}])
        self.assertTrue(all(receipt['verified_controls'].values()))
        self.assertTrue(released)
        self.assertEqual(receipt['execution_status'], 'EXITED')
        self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')
        args = receipt['sandbox_argv']
        index = args.index('/controller.sock')
        self.assertEqual(args[index-2], '--ro-bind')
        self.assertEqual(args.count('/controller.sock'), 1)

    def test_socket_and_callable_registration_must_be_paired_before_dispatch(self):
        for controller, options in ((True, {}), (False, {'before_release': lambda info: True}),
                                    (True, {'before_release': True})):
            with self.subTest(controller=controller, options=options):
                receipt, calls, released = self.run_fixture(controller=controller, launch_options=options)
                self.assertEqual(receipt['execution_status'], 'REFUSED')
                self.assertFalse(calls)
                self.assertFalse(released)
                self.assertEqual(receipt['cleanup']['status'], 'NOT_NEEDED')

    def test_registration_requires_exact_true_and_cleans_refusal(self):
        for index, result in enumerate((False, None, 1, 'yes', {}, [])):
            with self.subTest(result=result):
                receipt, calls, released = self.run_fixture(controller=True,
                    launch_options={'before_release': lambda info: result},
                    evidence_name='synthetic-denied-' + str(index))
                self.assertFalse(released)
                self.assertEqual(receipt['execution_status'], 'REFUSED')
                self.assertNotIn('released_elapsed_sec', receipt)
                self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')
                self.assertIn(['/usr/bin/systemctl', '--user', 'stop', receipt['unit']], calls)

    def test_cgroup_observation_failure_still_attempts_exact_stop(self):
        receipt, calls, released = self.run_fixture(cgroup_error=True)
        self.assertIn(['/usr/bin/systemctl', '--user', 'stop', receipt['unit']], calls)
        self.assertFalse(released)
        self.assertEqual(receipt['cleanup']['status'], 'UNVERIFIED')

    def test_cancellation_during_registration_prevents_release(self):
        receipt, calls, released = self.run_fixture(controller=True, cancel_phase='registration',
            launch_options={'before_release': lambda info: True}, evidence_name='synthetic-hook-cancel')
        self.assertFalse(released)
        self.assertEqual(receipt['execution_status'], 'CANCELLED')
        self.assertTrue(receipt['cancellation']['acknowledged'])
        self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')

    def test_registration_exception_never_releases(self):
        def register(info):
            raise RuntimeError('registration unavailable')
        receipt, calls, released = self.run_fixture(controller=True,
            launch_options={'before_release': register}, evidence_name='synthetic-hook-exception')
        self.assertFalse(released)
        self.assertEqual(receipt['execution_status'], 'REFUSED')
        self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')

    def test_unverified_controls_never_call_registration(self):
        from unittest.mock import Mock
        register = Mock(return_value=True)
        receipt, calls, released = self.run_fixture(controller=True, controls={'MemoryMax': 'invalid'},
            launch_options={'before_release': register}, evidence_name='synthetic-hook-unverified')
        register.assert_not_called()
        self.assertFalse(released)
        self.assertEqual(receipt['execution_status'], 'REFUSED')
        self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')

    def test_lost_dispatch_acknowledgement_uses_actual_cleanup_readbacks(self):
        receipt, calls, released = self.run_fixture(dispatch_lost=True)
        self.assertFalse(released)
        self.assertEqual(receipt['execution_status'], 'REFUSED')
        self.assertIn(['/usr/bin/systemctl', '--user', 'stop', receipt['unit']], calls)
        self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')

    def test_lingering_host_pid_identity_prevents_acknowledgement(self):
        receipt, calls, released = self.run_fixture(cancel_phase='before-release', lingering_pid=True)
        self.assertTrue(receipt['cleanup']['unit_absent'])
        self.assertTrue(receipt['cleanup']['cgroup_absent'])
        self.assertTrue(receipt['cleanup']['cgroup_empty'])
        self.assertFalse(receipt['cleanup']['observed_host_pids_absent'])
        self.assertFalse(receipt['cancellation']['acknowledged'])
        self.assertEqual(receipt['cleanup']['status'], 'UNVERIFIED')

    def test_unknown_cgroup_is_not_reported_empty(self):
        receipt, calls, released = self.run_fixture(controls={'ControlGroup': 'invalid'})
        self.assertFalse(receipt['cleanup']['cgroup_empty'])
        self.assertEqual(receipt['cleanup']['status'], 'UNVERIFIED')

    def test_missing_or_invalid_manager_controls_never_release(self):
        for key in ('RuntimeMaxUSec', 'TimeoutStopUSec', 'KillMode', 'NoNewPrivileges',
                    'RemainAfterExit', 'MemoryMax', 'TasksMax', 'CPUQuotaPerSecUSec'):
            for value in (None, 'invalid'):
                with self.subTest(key=key, value=value):
                    receipt, calls, released = self.run_fixture(controls={key: value})
                    self.assertFalse(released)
                    self.assertEqual(receipt['execution_status'], 'REFUSED')
                    self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')
                    self.assertIn(['/usr/bin/systemctl', '--user', 'stop', receipt['unit']], calls)

    def test_empty_present_cgroup_never_acknowledges_cancellation(self):
        receipt, calls, released = self.run_fixture(cancel_phase='before-release', absent=False)
        self.assertTrue(receipt['cleanup']['cgroup_empty'])
        self.assertFalse(receipt['cleanup']['cgroup_absent'])
        self.assertEqual(receipt['cleanup']['status'], 'UNVERIFIED')
        self.assertFalse(receipt['cancellation']['acknowledged'])

    def test_observation_failure_still_stops_exact_dispatched_unit(self):
        for lost in (False, True):
            with self.subTest(dispatch_acknowledgement_lost=lost):
                receipt, calls, released = self.run_fixture(observation_error=True, dispatch_lost=lost)
                self.assertIn(['/usr/bin/systemctl', '--user', 'stop', receipt['unit']], calls)
                self.assertFalse(released)
                self.assertEqual(receipt['cleanup']['status'], 'UNVERIFIED')
                self.assertFalse(receipt['cleanup']['cgroup_absent'])
                self.assertFalse(receipt['cancellation']['acknowledged'])

    def test_immediate_pre_release_cancellation_prevents_execution(self):
        receipt, calls, released = self.run_fixture(cancel_phase='before-release')
        self.assertFalse(released)
        self.assertEqual(receipt['execution_status'], 'CANCELLED')
        self.assertNotIn('released_elapsed_sec', receipt)
        self.assertIn(['/usr/bin/systemctl', '--user', 'stop', receipt['unit']], calls)
        self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')

    def test_readiness_cancellation_prevents_release_and_stops_exact_unit(self):
        receipt, calls, released = self.run_fixture(cancel_phase='readiness')
        self.assertEqual(receipt['execution_status'], 'CANCELLED')
        self.assertFalse(released)
        self.assertIn(['/usr/bin/systemctl', '--user', 'stop', receipt['unit']], calls)
        self.assertEqual(receipt['cleanup']['status'], 'VERIFIED')
        self.assertTrue(receipt['cancellation']['acknowledged'])

    def test_preset_cancellation_prevents_dispatch(self):
        receipt, calls, released = self.run_fixture(cancel_phase='preset')
        self.assertFalse(any(c[0] == '/usr/bin/systemd-run' for c in calls))
        self.assertFalse(released)
        self.assertEqual(receipt['execution_status'], 'CANCELLED')
        self.assertEqual(receipt['cleanup']['status'], 'NOT_NEEDED')

    def test_cli_requires_every_exact_cleanup_component_and_verified_status(self):
        import contextlib
        import io
        keys = ('unit_absent', 'cgroup_absent', 'cgroup_empty', 'observed_host_pids_absent', 'status')
        for key in keys:
            for missing in (False, True):
                cleanup: dict[str, object] = {k: True for k in keys[:-1]}
                cleanup['status'] = 'VERIFIED'
                if missing:
                    del cleanup[key]
                else:
                    cleanup[key] = 'UNVERIFIED' if key == 'status' else False
                result = {'unit': 'synthetic.service', 'execution_status': 'EXITED', 'returncode': 0, 'cleanup': cleanup}
                with self.subTest(key=key, missing=missing), patch.object(module, 'launch', return_value=result), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(module.main(['--scratch', '/synthetic', '--receipt', '/synthetic.json', '--', '/usr/bin/true']), 1)

    def test_cancellation_does_not_acknowledge_failed_exact_cleanup(self):
        receipt, calls, released = self.run_fixture(cancel_phase='before-release', stop_ok=False)
        self.assertTrue(receipt['cancellation']['requested'])
        self.assertEqual(receipt['cleanup']['stop_returncode'], 1)
        self.assertEqual(receipt['cleanup']['status'], 'UNVERIFIED')
        self.assertFalse(receipt['cancellation']['acknowledged'])

if __name__ == '__main__':
    unittest.main()
