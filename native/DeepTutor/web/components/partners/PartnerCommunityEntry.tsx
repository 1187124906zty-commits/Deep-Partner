"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Users } from "lucide-react";
import { apiFetch, apiUrl } from "@/lib/api";
import { pageActionClass } from "@/components/layout/FeaturePage";

/** A missing optional module never changes the native Partner directory. */
export default function PartnerCommunityEntry() {
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    let active = true;
    void apiFetch(apiUrl("/api/community/capability"))
      .then(async (response) => response.ok ? response.json() : null)
      .then((result) => { if (active) setAvailable(result?.available === true); })
      .catch(() => { if (active) setAvailable(false); });
    return () => { active = false; };
  }, []);
  if (!available) return null;
  return (
    <Link href="/partners/community" className={pageActionClass("secondary")}>
      <Users className="h-3.5 w-3.5" />
      Partner 社区
    </Link>
  );
}
