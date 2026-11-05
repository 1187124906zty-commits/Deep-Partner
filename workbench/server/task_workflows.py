"""Versioned task steps; progress comes from execution events, never elapsed time."""
from copy import deepcopy
from urllib.parse import quote,urlparse,parse_qs

VERSION=1
WORKFLOWS={
    'research-outline':('研究主线整理',[('read','读取项目对话与已有认识'),('retrieve','检索前人工作与依据'),('synthesize','组织主线与任务大纲'),('save','保存待确认提案')]),
    'simulation':('集群仿真',[('prepare','准备工况与输入'),('submit','提交Slurm作业'),('monitor','计算节点求解'),('validate','结果核验'),('archive','保存项目结果')]),
    'cluster-pdf-parse':('集群PDF解析',[('parse','计算节点解析'),('save','保存解析与页码')]),
    'research-flow':('研究工作流',[('search','检索文献'),('download','下载并入库'),('parse','集群解析PDF'),('read','按页读取原文'),('analyze','整理证据与问题'),('dispatch','专用工具执行'),('archive','保存项目与关系')]),
    'writing':('写作工作流',[('intent','理解任务'),('exemplar','标杆解构'),('alignment','主题与沙漏架构'),('narrow','方法与结果'),('wide','引言与首尾'),('review','期刊表达与审稿'),('deliver','保存成果')]),
    'material-import':('材料导入',[('inspect','检查材料包'),('files','保存文件'),('document','整理稿件'),('catalog','加入项目')]),
    'literature-download':('文献下载',[('download','下载全文'),('verify','核对 PDF'),('upload','上传集群'),('cluster','验收副本'),('deliver','加入文献库')]),
    'literature-metadata':('文献识别',[('identify','识别题录与作者'),('save','保存题录')]),
    'paper-content-map':('论文内容图谱',[('parse','提取章节与段落'),('organize','梳理内容组织'),('connect','连接问题与证据'),('save','核对并保存图谱')]),
    'literature-classify':('文献分类',[('read','读取材料'),('classify','整理分类'),('check','核对来源'),('save','保存分类'),('review','阶段评审')]),
    'manuscript-export':('稿件导出',[('prepare','准备正文'),('layout','生成版式'),('save','保存文件'),('review','阶段评审')]),
    'manuscript-preview':('稿件预览',[('prepare','准备正文'),('layout','生成版式'),('save','保存预览')]),
    'manuscript-translate':('稿件翻译',[('translate','翻译段落'),('check','核对版本'),('save','保存译稿'),('review','阶段评审')]),
    'template':('模板解析',[('read','读取模板'),('parse','解析版式'),('save','保存预览')]),
    'slides-plan':('汇报内容生成',[('prepare','读取研究材料'),('generate','组织汇报内容'),('save','保存内容计划'),('review','阶段评审')]),
    'slides-export':('汇报导出',[('build','生成可编辑页'),('render','渲染预览'),('check','检查页面'),('save','保存文件'),('review','阶段评审')]),
    'quality-review':('阶段评审',[('bind','核对评审对象'),('evaluate','独立评审'),('check','核验检查项'),('save','保存评审结果')]),
    'pdf-translation-export':('PDF 译文导出',[('read','读取原文与译文'),('layout','保留公式与版面'),('compile','生成 PDF'),('save','保存译稿')]),
    'journal-preview':('期刊排版预览',[('author','核对作者资料'),('template','核对期刊版式'),('compile','生成排版预览'),('save','保存预览')]),
}
DOWNLOAD_PHASE={'queued':'download','downloading':'download','validating':'verify','cluster_upload':'upload','cluster_verified':'cluster','delivering':'deliver','completed':'deliver'}
TERMINAL={'completed','failed','interrupted','cancelled'}

def create(kind,project,context=None):
    context={k:v for k,v in (context or {}).items() if k in {'subject','source_name','format','target','files','document_id','stage','purpose','artifact_paths','route_steps'}}
    label,steps=WORKFLOWS.get(kind,('后台处理',[('execute','执行任务'),('save','保存结果')]))
    if context.get('route_steps') and kind in ('research-flow','simulation'):
        steps=[s for s in steps if s[0] in context['route_steps']]
    subject=str(context.get('subject') or context.get('source_name') or project['name'])[:350]
    return {'version':VERSION,'workflow':kind if kind in WORKFLOWS else 'generic','type_label':label,'subject':subject,'context':context,
            'steps':[{'id':key,'label':text,'state':'pending'} for key,text in steps],'events':[],'current_step':None}

def advance(tracking,fields,stamp,*,step=None,counts=None):
    value=deepcopy(tracking);steps=value['steps'];known={s['id'] for s in steps}
    if fields.get('status') in TERMINAL and value['events'] and value['events'][-1]['state']==fields['status'] and step is None and counts is None:return value
    if step is not None and step not in known:raise ValueError('任务步骤不属于当前流程')
    status=fields.get('status');previous=value.get('current_step')
    if step is None and isinstance(fields.get('result'),dict):
        phase=fields['result'].get('phase')
        if value['workflow']=='literature-download':step=DOWNLOAD_PHASE.get(phase)
    if step is None and status=='running' and previous is None:step=steps[0]['id']
    if step is not None:
        target=next(i for i,s in enumerate(steps) if s['id']==step)
        # A later entered step establishes completion only for an entered predecessor.
        for i,s in enumerate(steps):
            if i<target and s['state']=='running':
                s.update(state='done',finished=stamp);value['events'].append({'step':s['id'],'state':'done','time':stamp})
            elif i<target and s['state'] in ('pending','waiting'):s.update(state='skipped')
        current=steps[target]
        state='waiting' if status in ('queued','waiting_service','waiting_input','paused') else 'running'
        if current['state']!=state or previous!=step:
            current.update(state=state,started=current.get('started') or stamp)
            value['events'].append({'step':step,'state':state,'time':stamp})
        value['current_step']=step
    if counts is not None:
        done,total=int(counts['done']),int(counts['total'])
        if total<0 or not 0<=done<=total:raise ValueError('任务计数无效')
        value['counts']={'done':done,'total':total,'unit':str(counts.get('unit') or '项')[:12],'step':value.get('current_step')}
    if status in TERMINAL:
        current=next((s for s in steps if s['id']==value.get('current_step')),None)
        if current:
            current.update(state='done' if status=='completed' else 'failed' if status in ('failed','interrupted') else 'cancelled',finished=stamp)
        if status=='completed':
            for s in steps:
                if s['state'] in ('pending','waiting'):s['state']='skipped'
        value['events'].append({'step':value.get('current_step'),'state':status,'time':stamp})
    if status=='queued' and previous is not None and value['workflow']=='literature-download':
        # Retrying is explicit. Keep the first attempt in the event history.
        for s in steps:
            s.update(state='pending');s.pop('started',None);s.pop('finished',None)
        steps[0].update(state='waiting',started=stamp);value['current_step']=steps[0]['id'];value.pop('counts',None)
    elif status in ('queued','waiting_service','waiting_input','paused') and previous is not None:
        # Polling/reconnection resumes the same stage; it is not a fresh attempt.
        current=next(s for s in steps if s['id']==value['current_step'])
        if current['state'] not in ('done','skipped'):
            current['state']='waiting'
    elif status=='running' and step is None and previous is not None:
        current=next(s for s in steps if s['id']==previous)
        if current['state']=='waiting':current['state']='running'
    value['events']=value['events'][-100:]
    return value

def present(row,project):
    result=row.get('result') or {};tracking=row.get('tracking') or {}
    if not tracking:
        context={'subject':result.get('entry',{}).get('title') or result.get('filename') or result.get('name') or project['name']}
        tracking=create(row['kind'],project,context);tracking['legacy']=True
        # Only download workers previously persisted actual step events.
        if row['kind']=='literature-download':
            for item in result.get('timeline',[]):
                step=DOWNLOAD_PHASE.get(item.get('phase'))
                if step:tracking=advance(tracking,{'status':'queued' if item['phase']=='queued' else 'running'},item['time'],step=step)
            tracking=advance(tracking,{'status':row['status'],'result':result},row['updated'])
        else:
            tracking['steps']=[];tracking['current_step']=None
    value=deepcopy(tracking)
    if result.get('entry',{}).get('title'):value['subject']=result['entry']['title']
    verb={'material-import':'导入','literature-download':'下载','literature-classify':'整理','manuscript-export':'导出','manuscript-translate':'翻译','template':'解析','slides-plan':'生成汇报内容','slides-export':'导出汇报','quality-review':'评审','pdf-translation-export':'导出译文','journal-preview':'生成期刊预览'}.get(row['kind'],'处理')
    value['title']=verb+' · '+value['subject']
    context=value.get('context') or {}
    if context.get('format'):value['title']+=' · '+str(context['format']).upper()
    if context.get('target'):value['title']+=' · '+{'en':'英文','zh-CN':'中文','ja':'日文','de':'德文','fr':'法文'}.get(context['target'],str(context['target']))
    value['completed_steps']=sum(s['state']=='done' for s in value['steps'])
    value['total_steps']=sum(s['state']!='skipped' for s in value['steps'])
    value['counts']=value.get('counts') if (value.get('counts') or {}).get('step')==value.get('current_step') else None
    value['artifacts']=[{'label':result.get('name') or ('PDF 文件' if key=='pdf_url' else '查看产物'),'url':result[key]} for key in ('url','pdf_url') if isinstance(result.get(key),str) and result[key].startswith('/research/api/projects/'+row['project']+'/')]
    for artifact in value['artifacts']:
        params=parse_qs(urlparse(artifact['url']).query);artifact['filename']=(params.get('name') or params.get('asset') or params.get('path') or [artifact['label']])[0].split('/')[-1]
    receipt=result.get('receipt') or {}
    if row['kind']=='literature-download' and row['status']=='completed' and receipt.get('name'):
        value['artifacts'].append({'label':'查看全文','filename':result.get('filename') or receipt['name'].split('/')[-1],'url':'/research/api/projects/'+row['project']+'/literature/file?asset='+quote(receipt['name'],safe='')})
    value['summary']=row['stage']
    if row['status']=='completed':
        if isinstance(result.get('files'),int):value['summary']='已导入 '+str(result['files'])+' 个文件'
        elif isinstance(result.get('slides'),int):value['summary']='已生成 '+str(result['slides'])+' 页汇报内容'
        elif isinstance(result.get('segments'),int):value['summary']='已翻译 '+str(result['segments'])+' 个段落'
    quality=result.get('quality') or {}
    value['quality_note']=quality.get('reason') or ('产物已保存，评审建议修订后继续。' if quality and quality.get('can_proceed') is False else '')
    if row['status']=='completed' and quality.get('decision')=='evaluation_failed':
        for step in value['steps']:
            if step['id']=='review':step['state']='failed'
        value['completed_steps']=sum(s['state']=='done' for s in value['steps'])
        value['summary']='产物已保存，阶段评审未完成'
    elif row['status']=='completed' and quality and quality.get('can_proceed') is False:
        value['summary']+=' · 评审待处理'
    value['waiting']=row['status'] in ('queued','waiting_service','waiting_input','paused')
    return value
