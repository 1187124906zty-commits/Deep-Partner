"use client";

import { Suspense, useEffect, type ReactNode } from "react";
import { useActiveWorkspaceId } from "@/hooks/useActiveWorkspaceId";
import { clearMarkdownParseCache } from "@/components/common/markdown-parse-cache";
import { RECOVERY_PRINCIPAL_CHANGED } from "@/lib/recovery-principal";
import { clearTraceDisclosures } from "./trace/memory";
import { ChatRuntimeProvider } from "./ChatRuntimeProvider";

function ScopedRuntime({ children }: { children: ReactNode }) {
  const workspaceId = useActiveWorkspaceId();
  useEffect(() => {
    const clearVisualCaches = () => { clearMarkdownParseCache(); clearTraceDisclosures(); };
    clearVisualCaches();
    window.addEventListener(RECOVERY_PRINCIPAL_CHANGED, clearVisualCaches);
    return () => {
      window.removeEventListener(RECOVERY_PRINCIPAL_CHANGED, clearVisualCaches);
      clearVisualCaches();
    };
  }, [workspaceId]);
  // Page groups can unmount; the root and this socket/state owner stay alive.
  // A different workspace still gets its own fresh, isolated runtime.
  return <ChatRuntimeProvider key={workspaceId}>{children}</ChatRuntimeProvider>;
}

export function ChatRuntimeRoot({ children }: { children: ReactNode }) {
  return <Suspense><ScopedRuntime>{children}</ScopedRuntime></Suspense>;
}
