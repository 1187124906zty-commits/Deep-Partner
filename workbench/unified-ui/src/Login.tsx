import {useState} from 'react'
import {BookOpen} from 'lucide-react'
import {login} from '@/lib/auth'
import Button from '@/shared/ui/Button'
export default function Login({onSuccess}:{onSuccess:()=>Promise<void>}){
 const [username,setUsername]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const submit=async()=>{if(!username.trim()||!password||busy)return;setBusy(true);setError('');try{const result=await login(username.trim(),password);if(!result.ok)throw new Error(result.error||'登录未完成');setPassword('');await onSuccess()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <main className="dp-login"><div className="dp-brand"><BookOpen size={27} strokeWidth={1.5}/><span>DeepPartner</span></div><h1>登录研究空间</h1><p>使用已有账户继续项目、会话与审查。</p><form onSubmit={e=>{e.preventDefault();void submit()}}><label className="dp-field">邮箱或用户名<input autoFocus autoComplete="username" required value={username} onChange={e=>setUsername(e.target.value)}/></label><label className="dp-field">密码<input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/></label>{error&&<p role="alert" className="dp-login-error">{error}</p>}<Button type="submit" loading={busy} disabled={!username.trim()||!password}>登录</Button></form></main>
}
