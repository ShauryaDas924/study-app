"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";

export default function StudyPlanView() {
  const classId = useStore(s => s.selectedClassId);

  const m = useMutation({
    mutationFn: api.planDaily,
  });

  return (
    <div>
      <button
        onClick={() => {
          if (!classId) {
            alert("Create & select a class first");
            return;
          }

          m.mutate({
            class_id: classId,
            exam_date_iso: new Date().toISOString(),
            available_minutes_per_day: 60,
          });
        }}
        className="bg-green-300 px-4 py-2 rounded"
      >
        Generate Plan
      </button>

      <pre>{JSON.stringify(m.data, null, 2)}</pre>
    </div>
  );
}