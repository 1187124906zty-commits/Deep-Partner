import {SPACE_ITEMS as source} from '@tutor/lib/space-items'
export * from '@tutor/lib/space-items'
export const SPACE_ITEMS=source.filter(item=>item.key!=='question_bank')
