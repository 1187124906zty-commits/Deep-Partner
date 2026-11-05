import {forwardRef,type AnchorHTMLAttributes} from 'react'
import {navigate,toHostHref} from './navigation'
type Props=Omit<AnchorHTMLAttributes<HTMLAnchorElement>,'href'>&{href:string|{pathname?:string;query?:Record<string,string>};prefetch?:boolean;replace?:boolean;scroll?:boolean}
export default forwardRef<HTMLAnchorElement,Props>(function Link({href,prefetch,replace,scroll,onClick,children,...props},ref){
  const raw=typeof href==='string'?href:(href.pathname||'')+(href.query?'?'+new URLSearchParams(href.query):'')
  const resolved=toHostHref(raw)
  return <a {...props} ref={ref} href={resolved} onClick={event=>{onClick?.(event);if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey||props.target==='_blank'||props.download)return;const url=new URL(resolved,location.href);if(url.origin===location.origin&&(/\?(?:.*&)?(?:session|project|surface)=/.test(url.search)||url.pathname===location.pathname)){event.preventDefault();navigate(raw,replace)}}}>{children}</a>
})
