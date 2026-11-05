"""Runs inside an actual Slurm allocation; records process evidence separately."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from cluster_dispatch import ROOT, RUNTIMES, write_json


def main(folder):
    job = os.environ.get('SLURM_JOB_ID', '')
    if not job or not job.isdigit():
        raise RuntimeError('A real Slurm allocation is required')
    folder = Path(folder).resolve()
    if folder.parent != ROOT or folder.is_symlink():
        raise ValueError('Experiment root mismatch')
    manifest = json.loads((folder / 'experiment.json').read_text())
    spec = manifest['spec']
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS=os.environ.get('SLURM_CPUS_PER_TASK', '1'),
               OPENBLAS_NUM_THREADS=os.environ.get('SLURM_CPUS_PER_TASK', '1'), MPLBACKEND='Agg',
               PYVISTA_OFF_SCREEN='true', APPTAINERENV_SLURM_JOB_ID=job,
               APPTAINERENV_OMP_NUM_THREADS=os.environ.get('SLURM_CPUS_PER_TASK', '1'),
               APPTAINERENV_MPLBACKEND='Agg', APPTAINERENV_PYVISTA_OFF_SCREEN='true')
    client = '/work/home/cluster_user/.local/share/pi-research/openpaso-mcp'
    if spec['runtime'] == 'openpaso_catalog':
        args = [client, '--list', '--schemas', '--output', str(folder / 'outputs/openpaso-catalog.json')]
    elif spec['runtime'] == 'openpaso':
        inputs = folder / 'receipts/openpaso-arguments.json'
        write_json(inputs, spec['openpaso']['arguments'])
        args = [client, '--tool', spec['openpaso']['tool'], '--arguments-file', str(inputs),
                '--timeout', str(min(600, spec['resources']['minutes'] * 60 - 15)),
                '--output', str(folder / 'outputs/openpaso-result.json')]
    else:
        args = [RUNTIMES[spec['runtime']], spec['entrypoint'], *spec['arguments']]
    started = time.time()
    with (folder / 'logs/program.stdout').open('wb') as stdout, (folder / 'logs/program.stderr').open('wb') as stderr:
        completed = subprocess.run(args, cwd=folder, env=env, stdout=stdout, stderr=stderr)
    write_json(folder / 'receipts/execution.json', {
        'schema_version': 1, 'experiment_id': manifest['experiment_id'], 'job_id': job,
        'host': os.uname().nodename, 'argv': args, 'exit_code': completed.returncode,
        'started_at': started, 'finished_at': time.time(),
        'runtime': spec['runtime'], 'reference_scope': 'process_execution_only',
        'stdout': 'logs/program.stdout', 'stderr': 'logs/program.stderr'})
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
