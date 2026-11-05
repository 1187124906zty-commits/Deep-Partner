import {beforeAll,describe,it,expect} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import i18n from 'i18next'
import {initReactI18next} from 'react-i18next'
import {ANNOTATION_TASK_HEADER,OPERATION_DELIMITER,WORKBENCH_STANDARD_START,parseWorkbenchFeedback} from './workbench-feedback'
import WorkbenchMessageBody from './WorkbenchMessageBody'

const item=(request:string,id='q1')=>({id,area:'paper',asset:'manuscript/paper.json',title:'论文第2段',quote:'原始材料',request,locator:{page:2,current_draft:{revision:17,content:{type:'doc',text:'x'.repeat(5000)}}}})
const envelope=(items:unknown[],double=false)=>WORKBENCH_STANDARD_START+'完整规则。'+OPERATION_DELIMITER+(double?WORKBENCH_STANDARD_START+'原有规则。'+OPERATION_DELIMITER:'')+ANNOTATION_TASK_HEADER+'项目根目录：/work/project\n\n'+JSON.stringify(items,null,2)
beforeAll(async()=>{await i18n.use(initReactI18next).init({lng:'zh',fallbackLng:'zh',resources:{zh:{translation:{}}},interpolation:{escapeValue:false}})})
describe('generated workbench feedback display',()=>{
 it('renders the exact request without changing negation, quantities or units',()=>{const request='不要删除第2段。只核对3处引文，保留0.05 mol/L和负号 −2；不得新增实验。\n“不是2份，是3份”。';expect(parseWorkbenchFeedback(envelope([item(request)]))?.items[0].request).toBe(request)})
 it('preserves the order and complete wording of multiple questions',()=>{const requests=['仅改图2，不改图1。','保留两组原始值，不能取平均。'];expect(parseWorkbenchFeedback(envelope(requests.map((text,index)=>item(text,'q'+index))))?.items.map(x=>x.request)).toEqual(requests)})
 it('recognizes both the current single wrapper and already-stored double wrapper',()=>{for(const double of [false,true])expect(parseWorkbenchFeedback(envelope([item('保持原文，不作修改。')],double))?.items[0].request).toBe('保持原文，不作修改。')})
 it('leaves ordinary prose, pasted JSON and partial markers unchanged',()=>{for(const content of ['普通问题：不要修改第三段。',JSON.stringify([item('不要改动')]),ANNOTATION_TASK_HEADER+'项目根目录：/work/project\n\n'+JSON.stringify([item('要求')]),WORKBENCH_STANDARD_START+'请解释这些规则'])expect(parseWorkbenchFeedback(content)).toBeNull()})
 it('does not fold malformed payloads or a loose question-shaped object',()=>{expect(parseWorkbenchFeedback(envelope([{request:'不是合法批注'}]))).toBeNull();expect(parseWorkbenchFeedback(envelope([item('原文')])+' trailing notes')).toBeNull()})
 it('keeps the entire stored source available inside a closed native details control',()=>{const source=envelope([item('不做新实验，只复核现有3组结果。')],true);const holder=document.createElement('div');holder.innerHTML=renderToStaticMarkup(<WorkbenchMessageBody content={source}/>);const details=holder.querySelector('details')!;expect(details.hasAttribute('open')).toBe(false);expect(details.querySelector('summary')?.textContent).toBe('材料与执行上下文');expect(details.querySelector('pre')?.textContent).toBe(source);expect(holder.querySelector('.dp-feedback-request')?.textContent).toBe('不做新实验，只复核现有3组结果。')})
 it('keeps ordinary user content complete in the unchanged plain-text body',()=>{const content='普通问题：不要删除第2段。\n保留3组数据。';const holder=document.createElement('div');holder.innerHTML=renderToStaticMarkup(<WorkbenchMessageBody content={content}/>);expect(holder.querySelector('details')).toBeNull();expect(holder.textContent).toBe(content)})
})
