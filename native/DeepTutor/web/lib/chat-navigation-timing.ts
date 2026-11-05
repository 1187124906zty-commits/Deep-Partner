let startedAt: number | null = null;
export function markChatNavigation(): void { startedAt = performance.now(); }
export function chatNavigationStartedAt(): number | null { return startedAt; }
