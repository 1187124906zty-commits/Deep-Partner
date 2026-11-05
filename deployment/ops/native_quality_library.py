"""Use Tutor's existing owner-scoped KB for the actual converted references."""
from pathlib import Path
from contextlib import ExitStack
from urllib.parse import quote
import argparse
import json
import subprocess
import httpx

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/native-quality-library.json'
PROJECT_NAME='写作与汇报参考资料'
KB_NAME='writing-presentation-references-20261102'
ORIGIN='https://tutor.example.invalid'


def save(value):
    temp=REPORT.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(REPORT)


def prepare():
    manifest=json.loads((ROOT/'reports/mineru-all-source-manifest.json').read_text(encoding='utf8'))
    sources=json.loads((ROOT/'reports/presentation-source-ingest.json').read_text(encoding='utf8'))
    rows=[]
    for source in manifest['books']:
        reading=source.get('preferred_local_markdown') or source.get('local_reading_markdown')
        path=Path(reading) if reading and Path(reading).is_file() else Path(source['local_markdown'])
        rows.append({'id':source['source_id'],'path':str(path),'url':source['source_url'],
                     'review_status':'Full book unreviewed; only designated pilot pages have agent visual checks.',
                     'scope':'Private writing reference; guidance is conditional and is not a mandatory scientific rule.'})
    for source in sources['sources'] + sources.get('alternatives',[]):
        if not source.get('mineru',{}).get('processed'):
            continue
        reading=source.get('recommended_reading_path')
        if not reading:raise ValueError('Source reading disposition is not ready: '+source['source_id'])
        path=Path(reading)
        if not path.is_absolute():path=Path(sources['local_source_root'])/path
        rows.append({'id':source['source_id'],'path':str(path),'url':source.get('canonical_url') or source['source_url'],
                     'review_status':source.get('reading_status') or source.get('content_review_status','See source ingest QA.'),
                     'scope':'Institutional guidance with stated local scope; not a universal school or journal requirement.'})
    assert len(rows)==14, len(rows)
    target=ROOT/'.local/native-quality-library-inputs';target.mkdir(exist_ok=True)
    for row in rows:
        path=Path(row['path']);before=path.stat().st_mtime_ns;content=path.read_text(encoding='utf8')
        if path.stat().st_mtime_ns!=before:raise ValueError('Source changed while preparing: '+row['id'])
        header=(f"# Source {row['id']}\n\nOriginal source: {row['url']}\n\nReview status: {row['review_status']}\n\n"
                f"Use scope: {row['scope']}\n\nRetrieval covers text. Original PDF/HTML, page mapping, images and raw parser output remain in the private source package.\n\n---\n\n")
        destination=target/(row['id']+'.md');destination.write_text(header+content,encoding='utf8')
        row.update(upload_path=str(destination),source_modified=before,characters=len(content))
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','status','update-reading','rebuild','verify','review','review-revised']);args=parser.parse_args()
    credentials=subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True)
    account=json.loads(credentials.stdout)
    state=json.loads(REPORT.read_text(encoding='utf8')) if REPORT.is_file() else {}
    with httpx.Client(headers={'Origin':ORIGIN},trust_env=False,timeout=120) as http:
        login=http.post(ORIGIN+'/api/auth/login',json={'username':account['username'],'password':account['password']});login.raise_for_status()
        if args.action=='start':
            rows=prepare()
            response=http.get(ORIGIN+'/research/api/projects');response.raise_for_status()
            project=next((p for p in response.json()['projects'] if p['name']==PROJECT_NAME),None)
            if project is None:
                response=http.post(ORIGIN+'/research/api/projects',json={'name':PROJECT_NAME});response.raise_for_status();project=response.json()
            state.update(project_id=project['id'],native_id=project['native_id'],project_name=PROJECT_NAME,
                         url=ORIGIN+'/research/?project='+project['id'],private_owner_only=True,
                         source_files=rows,source_count=len(rows),content_quality='Not upgraded by indexing',
                         text_only_retrieval=True,rag_provider='llamaindex')
            save(state)
            scope={'dt_workspace':state['native_id']}
            response=http.get(ORIGIN+'/api/knowledge-bases',params={**scope,'resource_library':'true'});response.raise_for_status()
            kb=next((v for v in response.json() if v['name']==KB_NAME),None)
            if kb is None:
                with ExitStack() as stack:
                    files=[('files',(Path(x['upload_path']).name,stack.enter_context(Path(x['upload_path']).open('rb')),'text/markdown')) for x in rows]
                    response=http.post(ORIGIN+'/api/knowledge-bases',params=scope,
                        data={'name':KB_NAME,'rag_provider':'llamaindex','storage_workspace_id':state['native_id']},files=files)
                response.raise_for_status();kb=response.json()
            state.update(knowledge_base=kb['id'],task_id=kb.get('task_id'),native_creation=kb,status='indexing')
            save(state)
            response=http.patch(ORIGIN+'/research/api/projects/'+state['project_id'],json={'knowledge_bases':[kb['id']]})
            state['binding_response']={'status':response.status_code,'body':response.json()}
            save(state)
        else:
            if not state.get('knowledge_base'):raise ValueError('No admitted native indexing task')
        scope={'dt_workspace':state['native_id']};route=ORIGIN+'/api/knowledge-bases/'+quote(state['knowledge_base'],safe='')
        response=http.get(route,params=scope);response.raise_for_status();details=response.json()
        if args.action=='rebuild':
            response=http.post(route+'/reindex',params=scope,data={'embedding_model':json.dumps(details['metadata']['embedding_selection'])})
            response.raise_for_status();state.update(clean_rebuild=response.json(),status='rebuilding_current_reading_sources')
            save(state);print(json.dumps({'status':state['status'],'task':state['clean_rebuild']},ensure_ascii=False));return
        if args.action=='update-reading':
            if details.get('status')!='ready':raise ValueError('Wait for the admitted index before replacing reading views')
            rows=prepare()
            changed=[x for x in rows if x['id'].startswith('book.')]
            with ExitStack() as stack:
                files=[('files',(Path(x['upload_path']).name,stack.enter_context(Path(x['upload_path']).open('rb')),'text/markdown')) for x in changed]
                response=http.post(route+'/upload',params=scope,data={'rag_provider':'llamaindex'},files=files)
            response.raise_for_status()
            state.update(source_files=rows,reading_update=response.json(),status='reading_update_indexing')
            save(state)
            print(json.dumps({'status':state['status'],'update':state['reading_update']},ensure_ascii=False));return
        response=http.get(route+'/indexing-run',params=scope);response.raise_for_status();run=response.json()
        state.update(native_details=details,indexing_run=run,status=details.get('status','unknown'))
        durable_state=(run.get('run') or {}).get('state')
        if durable_state in ('running','queued'):
            state['status']='indexing'
        if args.action=='verify':
            if durable_state in ('running','queued'):
                save(state)
                print(json.dumps({'status':'indexing','task_id':(run.get('run') or {}).get('task_id')},ensure_ascii=False));return
            if durable_state not in ('completed','succeeded'):
                raise ValueError('Native indexing run has not completed: '+str(durable_state))
            if details.get('status')!='ready':raise ValueError('Native index is not ready: '+str(details.get('status')))
            response=http.patch(ORIGIN+'/research/api/projects/'+state['project_id'],json={'knowledge_bases':[state['knowledge_base']]})
            state['binding_response']={'status':response.status_code,'body':response.json()};save(state)
            response.raise_for_status()
            queries=[('lexical','fulltext-keyword','word-of-mouth'),('semantic','semantic','How do the meanings of cell differ between scientific disciplines?')]
            results=[]
            for name,mode,query in queries:
                response=http.post(ORIGIN+'/research/api/projects/'+state['project_id']+'/knowledge/search',
                    json={'query':query,'mode':mode,'knowledge_base':state['knowledge_base'],'limit':4})
                response.raise_for_status();value=response.json()
                if mode=='fulltext-keyword':
                    assert any(x.get('asset')=='book.awg3.md' and 'word-of-mouth' in x.get('excerpt','').lower() for x in value.get('items',[])), 'Expected AWG3 phrase was not returned'
                    assert all(not x.get('truncated') for x in value['coverage']),'Native text was truncated'
                else:
                    content=value.get('result',{}).get('content','').lower()
                    assert all(x in content for x in ['pdf_page:93','oncosis','fuel cell','table of proportions']),'Semantic results did not reach the verified cell meanings'
                results.append({'check':name,'query':query,'response':value})
            state.update(status='ready_and_retrieval_verified',retrieval_checks=results)
            indexed=(run.get('run') or {}).get('documents',{})
            checks=[]
            for source in state['source_files']:
                local=Path(source['upload_path']);filename=local.name
                response=http.get(route+'/files/'+quote(filename,safe=''),params=scope);response.raise_for_status()
                same=response.content==local.read_bytes()
                assert same and indexed.get(filename,{}).get('status')=='completed',filename
                source['source_body_characters']=source.get('characters')
                source['uploaded_characters']=len(response.content.decode('utf8'))
                checks.append({'file':filename,'matches_admitted_reading_bytes':same,
                               'indexed_status':indexed[filename]['status'],'source_hash':indexed[filename].get('source_hash')})
            state['indexed_source_checks']=checks
            state['replay_request']={'method':'POST','path':'/research/api/projects/'+state['project_id']+'/knowledge/search',
                'authentication':'current owner session; credentials never included in the receipt',
                'bodies':[{'query':q,'mode':m,'knowledge_base':state['knowledge_base'],'limit':4} for _,m,q in queries]}
            anonymous=httpx.get(route,params=scope,trust_env=False,timeout=30,follow_redirects=False)
            assert anonymous.status_code in (401,403),anonymous.status_code
            state['anonymous_access_status']=anonymous.status_code
        if args.action in ('review','review-revised'):
            if not state.get('retrieval_checks') or durable_state not in ('completed','succeeded'):
                raise ValueError('Finish actual retrieval checks before evaluating this ingestion')
            if args.action=='review-revised' and not state.get('review_iteration'):
                prior=state.get('quality_job',{})
                if prior.get('status')!='completed':raise ValueError('Read the previous evaluation before revising it')
                state['parent_review_id']=prior['result']['review_id'];state['previous_quality_job']=prior
                state['review_iteration']=1;state.pop('quality_job_id',None);state.pop('quality_job',None);save(state)
            if not state.get('quality_job_id'):
                manifest=json.loads((ROOT/'reports/mineru-all-source-manifest.json').read_text(encoding='utf8'))
                purpose=json.loads((ROOT/'reports/presentation-source-ingest.json').read_text(encoding='utf8'))
                evidence={'book_receipts':[json.loads((ROOT/'reports/mineru-books'/b['source_id']/'source-mapping.json').read_text(encoding='utf8')) for b in manifest['books']],
                          'purpose_source_checks':json.loads((ROOT/'quality-knowledge/presentation-sources/mineru-source-review.json').read_text(encoding='utf8')),
                          'purpose_counts':purpose['summary'],'retrieval_checks':state['retrieval_checks'],
                          'indexing_run':state['indexing_run'],'indexed_source_checks':state.get('indexed_source_checks'),
                          'replay_request':state.get('replay_request'),'private_access_check':state.get('anonymous_access_status')}
                artifact={'purpose':'本批私人参考来源可回查、可检索，供按相关原页核对后引用；不宣称全文逐字校订或强制规则提取完成。',
                          'source_count':14,'book_pages':1042,'assets':451,'project_url':state['url'],
                          'selected_sources':[{k:v for k,v in x.items() if k!='upload_path'} for x in state['source_files']],
                          'known_limits':['仅六个原页做指定视觉核对，全文仍unreviewed','S11采用完整原生HTML，保留MinerU遗漏证据','S04与S05原页未取到，ALT单独登记','索引检索文本，图示与版面需回原件']}
                for relative,value in [('project/docs/quality-library-receipt.json',artifact),('project/data/quality-library-evidence.json',evidence)]:
                    response=http.put(ORIGIN+'/research/api/projects/'+state['project_id']+'/file',json={'path':relative.removeprefix('project/'),'content':json.dumps(value,ensure_ascii=False,indent=2),'reason':'保存本批私人参考库摄取与实际检索证据'})
                    response.raise_for_status()
                response=http.post(ORIGIN+'/research/api/projects/'+state['project_id']+'/quality/reviews',json={
                    'operation_id':'quality-library-ingestion-20261102'+('-r1' if state.get('review_iteration') else ''),'stage':'ingestion','purpose':'',
                    'parent_review_id':state.get('parent_review_id',''),
                    'artifact_paths':['project/docs/quality-library-receipt.json'],'source_paths':['project/data/quality-library-evidence.json'],
                    'intended_use':'只评价本批私人参考来源摄取的可回查性、来源定位、已知缺漏处置和实际检索。全文未逐页审读、图示依原件核对的边界明确保留，不把结构与索引通过升级为全书文字准确率证明。'})
                response.raise_for_status();state['quality_job_id']=response.json()['job_id'];save(state)
            response=http.get(ORIGIN+'/research/api/projects/'+state['project_id']+'/jobs');response.raise_for_status()
            job=next(x for x in response.json()['jobs'] if x['id']==state['quality_job_id'])
            state['quality_job']=job
            if job['status']=='completed':
                (ROOT/'reports/quality-native-ingestion-review.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf8')
            elif job['status'] in ('failed','interrupted'):raise ValueError('Ingestion review did not complete: '+str(job.get('error')))
        save(state)
    print(json.dumps({**{k:state.get(k) for k in ['status','project_id','knowledge_base','task_id','source_count','url']},'quality_job_status':state.get('quality_job',{}).get('status')},ensure_ascii=False))


if __name__=='__main__':main()
