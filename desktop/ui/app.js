
(() => {
'use strict';
const $=id=>document.getElementById(id), invoke=(action,payload={})=>window.__TAURI__.core.invoke('desktop_command',{action,payload});
const icon=name=>`<svg><use href="#i-${name}"/></svg>`;
let mode='chat',view='chat',sessions=[],models=[],knowledge=[],selectedKnowledge=[],status=null,currentSession=null,currentWorkspace=null,busy=false,waiting=false,assistantNode=null,assistantText='',renderTimer=null,folder='.',paused=false,attachments=[],ready=false,toastTimer,chatSelection=null,computerSelection=null;
const metrics=window.__DT_DESKTOP_METRICS||{samples:[]};
function toast(message,error=false){$('toast').textContent=message;$('toast').classList.toggle('error',error);$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,5000);}
async function action(name,payload={},button=null){if(button?.disabled)return;if(button)button.disabled=true;try{return await invoke(name,payload);}catch(error){toast(String(error),true);throw error;}finally{if(button)button.disabled=false;}}
function appendIcon(parent,name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#i-'+name);svg.append(use);parent.append(svg);}
function selectedModel(computer=mode==='computer'){const choice=computer?computerSelection:chatSelection;return models.find(o=>o.profile_id===choice?.profile_id&&o.model_id===choice?.model_id);}
function modelLabel(model){return (model?.model||'模型加载中').replace(/^gpt-/,'GPT-').replace(/-sol$/,' Sol').replace(/-terra$/,' Terra').replace(/-astra$/,' Astra');}
function populateModelSelect(select,choice){select.replaceChildren();for(const model of models){const option=document.createElement('option');option.value=JSON.stringify({profile_id:model.profile_id,model_id:model.model_id});option.textContent=modelLabel(model);option.selected=model.profile_id===choice?.profile_id&&model.model_id===choice?.model_id;select.append(option);}}
function updateModelUI(){const current=selectedModel();populateModelSelect($('model-select'),mode==='computer'?computerSelection:chatSelection);populateModelSelect($('learning-model'),chatSelection);populateModelSelect($('computer-model'),computerSelection);$('model-badge').textContent=modelLabel(current);$('controller-name').textContent=modelLabel(selectedModel(true));}
async function bootstrap(){
 const data=await invoke('bootstrap');models=data.models.options||[];sessions=data.sessions.sessions||[];knowledge=Array.isArray(data.knowledge)?data.knowledge:(data.knowledge.knowledge_bases||[]);
 status=await invoke('status');chatSelection=status.service.config.learning_model||data.models.active;
 const terra=models.find(m=>m.model==='gpt-6.1-terra');computerSelection=status.service.config.computer_model||(terra?{profile_id:terra.profile_id,model_id:terra.model_id}:null);
 if(!computerSelection)toast('当前服务没有配置 GPT-6.1 Terra',true);
 if(terra&&!status.service.config.computer_model)await invoke('set_model',{mode:'computer',selection:computerSelection});
 ready=true;renderSessions();renderKnowledge();updateModelUI();applyStatus(status);$('composer-status').textContent='已连接你的学习空间';
}
$('login-form').addEventListener('submit',async event=>{
 event.preventDefault();const button=$('login-submit');button.disabled=true;$('login-error').hidden=true;
 try{const result=await invoke('login',{username:$('username').value.trim(),password:$('password').value});$('password').value='';$('account-name').textContent=result.username||$('username').value;$('account-avatar').textContent=(result.username||$('username').value).slice(0,1).toUpperCase();$('login-screen').hidden=true;$('desktop-app').hidden=false;await bootstrap();}
 catch(error){if($('desktop-app').hidden){$('login-error').textContent=String(error);$('login-error').hidden=false;}else{toast(String(error),true);$('composer-status').textContent='资料同步未完成，可在设置中重新连接';}}
 finally{button.disabled=false;}
});
function renderSessions(){
 const list=$('session-list');list.replaceChildren();const query=$('history-query').value.trim().toLowerCase();const rows=sessions.filter(s=>!s.preferences?.archived&&(!query||String(s.title||'').toLowerCase().includes(query)));
 if(!rows.length){const empty=document.createElement('div');empty.className='sidebar-placeholder';empty.textContent=query?'没有找到相关对话':'还没有对话，从一个问题开始。';list.append(empty);return;}
 for(const session of rows){const button=document.createElement('button');button.className='session-item'+((session.session_id||session.id)===currentSession?' active':'');button.textContent=session.title||'未命名对话';button.title=session.title||'未命名对话';button.addEventListener('click',()=>openSession(session).catch(error=>toast(String(error),true)));list.append(button);}
}
async function openSession(session){
 if(busy){toast('当前回答仍在生成，可以先停止。');return;}
 const id=session.session_id||session.id,workspace=session.content_workspace_id||session.preferences?.workspace_id||'';
 const data=await action('get_session',{id,workspace_id:workspace});currentSession=id;currentWorkspace=workspace;
 mode=data.preferences?.llm_selection?.model_id===computerSelection?.model_id?'computer':'chat';setView(mode,false);$('session-title').textContent=data.title||session.title||'对话';$('messages').replaceChildren();$('welcome').hidden=true;
 selectedKnowledge=data.preferences?.knowledge_bases||[];updateKnowledgeCount();
 for(const message of data.messages||[]){if(message.role==='user'||message.role==='assistant')appendMessage(message.role,displayContent(message.content||''),false);}
 renderSessions();scrollBottom();
}
function displayContent(content){return content.replace(/^\[电脑助手任务：[\s\S]*?\]\n\n/,'');}
function setView(next,newConversation=true){
 if(busy&&['chat','computer'].includes(next)&&mode!==next&&newConversation){toast('请先停止当前任务，再切换助手。');return;}
 view=next;
 document.querySelectorAll('[data-view]').forEach(button=>button.classList.toggle('active',button.dataset.view===next));
 const isChat=next==='chat'||next==='computer';$('chat-view').hidden=!isChat;$('knowledge-view').hidden=next!=='knowledge';$('files-view').hidden=next!=='files';
 if(isChat){if(mode!==next&&newConversation)clearConversation();mode=next;const computer=mode==='computer';$('view-label').textContent=computer?'电脑助手':'学习助手';$('activity-panel').hidden=!computer;$('welcome-title').textContent=computer?'把任务交给这台电脑。':'从一个好问题开始。';$('welcome-eyebrow').textContent=computer?'YOUR IDEAS. YOUR COMPUTER. ONE CONVERSATION.':'A LITTLE CURIOSITY GOES A LONG WAY';$('welcome-description').textContent=computer?'描述你的目标，Terra 会读取页面、操作软件，和你一起完成。':'一起读懂复杂的知识，把想法变成下一步。';$('message-input').placeholder=computer?'让 Terra 帮你在电脑上做点什么…':'有什么想深入了解的？';$('capability-select').hidden=computer;$('knowledge-picker').hidden=computer;
 const buttons=[...$('suggestions').children];const prompts=computer?[
 ['globe','检索一个网页','打开、阅读、点击与输入','用本机工具浏览器打开百度，检索 DeepTutor，并告诉我当前页面的标题。'],
 ['folder','整理本机资料','读取文件，搜索关键信息','列出本机共享文件夹里的资料，并告诉我有哪些可以继续阅读的文本文件。'],
 ['computer','查看这台电脑','观察桌面，继续下一步','使用本机桌面截图观察当前打开的窗口，告诉我你看到什么，先不要点击。']
 ]:[['spark','深入一个问题','从疑问出发，理清思路','帮我梳理一个研究问题，先了解我的研究目标和已有材料。'],['search','寻找研究线索','查找文献，连接已有认识','帮我检索相关论文，并比较不同方法的假设与适用范围。'],['book','和资料聊一聊','基于原文，建立自己的理解','我想基于知识库中的资料学习，请先概览资料，再和我讨论。']];
 buttons.forEach((button,index)=>{button.replaceChildren();appendIcon(button,prompts[index][0]);const strong=document.createElement('strong');strong.textContent=prompts[index][1];const span=document.createElement('span');span.textContent=prompts[index][2];button.append(strong,span);button.dataset.prompt=prompts[index][3];});updateModelUI();
 }else{$('view-label').textContent=next==='knowledge'?'知识库':'本机文件';$('session-title').textContent='';$('activity-panel').hidden=true;if(next==='files')loadFiles().catch(error=>toast(String(error),true));}
}
function clearConversation(){currentSession=null;currentWorkspace=null;$('messages').replaceChildren();$('welcome').hidden=false;$('session-title').textContent='新对话';assistantNode=null;assistantText='';attachments=[];renderAttachments();renderSessions();}
function newChat(){if(busy){toast('当前任务仍在执行，可以先停止。');return;}clearConversation();setView(mode,false);$('message-input').focus();}
function renderMarkdown(node,text){const html=window.marked.parse(text,{breaks:true,gfm:true});node.innerHTML=window.DOMPurify.sanitize(html,{FORBID_TAGS:['style','iframe','object','form','input','button'],FORBID_ATTR:['style']});if(window.renderMathInElement){window.renderMathInElement(node,{delimiters:[{left:'$$',right:'$$',display:true},{left:'\\[',right:'\\]',display:true},{left:'$',right:'$',display:false},{left:'\\(',right:'\\)',display:false}],throwOnError:false,trust:false});}}
function appendMessage(role,text,streaming=false){
 const message=document.createElement('article');message.className='message '+role;const body=document.createElement('div');body.className='message-body';
 if(role==='assistant'){const heading=document.createElement('div');heading.className='message-heading';appendIcon(heading,'spark');const label=document.createElement('span');label.textContent=mode==='computer'?'Terra':'DeepTutor';heading.append(label);message.append(heading);if(text)renderMarkdown(body,text);else if(streaming){const status=document.createElement('div');status.className='message-status';const dot=document.createElement('span');dot.className='typing-dot';const label=document.createElement('span');label.textContent=mode==='computer'?'正在准备操作…':'正在思考…';status.append(dot,label);body.append(status);}}
 else body.textContent=text;
 message.append(body);$('messages').append(message);return body;
}
function scrollBottom(force=true){const scroll=$('conversation-scroll');if(force||scroll.scrollHeight-scroll.scrollTop-scroll.clientHeight<150)scroll.scrollTop=scroll.scrollHeight;}
function renderStream(){renderTimer=null;if(assistantNode&&assistantText){const scroll=$('conversation-scroll'),follow=scroll.scrollHeight-scroll.scrollTop-scroll.clientHeight<180;renderMarkdown(assistantNode,assistantText);scrollBottom(follow);}}
function scheduleRender(){if(renderTimer===null)renderTimer=setTimeout(()=>requestAnimationFrame(renderStream),40);}
function setBusy(value){busy=value;$('send').hidden=value;$('stop').hidden=!value;$('message-input').disabled=false;document.querySelectorAll('.suggestions button').forEach(b=>b.disabled=value);}
async function sendMessage(){
 const text=$('message-input').value.trim();if(!text)return;if(!ready){toast('学习服务尚未连接完成，请稍后再试。');return;}if(busy&&!waiting)return;
 if(waiting){await action('chat_control',{type:'submit_user_reply',text});appendMessage('user',text);$('message-input').value='';waiting=false;return;}
 $('welcome').hidden=true;appendMessage('user',text);$('message-input').value='';$('message-input').style.height='auto';assistantText='';assistantNode=appendMessage('assistant','',true);setBusy(true);$('composer-status').textContent=mode==='computer'?'Terra 正在执行任务…':'正在生成回答…';scrollBottom();
 let content=text;if(attachments.length)content+='\n\n本机共享文件夹中新添加的文件：'+attachments.join('、')+'。需要时使用 windows-desktop MCP 读取。';
 const payload={mode,content,capability:$('capability-select').value,knowledge_bases:selectedKnowledge};if(currentSession)payload.session_id=currentSession;if(currentWorkspace)payload.workspace_id=currentWorkspace;
 try{await invoke('send_message',payload);attachments=[];renderAttachments();}catch(error){setBusy(false);assistantNode.textContent=String(error);$('composer-status').textContent='发送未完成，可以重试';toast(String(error),true);}
}
function onChatEvent(event){
 const type=event.type,metadata=event.metadata||{};
 if(event.session_id&&!currentSession){currentSession=event.session_id;sessions.unshift({session_id:currentSession,title:$('messages').querySelector('.user .message-body')?.textContent?.slice(0,32)||'新对话',content_workspace_id:currentWorkspace});renderSessions();}
 if(type==='session_meta'&&metadata.title){$('session-title').textContent=metadata.title;const row=sessions.find(s=>(s.session_id||s.id)===currentSession);if(row){row.title=metadata.title;renderSessions();}}
 if(type==='content'){assistantText+=event.content||'';scheduleRender();}
 if(type==='result'){const response=metadata.response||metadata.agent_output;if(typeof response==='string'&&response){assistantText=response;scheduleRender();}}
 if(type==='tool_call'){addActivity(metadata.tool_name||metadata.name||metadata.tool||event.source||'正在调用工具',event.content||'');$('composer-status').textContent='正在调用工具…';}
 if(type==='tool_result'){addActivity(metadata.tool_name||metadata.name||event.source||'工具执行完成','已收到工具结果');}
 if(type==='thinking'||type==='stage_start'||type==='progress'){if(!assistantText&&assistantNode){const label=assistantNode.querySelector('.message-status span:last-child');if(label)label.textContent=mode==='computer'?'正在观察与执行…':'正在分析资料…';}}
 if(type==='wait_for_input'){waiting=true;$('composer-status').textContent='助手需要你的补充，请在输入框回复';}
 if(type==='desktop_error'||type==='protocol_error'){const error=event.content||event.message||'对话连接失败';toast(error,true);if(assistantNode&&!assistantText)assistantNode.textContent=error;}
 if(type==='desktop_reconnecting')$('composer-status').textContent=event.content;
 if(type==='done'){if(metadata.status==='failed'){toast('任务未完成，请查看执行信息。',true);}if(!assistantText&&assistantNode)assistantNode.textContent=metadata.status==='cancelled'?'已停止本次任务。':'本次执行结束。';}
 if(type==='desktop_finished'){setBusy(false);waiting=false;renderStream();$('composer-status').textContent='已连接你的学习空间';invoke('sessions').then(data=>{sessions=data.sessions||sessions;renderSessions();}).catch(()=>{});refreshStatus().catch(()=>{});}
}
function addActivity(title,detail){const timeline=$('tool-timeline');timeline.querySelector('.timeline-empty')?.remove();const row=document.createElement('div');row.className='timeline-item';const name=document.createElement('strong');name.textContent=String(title).replace(/^mcp_windows-desktop_/,'').slice(0,100);const description=document.createElement('span');description.textContent=String(detail).slice(0,180);row.append(name,description);timeline.prepend(row);while(timeline.children.length>30)timeline.lastChild.remove();}
function applyStatus(data){status=data;const cfg=data.service.config,connected=data.connection.connected;paused=!data.service.enabled;$('connection-label').textContent=connected?(paused?'电脑工具已暂停':'服务已连接'):'电脑连接中';$('connection-dot').style.background=connected?'#8eaa94':'#bca2c6';$('bridge-detail').textContent=connected?'电脑已连接，所有工具可用':data.connection.message;$('pause').textContent=paused?'恢复':'暂停';$('workspace-path').textContent=cfg.workspace;$('workers-label').textContent=`${cfg.cpu_workers} 个后台任务槽位 · 异步运行`;$('settings-server').textContent=new URL(cfg.server_url).host;$('cache-detail').textContent=`${(data.service.cache.bytes/1048576).toFixed(1)} / ${Math.round(data.service.cache.budget_bytes/1048576)} MB`;$('cpu-detail').textContent=`${cfg.cpu_workers} 个任务`;
 const samples=metrics.samples||[];if(samples.length){const sorted=samples.slice().sort((a,b)=>a-b);$('feedback-detail').textContent=`${sorted[Math.floor(sorted.length/2)].toFixed(1)} ms（中位数）`;}
}
async function refreshStatus(){applyStatus(await invoke('status'));}
function renderKnowledge(){const list=$('knowledge-list');list.replaceChildren();if(!knowledge.length){const empty=document.createElement('p');empty.className='empty-state';empty.textContent='当前账户还没有知识库。';list.append(empty);}for(const kb of knowledge){const card=document.createElement('article');card.className='knowledge-card';appendIcon(card,'book');const title=document.createElement('h3');title.textContent=kb.display_name||kb.name||'知识库';const description=document.createElement('p');description.textContent=kb.description||[kb.provider||kb.rag_provider,kb.status].filter(Boolean).join(' · ')||'已连接的学习资料';const button=document.createElement('button');button.className='text-button';button.textContent='基于资料开始对话 ↗';button.addEventListener('click',()=>{if(busy){toast('请先停止当前生成。');return;}selectedKnowledge=[kb.resource_id||kb.name];newChat();setView('chat');updateKnowledgeCount();$('message-input').value=`请基于“${title.textContent}”的资料回答我的问题：`;});card.append(title,description,button);list.append(card);}}
function updateKnowledgeCount(){$('knowledge-count').textContent=selectedKnowledge.length?`${selectedKnowledge.length} 个知识库`:'知识库';}
function openKnowledgePicker(){const list=$('knowledge-options');list.replaceChildren();for(const kb of knowledge){const label=document.createElement('label');label.className='knowledge-option';const input=document.createElement('input');input.type='checkbox';input.value=kb.resource_id||kb.name;input.checked=selectedKnowledge.includes(input.value);input.addEventListener('change',()=>{if(input.checked)selectedKnowledge.push(input.value);else selectedKnowledge=selectedKnowledge.filter(v=>v!==input.value);updateKnowledgeCount();});const name=document.createElement('span');name.textContent=kb.display_name||kb.name;label.append(input,name);list.append(label);}if(!knowledge.length){list.textContent='当前账户没有可选知识库。';}$('knowledge-dialog').showModal();}
async function loadFiles(){const result=await invoke('local_tool',{name:'workspace_list',arguments:{path:folder}});$('file-list').replaceChildren();$('current-folder').textContent=folder==='.'?'全部文件':folder;if(!result.entries.length){const empty=document.createElement('div');empty.className='empty-state';empty.textContent='这里还没有文件。添加资料，或选择你已有的文件夹。';$('file-list').append(empty);}for(const file of result.entries){const path=folder==='.'?file.name:folder+'/'+file.name;const row=document.createElement('div');row.className='file-row';appendIcon(row,file.directory?'folder':'file');const button=document.createElement('button');button.textContent=file.name;button.addEventListener('click',async()=>{try{if(file.directory){folder=path;await loadFiles();}else{const result=await invoke('local_tool',{name:'workspace_read',arguments:{path}});$('file-preview').textContent=result.text;$('file-preview').hidden=false;}}catch(error){toast(String(error),true);}});const detail=document.createElement('span');detail.textContent=file.directory?'文件夹':file.bytes>1048576?(file.bytes/1048576).toFixed(1)+' MB':Math.ceil(file.bytes/1024)+' KB';row.append(button,detail);$('file-list').append(row);}}
async function searchFiles(){const query=$('file-search').value.trim();if(!query){await loadFiles();return;}const result=await invoke('local_tool',{name:'workspace_search',arguments:{query}});if(query!==$('file-search').value.trim())return;$('file-list').replaceChildren();$('current-folder').textContent=`${result.matches.length} 处匹配`;for(const match of result.matches){const row=document.createElement('div');row.className='file-row';appendIcon(row,'file');const button=document.createElement('button');button.textContent=`${match.path} · 第 ${match.line} 行`;button.title=match.text;button.addEventListener('click',async()=>{const result=await action('local_tool',{name:'workspace_read',arguments:{path:match.path,start_line:Math.max(1,match.line-5)}});$('file-preview').textContent=result.text;$('file-preview').hidden=false;});row.append(button);$('file-list').append(row);}}
function renderAttachments(){$('attachment-chips').replaceChildren();for(const name of attachments){const chip=document.createElement('span');chip.className='attachment-chip';chip.textContent=name;$('attachment-chips').append(chip);}}
async function importFile(attach=false){const result=await action('import_file');if(result&&!result.cancelled){if(attach){attachments.push(result.imported.split(/[\\/]/).pop());renderAttachments();}else await loadFiles();}}
$('new-chat').addEventListener('click',newChat);document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>setView(button.dataset.view)));
$('suggestions').addEventListener('click',event=>{const button=event.target.closest('button[data-prompt]');if(button){$('message-input').value=button.dataset.prompt;$('message-input').focus();}});
$('message-input').addEventListener('input',event=>{event.target.style.height='auto';event.target.style.height=Math.min(event.target.scrollHeight,190)+'px';});
$('message-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();sendMessage();}});$('send').addEventListener('click',sendMessage);$('stop').addEventListener('click',()=>action('chat_control',{type:'cancel_turn'}).catch(()=>{}));
$('search-history').addEventListener('click',()=>{$('history-query').hidden=!$('history-query').hidden;if(!$('history-query').hidden)$('history-query').focus();});$('history-query').addEventListener('input',renderSessions);
$('activity-toggle').addEventListener('click',()=>{$('activity-panel').hidden=!$('activity-panel').hidden;});
$('connect').addEventListener('click',event=>action('connect',{},event.currentTarget).then(refreshStatus).catch(()=>{}));$('pause').addEventListener('click',()=>action('pause',{paused:!paused}).then(refreshStatus).catch(()=>{}));
$('settings-button').addEventListener('click',()=>{refreshStatus().catch(()=>{});$('settings-dialog').showModal();});$('close-settings').addEventListener('click',()=>$('settings-dialog').close());
$('logout').addEventListener('click',async()=>{if(busy){toast('请先停止当前任务。');return;}await invoke('logout');ready=false;$('desktop-app').hidden=true;$('login-screen').hidden=false;clearConversation();});
for(const [id,computer] of [['learning-model',false],['computer-model',true],['model-select',null]])$(id).addEventListener('change',async event=>{const control=computer===null?mode==='computer':computer;const selection=JSON.parse(event.target.value);await action('set_model',{mode:control?'computer':'chat',selection});if(control)computerSelection=selection;else chatSelection=selection;updateModelUI();});
$('knowledge-picker').addEventListener('click',openKnowledgePicker);$('close-knowledge').addEventListener('click',()=>$('knowledge-dialog').close());$('knowledge-done').addEventListener('click',()=>$('knowledge-dialog').close());
$('choose-folder').addEventListener('click',()=>action('choose_folder').then(async()=>{folder='.';await refreshStatus();await loadFiles();}).catch(()=>{}));$('open-workspace').addEventListener('click',()=>action('open_workspace').catch(()=>{}));$('open-data').addEventListener('click',()=>action('open_data').catch(()=>{}));$('import-file').addEventListener('click',()=>importFile().catch(()=>{}));$('attach-file').addEventListener('click',()=>importFile(true).catch(()=>{}));$('parent-folder').addEventListener('click',()=>{folder=folder.split('/').slice(0,-1).join('/')||'.';loadFiles().catch(error=>toast(String(error),true));});let searchTimer;$('file-search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>searchFiles().catch(error=>toast(String(error),true)),250);});
$('messages').addEventListener('click',event=>{const link=event.target.closest('a[href]');if(!link)return;event.preventDefault();if(/^https?:\/\//i.test(link.href))action('local_tool',{name:'open_url',arguments:{url:link.href}}).catch(()=>{});});
window.__TAURI__.event.listen('chat-event',event=>onChatEvent(event.payload)).catch(()=>{});
document.addEventListener('keydown',event=>{if(event.ctrlKey&&event.key==='n'&&!$('desktop-app').hidden){event.preventDefault();newChat();}});
setInterval(()=>{if(!$('desktop-app').hidden&&!document.hidden)refreshStatus().catch(()=>{});},5000);
})();
