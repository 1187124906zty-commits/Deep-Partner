import React from 'react'
import {createRoot} from 'react-dom/client'
import {AppShellProvider} from '@/context/AppShellContext'
import {I18nClientBridge} from '@/i18n/I18nClientBridge'
import MotionProvider from '@/components/common/MotionProvider'
import ToastViewport from '@/components/common/ToastViewport'
import {applyUiLayoutToDocument,readStoredUiLayout} from '@/lib/ui-layout'
import {applyThemeToDocument,type Theme} from '@/lib/theme'
import {restoreDesktopPreferences} from './desktop-preferences'
import App from './App'
import '@/app/globals.css'
import '@/features/ui-layout/classic/classic.css'
import '@/features/ui-layout/modern/modern.css'
import './fonts.css'
import '@workbench/style.css'
import '@workbench/tutor-ui.css'
import '@workbench/figure-canvas.css'
import '@workbench/workspace-refinement.css'
import '@workbench/authoring.css'
import '@workbench/dito-workspace.css'
import '@workbench/figure-studio.css'
import '@workbench/usability.css'
import '@workbench/workbench-design.css'
import './product.css'
import './workspace.css'
import './interaction-system.css'

class ProductErrorBoundary extends React.Component<{children:React.ReactNode},{error:Error|null}>{state={error:null as Error|null};static getDerivedStateFromError(error:Error){return{error}};render(){return this.state.error?<main className="dp-start"><h1>页面未能完整打开</h1><p role="alert">{this.state.error.message}</p><button onClick={()=>location.reload()}>重新载入</button></main>:this.props.children}}
async function bootstrap(){
 await restoreDesktopPreferences()
 applyUiLayoutToDocument(readStoredUiLayout())
 try{if(!['light','dark','snow','glass'].includes(localStorage.getItem('deeptutor-theme')||''))localStorage.setItem('deeptutor-theme',matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');applyThemeToDocument(localStorage.getItem('deeptutor-theme') as Theme)}catch{}
 try{if(!localStorage.getItem('deeptutor-language'))localStorage.setItem('deeptutor-language','zh')}catch{}
 document.documentElement.dataset.deeppartnerHost='true'
 createRoot(document.getElementById('root')!).render(<ProductErrorBoundary><AppShellProvider><MotionProvider><I18nClientBridge><App/></I18nClientBridge><ToastViewport/></MotionProvider></AppShellProvider></ProductErrorBoundary>)
}
void bootstrap()
