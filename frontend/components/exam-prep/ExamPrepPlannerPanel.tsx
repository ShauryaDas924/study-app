"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type ExamPrepIntensity,
  type GenerateExamPrepPlanResponse,
  type UUID,
} from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/Button";
import SyllabusUploadCard from "@/components/exam-prep/SyllabusUploadCard";
import ExamPrepForm from "@/components/exam-prep/ExamPrepForm";
import TopicPredictionTable from "@/components/exam-prep/TopicPredictionTable";
import StudyPlanTimeline from "@/components/exam-prep/StudyPlanTimeline";
import PlanTaskList from "@/components/exam-prep/PlanTaskList";

function defaultExamDate() {
  const date = new Date();
  date.setDate(date.getDate() + 14);
  return date.toISOString().slice(0, 16);
}

function Warnings({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null;

  return (
    <div className="rounded-xl border border-amber-100 bg-amber-50 p-3">
      <div className="text-sm font-medium text-amber-800">Evidence notes</div>
      <div className="mt-1 space-y-1">
        {warnings.map((warning) => (
          <div key={warning} className="text-xs text-amber-700">
            {warning}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ExamPrepPlannerPanel() {
  const classId = useStore((s) => s.selectedClassId);
  const qc = useQueryClient();

  const [selectedSyllabusId, setSelectedSyllabusId] = useState<UUID>("" as UUID);
  const [examTitle, setExamTitle] = useState("Midterm");
  const [examDateIso, setExamDateIso] = useState(defaultExamDate);
  const [minutes, setMinutes] = useState(60);
  const [intensity, setIntensity] = useState<ExamPrepIntensity>("balanced");
  const [activePlanId, setActivePlanId] = useState<UUID | null>(null);
  const [generated, setGenerated] = useState<GenerateExamPrepPlanResponse | null>(null);

  const syllabiQ = useQuery({
    queryKey: ["exam-prep-syllabi", classId],
    queryFn: () => api.listExamPrepSyllabi(classId),
    enabled: Boolean(classId),
  });

  const plansQ = useQuery({
    queryKey: ["exam-prep-plans", classId],
    queryFn: () => api.listExamPrepPlans(classId),
    enabled: Boolean(classId),
  });

  const planQ = useQuery({
    queryKey: ["exam-prep-plan", activePlanId],
    queryFn: () => api.getExamPrepPlan(activePlanId as UUID),
    enabled: Boolean(activePlanId),
  });

  useEffect(() => {
    if (!selectedSyllabusId && syllabiQ.data?.length) {
      setSelectedSyllabusId(syllabiQ.data[0].id);
    }
  }, [selectedSyllabusId, syllabiQ.data]);

  const generateM = useMutation({
    mutationFn: () => {
      if (!classId) throw new Error("Select a course first.");
      if (!selectedSyllabusId) throw new Error("Upload or select a syllabus first.");

      return api.generateExamPrepPlan({
        class_id: classId,
        syllabus_id: selectedSyllabusId,
        exam_title: examTitle,
        exam_date_iso: new Date(examDateIso).toISOString(),
        available_minutes_per_day: minutes,
        intensity,
      });
    },
    onSuccess: async (data) => {
      setGenerated(data);
      setActivePlanId(data.exam_prep_plan_id);
      await qc.invalidateQueries({ queryKey: ["exam-prep-plans", classId] });
      await qc.invalidateQueries({ queryKey: ["exam-prep-plan", data.exam_prep_plan_id] });
    },
  });

  const createTasksM = useMutation({
    mutationFn: () => {
      if (!activePlanId) throw new Error("Generate or open a plan first.");
      return api.createExamPrepTasks(activePlanId, false);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["exam-prep-plan", activePlanId] });
    },
  });

  const displayedTopics = planQ.data?.topics ?? generated?.topics ?? [];
  const displayedDays = planQ.data?.plan_days ?? generated?.plan_days ?? [];
  const displayedWarnings = useMemo(() => {
    const warnings = planQ.data?.warnings ?? generated?.warnings ?? [];
    return Array.from(new Set(warnings));
  }, [generated?.warnings, planQ.data?.warnings]);
  const displayedTasks = planQ.data?.tasks ?? createTasksM.data?.tasks ?? [];

  if (!classId) {
    return (
      <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 text-sm text-slate-600">
        Select a course first to upload a syllabus and build an evidence-based prep plan.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.4fr]">
        <div className="space-y-4">
          <SyllabusUploadCard
            classId={classId}
            onUploaded={(out) => {
              setSelectedSyllabusId(out.syllabus_id);
            }}
          />

          {syllabiQ.data?.length ? (
            <div className="rounded-xl border border-slate-100 p-3">
              <div className="text-sm font-medium text-slate-900">Uploaded syllabi</div>
              <div className="mt-2 space-y-2">
                {syllabiQ.data.slice(0, 4).map((syllabus) => (
                  <button
                    key={syllabus.id}
                    onClick={() => setSelectedSyllabusId(syllabus.id)}
                    className="block w-full rounded-lg border px-3 py-2 text-left text-sm transition"
                    style={{
                      borderColor: selectedSyllabusId === syllabus.id ? "rgba(247,167,195,0.55)" : "var(--border-soft)",
                      background: selectedSyllabusId === syllabus.id ? "var(--gradient-main)" : "rgba(255,255,255,0.72)",
                      color: "var(--text-main)",
                    }}
                  >
                    <div className="font-medium">{syllabus.filename}</div>
                    <div className="text-xs opacity-70">
                      {syllabus.parsed_summary.schedule_topics_count ?? 0} schedule topics found
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-4">
          <ExamPrepForm
            syllabi={syllabiQ.data ?? []}
            selectedSyllabusId={selectedSyllabusId}
            setSelectedSyllabusId={(id) => setSelectedSyllabusId(id as UUID)}
            examTitle={examTitle}
            setExamTitle={setExamTitle}
            examDateIso={examDateIso}
            setExamDateIso={setExamDateIso}
            minutes={minutes}
            setMinutes={setMinutes}
            intensity={intensity}
            setIntensity={setIntensity}
            onGenerate={() => generateM.mutate()}
            isGenerating={generateM.isPending}
          />

          {generateM.error ? (
            <div className="rounded-xl border border-pink-100 bg-pink-50 p-3 text-sm text-pink-700">
              {String(generateM.error)}
            </div>
          ) : null}

          <Warnings warnings={displayedWarnings} />
        </div>
      </div>

      {plansQ.data?.length ? (
        <div>
          <div className="mb-2 text-sm font-medium text-slate-900">Saved exam prep plans</div>
          <div className="flex flex-wrap gap-2">
            {plansQ.data.slice(0, 5).map((plan) => (
              <button
                key={plan.id}
                onClick={() => {
                  setGenerated(null);
                  setActivePlanId(plan.id);
                }}
                className="rounded-full border border-slate-100 bg-slate-50 px-3 py-1 text-xs text-slate-700"
              >
                {plan.exam_title} · {new Date(plan.exam_date).toLocaleDateString()}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {displayedTopics.length ? (
        <div className="space-y-3">
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="text-lg font-semibold text-slate-900">Likely Exam Scope</div>
              <div className="text-sm text-slate-500">
                Estimated topics ranked from syllabus evidence and available course concepts.
              </div>
            </div>
            {activePlanId ? (
              <Button variant="secondary" onClick={() => createTasksM.mutate()} disabled={createTasksM.isPending}>
                {createTasksM.isPending ? "Creating..." : "Create Planner Tasks"}
              </Button>
            ) : null}
          </div>

          {createTasksM.error ? (
            <div className="rounded-xl border border-pink-100 bg-pink-50 p-3 text-sm text-pink-700">
              {String(createTasksM.error)}
            </div>
          ) : null}

          {createTasksM.data ? (
            <div className="text-sm text-slate-600">
              Created {createTasksM.data.created_count} task{createTasksM.data.created_count === 1 ? "" : "s"}.
            </div>
          ) : null}

          <TopicPredictionTable topics={displayedTopics} />
        </div>
      ) : null}

      {displayedDays.length ? (
        <div className="space-y-3">
          <div>
            <div className="text-lg font-semibold text-slate-900">Day-by-Day Study Plan</div>
            <div className="text-sm text-slate-500">
              Tasks stay within your selected daily study minutes.
            </div>
          </div>
          <StudyPlanTimeline days={displayedDays} />
        </div>
      ) : null}

      {activePlanId && displayedTasks.length ? (
        <div className="space-y-3">
          <div>
            <div className="text-lg font-semibold text-slate-900">Saved Planner Tasks</div>
            <div className="text-sm text-slate-500">Mark exam-prep tasks as your study work changes.</div>
          </div>
          <PlanTaskList planId={activePlanId} tasks={displayedTasks} />
        </div>
      ) : null}
    </div>
  );
}
