/** Product integration with explicit source anchors; changes fail closed on upgrades. */
function replaceOnce(code,before,after){if(code.split(before).length!==2)throw new Error('Native follow-up seam changed: '+before.slice(0,70));return code.replace(before,after)}
export function adaptFollowupContext(source){
 let code=source.replaceAll('\r\n','\n')
 code=code.replaceAll('  quotes?: string[];','  quotes?: string[];\n  attachments?: SendMessageInput["attachments"];')
 code=replaceOnce(code,'    messages: HydratedFollowupMessage[],\n  ): void;', '    messages: HydratedFollowupMessage[],\n    active?: {id:string;status:string},\n  ): void;')
 code=replaceOnce(code,'(key: string, sessionId: string, messages: HydratedFollowupMessage[]) => {','(key: string, sessionId: string, messages: HydratedFollowupMessage[], active?: {id:string;status:string}) => {')
 code=replaceOnce(code,'          ...(m.quotes?.length ? { quotes: m.quotes } : {}),','          ...(m.quotes?.length ? { quotes: m.quotes } : {}),\n          attachments:m.attachments,')
 code=replaceOnce(code,'            quotes: input.attachments.filter(isQuoteAttachment).map(quoteText),','            quotes: input.attachments.filter(isQuoteAttachment).map(quoteText),\n            attachments:input.attachments,')
 const start=code.indexOf('      updateThread(key, (prev) => ({',code.indexOf('  const hydrateThread ='))
 const end=code.indexOf('\n  const setOpenTabHandler',start)
 let hydrate=code.slice(start,end)
 hydrate=replaceOnce(hydrate,'        sessionId,','        sessionId,\n        activeTurnId:active?.id||null,\n        isStreaming:!!active,')
 hydrate=replaceOnce(hydrate,'      }));\n    },\n    [updateThread],','      }));\n      if(active){const runner=ensureRunner(key);runner.client.setResumeState(active.id,0);runner.client.send({type:"subscribe_turn",turn_id:active.id,after_seq:0});}\n    },\n    [updateThread,ensureRunner],')
 code=code.slice(0,start)+hydrate+code.slice(end)
 const cancelStart=code.indexOf('  const cancelTurn = useCallback('),cancelEnd=code.indexOf('\n  const openFollowupTab',cancelStart)
 if(cancelStart<0||cancelEnd<0)throw new Error('Native cancellation boundary changed')
 code=code.slice(0,cancelStart)+`  const cancelTurn = useCallback((key:string) => {
    const turnId=threadsRef.current[key]?.activeTurnId;if(!turnId)return;
    updateThread(key,prev=>({...prev,currentStage:'cancelling'}));
    void sendThroughRunner(key,{type:'cancel_turn',turn_id:turnId},{awaitAck:true}).then(accepted=>{
      if(!accepted)updateThread(key,prev=>({...prev,currentStage:'',error:'停止请求未被接受，请核对当前任务状态。'}));
    }).catch(()=>updateThread(key,prev=>({...prev,currentStage:'',error:'停止请求尚未确认，保留当前任务并继续核对。'})));
  },[sendThroughRunner,updateThread]);
`+code.slice(cancelEnd)
 code=replaceOnce(code,'      if (event.type === "done") {\n        updateThread(key, (prev) => ({','      if (event.type === "done") {\n        updateThread(key, (prev) => ({\n          ...prev,\n          messages:prev.messages.map((m,i)=>i===prev.messages.length-1&&m.role===\"assistant\"?{...m,events:[...(m.events||[]),event]}:m),')
 // ...prev following messages would restore old messages, so move it first.
 code=replaceOnce(code,'events:[...(m.events||[]),event]}:m),\n          ...prev,','events:[...(m.events||[]),event]}:m),')
 // Same replayed event must not duplicate content after a snapshot hydration.
 code=replaceOnce(code,'      updateThread(key, (prev) => {\n        const next = {','      updateThread(key, (prev) => {\n        if(event.seq&&event.turn_id&&prev.messages.some(m=>m.events?.some(e=>e.turn_id===event.turn_id&&e.seq===event.seq)))return prev;\n        const next = {')
 return code
}

export function adaptFollowupBody(source){
 let code=source.replaceAll('\r\n','\n')
 const start=code.indexOf('              visibleMessages.map((message, index) => {'),end=code.indexOf('\n            )}',start)
 if(start<0||end<0)throw new Error('Native message display boundary changed')
 code=code.slice(0,start)+`              <ResearchThreadMessages key={context.questionKey} questionKey={context.questionKey} messages={thread.messages} isStreaming={thread.isStreaming} activeTurnId={thread.activeTurnId} error={thread.error} stage={thread.currentStage} onSubmitUserReply={reply=>controller.submitAskUserReply(context.questionKey,reply)}/>`+code.slice(end)
 code=replaceOnce(code,'          events: m.events ?? [],','          events: m.events ?? [],\n          attachments:m.attachments as any,')
 code=replaceOnce(code,'          hydrated,\n        );','          hydrated,\n          resumableFollowup(detail),\n        );')
 return 'import ResearchThreadMessages from "@product/host/ResearchThreadMessages";\nimport {resumableFollowup} from "@product/host/followup-recovery";\n'+code
}
