"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabaseClient";
import { getSafeInternalPath } from "@/lib/navigation";
import { clearClientAccountState } from "@/lib/privacy";

function getOAuthError() {
  const search = new URLSearchParams(window.location.search);
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));

  return (
    search.get("error_description") ||
    search.get("error") ||
    hash.get("error_description") ||
    hash.get("error")
  );
}

function getSafeNextPath() {
  const raw = new URLSearchParams(window.location.search).get("next");
  return getSafeInternalPath(raw, window.location.origin);
}

export default function AuthCallbackPage() {
  const router = useRouter();
  const [message, setMessage] = useState("Checking your Google login...");

  useEffect(() => {
    let active = true;

    async function finishLogin() {
      const oauthError = getOAuthError();

      if (oauthError) {
        router.replace(`/login?error=${encodeURIComponent(oauthError)}`);
        return;
      }

      const code = new URLSearchParams(window.location.search).get("code");

      if (code) {
        const { error } = await supabase.auth.exchangeCodeForSession(code);

        if (error) {
          router.replace(`/login?error=${encodeURIComponent(error.message)}`);
          return;
        }
      }

      const { data, error } = await supabase.auth.getSession();

      if (!active) return;

      if (error) {
        router.replace(`/login?error=${encodeURIComponent(error.message)}`);
        return;
      }

      if (data.session) {
        setMessage("Login complete. Redirecting...");
        clearClientAccountState();
        router.replace(getSafeNextPath());
        return;
      }

      router.replace(
        `/login?error=${encodeURIComponent("Google login did not return a session.")}`
      );
    }

    finishLogin();

    return () => {
      active = false;
    };
  }, [router]);

  return (
    <div className="mx-auto max-w-md py-10 text-sm" style={{ color: "var(--text-soft)" }}>
      {message}
    </div>
  );
}
