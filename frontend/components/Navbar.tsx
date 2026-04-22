"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ClassSelector from "@/components/ClassSelector";

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

        <div className="w-[220px]">
          <ClassSelector />
        </div>
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