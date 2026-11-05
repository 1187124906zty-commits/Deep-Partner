const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
const root=path.resolve(__dirname,'..');
test('UI scripts compile and every referenced DOM id exists',()=>{
 const html=fs.readFileSync(path.join(root,'ui/index.html'),'utf8');const script=fs.readFileSync(path.join(root,'ui/app.js'),'utf8');
 new vm.Script(script);new vm.Script(fs.readFileSync(path.join(root,'ui/tutor-enhancements.js'),'utf8'));
 for(const match of script.matchAll(/\$\('([^']+)'\)/g))assert.ok(html.includes(`id="${match[1]}"`),`missing DOM id ${match[1]}`);
 assert.ok(script.includes('window.DOMPurify.sanitize(html'));assert.ok(!script.includes('eval('));
});
test('desktop uses one independent local UI and login has no settings',()=>{
 const main=fs.readFileSync(path.join(root,'src/main.rs'),'utf8');
 const html=fs.readFileSync(path.join(root,'ui/index.html'),'utf8');
 assert.ok(!main.includes('WebviewUrl::External'));assert.ok(!html.includes('<iframe'));
 const login=html.slice(html.indexOf('<section id="login-screen"'),html.indexOf('<div id="desktop-app"'));
 assert.ok(login.includes('id="username"'));assert.ok(login.includes('id="password"'));
 assert.ok(!login.includes('settings'));assert.ok(!login.includes('Terra'));assert.ok(!login.includes('bridge'));
});
test('press feedback does not replace application click handlers',()=>{
 const script=fs.readFileSync(path.join(root,'ui/tutor-enhancements.js'),'utf8');
 assert.ok(script.includes("addEventListener('pointerdown'"));assert.ok(script.includes('requestAnimationFrame'));
 assert.ok(!script.includes('preventDefault'));assert.ok(!script.includes('stopPropagation'));assert.ok(!script.includes('setInterval'));
});
