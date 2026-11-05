import {describe,it,expect} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {TaskCenter} from '@workbench/TaskCenter'
import type {Job,Project} from '@workbench/api'

const project={id:'project-1',name:'水分扩散',native_id:'ws-1',root:'',config:{}} as Project
function job(id:string,subject:string,status='queued'):Job{return {id,kind:'literature-download',status,stage:'等待下载设备',error:'',result:{},task:{version:1,workflow:'literature-download',type_label:'文献下载',title:'下载 · '+subject,subject,steps:[{id:'download',label:'下载全文',state:status==='failed'?'failed':'waiting'},{id:'verify',label:'核对 PDF',state:'pending'}],current_step:'download',completed_steps:0,total_steps:2,summary:'等待下载设备',waiting:status==='queued',events:[],artifacts:[]}}}
function markup(jobs:Job[]){const holder=document.createElement('div');holder.innerHTML=renderToStaticMarkup(<TaskCenter jobs={jobs} project={project} onClose={()=>{}} onChanged={()=>{}}/>);return holder}

describe('independent execution cards',()=>{
 it('keeps service waits and author decisions visible in active tasks',()=>{
  const service=job('offline','服务恢复','waiting_service');service.kind='research-flow'
  const decision=job('plan','需要审阅','waiting_input');decision.kind='research-flow';decision.result={code_result:{native_tool:true,interaction:{id:'review-1',request:{interaction_type:'plan_review',data:{plan:'Implementation plan text'}}}}}
  const holder=markup([service,decision])
  expect(holder.querySelectorAll('[data-task-id]').length).toBe(2)
  expect(holder.textContent).toContain('等待服务恢复')
  expect(holder.textContent).toContain('需要回复')
  expect(holder.textContent).toContain('Implementation plan text')
  expect(holder.textContent).toContain('确认计划并继续')
  expect(holder.querySelector('textarea')?.value).toBe('')
  expect([...holder.querySelectorAll('button')].find(b=>b.textContent==='提交修改意见')?.disabled).toBe(true)
 })
 it('keeps two runs of one workflow as distinct named cards',()=>{const holder=markup([job('one','Feng 2014 微结构模型'),job('two','Bullard 2011 水泥水化')]);expect(holder.querySelectorAll('[data-task-id]').length).toBe(2);expect(holder.querySelector('[data-task-id="one"]')?.textContent).toContain('Feng 2014');expect(holder.querySelector('[data-task-id="two"]')?.textContent).toContain('Bullard 2011')})
 it('opens a nonmodal panel and reports waiting without a running spinner',()=>{const holder=markup([job('one','待下载文献')]);expect(holder.querySelector('[role="dialog"]')?.getAttribute('aria-modal')).toBe('false');expect(holder.querySelector('.modal-backdrop')).toBeNull();expect(holder.querySelector('.task-state')?.textContent).toBe('等待中');expect(holder.querySelector('.task-state .spin')).toBeNull();expect(holder.textContent).toContain('等待本机下载设备领取')})
 it('retains an error on its real step and offers the supported retry',()=>{const failed=job('broken','失败的论文','failed');failed.error='PDF 首页与论文身份不一致';const holder=markup([failed]);expect(holder.querySelector('[role="alert"]')?.textContent).toContain('PDF 首页');expect(holder.querySelector('[aria-current="step"]')?.getAttribute('data-state')).toBe('failed');expect(holder.querySelectorAll('[data-state="done"]').length).toBe(0);expect(holder.textContent).toContain('重新下载')})
})
