import {describe,it,expect} from 'vitest'
import {needsUpgrade,compatibilityMessage} from './services'
describe('server capability compatibility',()=>{
 it('requires a manual upgrade when the server rejects the fixed client version',()=>expect(needsUpgrade({schema_version:'desktop-manifest.v1',compatibility:{compatible:false,reasons:['frontend version']}})).toBe(true))
 it('accepts compatible published capabilities without changing frontend files',()=>expect(needsUpgrade({schema_version:'desktop-manifest.v1',compatibility:{compatible:true,upgrade_required:false}})).toBe(false))
 it('turns backend reason enums into a readable upgrade message',()=>expect(compatibilityMessage(['frontend_upgrade_required'])).toBe('前端版本需要更新'))
 it('does not infer incompatibility from a temporarily missing compatibility result',()=>expect(needsUpgrade({schema_version:'desktop-manifest.v1'})).toBe(false))
})
