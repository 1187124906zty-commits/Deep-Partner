import {defineConfig} from 'vite'
import {createRequire} from 'node:module'
import {cpSync,existsSync} from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import postcss from 'postcss'
import {adaptFollowupContext,adaptFollowupBody} from './scripts/followup-adapter.mjs'

const here=path.dirname(fileURLToPath(import.meta.url))
const tutor=path.resolve(process.env.DEEPTUTOR_WEB_SOURCE||path.join(here,'../../deeptutor-coder-integration/frontend/web'))
const workbench=path.resolve(process.env.WORKBENCH_WEB_SOURCE||path.join(here,'../web'))
if(!existsSync(path.join(tutor,'features/chat/components/ChatWorkspace.tsx')))throw new Error(`Set DEEPTUTOR_WEB_SOURCE to production DeepTutor frontend/web: ${tutor}`)
const require=createRequire(import.meta.url)
const canonicalTailwind=require(path.join(tutor,'tailwind.config.js'))
const tailwind=require('tailwindcss')
const autoprefixer=require('autoprefixer')

export default defineConfig({
  base:'./',
  resolve:{alias:[
    {find:'next/navigation',replacement:path.join(here,'src/host/navigation.ts')},
    {find:'next/link',replacement:path.join(here,'src/host/Link.tsx')},
    {find:'next/dynamic',replacement:path.join(here,'src/host/dynamic.tsx')},
    {find:'next/image',replacement:path.join(here,'src/host/Image.tsx')},
    {find:'@/features/capabilities/presentation',replacement:path.join(here,'src/host/capabilities.ts')},
    {find:'@/shared/auth/return-url',replacement:path.join(here,'src/host/auth-return.ts')},
    {find:'@/lib/space-items',replacement:path.join(here,'src/host/space-items.ts')},
    {find:'@/components/chat/home/ChatComposer',replacement:path.join(here,'src/host/ChatComposer.tsx')},
    {find:'@/components/workspaces/WorkspacePill',replacement:path.join(here,'src/host/WorkspacePill.tsx')},
    {find:'@/features/chat/transport/UnifiedTurnClient',replacement:path.join(here,'src/host/UnifiedTurnClient.ts')},
    {find:'@product',replacement:path.join(here,'src')}, {find:'@tutor',replacement:tutor}, {find:'@workbench',replacement:path.join(workbench,'src')}, {find:'@',replacement:tutor},
  ],dedupe:['cytoscape','react','react-dom','i18next','react-i18next','@tiptap/core','@tiptap/react','@tiptap/pm','@tiptap/starter-kit','prosemirror-model','prosemirror-state','prosemirror-view','prosemirror-transform','prosemirror-history','prosemirror-commands','prosemirror-keymap','prosemirror-schema-list','prosemirror-inputrules','prosemirror-dropcursor','prosemirror-gapcursor','prosemirror-tables','prosemirror-markdown','prosemirror-collab','prosemirror-schema-basic','prosemirror-changeset']},
  esbuild:{jsx:'automatic'},
  define:{'process.env.NEXT_PUBLIC_API_BASE':'""','process.env.NEXT_PUBLIC_AUTH_ENABLED':'"true"'},
  css:{postcss:{plugins:[tailwind({...canonicalTailwind,content:[path.join(tutor,'{app,components,features,shared}/**/*.{js,ts,jsx,tsx}'),path.join(here,'src/**/*.{ts,tsx}'),path.join(workbench,'src/**/*.{ts,tsx}')]}),autoprefixer()]}},
  plugins:[{
    name:'scope-existing-workbench-css',enforce:'pre',
    resolveId(source,importer){if(source==='./ModelSelector'&&importer?.replaceAll('\\','/').endsWith('/components/chat/home/ChatComposer.tsx'))return path.join(here,'src/host/ModelSelector.tsx');if(source==='./SettingsNav'&&importer?.replaceAll('\\','/').endsWith('/components/settings/SettingsMain.tsx'))return path.join(here,'src/host/NativeSettingsNav.tsx')},
    transform(code,id){
      if(id.replaceAll('\\','/').endsWith('/context/QuizFollowupContext.tsx'))return {code:adaptFollowupContext(code),map:null}
      if(id.replaceAll('\\','/').endsWith('/components/chat/home/SessionViewerPanel.tsx')){const anchor='<WebTabBody key={activeTab.url} url={activeTab.url} />';if(code.split(anchor).length!==2)throw new Error('Native web tab anchor changed');return {code:'import ProductWebPreview from "@product/host/WebPagePreview";\n'+code.replace(anchor,'<ProductWebPreview key={activeTab.url} url={activeTab.url} />'),map:null}}
      if(id.replaceAll('\\','/').endsWith('/features/chat/components/ChatWorkspace.tsx')){
        const anchor='  const cancelSessionTitleEdit = useCallback(() => {'
        if(code.split(anchor).length!==2)throw new Error('Native ChatWorkspace Dito bridge anchor changed')
        const preview=String.raw`    if (!/^https?:\/\//i.test(href)) return;
    event.preventDefault();
    viewerPanelRef.current?.openWebTab(href);`
        if(code.replaceAll('\r\n','\n').split(preview).length!==2)throw new Error('Native conversation link-preview slot changed')
        code=code.replaceAll('\r\n','\n').replace(preview,"    const targetPreview=messagePreview(href,location.origin);if(!targetPreview)return;event.preventDefault();if(targetPreview.kind==='file')viewerPanelRef.current?.openFileTab(targetPreview.attachment);else viewerPanelRef.current?.openWebTab(targetPreview.url);")
        return {code:'import {messagePreview} from "@product/host/message-preview";\nimport {useNativeDitoBridge} from "@product/host/DitoTasks";\n'+code.replace(anchor,'  useNativeDitoBridge(viewerPanelRef);\n'+anchor),map:null}
      }
      if(id.replaceAll('\\','/').endsWith('/components/quiz/QuizFollowupTabBody.tsx')){
        code=adaptFollowupBody(code)
        code=code.replace('sideChat.parentSessionId ? (','false ? (')
        const hint='              <p className="px-1 text-[12px] leading-[1.6] text-[var(--muted-foreground)]">'
        const start=code.indexOf(hint),end=code.indexOf('</p>',start)
        if(start<0||end<0)throw new Error('Dito empty helper text boundary changed')
        return {code:code.slice(0,start)+'              <span />'+code.slice(end+4),map:null}
      }
      if(id.replaceAll('\\','/').endsWith('/features/chat/ChatStateAdapter.tsx')){
        const start=code.indexOf('  const newSession = useCallback('),end=code.indexOf('  const configureSession = useCallback(',start)
        if(start<0||end<0)throw new Error('Explicit new-session boundary changed')
        const segment=code.slice(start,end).replace(/      dispatch\(\{\s*type: "ENSURE_DRAFT_SESSION",[\s\S]*?      \}\);/,'')
        if(segment===code.slice(start,end))throw new Error('New-session recovery seam changed')
        return {code:code.slice(0,start)+segment+code.slice(end),map:null}
      }
      if(id.replaceAll('\\','/').endsWith('/components/quiz/FollowupChatComposer.tsx')){
        code=code.replaceAll('\r\n','\n')
        const anchor='  return (\n    <StandaloneComposer',seed='seedAttachments={seedAttachments}'
        if(code.split(anchor).length!==2||code.split(seed).length!==2)throw new Error('Native Dito composer task slot changed')
        const submit='onSubmit={handleSubmit}'
        if(code.split(submit).length!==2)throw new Error('Native Dito submit slot changed')
        code=code.replace('const { t } = useTranslation();','const { t, i18n } = useTranslation();').replace('        language: context.language,','        language: config.partner_mode==="research" ? (i18n.resolvedLanguage||i18n.language) : context.language,').replace('      context,\n      controller,','      context,\n      i18n.resolvedLanguage,\n      i18n.language,\n      controller,')
        const config='      const config: Record<string, unknown> = { ...baseConfig };'
        if(code.split(config).length!==2)throw new Error('Native Dito turn configuration slot changed')
        return {code:'import {useProductDitoComposer} from "@product/host/DitoTasks";\n'+code.replace(config,'      const config: Record<string, unknown> = { ...baseConfig, ...submission.config };').replace(anchor,'  const productTask=useProductDitoComposer(context);\n'+anchor+'\n      inputHeader={productTask.header}\n      prefillInputRef={productTask.prefillInputRef}').replace('inputPlaceholder={followupPlaceholder(context, t)}',"inputPlaceholder={productTask.researchContext?'继续当前研究任务…':followupPlaceholder(context, t)}").replace(seed,'seedAttachments={productTask.active?productTask.seedAttachments:seedAttachments}').replace(submit,'onSubmit={submission=>void productTask.submit(submission,handleSubmit)}'),map:null}
      }
      if(id.replaceAll('\\','/').startsWith(workbench.replaceAll('\\','/')+'/src/')&&id.endsWith('.tsx')&&/<select[\s>]/.test(code))return {code:'import ThemeSelect from "@product/ThemeSelect";\n'+code.replace(/<select(?=[\s>])/g,'<ThemeSelect').replace(/<\/select>/g,'</ThemeSelect>'),map:null}
      if(id.replaceAll('\\','/').endsWith('/features/chat/messages/ChatMessageList.tsx')){
        const body='<div className="whitespace-pre-wrap">{msg.content}</div>'
        const row='<div key={`${msg.role}-${index}`} className="group flex justify-end">'
        if(code.split(body).length!==2||code.split(row).length!==2)throw new Error('Production UserMessage body changed; review the finite workbench message display adapter before building.')
        return {code:'import WorkbenchMessageBody from "@product/host/WorkbenchMessageBody";\nimport ChatAttachmentPreviews from "@product/host/ChatAttachmentPreviews";\n'+code.replace(body,'<><ChatAttachmentPreviews attachments={msg.attachments} onOpen={onPreviewAttachment}/><WorkbenchMessageBody content={msg.content} /></>').replace(row,'<div key={`${msg.role}-${index}`} data-product-user-message="true" className="group flex min-w-0 max-w-full justify-end">'),map:null}
      }
      const locale=id.replaceAll('\\','/').match(/\/locales\/(en|zh)\/app\.json$/)?.[1]
      if(locale){const messages=JSON.parse(code);messages['What would you like to learn?']=locale==='zh'?'今天想推进哪项研究？':'What would you like to explore?';return {code:JSON.stringify(messages),map:null}}
      if(id.replaceAll('\\','/').endsWith('/components/chat/home/StarterSuggestions.tsx'))return {code:code.replace('{ id: "practice", icon: PracticeMark },',''),map:null}
      if(!id.replaceAll('\\','/').startsWith(workbench.replaceAll('\\','/')+'/src/')||!id.endsWith('.css'))return
      const tree=postcss.parse(code)
      tree.walkRules(rule=>{
        if(rule.parent?.type==='atrule'&&/keyframes$/.test(rule.parent.name))return
        const scoped=rule.selectors.filter(s=>!/^(:root|html|body|#root)$/.test(s.trim())).map(s=>`.dp-artifacts ${s}`)
        if(!scoped.length)rule.remove()
        else rule.selectors=scoped
      })
      return {code:tree.toString(),map:null}
    },
    closeBundle(){const out=path.join(here,'dist');if(existsSync(path.join(tutor,'public')))cpSync(path.join(tutor,'public'),out,{recursive:true});if(existsSync(path.join(here,'public')))cpSync(path.join(here,'public'),out,{recursive:true})},
  }],
  server:{fs:{allow:[here,tutor,workbench]},proxy:{'/api':'http://127.0.0.1:8008','/ws':{target:'ws://127.0.0.1:8008',ws:true},'/research/api':'http://127.0.0.1:47900'}},
  build:{outDir:'dist',emptyOutDir:true,sourcemap:false,chunkSizeWarningLimit:1500},
  test:{environment:'jsdom',server:{deps:{inline:[/@radix-ui/,/@tanstack/,/@assistant-ui/] }},include:['src/**/*.test.{ts,tsx}']},
})
