"use client";

import type { ExamPrepPlanDay } from "@/lib/api";

export default function StudyPlanTimeline({ days }: { days: ExamPrepPlanDay[] }) {
  if (!days.length) {
    return <div className="text-sm text-slate-500">No study plan generated yet.</div>;
  }

  return (
    <div className="space-y-3">
      {days.map((day) => (
        <div key={day.date} className="rounded-xl border border-slate-100 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="font-semibold text-slate-900">{day.date}</div>
              <div className="text-xs text-slate-500">{day.title}</div>
            </div>
            <div className="text-xs text-slate-500">
              {day.tasks.reduce((sum, task) => sum + Number(task.minutes || 0), 0)} min
            </div>
          </div>

          <div className="mt-3 space-y-2">
            {day.tasks.map((task, index) => (
              <div key={`${day.date}-${index}`} className="rounded-lg bg-slate-50 px-3 py-2">
                <div className="flex flex-col gap-1 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div className="text-sm font-medium text-slate-900">{task.title}</div>
                    {task.description ? (
                      <div className="text-xs text-slate-600">{task.description}</div>
                    ) : null}
                    {task.rationale ? (
                      <div className="mt-1 text-xs text-slate-500">{task.rationale}</div>
                    ) : null}
                  </div>
                  <div className="shrink-0 text-xs text-slate-500">
                    {task.minutes} min · {task.task_type.replace("_", " ")}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
