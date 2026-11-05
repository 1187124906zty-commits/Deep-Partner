"""Runtime settings and locks are not generated project source artifacts."""
from pathlib import Path
import sys, tempfile, unittest
sys.path.insert(0, 'C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts')
from tool_runtime import collect,publication_baseline


class PublicationTests(unittest.TestCase):
    def test_document_turn_does_not_republish_previous_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'old.py').write_text('print(1)')
            state={'workspace':directory,'payload':{'code_engine':'agent','publish_root':'docs'},'status':'completed',
                   'publication_baseline':publication_baseline(root),'input_paths':[]}
            (root/'README.md').write_text('Requested documentation')
            self.assertEqual([row['path'] for row in collect(state)['files']],['docs/README.md'])

    def test_modified_input_retains_its_project_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'src').mkdir();(root/'src/model.py').write_text('old')
            state={'workspace':directory,'payload':{'code_engine':'agent','publish_root':'src'},'status':'completed',
                   'publication_baseline':publication_baseline(root),'input_paths':['src/model.py']}
            (root/'src/model.py').write_text('updated implementation')
            (root/'src/new.py').write_text('new implementation')
            self.assertEqual([row['path'] for row in collect(state)['files']],['src/model.py','src/new.py'])

    def test_verification_only_turn_can_finish_without_republishing_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'model.py').write_text('pass')
            state={'workspace':directory,'payload':{'code_engine':'agent','publish_root':'src'},'status':'completed',
                   'publication_baseline':publication_baseline(root),'input_paths':['model.py'],'summary':'Existing checks completed'}
            value=collect(state)
            self.assertEqual(value['files'],[])
            self.assertEqual(value['publication_scope'],'current_turn_changes')
            self.assertEqual(value['summary'],'Existing checks completed')

    def test_collect_omits_runtime_settings_and_locks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['native_check.py', 'test_native_check.py', 'deepcode_config.json', 'deepcode_config.json.lock']:
                (root / name).write_text('{}', encoding='utf8')
            result = collect({'workspace': directory, 'payload': {'publish_root': 'src'}, 'status': 'completed'})
            self.assertEqual([row['path'] for row in result['files']], ['src/native_check.py', 'src/test_native_check.py'])


if __name__ == '__main__':
    unittest.main()
