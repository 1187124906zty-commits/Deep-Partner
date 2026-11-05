import {afterEach,describe,it,expect} from 'vitest'
import {canSendCommand,setProtocolUpgradeRequired} from './protocol-policy'
afterEach(()=>setProtocolUpgradeRequired(false))
describe('fixed frontend protocol admission',()=>{
 it('blocks new turns and regeneration while allowing replay, cancellation and replies to a running turn',()=>{setProtocolUpgradeRequired(true);expect(canSendCommand('start_turn')).toBe(false);expect(canSendCommand('regenerate')).toBe(false);for(const type of ['resume_from','subscribe_turn','cancel_turn','submit_user_reply','user_input'])expect(canSendCommand(type)).toBe(true)})
 it('admits new turns again after a compatible manifest is confirmed',()=>{setProtocolUpgradeRequired(true);setProtocolUpgradeRequired(false);expect(canSendCommand('start_turn')).toBe(true)})
})
