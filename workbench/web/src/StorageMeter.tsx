import {useEffect,useState} from 'react'
import {HardDrive} from 'lucide-react'
import {api,prettySize} from './api'

export function StorageMeter({compact=false}:{compact?:boolean}){
 const [value,setValue]=useState<any>();useEffect(()=>{const load=()=>void api('/storage').then(setValue).catch(()=>{});load();const timer=setInterval(load,30000);window.addEventListener('workbench:artifact-updated',load);return()=>{clearInterval(timer);window.removeEventListener('workbench:artifact-updated',load)}},[])
 return value?<details className={'storage-meter'+(compact?' compact':'')}><summary><HardDrive size={14}/><span>{prettySize(value.used)} / 2 GiB</span><i><b style={{width:Math.min(100,value.used/value.quota*100)+'%'}}/></i></summary><div className="storage-breakdown"><strong>我的工作台空间</strong>{value.categories.map((c:any)=><div key={c.id}><span>{c.label}</span><span>{prettySize(c.bytes)}</span></div>)}{value.cache_used>0&&<div><span>系统可再生成缓存</span><span>{prettySize(value.cache_used)} · 不计额度</span></div>}<small>所有项目共用 2 GiB，原文、译文和历史版本计入占用；系统预览与阅读缓存由服务管理。</small></div></details>:null
}
