/** A completed translation can arrive while the author is typing. */
export function mergeTranslationUpdate<T extends {revision:number;title:string;template:string;content:unknown;comments:unknown;references?:unknown;translation?:unknown}>(base:T,local:T,remote:T):T|null{
 const same=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b)
 const source=(d:T)=>({title:d.title,template:d.template,content:d.content,comments:d.comments,references:d.references})
 if(!same(source(base),source(remote)))return null
 const editedTranslation=!same(base.translation,local.translation)
 if(editedTranslation&&!same(base.translation,remote.translation))return null
 return {...local,revision:remote.revision,translation:editedTranslation?local.translation:remote.translation}
}
