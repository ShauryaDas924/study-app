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
  { href: "/tutor", label: "Tutor" },
  { href: "/homework", label: "Homework" },
  { href: "/flashcards", label: "Flashcards" },
  { href: "/insights", label: "Insights" },
];

export default function Navbar() {
  const path = usePathname();

  return (
    <header className="sticky top-0 z-20 bg-white/80 backdrop-blur border-b border-slate-100">
      <div className="mx-auto max-w-6xl px-5 py-4 flex items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-2xl bg-green-200 flex items-center justify-center font-semibold text-slate-800">
            T
          </div>
          <div>
            <div className="font-semibold text-slate-900 leading-tight">Study Tutor</div>
            <div className="text-xs text-slate-500">Calm AI tutoring for deep work</div>
          </div>
        </div>

        <nav className="hidden md:flex items-center gap-1">
          {items.map((it) => {
            const active = path?.startsWith(it.href);
            return (
              <Link
                key={it.href}
                href={it.href}
                className={[
                  "px-3 py-2 rounded-xl text-sm transition",
                  active ? "bg-green-100 text-slate-900" : "text-slate-600 hover:bg-slate-100",
                ].join(" ")}
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
              className={[
                "px-3 py-2 rounded-xl text-sm transition border",
                active ? "bg-green-100 border-green-200 text-slate-900" : "border-slate-200 text-slate-600",
              ].join(" ")}
            >
              {it.label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}