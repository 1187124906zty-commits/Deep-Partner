import {normalizeInternalReturnPath} from '@tutor/shared/auth/return-url'
export * from '@tutor/shared/auth/return-url'
export function loginHref(returnPath:string){const entry=location.pathname.endsWith('/')?location.pathname:location.pathname.replace(/[^/]*$/,'')||'/';const q=new URLSearchParams({surface:'login',next:normalizeInternalReturnPath(returnPath)});return entry+'?'+q}
