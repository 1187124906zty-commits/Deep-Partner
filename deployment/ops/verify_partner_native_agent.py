"""Verify real project routing -> native MCP -> execution -> saved files."""
from pathlib import Path
import asyncio, json, subprocess, sys, time, uuid
from verify_partner_workflow import client, ROOT, STAGE

DP = Path('C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe')
SCRIPTS = Path('C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts')
sys.path.insert(0, str(SCRIPTS))
from deepcode_native import rpc


def main():
    fixture = json.loads((STAGE / 'fixture.json').read_text(encoding='utf8'))
    previous = json.loads((ROOT / 'reports/partner-workflow-live.json').read_text(encoding='utf8'))
    pid, sid = fixture['id'], previous['session_id']
    owner = uuid.uuid5(uuid.NAMESPACE_URL, 'local-admin').hex
    workspace = Path('C:/Users/DEVELOPER/.codex/deep-partner/tool-runtime/workspaces') / owner / pid / uuid.uuid5(uuid.NAMESPACE_URL, sid).hex
    workspace.mkdir(parents=True, exist_ok=True)

    async def grant():
        row = await rpc('project/add', {'path': str(workspace), 'displayName': 'Deep Partner 软件验收', 'trustState': 'trusted'})
        project = row['project']
        if project['trustState'] != 'trusted':
            await rpc('project/update', {'projectId': project['id'], 'trustState': 'trusted'})
        result = await rpc('settings/update', {'scope': 'project', 'projectId': project['id'], 'patch': {
            'security': {'permissions': {'write': 'allow', 'edit': 'allow', 'apply_patch': 'allow',
                'bash': {'*python*': 'allow', '*pytest*': 'allow'}}}}})
        profile = result['settings']['resolvedDefaultSecurityProfile']
        assert profile['filesystemScope'] == 'workspace' and profile['commandSandbox']
        return {'project_id': project['id'], 'filesystem_scope': profile['filesystemScope'],
                'command_sandbox': profile['commandSandbox']}

    permission = asyncio.run(grant())
    request = {'kind': 'code', 'code_engine': 'agent', 'session_id': sid,
               'query': '原生DeepCode项目执行与回交的软件验收',
               'instruction': '续接刚才的软件验收。复用当前目录已有native_check.py和test_native_check.py，不重新生成文件。确认harmonic_mean的四项既有测试，使用C:/Users/DEVELOPER/DeepTutor/.venv/Scripts/python.exe -m unittest -v实际运行并报告结果。无需依赖安装。不要调用其他智能体。',
               'publish_root': 'src/native-authorized-verified', 'input_paths': [],
               'request_id': 'native-agent-authorized-verified-20261105'}
    path = STAGE / 'native-authorized-request.json'
    path.write_text(json.dumps(request, ensure_ascii=False), encoding='utf8')
    called = subprocess.run([str(DP), 'workflow', 'run', '--project', pid, '--file', str(path)],
                            capture_output=True, encoding='utf8', timeout=90)
    if called.returncode:
        raise RuntimeError(called.stderr[-1500:] + called.stdout[-1500:])
    started = json.loads(called.stdout)
    report_path = ROOT / 'reports/partner-native-authorized-live.json'
    with client() as connection:
        end = time.monotonic() + 480
        while True:
            response = connection.get('/research/api/projects/' + pid + '/research-flow/runs/' + started['id'])
            response.raise_for_status(); row = response.json()
            report_path.write_text(json.dumps({'permission': permission, 'run': row}, ensure_ascii=False, indent=2), encoding='utf8')
            if row['status'] in ('completed', 'failed', 'cancelled', 'waiting_input'):
                break
            if time.monotonic() > end:
                raise TimeoutError('Native task remains active; preserve its existing run id')
            time.sleep(3)
        assert row['status'] == 'completed', row.get('error') or row.get('result')
        code = row['result']['code_result']
        assert code['native_tool'] and len(code['files']) == 2
        output = ROOT / '.local/partner-workflow/native-authorized-files'
        output.mkdir(exist_ok=True)
        for entry in code['files']:
            response = connection.get('/research/api/projects/' + pid + '/file', params={'path': entry['path']})
            response.raise_for_status()
            assert len(response.content) == entry['bytes'] and entry['read_back']
            (output / Path(entry['path']).name).write_bytes(response.content)
    verification = subprocess.run([sys.executable, '-m', 'unittest', '-v'], cwd=output,
                                   capture_output=True, encoding='utf8', timeout=45)
    assert verification.returncode == 0, verification.stderr
    report = {'permission': permission, 'run': row, 'project_file_readback': True,
              'independent_verification': {'exit_code': verification.returncode,
                                          'stdout': verification.stdout, 'stderr': verification.stderr}}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'run_id': row['id'], 'status': row['status'], 'native_session': row['result']['native_code']['mcp_session_id'],
                      'saved_files': len(code['files']), 'actual_readback': True,
                      'independent_tests': verification.stderr[-1200:]}, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    main()
