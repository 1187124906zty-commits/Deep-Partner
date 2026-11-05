import {describe,it,expect} from 'vitest'
import {surfaceFromRoute} from './workspace-navigation'
describe('research overview entry',()=>{
 it('opens the project overview unless a concrete destination was requested',()=>{
  expect(surfaceFromRoute('?project=p&dt_workspace=w')).toBe('overview')
  expect(surfaceFromRoute('?project=p&session=s')).toBe('chat')
  expect(surfaceFromRoute('?project=p&view=chat')).toBe('chat')
  expect(surfaceFromRoute('?project=p&area=paper')).toBe('artifacts')
  expect(surfaceFromRoute('?project=p&view=workflow')).toBe('workflow')
  expect(surfaceFromRoute('?project=p&view=overview&session=s')).toBe('overview')
 })
})
