import {createContext,useContext} from 'react'
import OriginalSettingsNav from '@tutor/components/settings/SettingsNav'
import {LogOut,Terminal} from 'lucide-react'
import {navigate,useSearchParams} from './navigation'
import type {DesktopStatus,Manifest} from '../services'
export const ProductSettingsContext=createContext<{user:any;desktop:DesktopStatus|null;manifest:Manifest|null;onLogout:()=>void}|null>(null)
export default function NativeSettingsNav(props:Parameters<typeof OriginalSettingsNav>[0]){
 const context=useContext(ProductSettingsContext),query=useSearchParams()
 return <><OriginalSettingsNav {...props}/>{context&&<div className="shrink-0 border-t border-[var(--border)] p-3 text-[13px]">{context.desktop&&<button aria-current={query.get('settings_section')==='local-tools'?'page':undefined} onClick={()=>{navigate('/settings/local-tools');props.onNavigate?.()}} className="flex min-h-9 w-full items-center gap-2 rounded-lg px-2.5 py-2 hover:bg-[var(--accent)]"><Terminal size={15}/>本机工具</button>}<button onClick={context.onLogout} className="flex min-h-9 w-full items-center gap-2 rounded-lg px-2.5 py-2 text-[var(--muted-foreground)] hover:bg-[var(--accent)]"><LogOut size={15}/>退出登录<span className="ml-auto truncate text-xs">{context.user?.username||''}</span></button><p className="px-2.5 pt-2 text-[11px] text-[var(--muted-foreground)]">DeepPartner 0.4.2{context.desktop?' · 桌面 '+context.desktop.version:''}</p></div>}</>
}
