import {describe,it,expect} from 'vitest'
import {initialProject,imageLocation} from './workspaceLocation'
describe('account-scoped workspace navigation',()=>{
 const rows=[{id:'current',name:'Current project'},{id:'other',name:'Another project'}]
 it('does not silently replace an inaccessible explicit project',()=>{
  expect(initialProject(rows,'unavailable','current')).toEqual({project:null,unavailable:true})
 })
 it('opens the requested project before a remembered or first project',()=>{
  expect(initialProject(rows,'other','current').project).toBe(rows[1])
  expect(initialProject(rows,null,'other').project).toBe(rows[1])
 })
 it('honours only an explicit alias carried by a project owned by this account',()=>{
  const current=[{id:'migrated',config:{link_aliases:['previous-author-project']}}]
  expect(initialProject(current,'previous-author-project',null).project).toBe(current[0])
  expect(initialProject(current,'unrelated',null)).toEqual({project:null,unavailable:true})
 })
 it('opens a figure link directly in its containing directory',()=>{
  expect(imageLocation('https://example.test/research?file=results%2Ffigure14.png')).toEqual({image:'results/figure14.png',directory:'results'})
 })
 it('does not accept absolute paths or traversal in a file link',()=>{
  expect(imageLocation('https://example.test/research?file=../private.png').image).toBe('')
  expect(imageLocation('https://example.test/research?file=/private.png').image).toBe('')
 })
})
