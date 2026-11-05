import type {ComponentProps} from 'react'
import OriginalModelSelector from '@tutor/components/chat/home/ModelSelector'

/** Keep model choices and updates on the native conversation runtime. */
export default function ResearchModelSelector(props:ComponentProps<typeof OriginalModelSelector>){
 return <div className="dp-model-selector"><OriginalModelSelector {...props} pinned/></div>
}
