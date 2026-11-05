/** Author order and names are taken from the source metadata, never expanded by guess. */
export function AuthorNames({names=[]}:{names?:string[]}){
 return <span className="author-names">{names.length?names.map((name,i)=><span key={i}>{name.includes(',')?name.split(',').slice(1).join(',').trim()+' '+name.split(',')[0].trim():name}</span>):<span>—</span>}</span>
}
