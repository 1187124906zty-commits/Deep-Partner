"""Small progress snapshots for the current project's live task panel."""
import asyncio,json,time


def progress_snapshot(rows):
    result=[]
    for row in rows:
        item={key:row.get(key) for key in ('id','kind','status','stage','created','updated','error','task')}
        # Artifacts and their safe labels are already exposed by task.present.
        # Model output and full parsed documents belong in their own viewers.
        item['result']={key:value for key,value in (row.get('result') or {}).items() if key in ('name','filename','url','mime','identifier','entry','document_id','revision')}
        result.append(item)
    return {'jobs':result}


async def progress_events(store,owner,pid,disconnected,interval=.35,heartbeat=15):
    previous=None;last_sent=time.monotonic()
    while not await disconnected():
        payload=json.dumps(progress_snapshot(store.jobs(owner,pid)),ensure_ascii=False,separators=(',',':'))
        if payload!=previous:
            yield 'event: jobs\ndata: '+payload+'\n\n'
            previous=payload;last_sent=time.monotonic()
        elif time.monotonic()-last_sent>=heartbeat:
            yield ': keep-alive\n\n';last_sent=time.monotonic()
        await asyncio.sleep(interval)
