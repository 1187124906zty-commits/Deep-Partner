import type { MessageTraceMetadata } from "./memory";

type CachedMessage = {
  id?: number;
  role: string;
  content: string;
  events?: unknown[];
  trace?: MessageTraceMetadata;
};

/** Keep full traces and React's memo inputs while the server revision agrees. */
export function reuseMessageSnapshots<T extends CachedMessage>(previous: T[], incoming: T[]): T[] {
  const byId = new Map(previous.filter(message => message.id != null).map(message => [message.id, message]));
  let allSame = previous.length === incoming.length;
  const next = incoming.map((message, index) => {
    const cached = byId.get(message.id);
    let merged = message;
    if (cached?.trace?.turn_id && cached.trace.truncated === false &&
        cached.content === message.content && cached.trace.turn_id === message.trace?.turn_id &&
        cached.trace.last_seq === message.trace?.last_seq && cached.trace.total === message.trace?.total) {
      merged = { ...message, events: cached.events, trace: cached.trace };
    }
    if (cached) {
      const left = cached as Record<string, unknown>;
      const right = merged as Record<string, unknown>;
      const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
      const same = [...keys].every(key => left[key] === right[key] ||
        (typeof left[key] === "object" && typeof right[key] === "object" &&
         JSON.stringify(left[key]) === JSON.stringify(right[key])));
      if (same) merged = cached;
    }
    if (merged !== previous[index]) allSame = false;
    return merged;
  });
  return allSame ? previous : next;
}
