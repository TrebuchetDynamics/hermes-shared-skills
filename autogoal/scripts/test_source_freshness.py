"""Offline source snapshot regressions. No cards, projects or network writes."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

class FreshnessTests(unittest.TestCase):
    def test_changed_source_invalidates_selection(self):
        file=Path(__file__).with_name('source_freshness.py')
        self.assertTrue(file.exists(), 'Missing source-freshness preflight')
        spec=importlib.util.spec_from_file_location('freshness',file)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as directory:
            r=Path(directory);(r/'src').mkdir();p=r/'src/client.py';p.write_text('pending fix\n')
            snapshot=m.capture(r,['src/client.py','README.md'])
            self.assertTrue(m.check(snapshot,r)['fresh'])
            p.write_text('fixed by another owner\n')
            result=m.check(snapshot,r)
            self.assertFalse(result['fresh']);self.assertIn('src/client.py',result['changed'])

    def test_credentials_are_not_evidence_sources(self):
        spec=importlib.util.spec_from_file_location('freshness',Path(__file__).with_name('source_freshness.py'))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as directory:
            r=Path(directory);(r/'.env').write_text('fixture only\n')
            with self.assertRaisesRegex(ValueError,'Do not fingerprint credentials'):
                m.capture(r,['.env'])

    def test_appearance_deletion_symlink_and_wrong_workspace(self):
        spec=importlib.util.spec_from_file_location('freshness',Path(__file__).with_name('source_freshness.py'))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as directory:
            r=Path(directory);p=r/'README.md';s=m.capture(r,['README.md'])
            p.write_text('another owner added the requested document\n')
            self.assertEqual(m.check(s,r)['changed'],['README.md'])
            s=m.capture(r,['README.md']);p.unlink();self.assertFalse(m.check(s,r)['fresh'])
            p.write_text('restored\n');(r/'link').symlink_to(p)
            for path in ['link','../README.md',str(p)]:
                with self.assertRaises(ValueError):m.capture(r,[path])
            (r/'other').mkdir()
            with self.assertRaisesRegex(ValueError,'different workspace'):m.check(s,r/'other')
            with self.assertRaises(ValueError):m.capture(r,[])

if __name__=='__main__':unittest.main()
