import * as original from '@tutor/features/capabilities/presentation'
export * from '@tutor/features/capabilities/presentation'
const education=new Set(['deep_question','course_study','mastery_path','math_animator','video_course'])
export const CHAT_CAPABILITIES=original.CHAT_CAPABILITIES.filter(c=>!education.has(c.value))
export const HOME_CHAT_CAPABILITIES=CHAT_CAPABILITIES.filter(c=>!c.legacy&&c.value!=='immersive_reading')
export function visibleCapabilityPresentations(capabilities:Parameters<typeof original.visibleCapabilityPresentations>[0]){return original.visibleCapabilityPresentations(capabilities).filter(c=>!education.has(c.value))}
