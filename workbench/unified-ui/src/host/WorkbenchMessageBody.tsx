import {useMemo} from 'react'
import {useTranslation} from 'react-i18next'
import {parseWorkbenchFeedback} from './workbench-feedback'

/** Only the body slot of the original UserMessage is adapted. The original
 * message, editor, copy button, branches and runtime remain its owners. */
export default function WorkbenchMessageBody({content}:{content:string}){
 const feedback=useMemo(()=>parseWorkbenchFeedback(content),[content])
 const {i18n}=useTranslation()
 if(!feedback)return <div className="dp-user-message-body whitespace-pre-wrap">{content}</div>
 const english=i18n.language==='en'
 return <div className="dp-workbench-feedback" data-workbench-feedback="annotations">
  <div className="dp-feedback-requests">{feedback.items.map((item,index)=><section key={item.id+':'+index}>
   <p className="dp-feedback-request">{item.request}</p>
   <span className="dp-feedback-location">{item.title||item.asset}</span>
  </section>)}</div>
  <details className="dp-feedback-context"><summary>{english?'Materials and execution context':'材料与执行上下文'}</summary><pre>{content}</pre></details>
 </div>
}
