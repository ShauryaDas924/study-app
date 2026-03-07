"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";

export default function AnalyticsMistakeHeatmap() {
  const classId = useStore((s) => s.selectedClassId);

  const q = useQuery({
    queryKey: ["mistakeHeatmap", classId],
    queryFn: () => api.mistakeHeatmap(classId),
  });

  if (q.isLoading) return <div className="text-sm text-slate-500">Loading…</div>;
  if (q.error) return <div className="text-sm text-pink-600">{String(q.error)}</div>;

  const rows = q.data || [];
  if (!rows.length) return <div className="text-sm text-slate-500">No mistakes logged yet.</div>;

  const max = Math.max(...rows.map((r) => r.mistakes), 1);

  return (
    <div className="space-y-2">
      {rows.slice(0, 12).map((r) => {
        const w = Math.round((r.mistakes / max) * 100);
        return (
          <div key={r.concept_id} className="text-xs">
            <div className="flex justify-between text-slate-600">
              <span className="truncate max-w-[180px]">{r.concept_id}</span>
              <span>{r.mistakes}</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-2 bg-pink-300" style={{ width: `${w}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}