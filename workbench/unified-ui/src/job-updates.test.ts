import {afterEach,expect,it,vi} from 'vitest'
import {subscribeProjectJobs} from '../../web/src/jobUpdates'

const project={id:'owned',native_id:'workspace',name:'测试项目',root:'',config:{}}
afterEach(()=>{vi.unstubAllGlobals();vi.useRealTimers()})
it('updates task state as soon as the stream arrives without waiting for a polling interval',()=>{
 class Stream{static current:Stream;listeners=new Map<string,(event:any)=>void>();onopen:any;onerror:any;close=vi.fn();constructor(public url:string){Stream.current=this}addEventListener(name:string,fn:(event:any)=>void){this.listeners.set(name,fn)}}
 vi.stubGlobal('EventSource',Stream);const fetch=vi.fn();vi.stubGlobal('fetch',fetch);const received=vi.fn();const dispose=subscribeProjectJobs(project,received)
 const stream=Stream.current;expect(stream.url).toContain('/projects/owned/jobs/events')
 stream.listeners.get('jobs')?.({data:JSON.stringify({jobs:[{id:'a',status:'running',stage:'上传集群'}]})})
 expect(received).toHaveBeenCalledWith([{id:'a',status:'running',stage:'上传集群'}]);expect(fetch).not.toHaveBeenCalled()
 dispose();expect(stream.close).toHaveBeenCalledOnce()
 stream.listeners.get('jobs')?.({data:JSON.stringify({jobs:[]})});expect(received).toHaveBeenCalledTimes(1)
})
