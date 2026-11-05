"""Use the installed ScanSci session, verify a cluster copy, then deliver that copy."""
from pathlib import Path
from datetime import datetime,timezone
from difflib import SequenceMatcher
import argparse,hashlib,json,logging,os,re,shlex,subprocess,threading,time
import requests

SSH='C:/Windows/System32/OpenSSH/ssh.exe'
SCP='C:/Windows/System32/OpenSSH/scp.exe'
CLUSTER='research-cluster-xh5'
CLUSTER_PYTHON='/public/software/apps/anaconda3/2023.09/bin/python'
CLUSTER_ROOT='/work/home/cluster_user/research-projects/deeptutor-integration/research-workbench/literature'


def stamp():return datetime.now(timezone.utc).isoformat()
def atomic(path,value):
    pending=path.with_suffix('.pending');pending.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');pending.replace(path)

def remote(code,timeout=60):
    result=subprocess.run([SSH,'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',CLUSTER,CLUSTER_PYTHON+' -'],input=code.encode('utf8'),capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError('集群操作未完成：'+result.stderr.decode('utf8',errors='replace')[-700:])
    return json.loads(result.stdout.decode('utf8').strip().splitlines()[-1])


def inspect_pdf(source,job):
    import fitz
    size=source.stat().st_size
    if not 200<size<=100*1024**2:raise RuntimeError('PDF 大小无效或超过100MiB')
    with fitz.open(source) as doc:
        if not len(doc) or doc.is_encrypted:raise RuntimeError('下载文件没有可阅读页面')
        excerpt='\n'.join(doc[i].get_text() for i in range(min(2,len(doc))))
        metadata=doc.metadata or {};pages=len(doc)
        spans=[s for b in doc[0].get_text('dict').get('blocks',[]) for line in b.get('lines',[]) for s in line.get('spans',[]) if s.get('text','').strip()]
        title=' '.join(s['text'] for s in spans if s['size']>=max((s['size'] for s in spans),default=0)-.3)
    identity=job['identifier'].removeprefix('arXiv:').casefold();compact=re.sub(r'\s+','',excerpt).casefold()
    clean=lambda s:re.sub(r'[\W_]+','',s or '').casefold()
    expected=clean(job.get('entry',{}).get('title',''));title_match=bool(expected and (expected in clean(excerpt) or max(SequenceMatcher(None,expected,clean(title)).ratio(),SequenceMatcher(None,expected,clean(metadata.get('title',''))).ratio())>.86))
    if identity not in compact and not title_match:raise RuntimeError('已下载 PDF 与所选文献的 DOI/arXiv/首页标题不一致，保留本机文件供核对')
    with source.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    return {'sha256':digest,'bytes':size,'pages':pages,'local_path':str(source.resolve()),'identity_match':'identifier' if identity in compact else 'title'}


def upload_cluster(source,job,inspection):
    assert job['cluster_root']==CLUSTER_ROOT,'Unexpected cluster root'
    assert re.fullmatch(r'[a-f0-9]{32}',job['owner_key']) and re.fullmatch(r'[a-f0-9]{32}',job['project']) and re.fullmatch(r'[a-f0-9]{32}',job['id'])
    root=CLUSTER_ROOT+'/owners/'+job['owner_key']+'/'+job['project'];final=root+'/papers/'+inspection['sha256']+'.pdf';pending=root+'/incoming/'+job['id']+'.pdf.part'
    value=remote('from pathlib import Path\nimport json,hashlib\nr=Path('+repr(root)+')\nfor d in [r/"papers",r/"incoming",r/"receipts"]:d.mkdir(parents=True,exist_ok=True)\np=Path('+repr(final)+')\nprint(json.dumps({"exists":p.is_file(),"bytes":p.stat().st_size if p.is_file() else 0,"sha256":hashlib.file_digest(p.open("rb"),"sha256").hexdigest() if p.is_file() else ""}))')
    if not (value['exists'] and value['sha256']==inspection['sha256'] and value['bytes']==inspection['bytes']):
        result=subprocess.run([SCP,'-q','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',str(source),CLUSTER+':'+pending],capture_output=True,timeout=300)
        if result.returncode:raise RuntimeError('PDF 上传集群失败：'+result.stderr.decode('utf8',errors='replace')[-600:])
    receipt={**inspection,'connection':CLUSTER,'cluster_path':final,'cluster_verified':True,'verified_at':stamp(),'payload_origin':'cluster'}
    code='from pathlib import Path\nimport json,hashlib,os\np=Path('+repr(pending)+');target=Path('+repr(final)+')\nsource=p if p.exists() else target\nwith source.open("rb") as f:digest=hashlib.file_digest(f,"sha256").hexdigest()\nassert digest=='+repr(inspection['sha256'])+' and source.stat().st_size=='+str(inspection['bytes'])+',"Transfer mismatch"\nif source==p:os.replace(p,target)\nreceipt='+repr(receipt)+'\nPath('+repr(root+'/receipts/'+job['id']+'.json')+').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf8")\nwith Path('+repr(CLUSTER_ROOT+'/transfer-manifest.jsonl')+').open("a",encoding="utf8") as f:f.write(json.dumps({**receipt,"owner_key":'+repr(job['owner_key'])+',"project":'+repr(job['project'])+',"job":'+repr(job['id'])+'},ensure_ascii=False)+"\\n")\nprint(json.dumps(receipt))'
    return remote(code)


def deliver_cluster(job,receipt,url,token):
    """Send the accepted cluster file directly to the owning workbench job."""
    code='''from pathlib import Path
import hashlib,json,uuid
from urllib.request import Request,urlopen
path=Path(PATH)
payload=path.read_bytes()
receipt=RECEIPT
assert len(payload)==receipt['bytes'] and hashlib.sha256(payload).hexdigest()==receipt['sha256'],'Cluster file changed'
boundary='workbench-'+uuid.uuid4().hex
parts=[('--'+boundary+'\\r\\nContent-Disposition: form-data; name="transfer"\\r\\n\\r\\n'+json.dumps(receipt)+'\\r\\n').encode(),('--'+boundary+'\\r\\nContent-Disposition: form-data; name="file"; filename="paper.pdf"\\r\\nContent-Type: application/pdf\\r\\n\\r\\n').encode(),payload,('\\r\\n--'+boundary+'--\\r\\n').encode()]
request=Request(URL,data=b''.join(parts),headers={'Content-Type':'multipart/form-data; boundary='+boundary,'x-workbench-delivery':TOKEN},method='POST')
with urlopen(request,timeout=240) as response:result=json.load(response)
print(json.dumps(result,ensure_ascii=False))
'''
    code=code.replace('PATH',repr(receipt['cluster_path'])).replace('RECEIPT',repr(receipt)).replace('URL',repr(url)).replace('TOKEN',repr(token))
    return remote(code,timeout=270)


class Worker:
    def __init__(self,config):
        self.config=config;self.output=Path(config['output']);self.output.mkdir(parents=True,exist_ok=True)
        self.status_path=Path(config['_config_path']).with_suffix('.status.json') if config.get('_config_path') else None
        self.current_job=None;self.current_phase='idle';self.status_lock=threading.Lock()
        self.base=config['origin'].rstrip('/')+'/research/api/download-worker'
        self.session=requests.Session();self.session.trust_env=False;self.session.headers['x-workbench-worker']=config['token']
    def report(self,state,error=''):
        if not self.status_path:return
        with self.status_lock:atomic(self.status_path,{'pid':os.getpid(),'heartbeat':time.time(),'state':state,'job_id':self.current_job,'phase':self.current_phase,'error':error[:500]})
    def progress(self,job,phase,transfer=None):
        self.current_phase=phase;self.report('working')
        payload={'phase':phase}
        if transfer:payload['transfer']=transfer
        response=self.session.post(self.base+'/'+job['id']+'/progress',json=payload,timeout=30);response.raise_for_status()
        if response.json().get('cancelled'):raise RuntimeError('任务已由用户取消；已有本机和集群副本保留')
    def run(self,job):
        self.current_job=job['id'];self.current_phase='downloading';self.report('working')
        folder=self.output/job['id'];folder.mkdir(parents=True,exist_ok=True);state_path=folder/'pipeline.json';state=json.loads(state_path.read_text(encoding='utf8')) if state_path.exists() else {}
        stop=threading.Event();phase={'value':'downloading'}
        def heartbeat():
            while not stop.wait(25):
                try:self.progress(job,phase['value'])
                except Exception:pass
        thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
        try:
            source=Path(state['source']) if state.get('source') else None
            if not source or not source.is_file():
                self.progress(job,'downloading')
                from scansci_pdf.server import scansci_pdf_download
                raw=scansci_pdf_download(identifier=job['identifier'],output_dir=str(folder),scihub_enabled=False,strategy='legal_only',use_tor=False,use_vpnsci=True)
                value=json.loads(raw) if isinstance(raw,str) else raw
                if not value.get('success') or not value.get('file'):raise RuntimeError(value.get('error') or value.get('reason') or '需要在 ScanSci 专用浏览器中完成机构认证')
                source=Path(value['file']);state.update(source=str(source),downloaded=stamp(),download_source=value.get('source','ScanSci'));atomic(state_path,state)
            phase['value']='validating';self.progress(job,'validating');inspection=inspect_pdf(source,job);state['inspection']=inspection;atomic(state_path,state)
            phase['value']='cluster_upload';self.progress(job,'cluster_upload',inspection);receipt=upload_cluster(source,job,inspection);state['transfer']=receipt;atomic(state_path,state)
            phase['value']='cluster_verified';self.progress(job,'cluster_verified',receipt)
            # A job-scoped temporary credential lets the cluster send its copy
            # directly, avoiding a second large transfer through this computer.
            phase['value']='delivering';self.progress(job,'delivering',receipt)
            response=self.session.post(self.base+'/'+job['id']+'/delivery-ticket',timeout=30);response.raise_for_status();ticket=response.json()
            saved=deliver_cluster(job,receipt,self.base+'/'+job['id']+'/result',ticket['token'])
            if not saved.get('saved'):raise RuntimeError('用户文件夹未接收全文，保留本机与集群副本')
            state.update(completed=stamp(),receipt=saved.get('receipt'));atomic(state_path,state)
            if source.resolve().is_relative_to(folder.resolve()):source.unlink(missing_ok=True)
            print(json.dumps({'job':job['id'],'status':'completed','cluster_path':receipt['cluster_path'],'user_asset':saved.get('receipt',{}).get('name'),'bytes':receipt['bytes']},ensure_ascii=False),flush=True)
        except Exception as error:
            message=str(error)[:900];state.update(error=message,failed_at=stamp());atomic(state_path,state)
            try:self.session.post(self.base+'/'+job['id']+'/result',data={'error':message},timeout=30)
            except requests.RequestException:pass
            print(json.dumps({'job':job['id'],'status':'failed','error':message},ensure_ascii=False),flush=True)
        finally:
            stop.set();thread.join(timeout=1);self.current_job=None;self.current_phase='idle';self.report('idle')
    def loop(self,once=False):
        while True:
            try:
                self.report('idle')
                response=self.session.get(self.base+'/next',timeout=35);response.raise_for_status();job=response.json().get('job')
                if job:self.run(job)
            except Exception as error:
                self.report('error',str(error));print(json.dumps({'status':'worker_wait','error':str(error)[:400]},ensure_ascii=False),flush=True)
            if once:return
            time.sleep(15)


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--once',action='store_true');args=p.parse_args()
    config=json.loads(Path(args.config).read_text(encoding='utf8'));config['_config_path']=str(Path(args.config).resolve());logging.basicConfig(level=logging.ERROR)
    os.environ.setdefault('SCANSCI_PDF_DATA_DIR',str(Path(os.environ['LOCALAPPDATA'])/'ScanSciPDF'))
    # One device configuration has one active local browser/download worker.
    # Lock lifetime is the process lifetime; a crash releases the OS lease.
    lock_path=Path(args.config).resolve().with_suffix('.worker.lock')
    with lock_path.open('a+b') as lease:
        try:
            lease.seek(0)
            if os.name=='nt':
                import msvcrt
                if lock_path.stat().st_size==0:lease.write(b'1');lease.flush();lease.seek(0)
                msvcrt.locking(lease.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise SystemExit('This ScanSci device configuration already has an active worker')
        Worker(config).loop(args.once)


if __name__=='__main__':main()
