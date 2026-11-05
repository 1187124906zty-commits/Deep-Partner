"""Invoke the installed native RAG within the authenticated account scope."""
from pathlib import Path
from types import SimpleNamespace
import asyncio,json,os,sys

sys.path.insert(0,'/app')
os.chdir('/app')
os.environ.setdefault('DEEPTUTOR_WORKSPACE_ALLOWED_ROOTS','/workspace')
os.environ.setdefault('DEEPTUTOR_WORKSPACE_ROOT','/workspace')


async def main(payload):
    from deeptutor.multi_user.context import set_current_user,reset_current_user,user_from_token_payload
    from deeptutor.tools.rag_tool import rag_search
    user=payload['owner'];context=user_from_token_payload(SimpleNamespace(user_id=user['id'],username=user['username'],role=user['role']))
    token=set_current_user(context)
    try:
        from deeptutor.services.workspace.context import install_workspace_scope
        install_workspace_scope(payload['workspace'])
        result=await rag_search(payload['query'],kb_name=payload['knowledge_base'],top_k=payload['limit'])
        if result.get('error_type'):return {'ok':False,'error':str(result.get('answer') or result['error_type'])[:600]}
        return {'ok':True,'result':result}
    finally:reset_current_user(token)


if __name__=='__main__':
    try:result=asyncio.run(main(json.loads(sys.stdin.read())))
    except Exception as error:result={'ok':False,'error':'原生 RAG 配置或索引不可用：'+str(error)[:400]}
    print(json.dumps(result,ensure_ascii=False,default=str))
