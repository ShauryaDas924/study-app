"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function WeeklyPlanGenerator() {
  const classId = useStore((s) => s.selectedClassId);

  const [examDateIso, setExamDateIso] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() + 21);
    return d.toISOString().slice(0, 16);
  });

  const [minutes, setMinutes] = useState(60);

  const m = useMutation({
    mutationFn: () =>
      api.planWeekly({
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
          <Input type="datetime-local" value={examDateIso} onChange={(e) => setExamDateIso(e.target.value)} />
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
        <div className="space-y-4">
          <div className="text-sm text-slate-600">
            Weeks left: {m.data.weeks_left} • Days left: {m.data.days_left}
          </div>

          {m.data.weekly_plan.map((w) => (
            <div key={w.week} className="rounded-2xl border border-slate-100 p-4">
              <div className="flex justify-between">
                <div className="font-semibold text-slate-900">Week {w.week}</div>
                <div className="text-xs text-slate-500">Start: {w.week_start}</div>
              </div>

              <div className="mt-3 space-y-3">
                {w.days.map((d) => (
                  <div key={d.day} className="rounded-xl bg-slate-50 border border-slate-100 p-3">
                    <div className="text-sm font-medium text-slate-900">{d.day}</div>
                    <div className="mt-2 space-y-1">
                      {d.tasks.map((t, i) => (
                        <div key={i} className="text-sm text-slate-700 flex justify-between gap-4">
                          <span>
                            <b className="capitalize">{t.type}</b>: {t.goal}
                          </span>
                          <span className="text-xs text-slate-500">{t.minutes} min</span>
                        </div>
                      ))}
                    </div>
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