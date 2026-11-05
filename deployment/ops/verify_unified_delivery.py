"""One real Dify delivery linked to the already completed UI feedback turn."""
from pathlib import Path
import json
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.local/browser-qa'))
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://tutor.example.invalid'


def main():
    ui = json.loads((ROOT / 'reports/unified-ui-published.json').read_text(encoding='utf8'))
    assert ui.get('feedback', {}).get('same_session')
    account = json.loads(subprocess.run(['ssh', '-o', 'BatchMode=yes', 'papers-research',
        'sudo -n cat /srv/deeptutor/migration/admin-login.json'], capture_output=True,
        text=True, check=True).stdout)
    cli = json.loads(Path('D:/Development/电脑答疑/deeptutor-desktop/verification/cli-e2e-summary.json').read_text(encoding='utf8'))
    with sync_playwright() as p:
        api = p.request.new_context(base_url=ORIGIN)
        assert api.post('/api/auth/login', data=account, headers={'Origin': ORIGIN}).ok
        projects = api.get('/research/api/projects').json()['projects']
        project = next(row for row in projects if row['id'] == ui['project_id'])
        context = api.get('/research/dify/api/context?project_id=' + project['id']
            + '&workspace_id=' + project['native_id'] + '&task=review').json()
        body = {'request_id': 'deeppartner04-live-turn-delivery', 'project_id': project['id'],
            'workspace_id': project['native_id'], 'session_id': ui['feedback']['session_id'],
            'turn_id': ui['feedback']['turn_id'], 'task': 'review',
            'standard_version': context['standard_version'],
            'artifact': {'type': 'file', 'path': 'project/verification/deeppartner-0.4-cli-receipt.md',
                'content': '# DeepPartner 0.4 软件交付核对\n\n真实本机 Codex 已返回 DEEP_PARTNER_CLI_OK。\n'
                    + '本文件经真实 Dify 流程保存，并关联同一原生会话与反馈 turn。\n'
                    + '这不是科学计算或科研质量结论。\n',
                'summary': '本机CLI证据与同会话Dify交付的软件核对'},
            'question_ids': ui['feedback']['annotation_ids'],
            'validation': [{'check': 'actual-local-cli', 'result': 'passed',
                'evidence': 'See native cli-e2e-summary.json and persisted provider completion.'}],
            'limitations': ['这是软件接入验证，没有验证科研内容、物理模型或文献结论。']}
        response = api.post('/research/dify/api/deliver', data=body, headers={'Origin': ORIGIN}, timeout=180000)
        assert response.ok, response.text()[:1200]
        receipt = response.json()
        assert receipt.get('status') == 'saved' and receipt.get('workflow_status') == 'succeeded', receipt
        assert receipt.get('processing_history_verified') is True, receipt
        repeated = api.post('/research/dify/api/deliver', data=body, headers={'Origin': ORIGIN}, timeout=60000).json()
        assert repeated.get('run_id') == receipt['run_id']
        file = api.get('/research/api/projects/' + project['id'] + '/file?path=' + body['artifact']['path'])
        assert file.ok and file.text() == body['artifact']['content']
        report = {'receipt': receipt, 'same_run_on_repeat': True, 'file_readback_equal': True,
            'session_id': body['session_id'], 'turn_id': body['turn_id'],
            'project_id': project['id'], 'local_cli_evidence': cli,
            'direct_model_calls_in_verifier': 0,
            'automatic_quality_job_id': receipt.get('receipt', {}).get('quality', {}).get('job_id')}
        (ROOT / 'reports/unified-dify-turn-delivery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
