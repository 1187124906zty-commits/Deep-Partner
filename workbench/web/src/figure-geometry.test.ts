import {describe,it,expect} from 'vitest'
import {clippedRect,cellRect,logicalSelection} from './figureGeometry'
describe('visible figure geometry',()=>{
 it('clips annotations and moved outlines to the paper',()=>{
  expect(clippedRect([-.2,.8,.5,.4])).toEqual({x:0,y:.8,width:.3,height:1-.8})
  expect(clippedRect([.2,.2,.3,.3],{x:1,y:0})).toBeNull()
  expect(clippedRect([NaN,0,1,1])).toBeNull()
 })
 it('uses authored unequal cells and multi-column spans',()=>{
  expect(cellRect({rows:2,cols:2},{rect:[0,.4,1,.6],colspan:2})).toEqual([0,.4,1,.6])
 })
 it('treats an axis and all its labels as one selected object',()=>{
  const axes={id:'axes-0',kind:'axes'}
  expect(logicalSelection({id:'ax0-yticks',kind:'ticks',role:'y',parent:axes.id},[axes])).toEqual({id:axes.id,axis:'y'})
  expect(logicalSelection({id:'ax0-spine-top',kind:'spine',role:'top',parent:axes.id},[axes])).toEqual({id:axes.id,axis:'x'})
 })
})
