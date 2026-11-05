"""Archive authorized native execution and real Scholar workflow verification."""
from pathlib import Path
import json, subprocess, sys
from verify_partner_workflow import ROOT, STAGE, client

PROJECT = 'c37b9168a0db40e3b258c9c03cd56697'
DP = Path('C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe')


def cli(*args):
    run = subprocess.run([str(DP), *map(str, args)], capture_output=True, encoding='utf8', timeout=180)
    if run.returncode:
        raise RuntimeError(run.stderr[-1500:] + run.stdout[-1500:])
    return json.loads(run.stdout)


def main():
    scholar = json.loads((ROOT / 'reports/partner-scholar-contract-live.json').read_text(encoding='utf8'))
    native = json.loads((ROOT / 'reports/partner-native-authorized-live.json').read_text(encoding='utf8'))
    assert scholar['actual_tools_and_pagination_passed'] and len(scholar['calls']) == 3
    assert native['run']['status'] == 'completed' and native['project_file_readback']
    assert native['independent_verification']['exit_code'] == 0
    code = native['run']['result']['code_result']
    assert len(code['files']) == 2
    assert native['run']['result']['native_code']['mcp_session_id'] == '4cfbf911'
    assert any(call['tool'] == 'deepcode-reply' for call in code['tool_calls'])
    release = {
        'date': '2026-11-05', 'project_id': PROJECT,
        'authorization': {'answer': '允许本项目修改与测试', 'scope': 'workbench project',
                          'native_project': 'proj_4e34fb035f754c1e8964fe9af2dafd13',
                          'official_method': 'settings/update', 'filesystem_scope': 'workspace',
                          'command_sandbox': True, 'global_permissions_changed': False},
        'implementation': {'native_mcp_tool': 'deepcode-reply', 'session_id': '4028c003',
                           'files': ['server/scholar_mcp_client.py', 'server/search_mcp.py',
                                     'scripts/local_search_bridge.py', 'tests/test_scholar_workflow_contract.py'],
                           'compile_passed': True, 'scholar_contract_tests': 14,
                           'production_candidate_tests': 19, 'publication_filter_tests': 1},
        'real_scholar_workflow': {'calls': [{'run_id': row['id'], 'tool': row['request']['search_tool'],
                                           'count': len(row['result']['sources']),
                                           'cursor_in': row['request'].get('cursor'),
                                           'cursor_out': row['result'].get('next_cursor')}
                                          for row in scholar['calls']],
                                  'search_fallback_enabled': False,
                                  'crossref_role': 'metadata identity reconciliation only'},
        'real_native_project_workflow': {'run_id': native['run']['id'], 'session_id': '4cfbf911',
                                        'native_tool': True, 'continued_with': 'deepcode-reply',
                                        'saved_files': code['files'], 'project_readback': True,
                                        'independent_tests_passed': 4,
                                        'runtime_configs_excluded': True,
                                        'initial_publication_run': 'a1fc6b2128644326baf7cae91bcceb75',
                                        'initial_runtime_test_artifacts_removed': True},
        'deployment': {'worker': 'research-flow-project', 'port': 47907,
                       'project_scoped_native_execution': [PROJECT, '64c6b5e79b824bc4bf23637e8204446c'],
                       'original_research_and_native_workers_restarted': False},
        'limits': ['A fully unreachable Scholar bridge cannot repair itself through the same unreachable channel.',
                   'Recovery commands are explicit existing configuration; no challenge solving or arbitrary command execution.',
                   'The native test interpreter emitted a sitecustomize/core warning; all four tests and independent verification passed.',
                   'Original Paper2Code failed-state history remains preserved; its recovered verification is a separate receipt.'],
        'evidence': ['partner-deepcode-scholar-session.json', 'partner-scholar-contract-live.json',
                     'partner-native-authorized-live.json', 'partner-native-workflow-recovery-live.json',
                     'partner-third-tool-live.json']
    }
    release_path = ROOT / 'reports/partner-workflow-v2-release.json'
    release_path.write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding='utf8')
    previous_path = ROOT / 'reports/partner-workflow-v2-progress.json'
    previous = json.loads(previous_path.read_text(encoding='utf8'))
    previous['superseded_by'] = 'partner-workflow-v2-release.json'
    previous['backend_tests'] = 19
    previous['deepcode']['permissions'] = 'project-scoped file modification and Python tests authorized by the author'
    previous['deepcode']['scholar_adapter_implementation'] = 'completed by native deepcode-reply session4028c003;14tests passed'
    previous['deepcode']['actual_project_native_execution'] = release['real_native_project_workflow']
    previous['limitations'] = release['limits'] + ['OCR branch is installed but the earlier text-layer PDF did not require OCR']
    previous['tool_runtime']['actual_project_code_permission'] = 'enabled only for the integration and software acceptance projects'
    previous_path.write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding='utf8')
    files = [ROOT / 'docs/DeepPartner固定路线与自动纠错.md', release_path, previous_path,
             *[ROOT / 'reports' / name for name in release['evidence'][:3]]]
    uploaded = cli('project', 'upload', '--project', PROJECT, *files, '--category', 'documents', '--path', 'docs/workflow', '--json')
    refs = [{'path': 'docs/workflow/partner-workflow-v2-release.json'},
            {'path': 'docs/workflow/partner-scholar-contract-live.json'},
            {'path': 'docs/workflow/partner-native-authorized-live.json'}]
    record = {'id': 'authorized-native-tools-20261105', 'title': '项目授权后的原生工具修复与验收',
              'content': '作者允许本项目修改与测试后，DeepCode原会话完成Scholar桥接修改。19项候选测试通过；正式项目真实调用主题、作者与下一页工具。原生代码路由同会话续接，4项测试通过，2份源码回交及独立回读测试通过。',
              'nodes': [
                  {'id': 'authorized:scope', 'kind': 'decision', 'label': '当前项目允许修改与测试', 'status': 'recorded', 'evidence_refs': refs},
                  {'id': 'authorized:scholar', 'kind': 'implementation', 'label': 'Scholar工具分派、分页与有界诊断', 'status': 'recorded', 'evidence_refs': refs},
                  {'id': 'authorized:code', 'kind': 'implementation', 'label': '原生DeepCode续接、测试及源码回交', 'status': 'recorded', 'evidence_refs': refs},
                  {'id': 'authorized:limit', 'kind': 'limitation', 'label': '失效控制通道与验证要求保留明确状态', 'status': 'recorded', 'evidence_refs': refs}
              ],
              'edges': [{'source': 'authorized:scholar', 'target': 'authorized:scope', 'relation': 'derived_from'},
                        {'source': 'authorized:code', 'target': 'authorized:scope', 'relation': 'derived_from'},
                        {'source': 'authorized:scholar', 'target': 'authorized:limit', 'relation': 'limited_by'}]}
    record_path = STAGE / 'authorized-tools-record.json'
    record_path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf8')
    saved = cli('workflow', 'record', '--project', PROJECT, '--file', record_path)
    with client() as connection:
        for file in files:
            response = connection.get('/research/api/projects/' + PROJECT + '/file', params={'path': 'docs/workflow/' + file.name})
            response.raise_for_status()
            assert response.content == file.read_bytes(), file
    receipt = {'project_id': PROJECT, 'files_read_back': len(files), 'uploaded': uploaded,
               'record': saved, 'native_and_scholar_verified': True}
    (ROOT / 'reports/partner-authorized-tools-project.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'project_id': PROJECT, 'files_read_back': len(files), 'native_and_scholar_verified': True}, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    main()
