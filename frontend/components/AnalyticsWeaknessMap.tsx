"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";

export default function AnalyticsWeaknessMap() {
  const classId = useStore((s) => s.selectedClassId);

  const q = useQuery({
    queryKey: ["weaknessMap", classId],
    queryFn: () => api.weaknessMap(classId),
  });

  if (q.isLoading) return <div className="text-sm text-slate-500">Loading…</div>;
  if (q.error) return <div className="text-sm text-pink-600">{String(q.error)}</div>;

  const data = q.data;
  if (!data || !data.tags.length) return <div className="text-sm text-slate-500">No repeated weakness patterns yet.</div>;

  return (
    <div className="space-y-3">
      {data.tags.slice(0, 6).map((t) => (
        <div key={t.tag} className="rounded-xl border border-slate-100 p-3">
          <div className="flex justify-between">
            <div className="font-medium text-slate-900">{t.tag}</div>
            <div className="text-sm text-slate-600">{t.count}</div>
          </div>
          <div className="mt-2 text-xs text-slate-500">
            Top concepts:{" "}
            {t.top_concepts.slice(0, 3).map((c) => `${c.concept_name} (${c.count})`).join(", ")}
          </div>
        </div>
      ))}
    </div>
  );
}