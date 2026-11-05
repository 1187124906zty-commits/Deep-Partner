import {describe,it,expect} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {CodeTaskEvidence} from '@workbench/TaskCenter'
import type {Project} from '@workbench/api'
const project={id:'p',native_id:'w',name:'Research',config:{}} as Project
describe('code deliverables remain connected to verification and the original session',()=>{
 it('does not equate an empty verification receipt with tests passing',()=>{
  const html=renderToStaticMarkup(<CodeTaskEvidence project={project} result={{files:[{path:'src/main.py',read_back:true}],verification:{},session_id:'original'}} preview={()=>{}}/>)
  expect(html).toContain('执行器未回传结构化验证记录')
  expect(html).toContain('session=original')
  expect(html).toContain('src/main.py')
  expect(html).not.toContain('测试已通过')
 })
 it('retains failing checks and limitations instead of replacing them with the executor terminal status',()=>{
  const html=renderToStaticMarkup(<CodeTaskEvidence project={project} result={{status:'completed',files:[],verification:{checks:[{name:'mass_balance',status:'failed',error:0.1}]},limitations:['未满足守恒误差要求']}} preview={()=>{}}/>)
  expect(html).toContain('failed');expect(html).toContain('mass_balance');expect(html).toContain('未满足守恒误差要求')
 })
})
