let upgradeRequired=false
export function setProtocolUpgradeRequired(required:boolean){upgradeRequired=required}
export function canSendCommand(type:string){return !upgradeRequired||!['start_turn','regenerate'].includes(type)}
