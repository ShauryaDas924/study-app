"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Card } from "@/components/ui/Card";

export default function ClassSelector() {
  const selected = useStore((s) => s.selectedClassId);
  const setSelected = useStore((s) => s.setSelectedClassId);

  const { data: classes } = useQuery({
    queryKey: ["classes"],
    queryFn: api.listClasses,
  });

  return (
    <Card className="p-3">
     <div className="text-xs text-slate-500 mb-2">
  Selected course
</div>

      <select
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
        className="w-full border rounded-xl px-3 py-2 bg-white"
      >
       <option value="">Select course</option>

        {classes?.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
    </Card>
  );
}