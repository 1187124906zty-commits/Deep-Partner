import {lazy,Suspense,type ComponentType,type ReactNode} from 'react'
export default function dynamic<P=any>(loader:(()=>Promise<{default:ComponentType<P>}|ComponentType<P>>)|{loader:()=>Promise<{default:ComponentType<P>}>},options:{ssr?:boolean;loading?:ComponentType<any>}={}){
  const load=typeof loader==='function'?loader:loader.loader
  const Loaded=lazy(async()=>{const result=await load();return {default:result&&typeof result==='object'&&'default' in result?result.default:result} as {default:ComponentType<any>}})
  const Fallback=options.loading
  function DynamicComponent(props:P){return <Suspense fallback={Fallback?<Fallback/>:null}><Loaded {...props as any}/></Suspense>}
  return DynamicComponent as ComponentType<P>
}
