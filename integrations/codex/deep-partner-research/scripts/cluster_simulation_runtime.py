"""Durable cluster simulation stages over existing runtimes and Slurm."""
from pathlib import Path,PurePosixPath
import base64,json,re,shlex,subprocess,time
from cluster_pdf_runtime import ssh,scp,submit_once

BASE='/work/home/cluster_user/research-projects/deeptutor-integration/simulations'
RUNTIMES={'paso':'/work/home/cluster_user/opensource/openpaso/bin/paso-python','dune':'/work/home/cluster_user/opensource/openpaso/bin/dune-python','torch':'/work/home/cluster_user/opensource/openpaso/bin/torch-python'}

def relative(value):
    path=PurePosixPath(value)
    if path.is_absolute() or '\\' in value or any(v in ('','..','.') for v in value.split('/')):raise ValueError('Simulation input path is invalid')
    return path.as_posix()

def run(payload,persist):
    owner=payload['owner_key'];pid=payload['project_id'];jid=payload['run_id'];spec=payload['simulation']
    if any(not re.fullmatch(r'[a-f0-9]{32}',value) for value in (owner,pid,jid)):raise ValueError('Simulation project identity is invalid')
    remote=BASE+'/owners/'+owner+'/'+pid+'/runs/'+jid;local=Path(payload['local_state']);local.mkdir(parents=True,exist_ok=True)
    file=local/'cluster-job.json';state=json.loads(file.read_text(encoding='utf8')) if file.is_file() else {'remote_root':remote,'stage':'prepare','attempts':[]}
    def save():file.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8');persist({'cluster':state})
    if not state.get('prepared'):
        ssh('mkdir -p '+shlex.quote(remote+'/results'))
        for item in payload.get('inputs',[]):
            name=relative(item['path']);path=local/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(base64.b64decode(item['content_b64'],validate=True))
            ssh('mkdir -p '+shlex.quote(str(PurePosixPath(remote)/PurePosixPath(name).parent)));scp(path,remote+'/'+name)
        request=local/'request.json';request.write_text(json.dumps({'simulation':spec},ensure_ascii=False,indent=2),encoding='utf8');scp(request,remote+'/request.json');scp(Path(__file__).with_name('simulation_worker.py'),remote+'/workflow-worker.py')
        cpu=spec['resources']['cpus'];memory=spec['resources']['memory_mb'];seconds=spec['resources']['walltime_seconds'];duration=f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}'
        batch='\n'.join(['#!/bin/bash','#SBATCH --job-name=dp-simulation','#SBATCH --partition=xhacnormalb','#SBATCH --account=cluster_user','#SBATCH --qos=user_cluster_user','#SBATCH --nodes=1','#SBATCH --ntasks=1',f'#SBATCH --cpus-per-task={cpu}',f'#SBATCH --mem={memory}M',f'#SBATCH --time={duration}',f'#SBATCH --output={remote}/results/slurm-%j.log','set -euo pipefail','export PYVISTA_OFF_SCREEN=true MPLBACKEND=Agg','export APPTAINERENV_SLURM_JOB_ID="$SLURM_JOB_ID"','cd '+shlex.quote(remote),shlex.quote(RUNTIMES[spec['runtime']])+' '+shlex.quote(remote+'/workflow-worker.py')+' --request '+shlex.quote(remote+'/request.json')])+'\n'
        script=local/'simulation.sbatch';script.write_text(batch,encoding='utf8',newline='\n');scp(script,remote+'/simulation.sbatch');state.update(prepared=True,stage='submit');save()
    result_path=remote+'/results/workflow-result.json'
    if not state.get('job_id'):
        state['submission']='submitting';save();job=submit_once(remote+'/simulation.sbatch').split(';')[0]
        if not job.isdecimal():raise ValueError('Slurm did not return a simulation job id')
        state.update(job_id=job,submission='submitted',stage='monitor');save()
    while True:
        status=ssh('sacct -j '+state['job_id']+' -X --noheader --parsable2 --format=State,ExitCode').splitlines();state['slurm_state']=status[0] if status else 'not_yet_accounted';save()
        if status and status[0].split('|')[0] in ('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL'):break
        time.sleep(12)
    raw=ssh('if test -s '+shlex.quote(result_path)+'; then cat '+shlex.quote(result_path)+'; fi',timeout=60)
    if not raw:
        diagnostic=ssh('tail -35 '+shlex.quote(remote+'/results/slurm-'+state['job_id']+'.log'))
        raise RuntimeError('Simulation '+state['slurm_state']+' without result receipt; retained '+remote+'; '+diagnostic[-1200:])
    result=json.loads(raw)
    if result.get('job_id')!=state['job_id']:raise ValueError('Simulation result refers to another job')
    if state['slurm_state']!='COMPLETED|0:0' and result.get('status')=='completed':result.update(status='failed',error='Slurm did not complete successfully: '+state['slurm_state'])
    state['stage']='validate';save()
    return {'job_id':state['job_id'],'slurm_state':state['slurm_state'],'remote_root':remote,'result':result,'input_manifest':[item['path'] for item in payload.get('inputs',[])]}
