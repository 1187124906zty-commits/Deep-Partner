// Shared DeepTutor theme key and class contract, verified against its 1.7 UI.
export type Theme='light'|'dark'|'snow'|'glass'
export function applyTheme(value:Theme){
 const root=document.documentElement;root.classList.remove('dark','theme-glass','theme-snow')
 if(value==='dark'||value==='glass')root.classList.add('dark')
 if(value==='glass')root.classList.add('theme-glass')
 if(value==='snow')root.classList.add('theme-snow')
 root.dataset.tutorTheme=value
}
export function initializeTheme(){
 const initial=localStorage.getItem('deeptutor-theme');applyTheme(['light','dark','snow','glass'].includes(initial||'')?initial as Theme:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'snow')
 window.addEventListener('storage',e=>{if(e.key==='deeptutor-theme'&&e.newValue&&['light','dark','snow','glass'].includes(e.newValue))applyTheme(e.newValue as Theme)})
}
export function selectTheme(value:Theme){localStorage.setItem('deeptutor-theme',value);applyTheme(value)}
