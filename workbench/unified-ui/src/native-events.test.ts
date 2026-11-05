import {describe,it,expect} from 'vitest'
import {nativeEventText} from './native-events'
describe('native CLI durable event presentation',()=>{
 it('reads a real Codex agent message envelope',()=>expect(nativeEventText({seq:7,stream:'stdout',data:{type:'item.completed',item:{type:'agent_message',text:'已修复计算脚本'}}})).toBe('已修复计算脚本'))
 it('reads Claude assistant text blocks',()=>expect(nativeEventText({data:{type:'assistant',message:{content:[{type:'text',text:'分析完成'},{type:'tool_use',name:'read'}]}}})).toBe('分析完成'))
 it('preserves stderr text instead of displaying provider JSON',()=>expect(nativeEventText({stream:'stderr',data:{text:'directory does not exist'}})).toBe('directory does not exist'))
})
