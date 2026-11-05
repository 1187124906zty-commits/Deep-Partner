import {useEffect,useState} from 'react'
import {Check,Search,ArrowUpRight} from 'lucide-react'
import {api,jsonBody} from './api'

const empty={name:'',name_en:'',affiliation:'',affiliation_en:'',email:'',orcid:'',address:''}
export function AuthorProfile({onError,onSaved}:{onError:(e:unknown)=>void;onSaved?:()=>void}){
 const [value,setValue]=useState(empty),[busy,setBusy]=useState(false),[saved,setSaved]=useState(false),[institutions,setInstitutions]=useState<any>(),[checking,setChecking]=useState(false)
 useEffect(()=>{void api('/author-profile').then(r=>setValue({...empty,...r})).catch(onError)},[])
 const save=async()=>{setBusy(true);try{await api('/author-profile',jsonBody(value,'PUT'));setSaved(true);onSaved?.()}catch(e){onError(e)}finally{setBusy(false)}}
 const lookup=async()=>{setChecking(true);try{setInstitutions(await api('/author-profile/institutions?q='+encodeURIComponent(value.affiliation||value.affiliation_en)))}catch(e){onError(e)}finally{setChecking(false)}}
 const field=(key:keyof typeof empty,label:string,placeholder='')=><label key={key}>{label}<input aria-label={'作者资料 · '+label} type={key==='email'?'email':'text'} value={value[key]} placeholder={placeholder} onChange={e=>{setValue({...value,[key]:e.target.value});setSaved(false)}}/></label>
 return <fieldset className="settings-section author-profile"><legend>作者资料</legend><p>保存作者署名、单位和联系信息，用于稿件预览。原稿已有的作者信息会保留。</p><div className="author-profile-grid">{field('name','中文姓名')}{field('name_en','英文姓名')}{field('affiliation','中文单位','学院、学校或研究机构')}{field('affiliation_en','英文单位')}{field('email','联系邮箱')}{field('orcid','ORCID','0000-0000-0000-0000')}{field('address','通讯地址')}</div><div className="author-profile-actions"><button disabled={checking||!(value.affiliation||value.affiliation_en)} onClick={()=>void lookup()}><Search size={13}/>{checking?'正在核对…':'联网核对单位'}</button><button className="primary" disabled={busy} onClick={()=>void save()}><Check size={13}/>{saved?'资料已保存':busy?'正在保存…':'保存作者资料'}</button></div>{institutions&&<div className="institution-results"><small>{institutions.status==='ready'?'ROR 机构名录 · 可核对官方名称':institutions.message||'未查到机构，请保留所填信息'}</small>{institutions.items?.map((v:any)=><a key={v.id} href={v.source} target="_blank" rel="noreferrer">{v.names.slice(0,3).join(' / ')}<ArrowUpRight size={11}/></a>)}</div>}</fieldset>
}
