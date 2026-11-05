import {describe,it,expect} from 'vitest'
import {messagePreview} from './message-preview'
describe('conversation generated-file preview',()=>{
 it('opens a protected project output as a native file tab',()=>{const value=messagePreview('/research/api/projects/p/file?path=results%2Fplot.png','http://127.0.0.1:4567');expect(value?.kind).toBe('file');if(value?.kind==='file')expect(value.attachment.filename).toBe('plot.png')})
 it('opens a generated public PDF as a file and a source page as a webpage',()=>{expect(messagePreview('https://example.com/report.pdf','https://tutor.test')?.kind).toBe('file');expect(messagePreview('https://example.com/article','https://tutor.test')?.kind).toBe('web')})
 it('keeps local navigation and non-web schemes out of the viewer',()=>{expect(messagePreview('#ref-2','https://tutor.test')).toBeNull();expect(messagePreview('/settings','https://tutor.test')).toBeNull();expect(messagePreview('javascript:alert(1)','https://tutor.test')).toBeNull()})
})
