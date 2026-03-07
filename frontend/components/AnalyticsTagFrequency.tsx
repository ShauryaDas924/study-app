"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Tag } from "@/components/ui/Tag";

export default function AnalyticsTagFrequency() {
  const q = useQuery({
    queryKey: ["tagFrequency"],
    queryFn: () => api.tagFrequency(),
  });

  if (q.isLoading) return <div className="text-sm text-slate-500">Loading…</div>;
  if (q.error) return <div className="text-sm text-pink-600">{String(q.error)}</div>;

  const rows = q.data || [];
  if (!rows.length) return <div className="text-sm text-slate-500">No tags yet.</div>;

  return (
    <div className="flex flex-wrap gap-2">
      {rows.slice(0, 20).map((r) => (
        <Tag key={r.tag} text={`${r.tag} (${r.count})`} />
      ))}
    </div>
  );
}