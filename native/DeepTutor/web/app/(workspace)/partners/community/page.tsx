"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

function CommunityFrame() {
  const search = useSearchParams();
  const parameters = new URLSearchParams({ embedded: "1" });
  for (const name of ["invite", "partner"]) {
    const value = search.get(name);
    if (value && value.length < 240) parameters.set(name, value);
  }
  return (
    <iframe
      title="Partner 社区"
      src={`/api/community/app?${parameters.toString()}`}
      className="h-full min-h-[720px] w-full border-0 bg-[var(--background)]"
    />
  );
}

/** Keep the application root and active chat runtime mounted during a visit. */
export default function CommunityPage() {
  return <Suspense fallback={<p className="p-6">正在打开 Partner 社区…</p>}><CommunityFrame /></Suspense>;
}
