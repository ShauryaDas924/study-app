"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function StudyPlanGenerator() {
  const classId = useStore((s) => s.selectedClassId);

  const [examDateIso, setExamDateIso] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().slice(0, 16);
  });

  const [minutes, setMinutes] = useState(60);

  const m = useMutation({
    mutationFn: () =>
      api.planDaily({
        class_id: classId,
        exam_date_iso: new Date(examDateIso).toISOString(),
        available_minutes_per_day: minutes,
      }),
  });

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-3 gap-4">
        <div>
          <div className="text-xs text-slate-500 mb-1">Exam date</div>
          <Input
            type="datetime-local"
            value={examDateIso}
            onChange={(e) => setExamDateIso(e.target.value)}
          />
        </div>
        <div>
          <div className="text-xs text-slate-500 mb-1">Minutes per day</div>
          <Input type="number" min={10} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
        </div>
        <div className="flex items-end">
          <Button className="w-full" onClick={() => m.mutate()} disabled={m.isPending}>
            Generate
          </Button>
        </div>
      </div>

      {m.error ? <div className="text-sm text-pink-600">{String(m.error)}</div> : null}

      {m.data ? (
        <div className="space-y-3">
          <div className="text-sm text-slate-600">Days left: {m.data.days_left}</div>
          {m.data.plan.slice(0, 7).map((day) => (
            <div key={day.day} className="rounded-xl border border-slate-100 p-3">
              <div className="font-medium text-slate-900">{day.day}</div>
              <div className="mt-2 space-y-2">
                {day.tasks.map((t, i) => (
                  <div key={i} className="text-sm text-slate-700 flex justify-between gap-4">
                    <span>
                      <b className="capitalize">{t.type}</b>: {t.goal}
                      {t.concept_id ? <span className="text-xs text-slate-500"> ({t.concept_id})</span> : null}
                    </span>
                    <span className="text-xs text-slate-500">{t.minutes} min</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}