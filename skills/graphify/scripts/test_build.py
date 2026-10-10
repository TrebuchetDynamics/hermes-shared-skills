"""Offline adapter tests; never install packages or call a model/network."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('graphify_adapter', Path(__file__).with_name('build.py'))
assert SPEC is not None and SPEC.loader is not None
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'project with spaces'
        self.source.mkdir()
        self.output = self.root / 'output'

    def artifacts(self, nodes=None):
        directory = self.output / 'graphify-out'
        directory.mkdir(parents=True)
        (directory / 'graph.json').write_text(json.dumps({
            'nodes': [{'id': 'fixture'}] if nodes is None else nodes,
            'links': [], 'graph': {'schema_version': 1}}))
        (directory / 'graph.html').write_text('<html>test fixture</html>')
        (directory / 'GRAPH_REPORT.md').write_text('Test fixture')

    def test_local_flags_and_literal_paths(self):
        def run(args, **kwargs):
            if args[1] == 'cluster-only':
                self.artifacts()
        with patch.object(m.subprocess, 'run', side_effect=run) as cli:
            result = m.build(self.source, self.output, binary='graphify-fixture')
        self.assertEqual(result['nodes'], 1)
        first, second = cli.call_args_list
        self.assertEqual(first.args[0], ['graphify-fixture', 'extract', str(self.source),
            '--code-only', '--no-cluster', '--max-workers', '2', '--out', str(self.output)])
        self.assertEqual(second.args[0], ['graphify-fixture', 'cluster-only', str(self.output), '--no-label'])
        self.assertTrue(first.kwargs['check'])
        self.assertNotIn('shell', first.kwargs)

    def test_existing_output_is_preserved(self):
        self.artifacts()
        original = (self.output / 'graphify-out/graph.json').read_bytes()
        with patch.object(m.subprocess, 'run') as cli, self.assertRaisesRegex(ValueError, 'Existing'):
            m.build(self.source, self.output, binary='fixture')
        cli.assert_not_called()
        self.assertEqual((self.output / 'graphify-out/graph.json').read_bytes(), original)

    def test_output_inside_source_is_refused(self):
        with patch.object(m.subprocess, 'run') as cli, self.assertRaises(ValueError):
            m.build(self.source, self.source / 'generated', binary='fixture')
        cli.assert_not_called()

    def test_missing_cli_has_no_outputs(self):
        with patch.object(m.shutil, 'which', return_value=None), self.assertRaises(RuntimeError):
            m.build(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_failure_does_not_continue_to_cluster(self):
        with patch.object(m.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'fixture')) as cli:
            with self.assertRaises(subprocess.CalledProcessError):
                m.build(self.source, self.output, binary='fixture')
        self.assertEqual(cli.call_count, 1)

    def test_missing_artifacts_are_not_success(self):
        with patch.object(m.subprocess, 'run'), self.assertRaisesRegex(RuntimeError, 'Missing'):
            m.build(self.source, self.output, binary='fixture')

    def test_empty_required_artifacts_are_not_success(self):
        for name in ('graph.json', 'GRAPH_REPORT.md', 'graph.html'):
            with self.subTest(artifact=name):
                output = self.root / name
                def run(args, **kwargs):
                    if args[1] == 'cluster-only':
                        directory = output / 'graphify-out'
                        directory.mkdir(parents=True)
                        (directory / 'graph.json').write_text(json.dumps({
                            'nodes': [{'id': 'fixture'}], 'links': []}))
                        (directory / 'GRAPH_REPORT.md').write_text('Test fixture')
                        (directory / 'graph.html').write_text('<html>test fixture</html>')
                        (directory / name).write_bytes(b'')
                with patch.object(m.subprocess, 'run', side_effect=run):
                    with self.assertRaisesRegex(RuntimeError, 'artifacts'):
                        m.build(self.source, output, binary='fixture')

    def test_empty_graph_is_not_success(self):
        def run(args, **kwargs):
            if args[1] == 'cluster-only':
                self.artifacts(nodes=[])
        with patch.object(m.subprocess, 'run', side_effect=run), self.assertRaisesRegex(RuntimeError, 'Empty'):
            m.build(self.source, self.output, binary='fixture')


if __name__ == '__main__':
    unittest.main()
