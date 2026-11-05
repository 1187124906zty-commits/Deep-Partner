import {expect,it} from 'vitest'
import {cachedFileText,fileTextKey,rememberFileText} from '../../web/src/fileTextCache'

it('reopens the same version immediately and never reuses text for a changed file',()=>{
 const url='/research/api/projects/owned/file?path=model.py',key=fileTextKey(url,100)
 rememberFileText(key,'first version');expect(cachedFileText(key)).toBe('first version')
 expect(cachedFileText(fileTextKey(url,101))).toBeUndefined()
 window.dispatchEvent(new Event('deeppartner:auth-required'));expect(cachedFileText(key)).toBeUndefined()
})
