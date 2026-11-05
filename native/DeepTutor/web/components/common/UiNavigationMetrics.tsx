"use client";

import { Suspense, useEffect, useLayoutEffect } from "react";
import { usePathname } from "next/navigation";
import { recordUiNavigation, startUiNavigation } from "@/lib/ui-navigation-timing";

function Metrics() {
  const pathname = usePathname();
  useEffect(() => {
    performance.setResourceTimingBufferSize(2000);
    const start = (event: MouseEvent) => {
      if (event.button || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
      const anchor = (event.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) return;
      const url = new URL(anchor.href);
      if (url.origin === window.location.origin) startUiNavigation(url.href);
    };
    document.addEventListener("click", start, true);
    return () => document.removeEventListener("click", start, true);
  }, []);
  useLayoutEffect(() => { recordUiNavigation("route", pathname); }, [pathname]);
  return null;
}

export default function UiNavigationMetrics() { return <Suspense><Metrics /></Suspense>; }
