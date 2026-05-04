"use client";

import type { Session } from "@supabase/supabase-js";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabaseClient";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checking, setChecking] = useState(true);
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    let active = true;

    async function checkSession() {
      const { data } = await supabase.auth.getSession();
      if (!active) return;

      setSession(data.session ?? null);
      setChecking(false);

      if (!data.session && pathname !== "/login") {
        router.replace(`/login?next=${encodeURIComponent(pathname || "/")}`);
      }
    }

    checkSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (!active) return;

      setSession(nextSession);
      setChecking(false);

      if (!nextSession && pathname !== "/login") {
        router.replace(`/login?next=${encodeURIComponent(pathname || "/")}`);
      }
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [pathname, router]);

  if (checking) {
    return <div className="text-sm text-slate-500">Checking session...</div>;
  }

  if (!session) {
    return null;
  }

  return <>{children}</>;
}
