const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');const wait=(ms=40)=>new Promise(resolve=>setTimeout(resolve,ms));
function app(){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'ui/index.html'),'utf8'),{runScripts:'outside-only',pretendToBeVisual:true,url:'http://tauri.localhost/'});
 const win=dom.window,records=[],events={};
 const models=[{profile_id:'main',model_id:'sol',model:'gpt-6.1-sol',is_active_default:true},{profile_id:'main',model_id:'terra',model:'gpt-6.1-terra'}];
 const status={version:'0.1.0',connection:{connected:true,message:'Connected'},service:{enabled:true,config:{server_url:'https://tutor.example.invalid',workspace:'C:/Desktop Workspace',cpu_workers:6,desktop_control:true,computer_model:null,learning_model:null},cache:{bytes:0,budget_bytes:33554432}}};
 win.__TAURI__={core:{invoke:async(_,{action,payload})=>{
  records.push({action,payload});
  switch(action){case'login':return{ok:true,username:'tutor'};case'bootstrap':return{models:{active:{profile_id:'main',model_id:'sol'},options:models},sessions:{sessions:[{session_id:'old-session',title:'已有学习会话',content_workspace_id:'study'}]},knowledge:[{name:'材料科学',description:'原始文献'}]};case'status':return status;case'set_model':return{saved:true};case'send_message':return{accepted:true};case'sessions':return{sessions:[]};case'get_session':return{title:'已有学习会话',messages:[{role:'user',content:'一个真实问题'},{role:'assistant',content:'已有的回答'}]};case'local_tool':return{entries:[]};default:return{};}
 }},event:{listen:async(name,callback)=>{events[name]=callback;}}};
 win.eval(fs.readFileSync(path.join(root,'ui/vendor/marked.js'),'utf8'));win.eval(fs.readFileSync(path.join(root,'ui/vendor/purify.js'),'utf8'));win.eval(fs.readFileSync(path.join(root,'ui/app.js'),'utf8'));
 return{dom,win,records,events,document:win.document,emit:event=>events['chat-event']({payload:event})};
}
async function login(a){a.document.querySelector('#username').value='tutor';a.document.querySelector('#password').value='test-only-password';a.document.querySelector('#login-form').dispatchEvent(new a.win.Event('submit',{bubbles:true,cancelable:true}));await wait();}
test('login uses fixed server, clears password, loads sessions and Terra without setup screens',async()=>{
 const a=app();try{
  assert.equal(a.document.querySelector('#desktop-app').hidden,true);assert.equal(a.document.querySelector('#login-screen').hidden,false);
  assert.equal(a.document.querySelector('#login-screen select'),null);await login(a);
  assert.equal(a.document.querySelector('#password').value,'');assert.equal(a.document.querySelector('#login-screen').hidden,true);assert.equal(a.document.querySelector('#desktop-app').hidden,false);
  assert.match(a.document.querySelector('#session-list').textContent,/已有学习会话/);assert.match(a.document.querySelector('#computer-model').textContent,/Terra/);
  assert.ok(a.records.some(r=>r.action==='set_model'&&r.payload.mode==='computer'&&r.payload.selection.model_id==='terra'));
 }finally{a.dom.window.close();}
});
test('computer mode submits a real task and streams final Markdown safely',async()=>{
 const a=app();try{
  await login(a);a.document.querySelector('[data-view="computer"]').click();a.document.querySelector('#message-input').value='读取这台电脑的 CPU 信息';a.document.querySelector('#send').click();await wait();
  const send=a.records.find(r=>r.action==='send_message');assert.equal(send.payload.mode,'computer');assert.equal(send.payload.content,'读取这台电脑的 CPU 信息');
  assert.equal(a.document.querySelector('#stop').hidden,false);
  a.emit({type:'content',content:'**CPU** 信息',session_id:'new-session',turn_id:'t1',seq:1});await wait(80);
  assert.match(a.document.querySelector('.message.assistant .message-body').innerHTML,/<strong>CPU<\/strong>/);
  a.emit({type:'result',metadata:{response:'结果：<script>window.hacked=1</script>20 个逻辑核心。'}});a.emit({type:'done',metadata:{status:'completed'}});a.emit({type:'desktop_finished'});await wait(80);
  assert.equal(a.win.hacked,undefined);assert.equal(a.document.querySelector('.message.assistant script'),null);assert.match(a.document.querySelector('.message.assistant').textContent,/20 个逻辑核心/);assert.equal(a.document.querySelector('#send').hidden,false);
 }finally{a.dom.window.close();}
});
test('history loads persisted content and learning capability remains selectable',async()=>{
 const a=app();try{
  await login(a);a.document.querySelector('.session-item').click();await wait();assert.match(a.document.querySelector('#messages').textContent,/已有的回答/);
  a.document.querySelector('#new-chat').click();a.document.querySelector('#capability-select').value='deep_solve';a.document.querySelector('#message-input').value='求解这个方程';a.document.querySelector('#send').click();await wait();
  const send=a.records.find(r=>r.action==='send_message');assert.equal(send.payload.capability,'deep_solve');assert.equal(send.payload.mode,'chat');
 }finally{a.dom.window.close();}
});
