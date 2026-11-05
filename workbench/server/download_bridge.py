"""Batch download queue: local ScanSci -> verified cluster copy -> owning workspace."""
from pathlib import Path,PurePosixPath
from urllib.parse import unquote
import asyncio,hashlib,json,re,secrets,time,uuid
from fastapi import Depends,File,Form,HTTPException,Request,UploadFile
from .native import actor
from .storage import atomic_json,child,now
from .literature_providers import doi_key,title_key

CLUSTER_ROOT='/work/home/cluster_user/research-projects/deeptutor-integration/research-workbench/literature'
PHASES={'queued':'等待下载设备','downloading':'本机 ScanSci 下载中','validating':'核对本机 PDF','cluster_upload':'上传至计算集群','cluster_verified':'集群副本已验收','delivering':'从集群传递至用户文件夹','completed':'已加入文献库','failed':'下载未完成','cancelled':'已取消'}


def device_owner(value):
    # Legacy operator device keeps servicing its administrator; public accounts
    # must pair their own device and cannot inherit that institution session.
    return 'local-admin' if value.get('owner')=='*' else value.get('owner')


def device_allows(value,owner):
    return not value.get('revoked_at') and device_owner(value)==owner


def identifier(entry):
    value=doi_key(entry.get('doi') or entry.get('identifier'))
    if re.fullmatch(r'10\.\d{4,9}/\S+',value):return value
    value=str(entry.get('arxiv') or entry.get('identifier') or '').strip()
    match=re.fullmatch(r'(?:https?://arxiv.org/(?:abs|pdf)/|arXiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)(?:\.pdf)?',value,re.I)
    return 'arXiv:'+match[1] if match else ''


def paper_filename(entry,identity):
    title=re.sub(r'[<>:"/\\|?*\x00-\x1f]+',' ',str(entry.get('title') or identity)).strip(' .')[:140]
    return (title or 'paper')+'-'+hashlib.sha256(identity.encode()).hexdigest()[:8]+'.pdf'


def install(app,store,api_path):
    file=store.root/'download-workers.json'
    def read():return json.loads(file.read_text()) if file.exists() else {}
    def worker(request):
        token=request.headers.get('x-workbench-worker','');key=hashlib.sha256(token.encode()).hexdigest()
        with store.lock('download-workers'):
            rows=read();entry=rows.get(key)
            if not entry or entry.get('revoked_at'):raise HTTPException(403,'下载设备未配对或已撤销')
            entry['last_seen']=time.time();rows[key]=entry;atomic_json(file,rows)
        return {**entry,'owner':device_owner(entry),'worker_id':key}
    def get_job(value,jid):
        with store.db() as db:row=db.execute("SELECT * FROM jobs WHERE id=? AND kind='literature-download'",(jid,)).fetchone()
        if not row or value['owner']!=row['owner']:raise HTTPException(404,'下载任务不存在')
        result=json.loads(row['result'])
        if result.get('worker_id') and result['worker_id']!=value['worker_id']:raise HTTPException(403,'任务属于另一下载设备')
        return dict(row),result
    def update(jid,result,phase,*,status=None,**extra):
        result.update(phase=phase,heartbeat=time.time(),**extra)
        history=result.setdefault('timeline',[])
        if not history or history[-1].get('phase')!=phase:history.append({'phase':phase,'time':now()})
        store.set_job(jid,result=result,stage=PHASES[phase],**({'status':status} if status else {}))
    def present(row):
        result=row['result'] if isinstance(row.get('result'),dict) else json.loads(row['result'])
        return {**{k:row[k] for k in ('id','status','stage','created','updated','error')},**{k:result.get(k) for k in ('entry','identifier','folder','phase','batch_id','timeline','receipt','transfer','filename')},'stale':row['status']=='running' and time.time()-result.get('heartbeat',0)>180}

    @app.post('/research/api/download-worker/pair')
    async def pair(user=Depends(actor)):
        token=secrets.token_urlsafe(40)
        with store.lock('download-workers'):
            rows=read();rows[hashlib.sha256(token.encode()).hexdigest()]={'owner':user['id'],'created':now(),'last_seen':0};atomic_json(file,rows)
        return {'token':token}

    @app.get('/research/api/download-worker/devices')
    async def devices(user=Depends(actor)):
        with store.lock('download-workers'):
            rows=read()
        return {'devices':[{'id':key,'created':v.get('created'),'last_seen':v.get('last_seen',0),
            'revoked_at':v.get('revoked_at'),'scope':'当前账户的文献下载与任务结果上传'}
            for key,v in rows.items() if device_owner(v)==user['id']]}

    @app.post('/research/api/download-worker/devices/{device_id}/revoke')
    async def revoke(device_id:str,user=Depends(actor)):
        with store.lock('download-workers'):
            rows=read();entry=rows.get(device_id)
            if not entry or device_owner(entry)!=user['id']:raise HTTPException(404,'下载设备不存在')
            entry['revoked_at']=now();rows[device_id]=entry;atomic_json(file,rows)
        return {'revoked':True,'device_id':device_id}

    @app.get('/research/api/download-worker/status')
    async def status(user=Depends(actor)):
        values=[v for v in read().values() if device_allows(v,user['id'])];seen=max([v.get('last_seen',0) for v in values] or [0])
        return {'paired':bool(values),'online':time.time()-seen<90,'last_seen':seen,'pipeline':['local-scansci','research-cluster-xh5','user-workspace'],'cluster_root':CLUSTER_ROOT}

    async def create_batch(request,pid,payload,user):
        owner=user['id'];store.get(owner,pid);entries=payload.get('entries') or [{'identifier':payload.get('identifier','')}]
        if not isinstance(entries,list) or not 1<=len(entries)<=100:raise ValueError('每批请选择 1 至 100 篇文献')
        if not any(device_allows(v,owner) for v in read().values()):raise ValueError('当前账户尚未配对本机 ScanSci 下载设备')
        folder=str(payload.get('folder') or 'reading').strip('/')[:200];child(store.path(owner,pid)/'literature',folder+'/paper.pdf')
        from .literature import read_index
        existing={identifier(v) for v in read_index(store.path(owner,pid)).values()};settings=json.loads(api_path(owner).read_text()) if api_path(owner).exists() else {}
        batch_id=uuid.uuid4().hex;items=[];skipped=[];rejected=[];seen=set()
        with store.db() as db:current=db.execute("SELECT id,result FROM jobs WHERE owner=? AND project=? AND kind='literature-download' AND status IN ('queued','running')",(owner,pid)).fetchall()
        pending={json.loads(row['result']).get('identifier') for row in current}
        for raw in entries:
            entry={k:raw[k] for k in ('id','number','title','authors','year','venue','doi','arxiv','url','source','verified','issn','publisher','identifier','publication_type') if k in raw}
            identity=identifier(entry)
            if not identity and entry.get('title'):
                from .references import search
                try:
                    matches=await search(entry['title'],settings=settings,source='crossref',limit=3)
                    matched=[m for m in matches if title_key(m['title'])==title_key(entry['title'])]
                    matched.sort(key=lambda m:m.get('publication_type')=='journal-article',reverse=True)
                    match=next(iter(matched),None)
                    if match:entry={**entry,**match};identity=identifier(entry)
                except Exception:pass
            if not identity:rejected.append({'title':entry.get('title',''),'reason':'未核验到 DOI 或 arXiv 身份，请在来源页面确认题录'});continue
            entry.setdefault('doi' if identity.startswith('10.') else 'arxiv',identity if identity.startswith('10.') else identity.removeprefix('arXiv:'))
            if identity in seen or identity in existing or identity in pending:
                skipped.append({'identifier':identity,'title':entry.get('title',''),'reason':'全文已入库或已在下载队列'});continue
            seen.add(identity);jid=store.job(owner,pid,'literature-download',{'subject':entry.get('title') or identity})
            result={'identifier':identity,'entry':entry,'folder':folder,'batch_id':batch_id,'phase':'queued','filename':paper_filename(entry,identity),'timeline':[{'phase':'queued','time':now()}]}
            store.set_job(jid,result=result,stage=PHASES['queued']);items.append({'id':jid,'identifier':identity,'title':entry.get('title') or identity,'status':'queued'})
        return {'batch_id':batch_id,'items':items,'queued':len(items),'skipped':skipped,'rejected':rejected}

    @app.post('/research/api/projects/{pid}/literature/download-batch')
    async def enqueue_batch(request:Request,pid:str,payload:dict,user=Depends(actor)):return await create_batch(request,pid,payload,user)

    @app.post('/research/api/projects/{pid}/literature/download')
    async def enqueue(request:Request,pid:str,payload:dict,user=Depends(actor)):
        result=await create_batch(request,pid,payload,user)
        if result['items']:return {**result['items'][0],'batch_id':result['batch_id']}
        raise ValueError((result['rejected'] or result['skipped'] or [{'reason':'没有可下载文献'}])[0]['reason'])

    @app.get('/research/api/projects/{pid}/literature/downloads')
    async def download_jobs(pid:str,user=Depends(actor)):
        store.get(user['id'],pid)
        with store.db() as db:rows=db.execute("SELECT * FROM jobs WHERE owner=? AND project=? AND kind='literature-download' ORDER BY created DESC LIMIT 200",(user['id'],pid)).fetchall()
        return {'items':[present(dict(row)) for row in rows]}

    @app.post('/research/api/projects/{pid}/literature/downloads/{jid}/retry')
    async def retry(pid:str,jid:str,user=Depends(actor)):
        store.get(user['id'],pid)
        with store.db() as db:row=db.execute("SELECT * FROM jobs WHERE id=? AND owner=? AND project=? AND kind='literature-download'",(jid,user['id'],pid)).fetchone()
        if not row:raise KeyError('下载任务不存在')
        if row['status'] not in ('failed','interrupted','cancelled'):raise ValueError('该任务仍在执行或已经完成')
        result=json.loads(row['result']);result.pop('worker_id',None);update(jid,result,'queued',status='queued');store.set_job(jid,error='')
        return {'queued':True}

    @app.post('/research/api/projects/{pid}/literature/downloads/{jid}/cancel')
    async def cancel(pid:str,jid:str,user=Depends(actor)):
        store.get(user['id'],pid)
        with store.db() as db:row=db.execute("SELECT * FROM jobs WHERE id=? AND owner=? AND project=? AND kind='literature-download'",(jid,user['id'],pid)).fetchone()
        if not row:raise KeyError('下载任务不存在')
        if row['status']=='completed':raise ValueError('全文已经入库')
        result=json.loads(row['result']);update(jid,result,'cancelled');store.set_job(jid,status='cancelled')
        return {'cancelled':True}

    @app.get('/research/api/download-worker/next')
    async def next_job(request:Request,resume_id:str=''):
        value=worker(request)
        with store.lock('download-claim'):
            if resume_id:
                row,result=get_job(value,resume_id)
                if row['status'] in ('completed','cancelled','failed'):return {'job':None}
            else:
                with store.db() as db:
                    rows=db.execute("SELECT * FROM jobs WHERE kind='literature-download' AND status IN ('queued','running') ORDER BY created").fetchall()
                # A second poll with the same device token cannot claim a live
                # task again. Explicit resume_id handles intentional recovery.
                match=next((r for r in rows if value['owner']==r['owner'] and (r['status']=='queued' or time.time()-json.loads(r['result']).get('heartbeat',0)>600)),None)
                if not match:return {'job':None}
                row=dict(match);result=json.loads(row['result'])
            if not result.get('entry'):result['entry']={'identifier':result['identifier'],'doi' if result['identifier'].startswith('10.') else 'arxiv':result['identifier'].removeprefix('arXiv:')}
            result.setdefault('filename',paper_filename(result['entry'],result['identifier']));result['worker_id']=value['worker_id']
            update(row['id'],result,'downloading');store.set_job(row['id'],status='running',error='')
            return {'job':{'id':row['id'],'project':row['project'],'owner_key':uuid.uuid5(uuid.NAMESPACE_URL,row['owner']).hex,'cluster_root':CLUSTER_ROOT,**{k:result[k] for k in ('identifier','entry','folder','filename')},'transfer':result.get('transfer')}}

    @app.post('/research/api/download-worker/{jid}/progress')
    async def progress(request:Request,jid:str,payload:dict):
        value=worker(request);row,result=get_job(value,jid)
        if row['status']=='cancelled':return {'cancelled':True}
        if row['status']!='running':return {'active':False}
        phase=str(payload.get('phase') or result.get('phase') or 'downloading')
        if phase not in PHASES:raise ValueError('下载阶段无效')
        extra={}
        if isinstance(payload.get('transfer'),dict):extra['transfer']={k:v for k,v in payload['transfer'].items() if k in ('local_path','cluster_path','sha256','bytes','pages','verified_at','cluster_verified','connection')}
        update(jid,result,phase,**extra);return {'active':True,'cancelled':False}

    @app.post('/research/api/download-worker/{jid}/delivery-ticket')
    async def ticket(request:Request,jid:str):
        value=worker(request);row,result=get_job(value,jid)
        if row['status']!='running':raise HTTPException(409,'下载任务未在执行')
        token=secrets.token_urlsafe(40);expires=time.time()+1800
        result.update(delivery_ticket_sha=hashlib.sha256(token.encode()).hexdigest(),delivery_ticket_expires=expires)
        store.set_job(jid,result=result)
        return {'token':token,'expires':expires}

    def delivery_actor(request,jid):
        token=request.headers.get('x-workbench-delivery','')
        if not token:return worker(request)
        with store.db() as db:row=db.execute("SELECT * FROM jobs WHERE id=? AND kind='literature-download'",(jid,)).fetchone()
        if not row:raise HTTPException(403,'传输凭据无效')
        result=json.loads(row['result'])
        device=read().get(result.get('worker_id'))
        if not device or not device_allows(device,row['owner']):raise HTTPException(403,'下载设备授权已撤销或与账户不一致')
        if not secrets.compare_digest(hashlib.sha256(token.encode()).hexdigest(),result.get('delivery_ticket_sha','')) or time.time()>result.get('delivery_ticket_expires',0):raise HTTPException(403,'传输凭据无效或已过期')
        return {'owner':row['owner'],'worker_id':result.get('worker_id')}

    @app.post('/research/api/download-worker/{jid}/result')
    async def result(request:Request,jid:str,file:UploadFile|None=File(None),error:str=Form(''),transfer:str=Form('{}')):
        value=delivery_actor(request,jid);row,job=get_job(value,jid)
        if row['status']=='cancelled':return {'saved':False,'cancelled':True}
        if row['status']=='completed':return {'saved':True,'already_completed':True,'receipt':job.get('receipt')}
        if row['status']!='running':raise HTTPException(409,'下载任务未在执行')
        if error or not file:
            update(jid,job,'failed');store.set_job(jid,status='failed',error=(error or '未收到 PDF')[:1000]);return {'saved':False}
        receipt=json.loads(transfer);prefix=CLUSTER_ROOT+'/owners/'+uuid.uuid5(uuid.NAMESPACE_URL,row['owner']).hex+'/'+row['project']+'/'
        cluster_path=str(receipt.get('cluster_path',''))
        if receipt.get('connection')!='research-cluster-xh5' or not receipt.get('cluster_verified') or not cluster_path.startswith(prefix+'papers/') or '..' in PurePosixPath(cluster_path).parts or not re.fullmatch(r'[a-f0-9]{64}\.pdf',PurePosixPath(cluster_path).name):raise ValueError('请先完成所属账户的集群上传与验收')
        data=await file.read(100*1024**2+1)
        if len(data)>100*1024**2:raise ValueError('PDF 最大100MiB')
        if hashlib.sha256(data).hexdigest()!=receipt.get('sha256') or len(data)!=receipt.get('bytes'):raise ValueError('集群副本与用户文件夹接收内容不一致，保留任务等待重试')
        from .literature import save_pdf
        settings=json.loads(api_path(row['owner']).read_text()) if api_path(row['owner']).exists() else {}
        update(jid,job,'delivering',transfer=receipt)
        saved=await save_pdf(store,row['owner'],row['project'],job['filename'],data,job['folder'],settings,expected=job.get('entry'),provenance=receipt)
        update(jid,job,'completed',receipt=saved,transfer=receipt);store.set_job(jid,status='completed',error='')
        return {'saved':True,'receipt':saved}
