"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type ExamPrepPlanTask, type ExamPrepTaskStatus, type UUID } from "@/lib/api";
import { Select } from "@/components/ui/Select";

export default function PlanTaskList({
  planId,
  tasks,
}: {
  planId: UUID;
  tasks: ExamPrepPlanTask[];
}) {
  const qc = useQueryClient();

  const statusM = useMutation({
    mutationFn: ({ taskId, status }: { taskId: UUID; status: ExamPrepTaskStatus }) =>
      api.updateExamPrepTaskStatus(taskId, status),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["exam-prep-plan", planId] });
    },
  });

  if (!tasks.length) {
    return <div className="text-sm text-slate-500">No saved tasks created yet.</div>;
  }

  return (
    <div className="space-y-2">
      {tasks.map((task) => (
        <div key={task.id} className="rounded-xl border border-slate-100 p-3">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="min-w-0">
              <div className="text-sm font-medium text-slate-900">{task.title}</div>
              <div className="text-xs text-slate-500">
                {task.planned_for ? new Date(task.planned_for).toLocaleDateString() : "Unscheduled"} · {task.minutes} min
              </div>
            </div>

            {task.id ? (
              <Select
                className="md:w-36"
                value={task.status ?? "pending"}
                onChange={(e) =>
                  statusM.mutate({
                    taskId: task.id as UUID,
                    status: e.target.value as ExamPrepTaskStatus,
                  })
                }
              >
                <option value="pending">Pending</option>
                <option value="done">Done</option>
                <option value="skipped">Skipped</option>
              </Select>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}
