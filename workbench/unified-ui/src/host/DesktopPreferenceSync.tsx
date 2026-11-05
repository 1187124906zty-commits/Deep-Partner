import {useEffect} from 'react'
import {useAppShell} from '@/context/AppShellContext'
import {LANGUAGE_EVENT,RESPONSE_LANGUAGE_EVENT,CODE_BLOCK_SETTINGS_EVENT,readStoredResponseLanguage,readStoredCodeBlockTheme,readStoredCodeBlockShowLineNumbers,readStoredCodeBlockWrapLongLines} from '@/context/app-shell-storage'
import {readStoredUiLayout,UI_LAYOUT_EVENT} from '@/lib/ui-layout'
import {persistDesktopPreferences,type DesktopPreferences} from '../desktop-preferences'
import {notify} from '@/lib/notifications'
export default function DesktopPreferenceSync({enabled}:{enabled:boolean}){
 const {theme,language}=useAppShell()
 useEffect(()=>{if(!enabled)return;let timer:ReturnType<typeof setTimeout>;const save=()=>{clearTimeout(timer);timer=setTimeout(()=>{const value:DesktopPreferences={theme,language,response_language:readStoredResponseLanguage(),code_block_theme:readStoredCodeBlockTheme(),code_block_show_line_numbers:readStoredCodeBlockShowLineNumbers(),code_block_wrap_long_lines:readStoredCodeBlockWrapLongLines(),ui_layout:readStoredUiLayout()};void persistDesktopPreferences(value).catch(e=>notify(e.message,{tone:'error'}))},100)};save();const events=[LANGUAGE_EVENT,RESPONSE_LANGUAGE_EVENT,CODE_BLOCK_SETTINGS_EVENT,UI_LAYOUT_EVENT];events.forEach(name=>window.addEventListener(name,save));return()=>{clearTimeout(timer);events.forEach(name=>window.removeEventListener(name,save))}},[enabled,theme,language])
 return null
}
