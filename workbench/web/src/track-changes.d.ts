import '@tiptap/core'
// 0.2.1 exports its runtime commands but omits their interface augmentation.
declare module '@tiptap/core' {
 interface Commands<ReturnType> {
  trackChanges:{
   setSuggestMode:()=>ReturnType
   setEditMode:()=>ReturnType
   setViewMode:()=>ReturnType
   setTrackChangesMode:(mode:'edit'|'suggest'|'view')=>ReturnType
   acceptAll:()=>ReturnType
   rejectAll:()=>ReturnType
   acceptChange:(id:string)=>ReturnType
   rejectChange:(id:string)=>ReturnType
  }
 }
}
