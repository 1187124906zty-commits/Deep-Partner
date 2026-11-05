import {describe,it,expect} from 'vitest'
import {mergeTranslationUpdate} from './documentMerge'
const base={revision:1,title:'Title',template:'chinese',content:{text:'Original'},comments:[],translation:{text:'Old'}}
describe('translation completion during author edits',()=>{
 it('keeps the typed source and adds the newly completed translation',()=>{
  const local={...base,content:{text:'Typed while translating'}}
  const remote={...base,revision:2,translation:{text:'New translation'}}
  const merged=mergeTranslationUpdate(base,local,remote)!
  expect(merged.content).toEqual(local.content);expect(merged.translation).toEqual(remote.translation);expect(merged.revision).toBe(2)
 })
 it('requires reconciliation when another window edits the source',()=>{
  expect(mergeTranslationUpdate(base,{...base,content:{text:'Local'}},{...base,revision:2,content:{text:'Other author'}})).toBeNull()
 })
 it('keeps both versions available instead of overwriting a locally edited translation',()=>{
  expect(mergeTranslationUpdate(base,{...base,translation:{text:'Local target edit'}},{...base,revision:2,translation:{text:'New generated target'}})).toBeNull()
 })
})
