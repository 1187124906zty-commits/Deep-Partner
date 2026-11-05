"""Submit/reconnect a bounded PDF parsing job using the existing cluster runtime."""
from pathlib import Path
import base64,hashlib,json,re,shlex,subprocess,time

BASE='/work/home/cluster_user/research-projects/deeptutor-integration/research-workbench/literature'
HOST='research-cluster-xh5'
PYTHON='/public/software/apps/anaconda3/2023.09/bin/python'

def ssh(command,timeout=45):
    r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',HOST,command],capture_output=True,timeout=timeout)
    if r.returncode==255:raise ConnectionError('Cluster SSH connection unavailable; existing job identity retained')
    if r.returncode:raise RuntimeError('Cluster command failed: '+r.stderr.decode('utf8',errors='replace')[-1000:])
    return r.stdout.decode('utf8').strip()
def scp(local,remote):
    result=subprocess.run(['scp','-q',str(local),HOST+':'+remote],capture_output=True,timeout=90)
    if result.returncode==255:raise ConnectionError('Cluster transfer connection unavailable; existing operation retained')
    if result.returncode:raise RuntimeError('Cluster transfer failed: '+result.stderr.decode('utf8',errors='replace')[-700:])

def submit_once(script):
    """Remote lock and receipt survive an SSH client disconnect after sbatch."""
    code='''from pathlib import Path
import fcntl,json,os,signal,subprocess
script=Path(SCRIPT)
receipt=script.with_suffix('.submission.json')
signal.signal(signal.SIGHUP,signal.SIG_IGN)
with script.with_suffix('.submission.lock').open('a+b') as lease:
 fcntl.flock(lease,fcntl.LOCK_EX)
 if receipt.is_file():
  job=json.loads(receipt.read_text())['job_id']
 else:
  job=subprocess.check_output(['sbatch','--parsable',str(script)],text=True).strip().split(';')[0]
  assert job.isdecimal(),'Slurm returned no job identity'
  temporary=receipt.with_suffix('.pending');temporary.write_text(json.dumps({'job_id':job,'script':str(script)}));os.replace(temporary,receipt)
 print(job)
'''.replace('SCRIPT',repr(script))
    encoded=base64.b64encode(code.encode()).decode()
    return ssh(PYTHON+' -c '+shlex.quote('import base64;exec(base64.b64decode('+repr(encoded)+'))'))

def parse(payload,persist):
    owner=payload['owner_key'];pid=payload['project_id'];digest=payload['sha256']
    if not re.fullmatch(r'[a-f0-9]{32}',owner) or not re.fullmatch(r'[a-f0-9]{32}',pid) or not re.fullmatch(r'[a-f0-9]{64}',digest):raise ValueError('Cluster document identity is invalid')
    root=BASE+'/owners/'+owner+'/'+pid;source=root+'/papers/'+digest+'.pdf';output=root+'/parsed/'+digest+'/reader-v1';tools=root+'/parse-tools'
    local=Path(payload['local_state']);local.mkdir(parents=True,exist_ok=True);statefile=local/'cluster-job.json'
    state=json.loads(statefile.read_text(encoding='utf8')) if statefile.is_file() else {}
    def saved():statefile.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8');persist({'cluster':state})
    if not state.get('verified'):
        ssh('mkdir -p '+shlex.quote(root+'/papers')+' '+shlex.quote(output)+' '+shlex.quote(tools))
        actual=ssh('if test -f '+shlex.quote(source)+'; then sha256sum '+shlex.quote(source)+'; fi').split()
        if not actual or actual[0]!=digest:
            if not payload.get('pdf_b64'):raise ValueError('Verified cluster PDF is missing and no original PDF was supplied')
            data=base64.b64decode(payload['pdf_b64'],validate=True)
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Original PDF identity mismatch')
            p=local/'source.pdf';p.write_bytes(data);scp(p,source)
        check=ssh('sha256sum '+shlex.quote(source)).split()[0]
        if check!=digest:raise ValueError('Cluster PDF byte verification failed')
        state.update(verified=True,source=source,output=output);saved()
    ready=ssh('if test -s '+shlex.quote(output+'/receipt.json')+'; then cat '+shlex.quote(output+'/receipt.json')+'; fi')
    if ready:
        receipt=json.loads(ready)
        if receipt['sha256']==digest:state.update(cached=True,job_id=receipt.get('cluster_job_id'));saved()
        else:raise ValueError('Cached parsing source changed')
    elif not state.get('job_id'):
        for name,path in [('worker.py',Path(__file__).with_name('cluster_pdf_worker.py')),('reader_processor.py',Path('D:/Development/research-workbench/server/reader_processor.py'))]:scp(path,tools+'/'+name)
        script='''#!/bin/bash
#SBATCH --job-name=dp-pdf-parse
#SBATCH --partition=xhacnormalb
#SBATCH --account=cluster_user
#SBATCH --qos=user_cluster_user
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=6000M
#SBATCH --time=00:40:00
#SBATCH --output=OUTPUT/parse-%j.log
set -euo pipefail
module purge
module load apps/apptainer/1.3.4
tool=/work/home/cluster_user/tools/mineru
export APPTAINERENV_PYTHONPATH="$tool/env/lib/python3.12/site-packages:/work/home/cluster_user/opensource/openpaso/envs/torch/lib/python3.12/site-packages"
export APPTAINERENV_LD_LIBRARY_PATH="$tool/native"
export APPTAINERENV_SLURM_JOB_ID="$SLURM_JOB_ID"
export APPTAINERENV_OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export APPTAINERENV_MINERU_MODEL_SOURCE=local
export APPTAINERENV_MINERU_TOOLS_CONFIG_JSON="$tool/mineru.json"
export APPTAINERENV_MINERU_DEVICE_MODE=cpu
export APPTAINERENV_MINERU_PROCESSING_WINDOW_SIZE=1
export APPTAINERENV_HF_HUB_OFFLINE=1
export APPTAINERENV_TRANSFORMERS_OFFLINE=1
export APPTAINERENV_MINERU_TELEMETRY_DISABLED=1
apptainer exec --writable --cleanenv --bind /work --home /work/home/cluster_user:/work/home/cluster_user /work/home/cluster_user/opensource/openpaso/containers/python-runtime "$tool/env/bin/python" TOOLS/worker.py --source SOURCE --output OUTPUT --parser TOOLS/reader_processor.py
'''.replace('OUTPUT',output).replace('--source SOURCE','--source '+source).replace('TOOLS/worker.py',tools+'/worker.py').replace('TOOLS/reader_processor.py',tools+'/reader_processor.py')
        assert 'APPTAINERENV_MINERU_MODEL_SOURCE=local' in script and 'APPTAINERENV_MINERU_TOOLS_CONFIG_JSON=' in script
        batch=local/'parse.sbatch';batch.write_text(script,encoding='utf8',newline='\n');scp(batch,output+'/parse.sbatch')
        # Unknown submission outcome is retained; never blindly create a second Slurm job.
        state['submission']='submitting';saved()
        job=submit_once(output+'/parse.sbatch').split(';')[0]
        if not job.isdecimal():raise ValueError('Slurm did not return a job id')
        state.update(job_id=job,submission='submitted');saved()
    while not ready:
        status=ssh('sacct -j '+state['job_id']+' -X --noheader --parsable2 --format=State,ExitCode').splitlines()
        state['slurm_state']=status[0] if status else 'not_yet_accounted';saved()
        if status and status[0].split('|')[0] in ('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL'):
            if not status[0].startswith('COMPLETED|0:0'):
                log=ssh('tail -45 '+shlex.quote(output+'/parse-'+state['job_id']+'.log'))
                if 'not a valid identifier' in log and 'APPTAINERENV_MINERU_' in log and not state.get('script_repaired'):
                    state.setdefault('attempts',[]).append({'job_id':state['job_id'],'status':status[0],'diagnosis':'template replacement damaged a known environment variable','repair':'regenerate the exact argument placeholders'})
                    state.pop('job_id');state['submission']='reconciled_failed';state['script_repaired']=True;saved()
                    return parse(payload,persist)
                raise RuntimeError('Cluster parsing failed: '+status[0]+'; retained '+output+'/parse-'+state['job_id']+'.log')
            ready=ssh('cat '+shlex.quote(output+'/receipt.json'));break
        time.sleep(12)
    packet=json.loads(ssh('cat '+shlex.quote(output+'/pages.json'),timeout=60))
    receipt=json.loads(ready)
    if packet['sha256']!=digest or len(packet['pages'])!=packet['page_count']:raise ValueError('Parsing page coverage or source verification failed')
    return {'receipt':receipt,'packet':packet,'markdown':'\n\n---\n\n'.join('<!-- pdf_page:'+str(p['page'])+' -->\n\n'+p['text'] for p in packet['pages']),
            'cluster_path':output,'job_id':state.get('job_id'),'cached':state.get('cached',False)}
