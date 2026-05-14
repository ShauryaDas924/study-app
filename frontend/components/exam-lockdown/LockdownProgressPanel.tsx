"use client";

import type { ExamLockdownProgress } from "@/lib/api";

export default function LockdownProgressPanel({ progress }: { progress?: ExamLockdownProgress }) {
  if (!progress) {
    return <div className="text-sm text-slate-500">Progress will appear after questions are loaded.</div>;
  }

  const total = Math.max(1, progress.recommended_count);
  const pct = Math.round((progress.completed_count / total) * 100);

  return (
    <div className="rounded-xl border border-slate-100 p-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-slate-900">Lockdown progress</div>
        <div className="text-xs text-slate-500">{pct}%</div>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full bg-emerald-300" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-2 text-xs text-slate-500">
        {progress.completed_count} completed - {progress.attempted_count} attempts - {progress.recommended_count} recommended
      </div>
      {progress.pitfalls.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {progress.pitfalls.slice(0, 5).map((pitfall) => (
            <span key={pitfall.category} className="rounded-full border border-slate-100 bg-slate-50 px-2 py-1 text-xs text-slate-600">
              {pitfall.category.replace(/_/g, " ")}: {pitfall.count}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
