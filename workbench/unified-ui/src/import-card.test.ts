import {describe,it,expect} from 'vitest'
import {importPrompt} from './ImportProjectCard'
describe('explicit project import request',()=>{
 it('preserves source and scope without calling a tool when the card opens',()=>{const text=importPrompt('本地项目文件夹','D:\\作者资料','project-1','不要覆盖实验原始值');expect(text).toContain('D:\\作者资料');expect(text).toContain('不要覆盖实验原始值');expect(text).toContain('project_import(action="prepare"');expect(text).toContain('不训练模型');expect(text).toContain('其他账户的在线项目只能要求其所有者导出')})
})
