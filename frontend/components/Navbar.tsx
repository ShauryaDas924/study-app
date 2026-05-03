"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import ClassSelector from "@/components/ClassSelector";
import { api } from "@/lib/api";

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
    queryFn: () => api.getConceptExtractionStatus(meta!.noteId as any),
    enabled: !!meta?.noteId,
    refetchInterval: (query) => {
      const data: any = query.state.data;
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

    if (status === "completed" || status === "failed") {
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

  return (
    <header
      className="sticky top-0 z-20 border-b backdrop-blur"
      style={{
        background: "rgba(255, 255, 255, 0.72)",
        borderColor: "rgba(231, 218, 203, 0.9)",
      }}
    >
      <div className="mx-auto max-w-6xl px-5 py-4 flex items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div
            className="h-9 w-9 rounded-2xl flex items-center justify-center font-semibold"
            style={{
              background: "var(--gradient-main)",
              color: "var(--text-main)",
              boxShadow: "var(--shadow-button)",
            }}
          >
            T
          </div>

          <div>
            <div className="font-semibold leading-tight" style={{ color: "var(--text-main)" }}>
              Study Tutor
            </div>
            <div className="text-xs" style={{ color: "var(--text-soft)" }}>
              Calm AI tutoring for deep work
            </div>
          </div>
        </div>

        <nav className="hidden md:flex items-center gap-1">
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
        </nav>

        <div className="hidden lg:block">
          <GlobalExtractionProgress />
        </div>

        <div className="w-[220px]">
          <ClassSelector />
        </div>
      </div>

      <div className="lg:hidden px-5 pb-3">
        <GlobalExtractionProgress />
      </div>

      <div className="md:hidden px-5 pb-3 flex flex-wrap gap-2">
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
      </div>
    </header>
  );
}