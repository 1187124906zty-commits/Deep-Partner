import {useEffect} from 'react'
import {navigate,toHostHref} from './navigation'
/** Existing business views use plain anchors too. Rewrite their session URLs
 * so normal clicks, keyboard navigation and new tabs share one product root. */
export function UnifiedLinks(){useEffect(()=>{
 const rewrite=(root:ParentNode)=>{root.querySelectorAll<HTMLAnchorElement>('a[href]').forEach(anchor=>{const url=new URL(anchor.href,location.href);if(url.origin===location.origin&&/^\/chat(?:\/|$)/.test(url.pathname)){anchor.dataset.unifiedSession='true';anchor.href=toHostHref(url.pathname+url.search+url.hash)}})}
 rewrite(document.body)
 const observer=new MutationObserver(records=>{for(const record of records){if(record.type==='attributes'){const anchor=record.target as HTMLAnchorElement;if(anchor.tagName==='A')rewrite(anchor.parentElement||document.body)}else for(const node of record.addedNodes)if(node instanceof Element)rewrite(node.parentElement||node)}})
 observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['href']})
 const click=(event:MouseEvent)=>{const anchor=(event.target as Element).closest?.('a[data-unified-session]') as HTMLAnchorElement|null;if(!anchor||event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();event.stopImmediatePropagation();navigate(anchor.href)}
 document.addEventListener('click',click,true)
 return()=>{observer.disconnect();document.removeEventListener('click',click,true)}
},[]);return null}
