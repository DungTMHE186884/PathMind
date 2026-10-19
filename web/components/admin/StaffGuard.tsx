"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuthStatus } from "@/hooks/useAuthStatus";

/** The staff console is for R&D and administrators only. */
export default function StaffGuard({ children }: { children: React.ReactNode }) {
  const auth = useAuthStatus();
  const router = useRouter();
  const staff = !auth.enabled || auth.isAdmin || auth.isRnd;

  useEffect(() => {
    if (auth.loading) return;
    if (auth.enabled && !auth.authenticated) router.replace("/login?next=/admin");
    else if (!staff) router.replace("/chat");
  }, [auth.loading, auth.enabled, auth.authenticated, staff, router]);

  if (auth.loading || !staff) return null;
  return <>{children}</>;
}
