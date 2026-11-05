"""One bounded revision of the software receipt after its evidence review."""
from pathlib import Path
import json
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.local/browser-qa'))
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://tutor.example.invalid'
NATIVE = Path('D:/Development/电脑答疑/deeptutor-desktop')


def main():
    original = json.loads((ROOT / 'reports/unified-dify-turn-delivery.json').read_text(encoding='utf8'))
    job_id = original['local_cli_evidence']['job_id']
    job_root = NATIVE / 'verification/native-0.4-profile/jobs' / job_id
    job = json.loads((job_root / 'job.json').read_text(encoding='utf8'))
    events = [json.loads(line) for line in (job_root / 'events.jsonl').read_text(encoding='utf8').splitlines()]
    provider_events = [event for event in events if isinstance(event.get('data'), dict)
        and event['data'].get('type') in ('item.completed', 'turn.completed')]
    assert job['status'] == 'completed' and job['exit_code'] == 0
    assert any('DEEP_PARTNER_CLI_OK' in json.dumps(event) for event in provider_events)
    evidence = {'scope': 'software integration only; no scientific or numerical validity claim',
        'cli_job': job, 'cli_provider_events': provider_events,
        'cli_command': ['codex', 'exec', '--json', '--color', 'never', '--sandbox', 'workspace-write', '--skip-git-repo-check', '-'],
        'cli_prompt_input': 'stdin from cli_job.prompt',
        'original_dify_receipt': original['receipt'],
        'dify_verifier_checks': {'same_run_on_repeat': original['same_run_on_repeat'],
            'file_readback_equal': original['file_readback_equal']},
        'native_ui_feedback': json.loads((ROOT / 'reports/unified-feedback-live.json').read_text(encoding='utf8')),
        'persisted_stream': json.loads((ROOT / 'reports/unified-stream-live.json').read_text(encoding='utf8')),
        'native_identity_checks': json.loads((ROOT / 'reports/completed-native-identity-live.json').read_text(encoding='utf8'))}
    account = json.loads(subprocess.run(['ssh', '-o', 'BatchMode=yes', 'papers-research',
        'sudo -n cat /srv/deeptutor/migration/admin-login.json'], capture_output=True, text=True, check=True).stdout)
    with sync_playwright() as p:
        api = p.request.new_context(base_url=ORIGIN)
        assert api.post('/api/auth/login', data=account, headers={'Origin': ORIGIN}).ok
        pid = original['project_id']
        project = next(row for row in api.get('/research/api/projects').json()['projects'] if row['id'] == pid)
        evidence_path = 'verification/deeppartner-0.4-evidence.json'
        uploaded = api.put('/research/api/projects/' + pid + '/file', headers={'Origin': ORIGIN},
            data={'path': evidence_path, 'content': json.dumps(evidence, ensure_ascii=False, indent=2),
                  'reason': '按真实评审意见补齐本机与Dify原始证据'})
        assert uploaded.ok, uploaded.text()[:600]
        receipt = original['receipt']
        content = f'''# DeepPartner 0.4 软件链路核对

范围：本机 CLI 固定标记执行、原生会话流式保存与恢复、同会话批注反馈、Dify 文件交付。没有开展科学计算或验证文献结论。

## 本机执行

实际任务 `{job_id}`，engine=`codex`，状态 `{job['status']}`，退出码 `{job['exit_code']}`。
命令参数及 stdin 提示在来源 JSON 的 `cli_command`、`cli_job.prompt` 中；开始和结束时间为 `cli_job.created_at/updated_at`（Unix 毫秒）。
`cli_provider_events` 保留真实 `item.completed` 与 `turn.completed` 记录，实际响应为 `DEEP_PARTNER_CLI_OK`。这是固定文本链路检查，不能推出任意编程任务均成功。

## 会话与交付

原生会话 `{original['session_id']}`，反馈 turn `{original['turn_id']}`。
`native_ui_feedback` 保存批注与实际会话返回值；`persisted_stream` 记录持久事件及刷新恢复；`native_identity_checks` 保存完成 turn 归属接口的实际 200 回应。

上一轮 Dify 运行 `{receipt['workflow_run_id']}`，交付 `{receipt['run_id']}`，状态 `saved / succeeded`，处理历史事件 `{receipt['history_event_id']}`。
原始完整回执为 `original_dify_receipt`；重复请求复用同一 run、文件回读一致分别由 `dify_verifier_checks` 记录。

## 可回读来源与限制

项目来源：`project/{evidence_path}`。所有上述 JSON 字段均在这份实际输入中。
CLI 原始日志来自本机隔离验收目录，已导出本次任务与提供方完成事件，不含用户凭据。
本文件修订补齐首轮评审指出的证据缺口；保存结果和模型评分分别记录，不能相互替代。
'''
        body = {'request_id': 'deeppartner04-live-turn-delivery-evidence-r1', 'project_id': pid,
            'workspace_id': project['native_id'], 'session_id': original['session_id'],
            'turn_id': original['turn_id'], 'task': 'review', 'standard_version': receipt['standard_version'],
            'artifact': {'type': 'file', 'path': 'project/verification/deeppartner-0.4-cli-receipt.md',
                'content': content, 'summary': '按评审补齐实际CLI、Dify和会话原始证据',
                'expected_modified': receipt['artifact']['modified'], 'source_paths': ['project/' + evidence_path]},
            'question_ids': [], 'validation': [{'check': 'actual-source-export', 'result': 'passed',
                'evidence': 'project/' + evidence_path}],
            'limitations': ['仅为软件接入验证，不证明科学计算、论文或任意编程任务的质量。']}
        response = api.post('/research/dify/api/deliver', data=body, headers={'Origin': ORIGIN}, timeout=180000)
        assert response.ok, response.text()[:1000]
        result = response.json()
        assert result.get('status') == 'saved' and result.get('workflow_status') == 'succeeded', result
        report = {'revision_count': 1, 'reason': 'first review required readable original evidence',
            'evidence_path': 'project/' + evidence_path, 'receipt': result,
            'original_review_id': original['automatic_quality']['result'].get('id'),
            'automatic_quality_job_id': result.get('receipt', {}).get('quality', {}).get('job_id')}
        (ROOT / 'reports/unified-delivery-evidence-revision.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps({'saved': True, 'run_id': result['run_id'],
            'workflow_status': result['workflow_status'], 'revision_count': 1,
            'quality_job_id': report['automatic_quality_job_id']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
