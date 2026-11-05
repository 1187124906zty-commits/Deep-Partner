import {beforeEach,describe,expect,it} from 'vitest'
import {readWritingMode,storeWritingMode,writingTurnCommand} from './host/writing-mode'
describe('built-in writing mode',()=>{
 beforeEach(()=>localStorage.clear())
 it('defaults ordinary conversation to research',()=>expect(readWritingMode('ws')).toEqual({mode:'research',phase:'auto'}))
 it('carries selected phase and exact model selection into the native request',()=>{
  storeWritingMode('ws',{mode:'writing',phase:'revision'})
  const model={profile_id:'p',model_id:'m'}
  expect(writingTurnCommand({type:'start_turn',llm_selection:model,config:{temperature:.2}},'ws').config).toEqual({temperature:.2,partner_mode:'writing',partner_writing_phase:'revision',partner_llm_selection:model})
 })
 it('lets the person return to the original research mode',()=>{storeWritingMode('ws',{mode:'research',phase:'auto'});expect(writingTurnCommand({type:'start_turn'},'ws').config?.partner_mode).toBe('research')})
 it('does not alter cancel, resume or subscription commands',()=>{const command={type:'cancel_turn',turn_id:'t'};expect(writingTurnCommand(command,'ws')).toBe(command)})
 it('leaves other capability schemas unchanged',()=>{const command={type:'start_turn',capability:'deep_question',config:{num_questions:3}};expect(writingTurnCommand(command,'ws')).toBe(command)})
 it('keeps project choices independent',()=>{storeWritingMode('one',{mode:'writing',phase:'submission'});expect(readWritingMode('two').phase).toBe('auto')})
 it('lets a research-context turn override a project writing choice without changing that choice',()=>{
  storeWritingMode('ws',{mode:'writing',phase:'revision'})
  expect(writingTurnCommand({type:'start_turn',config:{partner_mode:'research'}},'ws').config).toEqual({partner_mode:'research',partner_writing_phase:'auto'})
  expect(readWritingMode('ws')).toEqual({mode:'writing',phase:'revision'})
 })
})
