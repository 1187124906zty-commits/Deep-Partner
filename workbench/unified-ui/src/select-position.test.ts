import {expect,it} from 'vitest'
import {selectPosition} from './host/select-position'
it('keeps a small trigger near the right edge within the viewport',()=>{
 const p=selectPosition({left:350,top:60,bottom:92,width:25},{width:390,height:844})
 expect(p.left+p.width).toBeLessThanOrEqual(382)
 expect(p.width).toBe(180)
})
it('opens above a bottom toolbar with enough room for the list',()=>{
 const p=selectPosition({left:20,top:790,bottom:826,width:200},{width:390,height:844})
 expect(p.top+p.maxHeight).toBeLessThan(790)
 expect(p.maxHeight).toBe(320)
})
