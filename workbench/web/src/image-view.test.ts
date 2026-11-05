import {describe,it,expect} from 'vitest'
import {boundedView} from './ImageInspector'

describe('bounded image navigation',()=>{
 it('centres an image that fits the frame',()=>{
  expect(boundedView({x:900,y:-700,scale:.5},1000,600,600,400)).toEqual({x:50,y:50,scale:.5})
 })
 it('keeps a zoomed image covering the frame at both pan limits',()=>{
  const a=boundedView({x:900,y:700,scale:2},1000,600,600,400)
  const b=boundedView({x:-9000,y:-7000,scale:2},1000,600,600,400)
  expect(a).toEqual({x:0,y:0,scale:2});expect(b).toEqual({x:-1400,y:-800,scale:2})
 })
})
