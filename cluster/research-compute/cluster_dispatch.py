"""One forced-command SSH endpoint for bounded, durable research computations.

Runs on the cluster's login node. Only Slurm starts numerical programs.
The matching runner stays outside experiment source directories.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import operator
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import time

ROOT = Path(os.environ.get('TUTOR_COMPUTE_ROOT', '/work/home/cluster_user/research-projects/tutor-compute'))
CONTROL = Path(__file__).resolve().parent
PYTHON = '/public/software/apps/anaconda3/2023.09/bin/python'
PASO = '/work/home/cluster_user/opensource/openpaso'
RUNTIMES = {'python': PYTHON, 'paso': PASO + '/bin/paso-python', 'torch': PASO + '/bin/torch-python'}
FINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE'}
OPS = {'lt': operator.lt, 'le': operator.le, 'gt': operator.gt, 'ge': operator.ge, 'eq': operator.eq}


def write_json(path, value):
    temporary = path.with_name(path.name + '.incoming')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def relative(value):
    value = str(value or '')
    parts = value.split('/')
    if not value or '\\' in value or ':' in value or PurePosixPath(value).is_absolute() or any(
            p in {'', '.', '..'} or p.startswith('.') for p in parts):
        raise ValueError('Use a visible experiment-relative path')
    return value


def command(args, *, timeout=25):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed: ' + args[0] + ': ' + result.stderr[-1500:])
    return result.stdout.strip()


def normalize_spec(value):
    if not isinstance(value, dict):
        raise ValueError('spec must be an object')
    question = str(value.get('question') or '').strip()
    if not question or len(question) > 6000:
        raise ValueError('A bounded scientific question is required')
    runtime = value.get('runtime', 'paso')
    if runtime not in RUNTIMES and runtime not in {'openpaso', 'openpaso_catalog'}:
        raise ValueError('runtime must be python, paso, torch, openpaso or openpaso_catalog')
    resources = value.get('resources') or {}
    resources = {'cpus': int(resources.get('cpus', 2)), 'memory_mb': int(resources.get('memory_mb', 4096)),
                 'minutes': int(resources.get('minutes', 5))}
    if not (1 <= resources['cpus'] <= 4 and 512 <= resources['memory_mb'] <= 8192 and 1 <= resources['minutes'] <= 15):
        raise ValueError('This deployment allows 1-4 CPUs, 512-8192 MB and 1-15 minutes; GPU jobs need a separate resource policy')
    files = value.get('files', [])
    if not isinstance(files, list) or len(files) > 30:
        raise ValueError('Provide at most 30 source/config files')
    seen, total, cleaned = set(), 0, []
    for item in files:
        path = relative(item['path'])
        if path in seen or path.split('/')[0] in {'outputs', 'logs', 'receipts'} or path == 'experiment.json':
            raise ValueError('Duplicate or reserved source path')
        seen.add(path)
        text = item['content']
        if not isinstance(text, str):
            raise ValueError('Source contents must be UTF-8 text')
        total += len(text.encode('utf-8'))
        cleaned.append({'path': path, 'content': text})
    if total > 1500000:
        raise ValueError('Source package exceeds 1.5 MB; use an existing staged dataset')
    entry = value.get('entrypoint', '')
    if runtime in RUNTIMES:
        entry = relative(entry)
        if entry not in seen or not entry.endswith('.py'):
            raise ValueError('entrypoint must name one supplied Python source')
    criteria = value.get('criteria', [])
    if not isinstance(criteria, list) or len(criteria) > 40:
        raise ValueError('Provide at most 40 predeclared criteria')
    for check in criteria:
        if not isinstance(check.get('name'), str) or not check['name'].strip() or check.get('op') not in OPS:
            raise ValueError('Each criterion needs name, metric, op and threshold')
        relative(check.get('metric', ''))
        if isinstance(check.get('threshold'), bool) or not isinstance(check.get('threshold'), (int, float)) or not math.isfinite(check['threshold']):
            raise ValueError('Criterion threshold must be a finite number')
    metrics = relative(value.get('metrics_path', 'outputs/metrics.json'))
    spec = {'question': question, 'runtime': runtime, 'resources': resources, 'files': cleaned,
            'entrypoint': entry, 'criteria': criteria, 'metrics_path': metrics,
            'reference': value.get('reference', {}), 'limitations': value.get('limitations', []),
            'arguments': value.get('arguments', [])}
    if not isinstance(spec['arguments'], list) or any(not isinstance(v, str) or len(v) > 1000 for v in spec['arguments']):
        raise ValueError('arguments must be a list of short strings')
    if runtime == 'openpaso':
        task = value.get('openpaso') or {}
        if not re.fullmatch(r'[a-z][a-z0-9_]+', str(task.get('tool', ''))):
            raise ValueError('Read the actual openPASO schema before specifying its tool')
        if task['tool'] in {'setup_backend', 'developer', 'reload_catalog'}:
            raise ValueError('Installation and modification of shared solvers are outside experiment execution')
        if not isinstance(task.get('arguments'), dict):
            raise ValueError('openpaso arguments must be an object matching its actual schema')
        spec['openpaso'] = task
    return spec


def prepare(payload):
    spec = normalize_spec(payload.get('spec'))
    identity = payload.get('identity') or {}
    owner = str(identity.get('owner_id') or '')
    if not owner:
        raise ValueError('The calling application must supply an owner')
    request_id = str(payload.get('request_id') or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', request_id):
        raise ValueError('A stable request_id is required')
    serialized = json.dumps([owner, request_id], sort_keys=True, ensure_ascii=False)
    ident = hashlib.sha256(serialized.encode()).hexdigest()[:24]
    ROOT.mkdir(parents=True, exist_ok=True)
    lockroot = ROOT / '.locks'
    lockroot.mkdir(exist_ok=True)
    with (lockroot / (ident + '.lock')).open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        folder = ROOT / ident
        if folder.exists():
            original = json.loads((folder / 'experiment.json').read_text())
            if original['spec'] != spec or original['identity'] != identity:
                raise ValueError('This request identity already names different immutable input')
            return {'experiment_id': ident, 'state': 'PREPARED', 'deduplicated': True, 'remote_path': str(folder)}
        folder.mkdir(mode=0o700)
        for name in ('outputs', 'logs', 'receipts'):
            (folder / name).mkdir()
        for item in spec['files']:
            target = folder / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item['content'], encoding='utf-8')
        manifest = {'schema_version': 1, 'experiment_id': ident, 'identity': identity,
                    'request_id': request_id, 'created_at': time.time(), 'spec': spec}
        write_json(folder / 'experiment.json', manifest)
        r = spec['resources']
        shell = '\n'.join(['#!/bin/bash', '#SBATCH --partition=xhacnormalb', '#SBATCH --account=cluster_user',
            '#SBATCH --nodes=1', '#SBATCH --ntasks=1', '#SBATCH --cpus-per-task=' + str(r['cpus']),
            '#SBATCH --mem=' + str(r['memory_mb']) + 'M', '#SBATCH --time=00:' + str(r['minutes']).zfill(2) + ':00',
            '#SBATCH --output=' + str(folder / 'logs/slurm-%j.out'), '#SBATCH --error=' + str(folder / 'logs/slurm-%j.err'),
            'set -euo pipefail', 'exec ' + shlex.join([PYTHON, str(CONTROL / 'cluster_runner.py'), str(folder)])]) + '\n'
        (folder / 'job.sbatch').write_text(shell)
    return {'experiment_id': ident, 'state': 'PREPARED', 'remote_path': str(folder), 'resources': r,
            'criteria_locked': len(spec['criteria']), 'submitted': False}


def experiment(payload):
    ident = str(payload.get('experiment_id') or '')
    if not re.fullmatch(r'[a-f0-9]{24}', ident):
        raise ValueError('A real experiment_id is required')
    folder = ROOT / ident
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError('Experiment not found')
    manifest = json.loads((folder / 'experiment.json').read_text())
    owner = str((payload.get('identity') or {}).get('owner_id') or '')
    if not owner or manifest['identity']['owner_id'] != owner:
        raise ValueError('Experiment belongs to a different owner')
    return folder, manifest


def submit(payload):
    folder, manifest = experiment(payload)
    with (folder / 'receipts/submit.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        receipt = folder / 'receipts/submission.json'
        if receipt.exists():
            return {**json.loads(receipt.read_text()), 'deduplicated': True}
        pending = folder / 'receipts/submitting.json'
        if pending.exists():
            return {'experiment_id': folder.name, 'state': 'SUBMISSION_UNCERTAIN',
                    'instruction': 'Inspect status and the existing Slurm name; keep the same experiment identity.'}
        write_json(pending, {'started_at': time.time(), 'job_name': 'dtv_' + folder.name})
        raw = command(['sbatch', '--parsable', '--job-name=dtv_' + folder.name, str(folder / 'job.sbatch')])
        job = raw.split(';')[0]
        if not job.isdigit():
            raise RuntimeError('Slurm did not return a numeric job id')
        result = {'experiment_id': folder.name, 'job_id': job, 'state': 'SUBMITTED',
                  'submitted_at': time.time(), 'resources': manifest['spec']['resources']}
        write_json(receipt, result)
        return result


def status(payload):
    folder, manifest = experiment(payload)
    location = folder / 'receipts/submission.json'
    if not location.exists():
        return {'experiment_id': folder.name, 'state': 'SUBMISSION_UNCERTAIN' if (folder / 'receipts/submitting.json').exists() else 'PREPARED'}
    receipt = json.loads(location.read_text())
    job = receipt['job_id']
    raw = command(['sacct', '-n', '-P', '-j', job, '--format=JobIDRaw,State,ExitCode,Elapsed,AllocCPUS,MaxRSS'])
    rows = [line.split('|') for line in raw.splitlines()]
    row = next((r for r in rows if r[0] == job), None)
    if row:
        state = row[1].split()[0].split('+')[0]
        receipt.update(state=state, exit_code=row[2], elapsed=row[3], allocated_cpus=row[4])
    else:
        live = command(['squeue', '-h', '-j', job, '-o', '%T'])
        receipt.update(state=live.splitlines()[0] if live else 'UNKNOWN')
    receipt['finished'] = receipt['state'] in FINAL
    completion = folder / 'receipts/execution.json'
    if completion.exists():
        receipt['execution'] = json.loads(completion.read_text())
    receipt['artifacts'] = [{'path': str(path.relative_to(folder)), 'bytes': path.stat().st_size}
        for path in sorted((folder / 'outputs').rglob('*')) if path.is_file() and not path.is_symlink()][:100]
    receipt['remote_path'] = str(folder)
    return receipt


def cancel(payload):
    folder, _ = experiment(payload)
    receipt = json.loads((folder / 'receipts/submission.json').read_text())
    command(['scancel', receipt['job_id']])
    current = status(payload)
    return {**current, 'cancel_requested': True, 'cancel_confirmed': current['state'] in FINAL}


def read(payload):
    folder, _ = experiment(payload)
    path = (folder / relative(payload.get('path'))).resolve()
    if not path.is_relative_to(folder) or not path.is_file():
        raise ValueError('Artifact not found inside the experiment')
    maximum = min(200000, max(1000, int(payload.get('max_bytes', 64000))))
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    return {'experiment_id': folder.name, 'path': str(path.relative_to(folder)),
            'content': data[:maximum].decode('utf-8'), 'truncated': len(data) > maximum}


def assess(payload):
    folder, manifest = experiment(payload)
    run = status(payload)
    spec = manifest['spec']
    if not run.get('finished'):
        return {'experiment_id': folder.name, 'status': 'INCONCLUSIVE', 'reason': 'Job has not reached a terminal state', 'run': run}
    execution = run.get('execution', {})
    executed = run['state'] == 'COMPLETED' and run.get('exit_code') == '0:0' and execution.get('exit_code') == 0
    metrics_path = folder / spec['metrics_path']
    metrics = {}
    if executed and metrics_path.is_file() and metrics_path.stat().st_size < 1000000:
        metrics = json.loads(metrics_path.read_text()).get('metrics', {})
    checks = []
    for check in spec['criteria']:
        value = metrics.get(check['metric'])
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
        checks.append({**check, 'observed': value, 'status': 'passed' if valid and OPS[check['op']](value, check['threshold']) else 'failed',
                       'evidence': spec['metrics_path'], 'missing_or_nonfinite': not valid})
    decision = 'FAILED' if not executed or any(c['status'] == 'failed' for c in checks) else 'NUMERICALLY_CHECKED' if checks else 'INCONCLUSIVE'
    result = {'experiment_id': folder.name, 'job_id': run.get('job_id'), 'status': decision,
              'executed': executed, 'question': spec['question'], 'checks': checks, 'reference': spec['reference'],
              'metrics_origin': 'experiment_program_output', 'criteria_origin': 'immutable_pre_submission_spec',
              'assessment_scope': 'Recorded execution and deterministic comparison against declared criteria; scientific interpretation remains with the research agent.',
              'limitations': spec['limitations'], 'run': run}
    write_json(folder / 'outputs/assessment.json', result)
    lines = ['# Computational assessment', '', 'Question: ' + spec['question'], '', 'Status: **' + decision + '**', '',
             'Slurm job: ' + str(run.get('job_id')) + '; state: ' + run['state'] + '; exit: ' + str(run.get('exit_code')), '',
             '| Check | Observed | Criterion | Result |', '|---|---:|---|---|']
    lines.extend('| ' + c['name'] + ' | ' + str(c['observed']) + ' | ' + c['op'] + ' ' + str(c['threshold']) + ' | ' + c['status'] + ' |' for c in checks)
    lines.extend(['', result['assessment_scope'], '', 'Reference supplied before execution: ' + json.dumps(spec['reference'], ensure_ascii=False),
                  '', 'Remote raw results: `' + str(folder) + '`', '', 'Limitations: ' + json.dumps(spec['limitations'], ensure_ascii=False)])
    (folder / 'outputs/assessment.md').write_text('\n'.join(lines) + '\n')
    return result


def dispatch(value):
    action = value.get('action')
    payload = value.get('payload') or {}
    if action == 'inventory':
        return {'cluster': 'xh5', 'user': os.environ.get('USER'), 'root': str(ROOT),
                'partition': command(['sinfo', '-h', '-p', 'xhacnormalb', '-o', '%P|%a|%l|%c|%m']),
                'association': command(['sacctmgr', '-n', '-P', 'show', 'assoc', 'where', 'user=cluster_user', 'format=Account,Partition,QOS']),
                'runtimes': {key: {'path': path, 'exists': Path(path).is_file()} for key, path in RUNTIMES.items()},
                'openpaso_client': '/work/home/cluster_user/.local/share/pi-research/openpaso-mcp',
                'resource_limit': {'cpus': 4, 'memory_mb': 8192, 'minutes': 15, 'gpu': False},
                'compute_requires_slurm': True}
    if action == 'openpaso_schema':
        folder, _ = experiment(payload)
        catalog = json.loads((folder / 'outputs/openpaso-catalog.json').read_text())
        tool = str(payload.get('tool') or '')
        if not tool:
            return {'tools': [t['name'] for t in catalog['tools']], 'server': catalog['server']}
        selected = next((t for t in catalog['tools'] if t['name'] == tool), None)
        if selected is None:
            raise ValueError('Tool not found in the actual recorded catalog')
        return selected
    functions = {'prepare': prepare, 'submit': submit, 'status': status, 'read': read, 'assess': assess, 'cancel': cancel}
    if action not in functions:
        raise ValueError('Unknown compute action')
    return functions[action](payload)


def main():
    try:
        raw = sys.stdin.buffer.read(2000001)
        if len(raw) > 2000000:
            raise ValueError('Request exceeds 2 MB')
        result = dispatch(json.loads(raw))
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': type(error).__name__ + ': ' + str(error)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
