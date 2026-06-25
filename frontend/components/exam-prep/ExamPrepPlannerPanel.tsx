"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
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
      <div className="text-sm font-medium text-amber-800">Plan warnings</div>
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

function SectionCard({
  step,
  title,
  description,
  children,
}: {
  step: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-100 bg-white/90 p-5 shadow-sm">
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
          {step}
        </div>
        <div>
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function MetricTile({
  label,
  value,
  tone = "slate",
}: {
  label: string;
  value: ReactNode;
  tone?: "slate" | "green" | "amber" | "rose" | "blue";
}) {
  const tones = {
    slate: "bg-slate-50 text-slate-700",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    rose: "bg-pink-50 text-pink-700",
    blue: "bg-sky-50 text-sky-700",
  };

  return (
    <div className={`rounded-xl px-3 py-2 ${tones[tone]}`}>
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs opacity-80">{label}</div>
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

function formatPlanDate(value?: string | null) {
  if (!value) return "No exam date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
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
  const displayedMissingDataWarnings = useMemo(() => {
    const warnings = planQ.data?.missing_data_warnings ?? generated?.missing_data_warnings ?? [];
    return Array.from(new Set(warnings));
  }, [generated?.missing_data_warnings, planQ.data?.missing_data_warnings]);
  const planWarnings = useMemo(
    () => Array.from(new Set([...displayedWarnings, ...displayedMissingDataWarnings])),
    [displayedMissingDataWarnings, displayedWarnings]
  );
  const displayedTasks = planQ.data?.tasks ?? createTasksM.data?.tasks ?? [];
  const displayedRecommendations = planQ.data?.recommended_questions ?? generated?.recommended_questions ?? [];
  const displayedMinimumPlan = planQ.data?.minimum_plan ?? generated?.minimum_plan;
  const displayedStrongPlan = planQ.data?.strong_plan ?? generated?.strong_plan;
  const displayedScoringExplanation = planQ.data?.scoring_explanation ?? generated?.scoring_explanation ?? [];
  const displayedPlanIntensity = planQ.data?.plan_intensity ?? generated?.plan_intensity;
  const failedMaterials = (materialsQ.data ?? []).filter((material) => material.extraction_status === "failed");
  const selectedAlreadyExtracted = selectedMaterials.filter((material) => material.question_count > 0).length;
  const selectedReadyForExtraction = selectedMaterials.filter(
    (material) => material.extraction_status === "success" && !material.question_count
  ).length;
  const selectedNeedsAttention = selectedMaterials.filter((material) => material.extraction_status === "failed").length;
  const selectedWaitingForText = selectedMaterials.filter(
    (material) => material.extraction_status !== "success" && material.extraction_status !== "failed"
  ).length;
  const activePlan = (plansQ.data ?? []).find((plan) => plan.id === activePlanId) ?? plansQ.data?.find((plan) => plan.active);
  const canGenerateQuestionPlan = selectedQuestionCount > 0;

  if (!classId) {
    return (
      <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 text-sm text-slate-600">
        Select a course first to upload a syllabus and build an evidence-based prep plan.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-100 bg-white/90 p-5 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Exam Lockdown Setup</div>
            <h2 className="mt-1 text-2xl font-semibold text-slate-900">Evidence-based exam command center</h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              Upload course evidence, extract located questions, then generate an estimated cram plan tied to exact uploaded-material problems.
            </p>
          </div>
          <div className="rounded-full border border-slate-100 bg-slate-50 px-3 py-1 text-xs text-slate-600">
            Likely scope, not guaranteed prediction
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <SectionCard
            step="1"
            title="Exam Setup"
            description="Set the target, schedule, and weak areas before the planner ranks your evidence."
          >
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
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
                showGenerateButton={false}
              />

              <div className="space-y-3">
                <SyllabusUploadCard
                  classId={classId}
                  onUploaded={(out) => {
                    setSelectedSyllabusId(out.syllabus_id);
                  }}
                />

                {syllabiQ.data?.length ? (
                  <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3">
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
                              borderColor:
                                effectiveSelectedSyllabusId === syllabus.id ? "rgba(247,167,195,0.55)" : "var(--border-soft)",
                              background:
                                effectiveSelectedSyllabusId === syllabus.id ? "var(--gradient-main)" : "rgba(255,255,255,0.72)",
                              color: "var(--text-main)",
                            }}
                          >
                            <div className="truncate font-medium">{syllabus.filename}</div>
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
            </div>
          </SectionCard>

          <SectionCard
            step="2"
            title="Evidence Library"
            description="Add past exams, homework, practice banks, notes, review sheets, and answer keys. Extracted questions power recommendations."
          >
            <div className="space-y-4">
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
            </div>
          </SectionCard>

          <SectionCard
            step="3"
            title="Generate Plan"
            description="Review readiness, then create a plan from located questions and uploaded evidence."
          >
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MetricTile label="materials selected" value={selectedMaterials.length} tone="blue" />
                <MetricTile label="extracted questions" value={selectedQuestionCount} tone={selectedQuestionCount ? "green" : "amber"} />
                <MetricTile label="need extraction" value={selectedReadyForExtraction} tone={selectedReadyForExtraction ? "amber" : "slate"} />
                <MetricTile label="need attention" value={selectedNeedsAttention + selectedWaitingForText} tone={selectedNeedsAttention ? "rose" : "slate"} />
              </div>

              <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3 text-sm text-slate-600">
                <div className="font-medium text-slate-800">Readiness summary</div>
                <div className="mt-1">
                  {selectedMaterials.length} selected · {selectedAlreadyExtracted} already extracted · {selectedReadyForExtraction} need extraction
                  {selectedNeedsAttention || selectedWaitingForText
                    ? ` · ${selectedNeedsAttention + selectedWaitingForText} need attention`
                    : ""}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  Question recommendations come from persisted extracted questions. Plans are estimated from your uploaded evidence.
                </div>
              </div>

              {!canGenerateQuestionPlan ? (
                <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-800">
                  Extract questions from selected materials before generating a question-based plan.
                  <div className="mt-1 text-xs">
                    If extraction is low-confidence, the plan will show missing-data warnings instead of inventing recommendations.
                  </div>
                </div>
              ) : null}

              {failedMaterials.length ? (
                <details className="rounded-xl border border-pink-100 bg-pink-50 p-3 text-sm text-pink-700">
                  <summary className="cursor-pointer font-medium">
                    {failedMaterials.length} material{failedMaterials.length === 1 ? "" : "s"} need attention
                  </summary>
                  <div className="mt-2 space-y-1 text-xs">
                    {failedMaterials.slice(0, 8).map((material) => (
                      <div key={material.id} className="truncate">
                        {material.filename}
                        {material.parse_error ? ` - ${material.parse_error}` : ""}
                      </div>
                    ))}
                  </div>
                </details>
              ) : null}

              {generateM.error ? (
                <div className="rounded-xl border border-pink-100 bg-pink-50 p-3 text-sm text-pink-700">
                  {errorMessage(generateM.error)}
                </div>
              ) : null}

              <Warnings warnings={planWarnings} />

              {activePlanId && !planQ.isLoading && !displayedRecommendations.length ? (
                <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-800">
                  This plan has 0 recommended questions. Extract questions from selected materials, then regenerate the plan.
                </div>
              ) : null}

              <div className="flex flex-col gap-2 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-sm text-slate-500">
                  Generate a saved, active plan with ranked topics, day blocks, and exact recommended questions.
                </div>
                <Button onClick={() => generateM.mutate()} disabled={!canGenerateQuestionPlan || generateM.isPending}>
                  {generateM.isPending ? "Generating..." : "Generate Evidence-Based Plan"}
                </Button>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            step="4"
            title="Generated Plan"
            description="Use this summary to see the likely exam scope, day-by-day work, and exact questions selected from evidence."
          >
            {displayedTopics.length || displayedDays.length || displayedRecommendations.length ? (
              <div className="space-y-6">
                <div className="flex flex-col gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">
                      {activePlan?.exam_title ?? planQ.data?.exam_title ?? examTitle}
                    </div>
                    <div className="text-xs text-slate-500">
                      {formatPlanDate(activePlan?.exam_date ?? planQ.data?.exam_date ?? examDateIso)} · {displayedRecommendations.length} recommended question
                      {displayedRecommendations.length === 1 ? "" : "s"}
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
                  <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3 text-sm text-emerald-700">
                    Created {createTasksM.data.created_count} task{createTasksM.data.created_count === 1 ? "" : "s"}.
                  </div>
                ) : null}

                {displayedPlanIntensity || displayedScoringExplanation.length ? (
                  <div className="rounded-xl border border-slate-100 p-4">
                    <div className="text-sm font-semibold text-slate-900">Plan intensity and scoring</div>
                    {displayedPlanIntensity ? <div className="mt-1 text-sm text-slate-600">{displayedPlanIntensity}</div> : null}
                    {displayedScoringExplanation.length ? (
                      <div className="mt-2 grid gap-2 md:grid-cols-2">
                        {displayedScoringExplanation.map((item) => (
                          <div key={item} className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                            {item}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {displayedTopics.length ? (
                  <div className="space-y-3">
                    <div>
                      <div className="text-lg font-semibold text-slate-900">Likely exam scope</div>
                      <div className="text-sm text-slate-500">
                        Estimated topics ranked from uploaded evidence, extracted questions, target goals, and known weak areas.
                      </div>
                    </div>
                    <TopicPredictionTable topics={displayedTopics} />
                  </div>
                ) : null}

                {displayedDays.length ? (
                  <div className="space-y-3">
                    <div>
                      <div className="text-lg font-semibold text-slate-900">Day-by-day study plan</div>
                      <div className="text-sm text-slate-500">
                        Blocks include assigned questions when the plan could link them to uploaded evidence.
                      </div>
                    </div>
                    <StudyPlanTimeline days={displayedDays} />
                  </div>
                ) : null}

                {(displayedMinimumPlan || displayedStrongPlan) ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    {displayedMinimumPlan ? (
                      <div className="rounded-xl border border-slate-100 p-4">
                        <div className="font-semibold text-slate-900">{displayedMinimumPlan.label}</div>
                        <div className="mt-2 space-y-1">
                          {displayedMinimumPlan.tasks.map((task) => (
                            <div key={task} className="text-sm text-slate-600">
                              {task}
                            </div>
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
                            <div key={task} className="text-sm text-slate-600">
                              {task}
                            </div>
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
                      <div className="text-lg font-semibold text-slate-900">Recommended questions</div>
                      <div className="text-sm text-slate-500">
                        Located questions from uploaded materials. No unlocated questions are recommended.
                      </div>
                    </div>
                    <RecommendedQuestionList recommendations={displayedRecommendations} />
                  </div>
                ) : null}

                {activePlanId && displayedTasks.length ? (
                  <div className="space-y-3">
                    <div>
                      <div className="text-lg font-semibold text-slate-900">Saved Planner tasks</div>
                      <div className="text-sm text-slate-500">Mark exam-prep tasks as your study work changes.</div>
                    </div>
                    <PlanTaskList planId={activePlanId} tasks={displayedTasks} />
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-5 text-sm text-slate-600">
                Your generated plan will appear here after you extract questions and generate an evidence-based plan.
              </div>
            )}
          </SectionCard>
        </div>

        <aside className="space-y-4 xl:sticky xl:top-4 xl:self-start">
          <div className="rounded-2xl border border-slate-100 bg-white/90 p-4 shadow-sm">
            <div className="text-sm font-semibold text-slate-900">Readiness</div>
            <div className="mt-3 grid gap-2">
              <MetricTile label="selected evidence" value={selectedMaterials.length} tone="blue" />
              <MetricTile label="question recommendations available" value={selectedQuestionCount} tone={selectedQuestionCount ? "green" : "amber"} />
              <MetricTile label="failed materials" value={failedMaterials.length} tone={failedMaterials.length ? "rose" : "slate"} />
            </div>
            <div className="mt-3 text-xs text-slate-500">
              {targetScore || targetGrade ? "Target goal included" : "Target goal missing"} ·{" "}
              {weakTopics.trim() ? "weak topics included" : "weak topics optional"}
            </div>
          </div>

          <Warnings warnings={planWarnings} />

          <div className="rounded-2xl border border-slate-100 bg-white/90 p-4 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-slate-900">Saved plans</div>
              {plansQ.data?.length ? (
                <span className="rounded-full bg-slate-50 px-2 py-1 text-xs text-slate-500">{plansQ.data.length}</span>
              ) : null}
            </div>

            {plansQ.data?.length ? (
              <div className="mt-3 space-y-2">
                {plansQ.data.slice(0, 6).map((plan) => {
                  const selected = activePlanId === plan.id || (!activePlanId && plan.active);
                  return (
                    <button
                      key={plan.id}
                      onClick={() => {
                        setGenerated(null);
                        setActivePlanId(plan.id);
                      }}
                      className={[
                        "block w-full rounded-xl border px-3 py-2 text-left transition",
                        selected ? "border-pink-200 bg-pink-50/70" : "border-slate-100 bg-slate-50/60 hover:bg-slate-50",
                      ].join(" ")}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="truncate text-sm font-medium text-slate-900">{plan.exam_title}</div>
                        {plan.active ? (
                          <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">active</span>
                        ) : null}
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {formatPlanDate(plan.exam_date)} · {plan.topic_count} topics · {plan.warning_count} warnings
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-3 text-sm text-slate-500">
                Generated plans will be saved here.
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
