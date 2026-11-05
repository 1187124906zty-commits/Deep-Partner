import ts from 'typescript'
import path from 'node:path'
import fs from 'node:fs'
import {fileURLToPath} from 'node:url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const tutor=path.resolve(process.env.DEEPTUTOR_WEB_SOURCE||path.join(root,'../../deeptutor-coder-integration/frontend/web'))
const wb=path.resolve(process.env.WORKBENCH_WEB_SOURCE||path.join(root,'../web'))
const config={compilerOptions:{target:'ES2022',lib:['ESNext','DOM','DOM.Iterable'],module:'ESNext',moduleResolution:'Bundler',jsx:'react-jsx',strict:true,skipLibCheck:true,resolveJsonModule:true,esModuleInterop:true,allowSyntheticDefaultImports:true,noEmit:true,baseUrl:root,types:['vite/client','node'],paths:{'react':[root+'/node_modules/@types/react/index.d.ts'],'react/*':[root+'/node_modules/@types/react/*'],'react-dom':[root+'/node_modules/@types/react-dom/index.d.ts'],'react-dom/*':[root+'/node_modules/@types/react-dom/*'],'@/*':[tutor+'/*'],'@tutor/*':[tutor+'/*'],'@workbench/*':[wb+'/src/*'],'@tiptap/*':[root+'/node_modules/@tiptap/*'],'prosemirror-*':[root+'/node_modules/prosemirror-*'],'next/navigation':['src/host/navigation.ts'],'next/link':['src/host/Link.tsx'],'next/dynamic':['src/host/dynamic.tsx'],'next/image':['src/host/Image.tsx']}},include:['src',tutor+'/types/**/*.d.ts',tutor+'/components/common/*.d.ts',wb+'/src/**/*.d.ts']}
const parsed=ts.parseJsonConfigFileContent(config,ts.sys,root)
const program=ts.createProgram(parsed.fileNames,parsed.options)
const all=ts.getPreEmitDiagnostics(program)
const edited=new Set(['App.tsx','TaskCenter.tsx','Review.tsx','ReviewWorkspace.tsx','Questions.tsx','EmbeddedHost.tsx','api.ts','FigureCanvas.tsx','StageQuality.tsx'].map(f=>path.normalize(path.join(wb,'src',f))))
const owned=all.filter(d=>!d.file||d.file.fileName.startsWith(path.join(root,'src'))||edited.has(path.normalize(d.file.fileName)))
const upstream=all.filter(d=>!owned.includes(d))
const host={getCanonicalFileName:f=>f,getCurrentDirectory:()=>root,getNewLine:()=> '\n'}
if(owned.length)process.stderr.write(ts.formatDiagnosticsWithColorAndContext(owned,host))
fs.writeFileSync(path.join(root,'upstream-type-diagnostics.txt'),ts.formatDiagnostics(upstream,host))
if(upstream.length)process.stdout.write(`Source dependency diagnostics retained in upstream-type-diagnostics.txt (${upstream.length}); these must be resolved before delivery.\n`)
process.stdout.write(`Checked ${parsed.fileNames.length} unified source files and edited Workbench boundaries: ${owned.length} errors.\n`)
process.exitCode=all.length?1:0
