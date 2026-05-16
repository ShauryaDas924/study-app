"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type ExamPrepIntensity,
  type ExamPrepMaterial,
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
import ExamPrepMaterialUploader from "@/components/exam-prep/ExamPrepMaterialUploader";
import ExamPrepMaterialsList from "@/components/exam-prep/ExamPrepMaterialsList";
import RecommendedQuestionList from "@/components/exam-prep/RecommendedQuestionList";

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

function errorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  try {
    const parsed = JSON.parse(message);
    return parsed?.detail || message;
  } catch {
    return message;
  }
}

export default function ExamPrepPlannerPanel() {
  const classId = useStore((s) => s.selectedClassId);
  const qc = useQueryClient();

  const [selectedSyllabusId, setSelectedSyllabusId] = useState<UUID>("" as UUID);
  const [examTitle, setExamTitle] = useState("Midterm");
  const [examDateIso, setExamDateIso] = useState(defaultExamDate);
  const [minutes, setMinutes] = useState(60);
  const [intensity, setIntensity] = useState<ExamPrepIntensity>("balanced");
  const [targetScore, setTargetScore] = useState("");
  const [targetGrade, setTargetGrade] = useState("");
  const [currentScores, setCurrentScores] = useState("");
  const [weakTopics, setWeakTopics] = useState("");
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<UUID[]>([]);
  const [materialSelectionTouched, setMaterialSelectionTouched] = useState(false);
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

  const materialsQ = useQuery({
    queryKey: ["exam-prep-materials", classId],
    queryFn: () => api.listExamPrepMaterials(classId),
    enabled: Boolean(classId),
  });

  const planQ = useQuery({
    queryKey: ["exam-prep-plan", activePlanId],
    queryFn: () => api.getExamPrepPlan(activePlanId as UUID),
    enabled: Boolean(activePlanId),
  });

  const effectiveSelectedSyllabusId = selectedSyllabusId || syllabiQ.data?.[0]?.id || "";
  const allMaterialIds = useMemo(() => (materialsQ.data ?? []).map((material) => material.id), [materialsQ.data]);
  const effectiveSelectedMaterialIds = materialSelectionTouched ? selectedMaterialIds : allMaterialIds;
  const selectedMaterials = useMemo(
    () => (materialsQ.data ?? []).filter((material) => effectiveSelectedMaterialIds.includes(material.id)),
    [effectiveSelectedMaterialIds, materialsQ.data]
  );
  const selectedQuestionCount = selectedMaterials.reduce((total, material) => total + Number(material.question_count || 0), 0);

  function parseCurrentScores() {
    const text = currentScores.trim();
    return text ? { notes: text } : {};
  }

  function parseWeakTopics() {
    return weakTopics
      .split(",")
      .map((topic) => topic.trim())
      .filter(Boolean);
  }

  const generateM = useMutation({
    mutationFn: () => {
      if (!classId) throw new Error("Select a course first.");

      return api.generateExamPrepPlan({
        class_id: classId,
        syllabus_id: effectiveSelectedSyllabusId || null,
        exam_title: examTitle,
        exam_date_iso: new Date(examDateIso).toISOString(),
        available_minutes_per_day: minutes,
        minutes_per_day: minutes,
        intensity,
        target_score: targetScore.trim() ? Number(targetScore) : null,
        target_grade: targetGrade.trim() || null,
        current_scores_json: parseCurrentScores(),
        weak_topics: parseWeakTopics(),
        selected_material_ids: effectiveSelectedMaterialIds,
        active: true,
      });
    },
    onSuccess: async (data) => {
      setGenerated(data);
      setActivePlanId(data.exam_prep_plan_id);
      await qc.invalidateQueries({ queryKey: ["exam-prep-plans", classId] });
      await qc.invalidateQueries({ queryKey: ["exam-prep-plans", classId, "active"] });
      await qc.invalidateQueries({ queryKey: ["exam-prep-plan", data.exam_prep_plan_id] });
      await qc.invalidateQueries({ queryKey: ["exam-prep-plan-questions", data.exam_prep_plan_id] });
      await qc.invalidateQueries({ queryKey: ["exam-prep-materials", classId] });
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
  const displayedRecommendations = planQ.data?.recommended_questions ?? generated?.recommended_questions ?? [];
  const displayedMinimumPlan = planQ.data?.minimum_plan ?? generated?.minimum_plan;
  const displayedStrongPlan = planQ.data?.strong_plan ?? generated?.strong_plan;
  const displayedScoringExplanation = planQ.data?.scoring_explanation ?? generated?.scoring_explanation ?? [];
  const displayedPlanIntensity = planQ.data?.plan_intensity ?? generated?.plan_intensity;
  const failedMaterials = (materialsQ.data ?? []).filter((material) => material.extraction_status === "failed");

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

          <ExamPrepMaterialUploader
            classId={classId}
            onUploaded={(material: ExamPrepMaterial) => {
              if (materialSelectionTouched) {
                setSelectedMaterialIds((ids) => Array.from(new Set([...ids, material.id])));
              }
            }}
          />

          <ExamPrepMaterialsList
            classId={classId}
            materials={materialsQ.data ?? []}
            selectedIds={effectiveSelectedMaterialIds}
            setSelectedIds={(ids) => {
              setMaterialSelectionTouched(true);
              setSelectedMaterialIds(ids);
            }}
          />

          {syllabiQ.data?.length ? (
            <div className="rounded-xl border border-slate-100 p-3">
              <div className="text-sm font-medium text-slate-900">Uploaded syllabi</div>
              <div className="mt-2 space-y-2">
                {syllabiQ.data.slice(0, 4).map((syllabus) => {
                  const topicCount =
                    syllabus.parsed_summary.accepted_topics_count ??
                    Number(syllabus.parsed_summary.study_topics_count ?? 0) +
                      Number(syllabus.parsed_summary.schedule_topics_count ?? 0);
                  return (
                    <button
                      key={syllabus.id}
                      onClick={() => setSelectedSyllabusId(syllabus.id)}
                      className="block w-full rounded-lg border px-3 py-2 text-left text-sm transition"
                      style={{
                        borderColor: effectiveSelectedSyllabusId === syllabus.id ? "rgba(247,167,195,0.55)" : "var(--border-soft)",
                        background: effectiveSelectedSyllabusId === syllabus.id ? "var(--gradient-main)" : "rgba(255,255,255,0.72)",
                        color: "var(--text-main)",
                      }}
                    >
                      <div className="font-medium">{syllabus.filename}</div>
                      <div className="text-xs opacity-70">
                        {topicCount} study topic{topicCount === 1 ? "" : "s"} found
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-4">
          <ExamPrepForm
            syllabi={syllabiQ.data ?? []}
            selectedSyllabusId={effectiveSelectedSyllabusId as UUID}
            setSelectedSyllabusId={(id) => setSelectedSyllabusId(id as UUID)}
            examTitle={examTitle}
            setExamTitle={setExamTitle}
            examDateIso={examDateIso}
            setExamDateIso={setExamDateIso}
            minutes={minutes}
            setMinutes={setMinutes}
            intensity={intensity}
            setIntensity={setIntensity}
            targetScore={targetScore}
            setTargetScore={setTargetScore}
            targetGrade={targetGrade}
            setTargetGrade={setTargetGrade}
            currentScores={currentScores}
            setCurrentScores={setCurrentScores}
            weakTopics={weakTopics}
            setWeakTopics={setWeakTopics}
            onGenerate={() => generateM.mutate()}
            isGenerating={generateM.isPending}
          />

          {generateM.error ? (
            <div className="rounded-xl border border-pink-100 bg-pink-50 p-3 text-sm text-pink-700">
              {errorMessage(generateM.error)}
            </div>
          ) : null}

          <Warnings warnings={displayedWarnings} />
          {selectedMaterials.length > 0 && selectedQuestionCount === 0 ? (
            <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-800">
              Extract questions from selected materials before generating a question-based plan.
              <div className="mt-1 text-xs">
                Plans are estimated from your uploaded evidence. Question recommendations require extracted questions.
              </div>
            </div>
          ) : null}
          {failedMaterials.length ? (
            <div className="rounded-xl border border-pink-100 bg-pink-50 p-3 text-sm text-pink-700">
              {failedMaterials.length} material{failedMaterials.length === 1 ? "" : "s"} had extraction issues. Re-upload or use clearer PDF/TXT materials before generating.
            </div>
          ) : null}
          {activePlanId && !planQ.isLoading && !displayedRecommendations.length ? (
            <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-800">
              This plan has 0 recommended questions. Extract questions from selected materials, then regenerate the plan.
            </div>
          ) : null}
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
                {plan.exam_title} - {new Date(plan.exam_date).toLocaleDateString()}
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

      {(displayedPlanIntensity || displayedScoringExplanation.length) ? (
        <div className="rounded-xl border border-slate-100 p-4">
          <div className="text-sm font-semibold text-slate-900">Plan scoring</div>
          {displayedPlanIntensity ? <div className="mt-1 text-sm text-slate-600">{displayedPlanIntensity}</div> : null}
          {displayedScoringExplanation.length ? (
            <div className="mt-2 space-y-1">
              {displayedScoringExplanation.map((item) => (
                <div key={item} className="text-xs text-slate-500">{item}</div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {(displayedMinimumPlan || displayedStrongPlan) ? (
        <div className="grid gap-3 md:grid-cols-2">
          {displayedMinimumPlan ? (
            <div className="rounded-xl border border-slate-100 p-4">
              <div className="font-semibold text-slate-900">{displayedMinimumPlan.label}</div>
              <div className="mt-2 space-y-1">
                {displayedMinimumPlan.tasks.map((task) => (
                  <div key={task} className="text-sm text-slate-600">{task}</div>
                ))}
              </div>
              {displayedMinimumPlan.note ? <div className="mt-2 text-xs text-slate-500">{displayedMinimumPlan.note}</div> : null}
            </div>
          ) : null}

          {displayedStrongPlan ? (
            <div className="rounded-xl border border-slate-100 p-4">
              <div className="font-semibold text-slate-900">{displayedStrongPlan.label}</div>
              <div className="mt-2 space-y-1">
                {displayedStrongPlan.tasks.map((task) => (
                  <div key={task} className="text-sm text-slate-600">{task}</div>
                ))}
              </div>
              {displayedStrongPlan.note ? <div className="mt-2 text-xs text-slate-500">{displayedStrongPlan.note}</div> : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {displayedRecommendations.length ? (
        <div className="space-y-3">
          <div>
            <div className="text-lg font-semibold text-slate-900">Recommended Questions</div>
            <div className="text-sm text-slate-500">
              These are located questions from uploaded materials. No unlocated questions are recommended.
            </div>
          </div>
          <RecommendedQuestionList recommendations={displayedRecommendations} />
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
