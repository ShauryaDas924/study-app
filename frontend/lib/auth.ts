"use client";

import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabaseClient";
import { clearClientAccountState } from "@/lib/privacy";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function getCurrentSession(): Promise<Session | null> {
  const { data, error } = await supabase.auth.getSession();

  if (error) {
    return null;
  }

  return data.session ?? null;
}

export async function getAuthHeaders(): Promise<Record<string, string>> {
  const session = await getCurrentSession();
  const token = session?.access_token;

  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function apiUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    return pathOrUrl;
  }

  const path = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`;
  return `${API_BASE_URL}${path}`;
}

export async function redirectToLogin() {
  if (typeof window === "undefined") return;
  if (window.location.pathname === "/login") return;

  const next = `${window.location.pathname}${window.location.search}`;
  window.location.assign(`/login?next=${encodeURIComponent(next)}`);
}

export async function handleUnauthorized() {
  await supabase.auth.signOut();
  clearClientAccountState();
  await redirectToLogin();
}

export async function authFetch(
  pathOrUrl: string,
  init?: RequestInit
): Promise<Response> {
  const headers = new Headers(init?.headers);
  const url = apiUrl(pathOrUrl);
  const apiOrigin = new URL(API_BASE_URL).origin;
  const requestOrigin = new URL(url).origin;
  const authHeaders = requestOrigin === apiOrigin ? await getAuthHeaders() : {};

  for (const [key, value] of Object.entries(authHeaders)) {
    headers.set(key, value);
  }

  const res = await fetch(url, {
    ...init,
    headers,
  });

  if (res.status === 401) {
    await handleUnauthorized();
  }

  return res;
}
