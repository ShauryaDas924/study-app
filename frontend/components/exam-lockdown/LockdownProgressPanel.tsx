"use client";

import type { ExamLockdownProgress } from "@/lib/api";

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-2">
      <div className="text-base font-semibold text-slate-900">{value}</div>
      <div className="text-[11px] uppercase tracking-[0.08em] text-slate-400">{label}</div>
    </div>
  );
}

export default function LockdownProgressPanel({ progress }: { progress?: ExamLockdownProgress }) {
  if (!progress) {
    return (
      <div className="rounded-2xl border border-slate-100 bg-white/90 p-4 text-sm text-slate-500 shadow-sm">
        Progress will appear after questions are loaded.
      </div>
    );
  }

  const total = Math.max(1, progress.recommended_count);
  const pct = Math.round((progress.completed_count / total) * 100);

  return (
    <div className="rounded-2xl border border-slate-100 bg-white/90 p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900">Lockdown progress</div>
          <div className="text-xs text-slate-500">Completion is based on marked-complete questions.</div>
        </div>
        <div className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-700">{pct}%</div>
      </div>

      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full bg-emerald-400 transition-all" style={{ width: `${pct}%` }} />
      </div>

      <div className="mt-3 grid grid-cols-4 gap-2">
        <Stat label="done" value={progress.completed_count} />
        <Stat label="tried" value={progress.attempted_count} />
        <Stat label="skipped" value={progress.skipped_count ?? 0} />
        <Stat label="total" value={progress.recommended_count} />
      </div>

      {progress.pitfalls.length ? (
        <div className="mt-3">
          <div className="mb-2 text-xs font-medium text-slate-500">Recent pitfall patterns</div>
          <div className="flex flex-wrap gap-2">
            {progress.pitfalls.slice(0, 5).map((pitfall) => (
              <span key={pitfall.category} className="rounded-full border border-slate-100 bg-slate-50 px-2 py-1 text-xs text-slate-600">
                {pitfall.category.replace(/_/g, " ")}: {pitfall.count}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <div className="mt-3 text-xs text-slate-500">No saved pitfalls yet.</div>
      )}
    </div>
  );
}
