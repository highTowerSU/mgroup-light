"""Check that publishing includes valid metadata without local captures."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location('build_repository', Path(__file__).resolve().parents[1]/'tools/build_repository.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class RepositoryTests(unittest.TestCase):
    def test_publish_archive_is_clean_and_has_repository_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            output = builder.build('https://github.com/example/mgroup-test.git', Path(folder)/'repository.zip')
            with ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn('hacs.json', names)
                self.assertIn('README.md', names)
                self.assertFalse(any(name.startswith(('analysis/', 'dist/')) or '__pycache__' in name for name in names))
                manifest = json.loads(archive.read('custom_components/mgroup_light/manifest.json'))
                self.assertEqual(manifest['documentation'], 'https://github.com/example/mgroup-test#readme')
                self.assertEqual(manifest['issue_tracker'], 'https://github.com/example/mgroup-test/issues')
                self.assertEqual(manifest['codeowners'], ['@example'])
                self.assertTrue(manifest['config_flow'])

    def test_rejects_non_github_urls(self):
        for url in ('https://example.com/user/repo', 'https://github.com/user/repo/issues', ''):
            with self.assertRaises(ValueError):
                builder.build(url)
