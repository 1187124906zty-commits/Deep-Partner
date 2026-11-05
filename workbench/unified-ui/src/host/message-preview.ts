/** File links and ordinary web sources reuse the native conversation viewer. */
export function messagePreview(href:string,origin:string){
 if(!href||href.startsWith('#'))return null
 let url:URL;try{url=new URL(href,origin)}catch{return null}
 if(!['http:','https:'].includes(url.protocol))return null
 const name=url.searchParams.get('filename')||url.searchParams.get('path')?.split('/').pop()||decodeURIComponent(url.pathname.split('/').pop()||'')
 const file=/\.(pdf|docx?|xlsx?|pptx?|csv|tsv|md|txt|py|m|r|json|ya?ml|svg|png|jpe?g|webp|gif|html)$/i.test(name)||url.origin===origin&&/^\/(?:api|research\/api)\/.+\/(?:file|download|exports?)(?:\/|$)/.test(url.pathname)
 if(file)return {kind:'file' as const,attachment:{type:'file',filename:name||'会话文件',url:url.href}}
 if(url.origin!==origin||/^https?:\/\//i.test(href))return {kind:'web' as const,url:url.href}
 return null
}
