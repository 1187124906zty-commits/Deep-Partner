import {forwardRef,type ImgHTMLAttributes} from 'react'
type Props=Omit<ImgHTMLAttributes<HTMLImageElement>,'src'>&{src:string|{src:string};fill?:boolean;priority?:boolean;unoptimized?:boolean;quality?:number;placeholder?:string;blurDataURL?:string;loader?:unknown}
export default forwardRef<HTMLImageElement,Props>(function Image({src,fill,priority,unoptimized,quality,placeholder,blurDataURL,loader,style,...props},ref){
 const value=typeof src==='string'?src:src.src
 const brand=/^\/brand\/(color-logo|color-word|white-word|white-logo)\.png$/.test(value)
 if(brand&&value.includes('word'))return <span className={(props.className||'')+' dp-product-wordmark'} style={{fontFamily:'var(--font-sans),sans-serif',fontSize:16,fontWeight:650,letterSpacing:'-.5px',color:'var(--foreground)'}}>DeepPartner</span>
 if(brand)return <span role="img" aria-label="DeepPartner" style={{display:'inline-grid',placeItems:'center',width:22,height:22,borderRadius:6,background:'var(--primary)',color:'var(--primary-foreground)',fontSize:13,fontWeight:650}}>D</span>
 return <img {...props} ref={ref} src={value} loading={priority?'eager':props.loading||'lazy'} style={fill?{position:'absolute',inset:0,width:'100%',height:'100%',...style}:style}/>
})
