"""Stage a single-file author preview that reuses the product canvas component."""
from pathlib import Path
import argparse,json,tarfile
from build_unified_ui import ROOT,REMOTE,scp
SOURCE=Path('D:/Development/research-workbench')

folder=ROOT/'.local/paper-map-preview';folder.mkdir(exist_ok=True)
parser=argparse.ArgumentParser()
parser.add_argument('--map',type=Path,default=ROOT/'reports/氯硫框架具体化/paper-maps-20261104/qin2020/key-canvas-candidate.json')
parser.add_argument('--title',default='Qin关键论证画布试读')
parser.add_argument('--source-pdf',help='Optional PDF URL or relative filename for the standalone preview')
parser.add_argument('--strip-intro-navigation',action='store_true')
args=parser.parse_args()
graph=json.loads(args.map.read_text(encoding='utf8'))
if args.strip_intro_navigation:
    graph['nodes']=[n for n in graph['nodes'] if n['id']!='sec.s0002']
    for n in graph['nodes']:
        if n['parent_id']=='sec.s0002':n['parent_id']='paper'
(folder/'map.json').write_text(json.dumps(graph,ensure_ascii=False),encoding='utf8')
(folder/'package.json').write_text(json.dumps({'type':'module'}),encoding='utf8')
(folder/'tsconfig.json').write_text(json.dumps({'compilerOptions':{'jsx':'react-jsx','target':'ES2022','module':'ESNext','moduleResolution':'Bundler'}}),encoding='utf8')
entry="""import React from 'react';
import {createRoot} from 'react-dom/client';
import {PaperContentMap} from './components/PaperContentMap.tsx';
import map from './map.json';
const originalFetch=window.fetch.bind(window);
window.fetch=async(input,init)=>String(input).includes('/literature/content-map')?new Response(JSON.stringify({status:'needs_review',map}),{headers:{'Content-Type':'application/json'}}):originalFetch(input,init);
const project={id:'author-preview',name:'Qin关键论证画布试读',native_id:'',root:'',config:{}};
const message=text=>{const target=document.querySelector('#message');if(target)target.textContent=text};
createRoot(document.querySelector('#root')).render(<PaperContentMap project={project} asset={map.source.asset} title={map.source.title} onBack={()=>message('此页是引言画布试读候选，可直接点击词组查看原文句子。')} onSource={locator=>{window.open('https://tutor.example.invalid/research/api/projects/1ea03384007d4bb9b88d43e3368099f3/literature/file?asset='+encodeURIComponent(map.source.asset)+'&library=workspace#page='+locator.page,'_blank')}} onError={error=>message(String(error))} notify={message}/>);

"""
entry=entry.replace("name:'Qin关键论证画布试读'",'name:'+json.dumps(args.title,ensure_ascii=False))
entry=entry.replace('此页是引言画布试读候选，可直接点击词组查看原文句子。','此页是论文内容图谱试读，可直接点击节点查看原文句子。')
if args.source_pdf:
    start=entry.index('onSource={locator=>{window.open(')
    end=entry.index(' onError=',start)
    entry=entry[:start]+"onSource={locator=>{window.open("+json.dumps(args.source_pdf,ensure_ascii=False)+"+'#page='+locator.page,'_blank')}}"+entry[end:]
(folder/'entry.tsx').write_text(entry,encoding='utf8')
builder=r"""import esbuild from 'ROOT/src/web/node_modules/esbuild/lib/main.js';
import fs from 'node:fs';
const dir='ROOT/tmp/paper-map-preview',out=dir+'/out';fs.mkdirSync(out,{recursive:true});
await esbuild.build({entryPoints:[dir+'/entry.tsx'],bundle:true,format:'iife',platform:'browser',target:'es2022',jsx:'automatic',minify:true,outfile:out+'/review.js',resolveExtensions:['.ts','.tsx','.js','.json','.css'],nodePaths:['ROOT/src/web/node_modules','ROOT/src/unified-ui/node_modules'],define:{'process.env.NODE_ENV':'"production"'}});
const script=fs.readFileSync(out+'/review.js','utf8').replaceAll('</script','<\\/script'),css=fs.readFileSync(out+'/review.css','utf8');
const page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Qin引言内容思维导图 · 作者试读</title><style>:root{--foreground:#202a25;--muted-foreground:#65746b;--card:#fff;--border:#d9e1db;--secondary:#f3f6f1;--primary:#146b50;--destructive:#b13d3d;font-family:"Microsoft YaHei UI","PingFang SC",sans-serif;color:var(--foreground);font-size:14px;line-height:1.6}*{box-sizing:border-box}body{margin:0}button,input,select{font:inherit;color:inherit}button{background:none;border:0;cursor:pointer}button:disabled{cursor:default}#message{height:47px;background:#edf5ec;border-bottom:1px solid #d9e1db;padding:12px 20px;font-size:13px}#root{height:100vh}.toolbar-spacer{flex:1}.icon-button{display:inline-flex;align-items:center;justify-content:center;border:1px solid transparent;border-radius:5px}.icon-button:hover{background:var(--secondary)}.content-map-status>button{display:none}'+css+'</style><div id="root"></div><script>'+script+'</script></html>';
fs.writeFileSync('ROOT/artifacts/paper-map-review.html',page);console.log('PAPER_MAP_REVIEW_BUILT',page.length);
""".replace('ROOT',REMOTE)
builder=builder.replace('.content-map-status>button{display:none}', '.content-map-status>button{display:none!important}').replace('--foreground:#202a25;','--foreground:#202a25;--background:#fbfcf9;').replace('本页仅展示Qin论文引言','本页精选Qin论文的关键论证节点').replace('Qin引言内容思维导图','Qin关键论证思维导图')
builder=builder.replace('Qin关键论证思维导图 · 作者试读',args.title.replace('<','&lt;').replace('>','&gt;'))
(folder/'build.mjs').write_text(builder,encoding='utf8')
archive=folder/'preview.tar.gz'
with tarfile.open(archive,'w:gz') as bundle:
    for name in ['map.json','entry.tsx','build.mjs','package.json','tsconfig.json']:bundle.add(folder/name,arcname=name)
    for name in ['PaperContentMap.tsx','paperContentMap.ts','paper-content-map.css','api.ts','ui.tsx','paper-content-map.test.tsx','paper-content-map-data.test.ts']:
        bundle.add(SOURCE/'web/src'/name,arcname='components/'+name)
scp(archive,REMOTE+'/paper-map-review-source.tar.gz')
print('Author preview source staged')
