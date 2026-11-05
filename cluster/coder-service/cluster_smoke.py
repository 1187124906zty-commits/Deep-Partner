"""SSH/SCP/Slurm round trip from inside the real coder container."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import time

HOST='research-cluster-xh5'
REMOTE='/work/home/cluster_user/research-projects/deeptutor-integration'
LOCAL=Path('/workspace/coder/cluster-validation')
LOCAL.mkdir(exist_ok=True)


def run(args,timeout=40):
    result=subprocess.run(args,text=True,encoding='utf-8',capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError(f'{args[0]} failed: {result.stderr[-1200:]}')
    return result.stdout.strip()


identity=run(['ssh',HOST,'hostname; id -un; pwd']).splitlines()
assert identity[-2:]==['cluster_user','/work/home/cluster_user'],identity
code='''import json,math,os,socket,sys
from pathlib import Path
n=64;D=0.02;dx=1/n;dt=0.2*dx*dx/D;steps=120
u=[1+0.2*math.cos(2*math.pi*j/n) for j in range(n)]
mass0=sum(u)*dx
for k in range(steps):
    u=[u[j]+D*dt/(dx*dx)*(u[(j-1)%n]-2*u[j]+u[(j+1)%n]) for j in range(n)]
t=steps*dt
exact=[1+0.2*math.exp(-D*4*math.pi**2*t)*math.cos(2*math.pi*j/n) for j in range(n)]
mass_error=abs(sum(u)*dx-mass0)
relative_l2=(sum((a-b)**2 for a,b in zip(u,exact))/sum(a*a for a in exact))**0.5
result={'job_id':os.environ['SLURM_JOB_ID'],'host':socket.gethostname(),'python':sys.version.split()[0],
        'benchmark':'periodic 1D diffusion, finite difference against Fourier mode',
        'n':n,'steps':steps,'D':D,'dt':dt,'mass_error':mass_error,'relative_l2':relative_l2,
        'nonnegative':min(u)>=0,'verified':mass_error<1e-12 and relative_l2<0.005}
Path('results/connection-smoke.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
assert result['verified']
'''
(LOCAL/'connection_smoke.py').write_text(code,'utf-8')
sbatch=f'''#!/bin/bash
#SBATCH --job-name=deeptutor-connect
#SBATCH --partition=xhacnormalb
#SBATCH --account=cluster_user
#SBATCH --qos=user_cluster_user
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=128M
#SBATCH --time=00:02:00
#SBATCH --chdir={REMOTE}
#SBATCH --output={REMOTE}/logs/connect-%j.out
#SBATCH --error={REMOTE}/logs/connect-%j.err
set -euo pipefail
/public/software/apps/anaconda3/2023.09/bin/python scripts/connection_smoke.py
'''
(LOCAL/'connection.sbatch').write_text(sbatch,'utf-8')
run(['ssh',HOST,f'mkdir -p {REMOTE}/scripts {REMOTE}/jobs {REMOTE}/logs {REMOTE}/results {REMOTE}/research'])
run(['scp',str(LOCAL/'connection_smoke.py'),HOST+':'+REMOTE+'/scripts/connection_smoke.py'])
run(['scp',str(LOCAL/'connection.sbatch'),HOST+':'+REMOTE+'/jobs/connection.sbatch'])
jid=run(['ssh',HOST,f'sbatch --parsable {REMOTE}/jobs/connection.sbatch']).split(';')[0]
assert jid.isdigit(),jid
print(json.dumps({'submitted_job':jid,'remote_root':REMOTE}),flush=True)
state=''
for _ in range(40):
    state=run(['ssh',HOST,f'sacct -j {jid} -n -P --format=JobIDRaw,State,ExitCode'],timeout=25)
    row=next((line.split('|') for line in state.splitlines() if line.split('|')[0]==jid),None)
    if row and row[1] in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY'}:break
    time.sleep(3)
if not row or row[1]!='COMPLETED' or row[2]!='0:0':
    raise RuntimeError('Slurm not completed successfully: '+state)
run(['scp',HOST+':'+REMOTE+'/results/connection-smoke.json',str(LOCAL/'connection-smoke.json')])
result=json.loads((LOCAL/'connection-smoke.json').read_text())
assert result['job_id']==jid and result['verified']
result.update(identity=identity,slurm_accounting=state,remote_root=REMOTE,
              authentication='dedicated source-restricted service public key; workstation key not copied',
              verified_at=datetime.now(timezone.utc).isoformat())
(LOCAL/'cluster-connection-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
state_text=f'''# DeepTutor 集群接入验证

这是独立的接入测试目录，不覆盖任何科研项目。
SSH身份：cluster_user，home /work/home/cluster_user。使用来自网页服务器的专用受限公钥，不依赖本机在线。
输入脚本 {REMOTE}/scripts/connection_smoke.py；Slurm脚本 jobs/connection.sbatch。
JobID {jid}，最终 COMPLETED，ExitCode 0:0。结果 results/connection-smoke.json。
数值检查：周期一维扩散，64点120步，质量误差 {result['mass_error']:.3g}，对傅里叶解析解相对L2误差 {result['relative_l2']:.3g}。
来源：编码容器 /workspace/coder/cluster-validation/；脚本经SCP上传，Slurm执行，摘要经SCP回传且核对JobID。
这仅验证认证、文件传输、Slurm执行及结果回查，不代表所有求解器、模型或GPU环境均已验证。
'''
(LOCAL/'STATE.md').write_text(state_text,'utf-8')
run(['scp',str(LOCAL/'STATE.md'),HOST+':'+REMOTE+'/research/STATE.md'])
print(json.dumps(result,ensure_ascii=False),flush=True)

