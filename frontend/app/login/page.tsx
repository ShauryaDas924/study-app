"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { supabase } from "@/lib/supabaseClient";

function getSafeNextPath() {
  if (typeof window === "undefined") return "/dashboard";

  const raw = new URLSearchParams(window.location.search).get("next");
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/dashboard";

  return raw;
}

function getInitialMessage() {
  if (typeof window === "undefined") return "";

  return new URLSearchParams(window.location.search).get("error") || "";
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState<"login" | "signup" | "google" | null>(null);
  const [message, setMessage] = useState(getInitialMessage);
  const next = getSafeNextPath();

  async function handleLogin() {
    setLoading("login");
    setMessage("");

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    setLoading(null);

    if (error) {
      setMessage(error.message);
      return;
    }

    router.replace(next);
  }

  async function handleSignup() {
    setLoading("signup");
    setMessage("");

    const { error } = await supabase.auth.signUp({
      email,
      password,
    });

    setLoading(null);

    if (error) {
      setMessage(error.message);
      return;
    }

    setMessage("Account created. Check your email if confirmation is enabled, then log in.");
  }

  async function handleGoogleLogin() {
    setLoading("google");
    setMessage("");

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    if (error) {
      setLoading(null);
      setMessage(error.message);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-6 py-10">
      <div>
        <h1 className="text-3xl font-semibold" style={{ color: "var(--text-main)" }}>
          Log in
        </h1>
        <p className="mt-2 text-sm" style={{ color: "var(--text-soft)" }}>
          Use your Supabase account to continue.
        </p>
      </div>

      <div className="space-y-4 rounded-2xl border p-5" style={{ borderColor: "var(--border-soft)", background: "rgba(255,255,255,0.78)" }}>
        <label className="block space-y-1">
          <span className="text-sm" style={{ color: "var(--text-soft)" }}>Email</span>
          <input
            className="app-input w-full px-4 py-2"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <label className="block space-y-1">
          <span className="text-sm" style={{ color: "var(--text-soft)" }}>Password</span>
          <input
            className="app-input w-full px-4 py-2"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        {message && (
          <div className="rounded-xl border px-3 py-2 text-sm" style={{ borderColor: "var(--border-soft)", color: "var(--text-main)" }}>
            {message}
          </div>
        )}

        <button
          className="app-button-secondary w-full px-4 py-2"
          disabled={!!loading}
          onClick={handleGoogleLogin}
        >
          {loading === "google" ? "Opening Google..." : "Continue with Google"}
        </button>

        <div className="text-center text-xs" style={{ color: "var(--text-soft)" }}>
          or use email
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            className="app-button-primary px-4 py-2"
            disabled={!!loading || !email || !password}
            onClick={handleLogin}
          >
            {loading === "login" ? "Logging in..." : "Log in"}
          </button>

          <button
            className="app-button-secondary px-4 py-2"
            disabled={!!loading || !email || !password}
            onClick={handleSignup}
          >
            {loading === "signup" ? "Creating..." : "Sign up"}
          </button>
        </div>
      </div>
    </div>
  );
}
