import React,{act} from 'react'
import {createRoot} from 'react-dom/client'
import {expect,it,vi} from 'vitest'
import ResearchThreadMessages from './ResearchThreadMessages'

vi.mock('./DitoTasks',()=>({useDitoTasks:()=>({project:{id:'project'}})}))
vi.mock('@/components/common/MarkdownRenderer',()=>({default:({content}:{content:string})=><p>{content}</p>}))

it('keeps tool output and the saved artifact available in an ordinary answer without a question card',async()=>{
 (globalThis as any).IS_REACT_ACT_ENVIRONMENT=true
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host)
 const event=(type:string,content:string,metadata:any={})=>({type,content,metadata,source:'chat',stage:'',turn_id:'turn'})
 try{
  await act(async()=>root.render(<ResearchThreadMessages questionKey="thread" activeTurnId={null} isStreaming={false} error={null} onSubmitUserReply={()=>false} messages={[{role:'assistant',content:'已按依据修订任务。',events:[
   event('tool_call','research_workbench',{tool_name:'research_workbench',tool_call_id:'call-1',call_id:'call-1',args:{research_operation:'update'}}),
   event('tool_result',JSON.stringify({status:'applied',path:'docs/research/update.md'}),{tool_name:'research_workbench',tool_call_id:'call-1',call_id:'call-1'}),
   event('thinking','PRIVATE_REASONING'),event('done','',{status:'completed'}),
  ] as any}]} />))
  expect(host.textContent).toContain('已按依据修订任务。')
  expect(host.textContent).toContain('修订研究记录与任务')
  expect(host.querySelector('a')?.getAttribute('href')).toBe('/research/api/projects/project/file?path=docs%2Fresearch%2Fupdate.md')
  expect(host.textContent).not.toContain('PRIVATE_REASONING')
 }finally{await act(async()=>root.unmount());host.remove()}
})
