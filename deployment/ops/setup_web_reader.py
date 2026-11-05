"""Expose the installed Dify WebScraper as a bounded, source-preserving capability."""
import json
from pathlib import Path
from optimize_workflow import ROOT,api,login,node,code

FORMAT='''import json
from datetime import datetime, timezone
def main(text: str, url: str) -> dict:
    content=(text or "").strip()
    blocked=(not content or content.startswith("URL returned status code") or content.startswith("Unsupported content-type")
        or content.lower().startswith("please input url") or "verify you are human" in content[:1500].lower())
    if blocked:raise ValueError("网页正文未取得，可能需要登录、人工验证或其他读取方式")
    value={"status":"ready","source_url":url,"content":content[:50000],"truncated":len(content)>50000,
        "retrieved_at":datetime.now(timezone.utc).isoformat(),"source":"Dify WebScraper",
        "evidence":"public-webpage-content","content_chars":len(content)}
    return {"evidence":json.dumps(value,ensure_ascii=False),"source_url":url,"content":value["content"]}
'''


def workflow():
    start=node('start','start','网页证据请求',80,180,variables=[{'variable':'url','label':'公开网页链接',
        'type':'text-input','required':True,'max_length':2000,'options':[]}])
    reader=node('read_page','tool','公开网页正文读取',420,180,provider_id='webscraper',provider_type='builtin',
        provider_name='webscraper',tool_name='webscraper',tool_label='网页正文读取',tool_node_version='2',
        is_team_authorization=True,tool_configurations={
            'generate_summary':{'type':'constant','value':False},
            'user_agent':{'type':'constant','value':'Mozilla/5.0 (compatible; ResearchWorkbench/1.0)'}},
        tool_parameters={'url':{'type':'mixed','value':'{{#start.url#}}'}})
    reader['data']['desc']='使用已安装的 WebScraper 提取公开网页正文，关闭模型摘要；来源链接随证据返回。'
    result=code('evidence','网页证据整理',760,180,FORMAT,
        {'text':['read_page','text'],'url':['start','url']},{'evidence':'string','source_url':'string','content':'string'})
    result['data']['desc']='保留原链接、读取时间与正文，标明截断；读取失败时不返回虚构内容。'
    end=node('end','end','网页证据结果',1100,180,outputs=[
        {'variable':key,'value_selector':['evidence',key]} for key in ('evidence','source_url','content')])
    nodes=[start,reader,result,end]
    return {'version':'0.7.0','kind':'app','dependencies':[],
        'app':{'name':'DeepTutor 扩展 · 网页证据读取','description':'按需读取公开网页，保留来源、正文和读取时间，返回 Tutor 继续判断。',
            'mode':'workflow','icon':'📄','icon_background':'#E5F0E8','use_icon_as_answer_icon':False},
        'workflow':{'conversation_variables':[],'environment_variables':[],
            'features':{'file_upload':{'enabled':False},'retriever_resource':{'enabled':False},
                'sensitive_word_avoidance':{'enabled':False},'speech_to_text':{'enabled':False},
                'text_to_speech':{'enabled':False},'suggested_questions':[],
                'suggested_questions_after_answer':{'enabled':False},'opening_statement':''},
            'graph':{'nodes':nodes,'edges':[{'id':a['id']+'-'+b['id'],'type':'custom','source':a['id'],
                'sourceHandle':'source','target':b['id'],'targetHandle':'target',
                'data':{'sourceType':a['data']['type'],'targetType':b['data']['type'],'isInIteration':False}}
                for a,b in zip(nodes,nodes[1:])],'viewport':{'x':15,'y':80,'zoom':0.8}}}}


def main():
    login();dsl=workflow();metadata=ROOT/'web-reader-app.json'
    if metadata.exists():
        app=json.loads(metadata.read_text());print(json.dumps({'retained':True,**app}));return
    result=api.call('POST','/apps/imports',{'mode':'yaml-content','yaml_content':json.dumps(dsl,ensure_ascii=False)})
    if result.get('status')=='pending':result=api.call('POST','/apps/imports/'+result['id']+'/confirm',{})
    app_id=result['app_id']
    api.call('POST','/apps/'+app_id+'/workflows/publish',{'marked_name':'公开网页证据读取','marked_comment':'使用现成 WebScraper，关闭模型摘要，保留正文与来源。'})
    value=api.call('POST','/apps/'+app_id+'/api-keys',{})
    key=ROOT/'private/web-reader-key';key.write_text((value.get('token') or value['api_key'])+'\n');key.chmod(0o600)
    app={'app_id':app_id,'name':dsl['app']['name'],'workflow_url':'https://tutor.example.invalid/dify/app/'+app_id+'/workflow'}
    metadata.write_text(json.dumps(app,ensure_ascii=False,indent=2))
    (ROOT/'reports/web-reader.dsl.json').write_text(json.dumps(dsl,ensure_ascii=False,indent=2))
    print(json.dumps(app,ensure_ascii=False))


if __name__=='__main__':main()
