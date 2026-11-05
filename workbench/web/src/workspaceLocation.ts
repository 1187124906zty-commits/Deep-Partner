/** An explicit project link must never open unrelated account content. */
export function initialProject<T extends {id:string;config?:{link_aliases?:string[]}}>(rows:T[],requested:string|null,remembered:string|null):{project:T|null;unavailable:boolean}{
 if(requested){
  const project=rows.find(row=>row.id===requested)||rows.find(row=>row.config?.link_aliases?.includes(requested))||null
  return {project,unavailable:!project}
 }
 return {project:rows.find(row=>row.id===remembered)||rows[0]||null,unavailable:false}
}

export function imageLocation(url:string):{image:string;directory:string}{
 const path=new URL(url).searchParams.get('file')||''
 if(path.startsWith('/')||path.includes('\\')||path.split('/').some(part=>part==='..'||!part)||!/\.(png|jpe?g|webp|gif)$/i.test(path))return {image:'',directory:''}
 return {image:path,directory:path.split('/').slice(0,-1).join('/')}
}
