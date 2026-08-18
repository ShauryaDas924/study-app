"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import ClassSelector from "@/components/ClassSelector";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabaseClient";
import { clearClientAccountState } from "@/lib/privacy";

const items = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/courses", label: "Courses" },
  { href: "/notes", label: "Notes" },
  { href: "/practice", label: "Practice" },
  { href: "/exam", label: "Exam" },
  { href: "/analytics", label: "Analytics" },
  { href: "/planner", label: "Planner" },
  { href: "/blurting", label: "Blurting" },
  { href: "/tutor", label: "Tutor" },
  { href: "/homework", label: "Homework" },
  { href: "/flashcards", label: "Flashcards" },
  { href: "/insights", label: "Insights" },
];

type ActiveExtractionMeta = {
  noteId: string;
  classId: string;
};

function getStage(progress: number, status?: string) {
  if (status === "failed") return "Failed";
  if (status === "cancelled") return "Cancelled";
  if (progress >= 100 || status === "completed") return "Cards ready";
  if (progress >= 90) return "Saving cards";
  if (progress >= 80) return "Generating cards";
  if (progress >= 72) return "Preparing cards";
  if (progress >= 50) return "Saving concepts";
  if (progress >= 28) return "Enriching concepts";
  if (progress >= 12) return "Extracting concepts";
  if (status === "queued") return "Queued";
  return "Processing";
}

function GlobalExtractionProgress() {
  const [meta, setMeta] = useState<ActiveExtractionMeta | null>(null);

  useEffect(() => {
    function readMeta() {
      const raw = localStorage.getItem("activeExtractionMeta");

      if (!raw) {
        setMeta(null);
        return;
      }

      try {
        const parsed = JSON.parse(raw);

        if (parsed?.noteId && parsed?.classId) {
          setMeta({
            noteId: parsed.noteId,
            classId: parsed.classId,
          });
        } else {
          setMeta(null);
        }
      } catch {
        localStorage.removeItem("activeExtractionMeta");
        localStorage.removeItem("activeExtractionNoteId");
        setMeta(null);
      }
    }

    readMeta();

    const interval = window.setInterval(readMeta, 1000);

    window.addEventListener("storage", readMeta);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("storage", readMeta);
    };
  }, []);

  const statusQ = useQuery({
    queryKey: ["global-extraction-status", meta?.noteId],
    queryFn: () => api.getConceptExtractionStatus(meta!.noteId),
    enabled: !!meta?.noteId,
    refetchInterval: (query) => {
      const data = query.state.data;
      const status = data?.status;

      if (status === "queued" || status === "running") return 3000;
      return false;
    },
  });

  const status = statusQ.data?.status;
  const progress = Number(statusQ.data?.progress ?? 0);
  const stage = getStage(progress, status);

  useEffect(() => {
    if (!meta?.noteId) return;

    if (status === "completed" || status === "failed" || status === "cancelled") {
      const timeout = window.setTimeout(() => {
        localStorage.removeItem("activeExtractionMeta");
        localStorage.removeItem("activeExtractionNoteId");
        setMeta(null);
      }, status === "completed" ? 6000 : 12000);

      return () => window.clearTimeout(timeout);
    }
  }, [status, meta?.noteId]);

  if (!meta?.noteId) return null;

  return (
    <Link
      href="/notes"
      className="block rounded-2xl border px-3 py-2 transition"
      style={{
        background:
          status === "failed"
            ? "linear-gradient(135deg, rgba(255,231,236,0.96), rgba(255,216,227,0.96))"
            : "linear-gradient(135deg, rgba(255,255,255,0.82), rgba(255,248,252,0.92))",
        borderColor: "var(--border-soft)",
        boxShadow: "var(--shadow-soft)",
        minWidth: 220,
      }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold" style={{ color: "var(--text-main)" }}>
          {stage}
        </div>

        <div className="text-xs" style={{ color: "var(--text-soft)" }}>
          {Math.round(progress)}%
        </div>
      </div>

      <div
        className="mt-2 h-2 w-full overflow-hidden rounded-full"
        style={{ background: "rgba(231, 218, 203, 0.7)" }}
      >
        <div
          className="h-full transition-all duration-500"
          style={{
            width: `${Math.max(0, Math.min(progress, 100))}%`,
            background:
              status === "failed"
                ? "linear-gradient(135deg, #ffd7df 0%, #ffb8c8 100%)"
                : status === "completed"
                ? "linear-gradient(135deg, #bfd8b8 0%, #f6df8b 100%)"
                : "linear-gradient(135deg, #f7a7c3 0%, #f6df8b 52%, #bfd8b8 100%)",
          }}
        />
      </div>

      <div className="mt-1 text-[11px]" style={{ color: "var(--text-soft)" }}>
        You can keep studying. This runs in the background.
      </div>
    </Link>
  );
}

export default function Navbar() {
  const path = usePathname();
  const router = useRouter();
  const isPublicPath = path === "/login" || path?.startsWith("/auth/");

  async function handleLogout() {
    await supabase.auth.signOut();
    clearClientAccountState();
    router.replace("/login");
  }

  return (
    <header
      className="sticky top-0 z-20 border-b backdrop-blur"
      style={{
        background: "rgba(255, 255, 255, 0.72)",
        borderColor: "rgba(231, 218, 203, 0.9)",
      }}
    >
          <div className="mx-auto max-w-7xl px-5 py-4 flex items-center justify-between gap-5">
          <div className="flex items-center gap-4">
            {!isPublicPath && (
              <button
                className="rounded-xl border px-3 py-2 text-sm transition"
                style={{
                  background: "rgba(255,255,255,0.68)",
                  borderColor: "var(--border-soft)",
                  color: "var(--text-soft)",
                }}
                onClick={handleLogout}
              >
                Logout
              </button>
            )}

          <Link href="/dashboard" className="flex items-center gap-3 group">
            <div
              className="relative h-10 w-10 shrink-0 rounded-2xl flex items-center justify-center overflow-hidden"
              style={{
                background:
                  "linear-gradient(135deg, rgba(247,167,195,0.95) 0%, rgba(246,223,139,0.95) 52%, rgba(191,216,184,0.95) 100%)",
                boxShadow: "0 14px 35px rgba(247, 167, 195, 0.28)",
                border: "1px solid rgba(231, 218, 203, 0.9)",
              }}
            >
              <div
                className="absolute inset-0 opacity-60"
                style={{
                  background:
                    "radial-gradient(circle at 30% 25%, rgba(255,255,255,0.95), transparent 34%)",
                }}
              />
              <span
                className="relative text-[13px] font-black tracking-[-0.08em]"
                style={{ color: "var(--text-main)" }}
              >
                ST
              </span>
            </div>

            <div className="leading-none">
              <div
                className="text-[17px] font-black tracking-[-0.04em]"
                style={{ color: "var(--text-main)" }}
              >
                StudyOS
              </div>
              <div
                className="mt-1 text-[10px] font-medium tracking-[0.16em] uppercase"
                style={{ color: "var(--text-soft)" }}
              >
                AI Workspace
              </div>
            </div>
          </Link>

        {!isPublicPath && <nav className="hidden md:flex items-center gap-1">
          {items.map((it) => {
            const active = path?.startsWith(it.href);

            return (
              <Link
                key={it.href}
                href={it.href}
                className="px-3 py-2 rounded-xl text-sm transition"
                style={
                  active
                    ? {
                        background: "var(--gradient-main)",
                        color: "var(--text-main)",
                        boxShadow: "var(--shadow-button)",
                      }
                    : {
                        color: "var(--text-soft)",
                      }
                }
              >
                {it.label}
              </Link>
            );
          })}
        </nav>}

        {!isPublicPath && <div className="hidden lg:block">
          <GlobalExtractionProgress />
        </div>}

          {!isPublicPath && (
            <div className="flex w-[120px] items-center gap-3">
              <div className="min-w-0 flex-1">
                <ClassSelector />
              </div>
            </div>
          )}
        </div>
      </div>

      {!isPublicPath && <div className="lg:hidden px-5 pb-3">
        <GlobalExtractionProgress />
      </div>}

      {!isPublicPath && <div className="md:hidden px-5 pb-3 flex flex-wrap gap-2">
        {items.map((it) => {
          const active = path?.startsWith(it.href);

          return (
            <Link
              key={it.href}
              href={it.href}
              className="px-3 py-2 rounded-xl text-sm transition border"
              style={
                active
                  ? {
                      background: "var(--gradient-main)",
                      borderColor: "var(--border-soft)",
                      color: "var(--text-main)",
                      boxShadow: "var(--shadow-button)",
                    }
                  : {
                      background: "rgba(255,255,255,0.68)",
                      borderColor: "var(--border-soft)",
                      color: "var(--text-soft)",
                    }
              }
            >
              {it.label}
            </Link>
          );
        })}
      </div>}
    </header>
  );
}
