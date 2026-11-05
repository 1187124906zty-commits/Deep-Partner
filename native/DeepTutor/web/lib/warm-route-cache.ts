import { PrefetchKind } from "next/dist/client/components/router-reducer/router-reducer-types";

type PrefetchRouter = { prefetch: (href: string, options: {
  kind: PrefetchKind; onInvalidate: () => void;
}) => void };

/** Refill stale page shells in the background for this mounted surface. */
export function keepRoutesWarm(router: PrefetchRouter, routes: readonly string[]): () => void {
  let active = true;
  const warm = (href: string) => {
    if (active) router.prefetch(href, {
      kind: PrefetchKind.FULL, onInvalidate: () => warm(href),
    });
  };
  for (const route of new Set(routes)) warm(route);
  return () => { active = false; };
}
