/** Small, local-only QA log. It records route names and timings, never settings
 * values or response bodies, and makes no telemetry requests. */
type Phase = "route" | "content" | "ready";
type Sample = {
  path: string; from: string; visit: number; startedAt: number;
  routeMs?: number; contentMs?: number; readyMs?: number;
  resources?: { path: string; ms: number; bytes: number }[];
};
const samples: Sample[] = [];
const visits = new Map<string, number>();
let current: Sample | null = null;

export function startUiNavigation(href: string): void {
  const path = new URL(href, window.location.origin).pathname;
  if (path === window.location.pathname) return;
  const visit = (visits.get(path) ?? 0) + 1;
  visits.set(path, visit);
  current = { path, from: window.location.pathname, visit, startedAt: performance.now() };
  samples.push(current);
  if (samples.length > 32) samples.shift();
}

export function recordUiNavigation(phase: Phase, path: string): void {
  if (!current || current.path !== path) return;
  const field = `${phase}Ms` as "routeMs" | "contentMs" | "readyMs";
  if (current[field] != null) return;
  current[field] = Number((performance.now() - current.startedAt).toFixed(2));
  current.resources = (performance.getEntriesByType("resource") as PerformanceResourceTiming[])
    .filter(entry => entry.startTime >= current!.startedAt &&
      (entry.name.includes("_rsc=") || new URL(entry.name).pathname.startsWith("/api/")))
    .slice(-12).map(entry => ({
      path: new URL(entry.name).pathname + (entry.name.includes("_rsc=") ? " [RSC]" : ""),
      ms: Number(entry.duration.toFixed(2)), bytes: entry.transferSize,
    }));
  document.documentElement.dataset.uiNavigationLog = JSON.stringify(samples);
}

export function navigationResourceSummary(startedAt: number): string {
  return JSON.stringify((performance.getEntriesByType("resource") as PerformanceResourceTiming[])
    .filter(entry => entry.startTime >= startedAt && entry.name.includes("_rsc="))
    .map(entry => ({ path: new URL(entry.name).pathname, ms: Number(entry.duration.toFixed(2)) })));
}
