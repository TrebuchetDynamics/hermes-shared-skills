"""Read-only source-lead regressions, isolated fixture repositories."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

class SignalsTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).with_name('engineering_signals.py')
        self.assertTrue(path.exists(), 'Source discovery must inspect selected implementation paths, not only planning docs')
        spec=importlib.util.spec_from_file_location('signals',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        return m
    def test_marks_source_comment_without_claiming_a_bug(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);(r/'src').mkdir();(r/'src/a.py').write_text('# TODO: cancellation regression\nvalue=1\n')
            result=m.scan(r,['src'])
            self.assertEqual(result['markers'],[{'path':'src/a.py','line':1,'marker':'TODO','lead_only':True}])
            self.assertFalse(result['scan_truncated'])
    def test_generated_and_symlink_files_are_not_scanned(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);(r/'src').mkdir();(r/'src/a.g.dart').write_text('// FIXME: generated\n');(r/'src/app_localizations_en.dart').write_text('// TODO: generated localization\n');(r/'outside.py').write_text('# TODO: outside\n');(r/'src/link.py').symlink_to(r/'outside.py')
            self.assertEqual(m.scan(r,['src'])['files_scanned'],0)
    def test_root_escape_is_rejected(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):m.scan(Path(d),['../elsewhere'])
    def test_file_budget_reports_truncation(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);(r/'src').mkdir()
            for n in range(3):(r/f'src/{n}.py').write_text('# FIXME: fixture\n')
            result=m.scan(r,['src'],max_files=1)
            self.assertEqual(result['files_scanned'],1)
            self.assertTrue(result['scan_truncated'])

if __name__=='__main__':unittest.main()
