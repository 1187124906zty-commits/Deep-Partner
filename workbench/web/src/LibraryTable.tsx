import {useMemo,useState} from 'react'
import {flexRender,getCoreRowModel,getSortedRowModel,useReactTable,type ColumnDef,type SortingState} from '@tanstack/react-table'
import {ArrowDown,ArrowUp,ArrowUpDown,BookOpen,Download,FileText} from 'lucide-react'
import {Button} from './components/ui/button'

export type LibraryRow={key:string;metadata:any;file?:any;category:string}
type Props={rows:LibraryRow[];selection:string;checked:Record<string,boolean>;pending:(row:LibraryRow)=>string|undefined;
 onSelect:(row:LibraryRow)=>void;onOpen:(row:LibraryRow)=>void;onDownload:(row:LibraryRow)=>void;
 onCheck:(key:string,value:boolean)=>void;onContext:(row:LibraryRow,x:number,y:number)=>void}

/** TanStack owns tabular ordering; project APIs remain the source of truth. */
export function LibraryTable({rows,selection,checked,pending,onSelect,onOpen,onDownload,onCheck,onContext}:Props){
 const [sorting,setSorting]=useState<SortingState>([])
 const columns=useMemo<ColumnDef<LibraryRow>[]>(()=>[
  {id:'selection',header:'',enableSorting:false,cell:({row})=><input aria-label={'选择下载 '+row.original.metadata.title} type="checkbox" disabled={!!row.original.file||!!pending(row.original)} checked={!!checked[row.id]} onChange={e=>onCheck(row.id,e.target.checked)} onClick={e=>e.stopPropagation()}/>},
  {id:'title',header:'文献',accessorFn:r=>r.metadata.title||'',cell:({row})=><div className="library-table-title"><FileText size={15}/><div><strong>{row.original.metadata.title}</strong><small>{[row.original.metadata.year,row.original.metadata.venue].filter(Boolean).join(' · ')||'题录信息待完善'}</small></div></div>},
  {id:'authors',header:'作者',accessorFn:r=>r.metadata.authors?.[0]||'',cell:({row})=>{const authors=row.original.metadata.authors||[];return <span title={authors.join('; ')}>{authors[0]||'—'}{authors.length>1?' 等':''}</span>}},
  {id:'year',header:'年份',accessorFn:r=>Number(r.metadata.year)||0,cell:({row})=>row.original.metadata.year||'—'},
  {id:'venue',header:'出版物',accessorFn:r=>r.metadata.venue||'',cell:({row})=><span title={row.original.metadata.venue}>{row.original.metadata.venue||'—'}</span>},
  {id:'access',header:'全文',accessorFn:r=>r.file?1:0,cell:({row})=>{const item=row.original,state=pending(item);return item.file?<Button variant="ghost" size="sm" className="bibliography-read library-row-action" onClick={e=>{e.stopPropagation();onOpen(item)}}><BookOpen size={13}/><span>阅读全文</span></Button>:<Button variant="ghost" size="sm" className="bibliography-download library-row-action" disabled={!!state} onClick={e=>{e.stopPropagation();onDownload(item)}}><Download size={13}/><span>{state==='running'?'下载中':state?'等待下载':'下载全文'}</span></Button>}}
 ],[checked,pending,onOpen,onDownload,onCheck])
 const table=useReactTable({data:rows,columns,getRowId:r=>r.key,state:{sorting},onSortingChange:setSorting,getCoreRowModel:getCoreRowModel(),getSortedRowModel:getSortedRowModel()})
 return <table className="bibliography-table library-data-table" aria-label="项目文献"><thead>{table.getHeaderGroups().map(group=><tr key={group.id}>{group.headers.map(header=><th key={header.id} data-column={header.column.id} aria-sort={header.column.getIsSorted()==='asc'?'ascending':header.column.getIsSorted()==='desc'?'descending':undefined}>{header.column.getCanSort()?<button onClick={header.column.getToggleSortingHandler()} aria-label={'按'+header.column.columnDef.header+'排序'}>{flexRender(header.column.columnDef.header,header.getContext())}{header.column.getIsSorted()==='asc'?<ArrowUp size={11}/>:header.column.getIsSorted()==='desc'?<ArrowDown size={11}/>:<ArrowUpDown size={11}/>}</button>:flexRender(header.column.columnDef.header,header.getContext())}</th>)}</tr>)}</thead><tbody>{table.getRowModel().rows.map((row,index)=>{const item=row.original;return <tr key={row.id} data-library-row={row.id} tabIndex={0} aria-selected={selection===row.id} className={selection===row.id?'selected':''} onClick={()=>onSelect(item)} onDoubleClick={()=>{if(item.file)onOpen(item)}} onKeyDown={e=>{if(e.target!==e.currentTarget)return;if(e.key==='Enter'){e.preventDefault();onSelect(item)}if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();const next=table.getRowModel().rows[index+(e.key==='ArrowDown'?1:-1)];if(next){const siblings=e.currentTarget.parentElement?.children;const element=siblings?.[index+(e.key==='ArrowDown'?1:-1)] as HTMLElement|undefined;element?.focus();if(selection)onSelect(next.original)}}}} onContextMenu={e=>{if(item.file){e.preventDefault();onContext(item,e.clientX,e.clientY)}}}>{row.getVisibleCells().map(cell=><td key={cell.id} data-column={cell.column.id}>{flexRender(cell.column.columnDef.cell,cell.getContext())}</td>)}</tr>})}</tbody></table>
}
