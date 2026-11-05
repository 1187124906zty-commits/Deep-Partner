import {useEffect} from 'react'
import SettingsLayout from '@tutor/app/(settings)/settings/layout'
import SettingsPageContent from '@/components/settings/SettingsPageContent'
import LearningProgressPage from '@tutor/app/(utility)/settings/progress/page'
import {CapabilityAccessProvider} from '@/components/access/CapabilityAccessContext'
import {SETTINGS_RETURN_KEY} from '@/components/settings/SettingsReturnTracker'
import {useSearchParams,entryPath} from './host/navigation'
import {ProductSettingsContext} from './host/NativeSettingsNav'
import type {DesktopStatus,Manifest} from './services'
import NativeTools from './NativeTools'
import DesktopPreferenceSync from './host/DesktopPreferenceSync'

export default function Settings({open,user,desktop,manifest,onLogout}:{open:boolean;onClose:()=>void;user:any;desktop:DesktopStatus|null;manifest:Manifest|null;onLogout:()=>void}){
 const query=useSearchParams(),section=query.get('settings_section')||'general'
 useEffect(()=>{if(!open)return;try{if(!sessionStorage.getItem(SETTINGS_RETURN_KEY)){const next=new URLSearchParams(location.search);next.delete('surface');next.delete('settings_section');sessionStorage.setItem(SETTINGS_RETURN_KEY,entryPath+'?'+next)}}catch{}},[open])
 return <><DesktopPreferenceSync enabled={!!desktop}/>{open&&<div className="dp-tutor-settings"><ProductSettingsContext.Provider value={{user,desktop,manifest,onLogout}}><CapabilityAccessProvider><SettingsLayout>{section==='local-tools'&&desktop?<div data-settings-page="local-tools" className="py-8"><NativeTools status={desktop}/></div>:section==='progress'?<LearningProgressPage/>:<SettingsPageContent section={section}/>}</SettingsLayout></CapabilityAccessProvider></ProductSettingsContext.Provider></div>}</>
}
