"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { getTokenClient } from "@/lib/auth";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (getTokenClient()) return;
    const returnTo = pathname ? `?returnTo=${encodeURIComponent(pathname)}` : "";
    router.replace(`/login${returnTo}`);
  }, [router, pathname]);

  return <>{children}</>;
}
