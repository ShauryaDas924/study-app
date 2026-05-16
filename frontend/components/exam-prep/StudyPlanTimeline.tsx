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
                    {task.learning_goal ? (
                      <div className="mt-1 text-xs text-slate-500">Goal: {task.learning_goal}</div>
                    ) : null}
                    {task.rationale ? (
                      <div className="mt-1 text-xs text-slate-500">{task.rationale}</div>
                    ) : null}
                    {task.assigned_questions?.length ? (
                      <div className="mt-2 space-y-1">
                        {task.assigned_questions.map((question) => {
                          const source = question.source || {};
                          const label = [
                            source.filename,
                            source.problem_number ? `Problem ${source.problem_number}` : null,
                            source.page ? `Page ${source.page}` : null,
                          ].filter(Boolean).join(" - ");
                          return (
                            <div key={question.recommended_question_id} className="text-xs text-slate-500">
                              Question rank {question.rank ?? "?"}{label ? ` - ${label}` : ""}
                            </div>
                          );
                        })}
                        {task.question_assignment_reason ? (
                          <div className="text-xs text-slate-500">{task.question_assignment_reason}</div>
                        ) : null}
                      </div>
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
