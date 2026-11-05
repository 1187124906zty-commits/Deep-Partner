import {describe,it,expect} from 'vitest'
import {preferenceEntries} from './desktop-preferences'
describe('native preference handoff across loopback ports',()=>{
 it('restores only the three canonical preference keys',()=>expect(preferenceEntries({theme:'dark',language:'zh',response_language:'en',token:'secret'} as any)).toEqual([['deeptutor-theme','dark'],['deeptutor-language','zh'],['deeptutor-response-language','en']]))
 it('ignores unsupported values instead of cloning arbitrary host storage',()=>expect(preferenceEntries({theme:'custom-code',language:'arbitrary',response_language:'unknown'})).toEqual([]))
 it('preserves original Tutor appearance and language preferences without arbitrary storage',()=>expect(preferenceEntries({language:'fr',response_language:'ja',code_block_theme:'oneDark',code_block_show_line_numbers:false,code_block_wrap_long_lines:true,ui_layout:'classic'})).toEqual([['deeptutor-language','fr'],['deeptutor-response-language','ja'],['deeptutor.code-block-theme','oneDark'],['deeptutor.code-block-show-line-numbers','false'],['deeptutor.code-block-wrap-long-lines','true'],['deeptutor.ui-layout','classic']]))
})
