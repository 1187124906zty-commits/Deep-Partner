import {BookOpen,Files,FilePenLine,Image,Presentation,FolderCode,History,Network} from 'lucide-react'
import type {WorkbenchArea} from '@workbench/App'

type WorkspaceEntry={id:WorkbenchArea;label:string;icon:typeof BookOpen}
export const workspaceGroups:{label:string;items:WorkspaceEntry[]}[] = [
  {label:'研究',items:[
    {id:'literature',label:'文献与知识库',icon:BookOpen},
    {id:'code',label:'程序',icon:FolderCode},
    {id:'paper',label:'论文',icon:FilePenLine},
  ]},
  {label:'成果',items:[
    {id:'figures',label:'图表',icon:Image},
    {id:'slides',label:'PPT',icon:Presentation},
  ]},
]

export const workspaceEntries=[...workspaceGroups.flatMap(group=>group.items),{id:'files' as const,label:'项目文件',icon:Files},{id:'questions' as const,label:'项目画布',icon:Network}]
export function workspaceArea(value:string|null):WorkbenchArea|undefined {
  return workspaceEntries.find(entry=>entry.id===value)?.id
}

export type Surface='overview'|'overview-split'|'chat'|'artifacts'|'split'|'native'|'workflow'
export function surfaceFromRoute(search:string):Surface {
 const q=new URLSearchParams(search)
 if(q.get('view')==='workflow')return 'workflow'
 if(q.get('view')==='overview')return 'overview'
 if(workspaceArea(q.get('area')))return 'artifacts'
 if(q.get('view')==='chat'||q.has('session'))return 'chat'
 return 'overview'
}
