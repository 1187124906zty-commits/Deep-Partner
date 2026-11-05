"""Publish actual cluster simulation receipts and project-linked evidence."""
from pathlib import Path
import json, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'c37b9168a0db40e3b258c9c03cd56697'
DP = Path('C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe')


def cli(*args):
    run = subprocess.run([str(DP), *map(str, args)], capture_output=True,
                         encoding='utf8', timeout=180)
    if run.returncode:
        raise RuntimeError(run.stderr[-1500:] + run.stdout[-1500:])
    return json.loads(run.stdout)


def main():
    from verify_partner_workflow import client
    path = ROOT / 'reports/partner-simulation-live.json'
    live = json.loads(path.read_text(encoding='utf8'))
    assert live['status'] == 'completed'
    result = live['result']['simulation_result']
    assert result['slurm_state'] == 'COMPLETED|0:0'
    assert result['saved'] and result['read_back']
    outcome = result['result']
    assert len(outcome['checks']) == 4 and all(x['passed'] for x in outcome['checks'])
    with client() as connection:
        prefix = '/research/api/projects/' + live['project'] + '/file'
        for name in ['request.json', 'result.json', 'report.md']:
            response = connection.get(prefix, params={'path': result['project_path'] + name})
            response.raise_for_status()
            if name == 'result.json':
                assert response.json()['job_id'] == result['job_id']
                assert response.json()['result']['checks'] == outcome['checks']
            elif name == 'request.json':
                assert response.json()['simulation']['physics'] == outcome['physics']
            else:
                assert result['job_id'] in response.text and result['remote_root'] in response.text
    files = [ROOT / 'docs/集群仿真工作流.md', path]
    uploaded = cli('project', 'upload', '--project', PROJECT, *files,
                   '--category', 'documents', '--path', 'docs/workflow', '--json')
    refs = [{'path': 'docs/workflow/' + file.name} for file in files]
    record = {
        'id': 'cluster-simulation-release-20261105',
        'title': '集群仿真工作流与实际制造解验收',
        'content': '仿真通过固定 prepare/submit/monitor/validate/archive 阶段执行。'
                   'Slurm 作业25411539在计算节点完成，四项预定检查通过。'
                   '原始结果留在集群，所属项目保存输入、结果、报告和运行关系。'
                   '本次证据为理论制造解数值核验。',
        'nodes': [
            {'id': 'simulation:route', 'kind': 'method', 'label': 'Deep Partner simulate 程序路由',
             'status': 'recorded', 'evidence_refs': refs},
            {'id': 'simulation:cluster', 'kind': 'implementation', 'label': 'Slurm 计算节点求解与预定检查',
             'status': 'recorded', 'evidence_refs': refs},
            {'id': 'simulation:poisson', 'kind': 'implementation', 'label': 'Poisson 制造解：四项检查通过',
             'status': 'recorded', 'detail': json.dumps(outcome['summary'], ensure_ascii=False),
             'evidence_refs': refs},
            {'id': 'simulation:scope', 'kind': 'limitation', 'label': '本次验收范围为单个理论算例',
             'status': 'recorded', 'detail': '尚未评价具体材料模型的实验一致性或所有求解工具。',
             'evidence_refs': refs}
        ],
        'edges': [
            {'source': 'simulation:route', 'target': 'simulation:cluster', 'relation': 'uses'},
            {'source': 'simulation:poisson', 'target': 'simulation:cluster', 'relation': 'derived_from'},
            {'source': 'simulation:poisson', 'target': 'simulation:scope', 'relation': 'limited_by'}
        ]
    }
    record_path = ROOT / '.local/partner-workflow/simulation-release-record.json'
    record_path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf8')
    saved = cli('workflow', 'record', '--project', PROJECT, '--file', record_path)
    with client() as connection:
        for file in files:
            response = connection.get('/research/api/projects/' + PROJECT + '/file',
                                      params={'path': 'docs/workflow/' + file.name})
            response.raise_for_status()
            assert response.content == file.read_bytes(), file
        response = connection.get('/research/api/projects/' + PROJECT + '/research-flow/graph')
        response.raise_for_status()
        assert any(n['id'] == 'simulation:route' for n in response.json()['nodes'])
    receipt = {'project_id': PROJECT, 'run_id': live['id'], 'job_id': result['job_id'],
               'actual_project_readback': True, 'uploaded': uploaded, 'record': saved,
               'backend_targeted_tests': 17, 'slurm_state': result['slurm_state'],
               'checks_passed': len(outcome['checks'])}
    (ROOT / 'reports/partner-simulation-release.json').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in receipt.items() if k not in ('uploaded', 'record')},
                     ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    main()
