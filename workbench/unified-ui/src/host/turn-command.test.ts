import {describe,it,expect} from 'vitest'
import {nativeTurnCommand} from './turn-command'
describe('native Dito new-session protocol',()=>{
 it('starts a separate side session while preserving its parent and model intent',()=>{
  const input={type:'start_turn',session_id:null,answer_by:'',content:'side question',selection_tutor_context:{parent_session_id:'main',source_message_id:12},llm_selection:null}
  const result=nativeTurnCommand(input)
  expect(result).not.toHaveProperty('session_id')
  expect(result.selection_tutor_context).toEqual(input.selection_tutor_context)
  expect(result.llm_selection).toBeNull()
  expect(result.answer_by).toBeNull()
  expect(input.session_id).toBeNull()
 })
 it('continues an existing side session with the actual assigned identifier',()=>{const input={type:'start_turn',session_id:'side-42'};expect(nativeTurnCommand(input)).toBe(input)})
 it('admits a new Dito session in the current project workspace without changing an explicit scope',()=>{
  expect(nativeTurnCommand({type:'start_turn',session_id:null},'ws-project')).toEqual({type:'start_turn',workspace_id:'ws-project'})
  expect(nativeTurnCommand({type:'start_turn',workspace_id:'ws-explicit'},'ws-project').workspace_id).toBe('ws-explicit')
  expect(nativeTurnCommand({type:'cancel_turn'},'ws-project')).toEqual({type:'cancel_turn'})
 })
 it('hands an existing side session back from a partner to Dito explicitly',()=>{const result=nativeTurnCommand({type:'start_turn',session_id:'side-42',answer_by:''});expect(result.session_id).toBe('side-42');expect(result).toHaveProperty('answer_by',null);expect(nativeTurnCommand({type:'start_turn',answer_by:'partner:p1'}).answer_by).toBe('partner:p1')})
})
