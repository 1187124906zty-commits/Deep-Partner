import asyncio,json
from server.job_stream import progress_events,progress_snapshot


def test_progress_snapshot_keeps_pipeline_and_file_links_without_full_model_output():
    item={'id':'owned','kind':'manuscript-export','status':'running','task':{'steps':[{'id':'export','state':'running'}]},'result':{'url':'/owned/file','name':'paper.docx','model_output':'x'*30000}}
    snapshot=progress_snapshot([item])
    assert snapshot['jobs'][0]['task']==item['task']
    assert snapshot['jobs'][0]['result']=={'url':'/owned/file','name':'paper.docx'}
    assert len(json.dumps(snapshot))<1000


def test_stream_sends_changed_steps_and_suppresses_unchanged_snapshots():
    class Store:
        calls=0
        def jobs(self,owner,pid):
            assert (owner,pid)==('owner','project');self.calls+=1
            return [{'id':'job','stage':'下载' if self.calls<3 else '入库'}]
    async def run():
        store=Store()
        async def disconnected():return False
        stream=progress_events(store,'owner','project',disconnected,interval=0)
        first=await anext(stream);second=await anext(stream);await stream.aclose()
        assert '下载' in first and '入库' in second and store.calls==3
    asyncio.run(run())
