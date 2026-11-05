import {describe,it,expect} from 'vitest'
import {matchedBlockPosition} from '../../web/src/documentScroll'
describe('bilingual block alignment',()=>{it('aligns the same paragraph when preceding translations are taller',()=>{expect(matchedBlockPosition(225,[{top:0,height:100},{top:100,height:100},{top:200,height:100}],[{top:0,height:300},{top:300,height:200},{top:500,height:200}])).toBe(550)})})
