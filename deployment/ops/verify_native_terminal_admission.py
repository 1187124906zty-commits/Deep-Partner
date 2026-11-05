"""Run inside the existing native container against its actual coordinator class."""
import asyncio,importlib.util,json,sys,uuid
from pathlib import Path
from deeptutor.app.container import load_integrations_settings,load_system_settings
from deeptutor.runtime.coordination import CoordinationSettings,MemoryCoordinator
from deeptutor.core.stream import StreamEvent,StreamEventType
from deeptutor.services.session._turn_runtime_shared import _TurnExecution


class Store:
    def __init__(self,status):self.status=status;self.events=[]
    async def get_turn(self,turn_id):return {'id':turn_id,'status':self.status}
    async def append_events(self,turn_id,events,**kwargs):
        self.events.extend(events);return events


async def main():
    settings=CoordinationSettings.from_runtime_settings(load_system_settings(),load_integrations_settings())
    assert settings.backend=='memory'
    memory_spec=importlib.util.spec_from_file_location('deeptutor.runtime.coordination.terminal_memory','/tmp/research-terminal/memory.candidate.py')
    memory_module=importlib.util.module_from_spec(memory_spec);sys.modules[memory_spec.name]=memory_module;memory_spec.loader.exec_module(memory_module)
    coordinator=memory_module.MemoryCoordinator()
    spec=importlib.util.spec_from_file_location('deeptutor.services.session.turns.terminal_candidate','/tmp/research-terminal/lifecycle.candidate.py')
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    from deeptutor.services.session.turns.lifecycle import TurnLifecycle as Baseline
    report={'checks':{},'coordinator':'installed MemoryCoordinator implementation, isolated instance'}
    try:
        for label,cls,status in [('baseline',Baseline,'completed'),('completed',module.TurnLifecycle,'completed'),('failed',module.TurnLifecycle,'failed'),('cancelled',module.TurnLifecycle,'cancelled'),('running',module.TurnLifecycle,'running')]:
            turn=label+'-first';session=label+'-session'
            lease=await coordinator.acquire_turn(turn,session,'acceptance');assert lease
            runtime=object.__new__(cls);runtime.store=Store(status);runtime.coordinator=coordinator;runtime._lock=asyncio.Lock()
            execution=_TurnExecution(turn,session,'chat',{},lease=lease)
            runtime._executions={turn:execution}
            heartbeat_stopped=asyncio.Event()
            async def heartbeat():
                try:await asyncio.Event().wait()
                finally:heartbeat_stopped.set()
            execution.coordination_task=asyncio.create_task(heartbeat());await asyncio.sleep(0)
            if status=='running':
                try:await runtime._publish_live_event(execution,StreamEvent(type=StreamEventType.DONE,source='acceptance',metadata={'status':'completed'}))
                except RuntimeError:report['checks']['nonterminal_done_rejected']=bool(await coordinator.get_lease(turn)) and not runtime.store.events
                else:raise AssertionError('Running turn published DONE')
            else:
                await runtime._publish_live_event(execution,StreamEvent(type=StreamEventType.DONE,source='acceptance',metadata={'status':status}))
                next_lease=await coordinator.acquire_turn(label+'-second',session,'next-worker')
                if label=='baseline':report['checks']['baseline_reproduces_rejected_next_turn']=next_lease is None
                else:
                    assert next_lease,'Next turn cannot start after DONE'
                    report['checks'][label+'_next_turn_immediate']=heartbeat_stopped.is_set() and runtime.store.events[-1]['type']=='done' and execution.lease is lease
                    report['checks'][label+'_released_turn_excluded_from_recovery']=turn not in await coordinator.list_expired_turn_ids()
                    late=await runtime._publish_live_event(execution,StreamEvent(type=StreamEventType.SESSION_META,source='acceptance',metadata={'title':'Late title'}))
                    await runtime._flush_buffered_events(execution)
                    await coordinator.release_turn(lease)
                    report['checks'][label+'_late_title_and_old_cleanup_preserve_new_lease']=late['seq']==2 and (await coordinator.get_lease(next_lease.turn_id))==next_lease and len(runtime.store.events)==2
                    await coordinator.release_turn(next_lease)
            if execution.flush_task:
                execution.flush_task.cancel()
                await asyncio.gather(execution.flush_task,return_exceptions=True)
            execution.coordination_task.cancel();await asyncio.gather(execution.coordination_task,return_exceptions=True)
            await coordinator.release_turn(lease)
        assert all(report['checks'].values()),report
        print(json.dumps(report))
    finally:
        await coordinator.close()


asyncio.run(main())
