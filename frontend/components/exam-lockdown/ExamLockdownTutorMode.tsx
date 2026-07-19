"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type ExamLockdownSession,
  type ExamPrepPlan,
  type ExamPrepRecommendedQuestion,
  type UUID,
} from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import ExamCoachResponse from "@/components/exam-lockdown/ExamCoachResponse";
import LockdownProgressPanel from "@/components/exam-lockdown/LockdownProgressPanel";

type QuestionFilter = "all" | "today" | "unattempted" | "completed";

function sameDate(a?: string | null, b?: Date) {
  if (!a || !b) return false;
  return new Date(a).toISOString().slice(0, 10) === b.toISOString().slice(0, 10);
}

function formatDateTime(value?: string | null) {
  if (!value) return "No exam date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function typeLabel(value?: string | null) {
  return value ? value.replace(/_/g, " ") : "uploaded evidence";
}

function sourceLine(rec?: ExamPrepRecommendedQuestion | null) {
  const q = rec?.question;
  const material = q?.material;
  const ref = q?.source_ref_json || {};
  return [
    material?.filename,
    material?.material_type ? typeLabel(material.material_type) : null,
    q?.problem_number ? `Problem ${q.problem_number}` : null,
    typeof ref.page === "number" || typeof ref.page === "string" ? `Page ${ref.page}` : null,
    q?.status === "stale" ? "stale source" : null,
  ].filter(Boolean).join(" - ");
}

function confidenceLabel(value?: number | null) {
  if (typeof value !== "number") return "confidence pending";
  return `${Math.round(value * 100)}% confidence`;
}

function Badge({
  children,
  tone = "slate",
}: {
  children: ReactNode;
  tone?: "slate" | "green" | "amber" | "rose" | "blue";
}) {
  const tones = {
    slate: "border-slate-100 bg-slate-50 text-slate-600",
    green: "border-emerald-100 bg-emerald-50 text-emerald-700",
    amber: "border-amber-100 bg-amber-50 text-amber-700",
    rose: "border-pink-100 bg-pink-50 text-pink-700",
    blue: "border-sky-100 bg-sky-50 text-sky-700",
  };

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

function statusTone(status?: string): "slate" | "green" | "amber" | "rose" | "blue" {
  if (status === "completed") return "green";
  if (status === "skipped") return "amber";
  if (status === "attempted") return "blue";
  return "slate";
}

export default function ExamLockdownTutorMode() {
  const classId = useStore((s) => s.selectedClassId);
  const qc = useQueryClient();
  const [selectedRecId, setSelectedRecId] = useState<UUID | null>(null);
  const [session, setSession] = useState<ExamLockdownSession | null>(null);
  const [userQuestion, setUserQuestion] = useState("");
  const [userAttempt, setUserAttempt] = useState("");
  const [confidence, setConfidence] = useState(3);
  const [coachMarkdown, setCoachMarkdown] = useState("");
  const [questionFilter, setQuestionFilter] = useState<QuestionFilter>("all");

  const plansQ = useQuery({
    queryKey: ["exam-prep-plans", classId, "active"],
    queryFn: () => api.listExamPrepPlans(classId, true),
    enabled: Boolean(classId),
  });

  const newestActivePlan = useMemo(
    () => [...(plansQ.data ?? [])].sort((a, b) => new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime())[0],
    [plansQ.data]
  );
  const effectivePlanId = newestActivePlan?.id ?? null;

  const planQ = useQuery({
    queryKey: ["exam-prep-plan", effectivePlanId],
    queryFn: () => api.getExamPrepPlan(effectivePlanId as UUID),
    enabled: Boolean(effectivePlanId),
  });

  const planQuestionsQ = useQuery({
    queryKey: ["exam-prep-plan-questions", effectivePlanId],
    queryFn: () => api.getExamPrepPlanQuestions(effectivePlanId as UUID),
    enabled: Boolean(effectivePlanId),
  });

  const progressQ = useQuery({
    queryKey: ["exam-lockdown-progress", effectivePlanId],
    queryFn: () => api.getExamLockdownProgress(effectivePlanId as UUID),
    enabled: Boolean(effectivePlanId),
  });

  const sessionM = useMutation({
    mutationFn: (plan: ExamPrepPlan) => api.createExamLockdownSession({ class_id: plan.class_id, plan_id: plan.id }),
    onSuccess: setSession,
  });

  useEffect(() => {
    if (planQ.data && session?.plan_id !== planQ.data.id && !sessionM.isPending) {
      sessionM.mutate(planQ.data);
    }
  }, [planQ.data, session?.plan_id, sessionM]);

  const plan = planQ.data;
  const recommendations = useMemo(() => {
    const direct = planQuestionsQ.data ?? [];
    if (direct.length) return direct;
    return plan?.recommended_questions ?? [];
  }, [plan?.recommended_questions, planQuestionsQ.data]);

  const selectedRec = useMemo(
    () => recommendations.find((rec) => rec.id === selectedRecId) ?? null,
    [recommendations, selectedRecId]
  );

  const todayBlock = useMemo(() => {
    const today = new Date();
    return plan?.plan_days?.find((day) => sameDate(day.date, today)) ?? plan?.plan_days?.[0];
  }, [plan?.plan_days]);

  const todayQuestionIds = useMemo(() => {
    const ids = new Set<UUID>();
    for (const task of todayBlock?.tasks ?? []) {
      for (const id of task.recommended_question_ids ?? []) ids.add(id);
      for (const question of task.assigned_questions ?? []) ids.add(question.recommended_question_id);
    }
    return ids;
  }, [todayBlock?.tasks]);

  const filteredRecommendations = useMemo(() => {
    return recommendations.filter((rec) => {
      if (questionFilter === "today") return todayQuestionIds.has(rec.id);
      if (questionFilter === "unattempted") return rec.status === "recommended";
      if (questionFilter === "completed") return rec.status === "completed";
      return true;
    });
  }, [questionFilter, recommendations, todayQuestionIds]);

  const tutorM = useMutation({
    mutationFn: () => {
      if (!classId || !plan || !selectedRec) throw new Error("Choose a recommended question first.");
      return api.callExamLockdownTutor({
        class_id: classId,
        plan_id: plan.id,
        recommended_question_id: selectedRec.id,
        user_question: userQuestion || null,
        user_attempt: userAttempt || null,
      });
    },
    onSuccess: (data) => setCoachMarkdown(data.response_markdown),
  });

  const saveM = useMutation({
    mutationFn: (status: "attempted" | "completed" | "skipped") => {
      if (!classId || !plan || !selectedRec) throw new Error("Choose a recommended question first.");
      return api.saveExamLockdownAttempt({
        class_id: classId,
        plan_id: plan.id,
        recommended_question_id: selectedRec.id,
        session_id: session?.id ?? null,
        user_answer_text: userAttempt || null,
        confidence,
        tutor_feedback_json: coachMarkdown ? { response_markdown: coachMarkdown } : {},
        status,
      });
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["exam-lockdown-progress", effectivePlanId] });
      await qc.invalidateQueries({ queryKey: ["exam-prep-plan", effectivePlanId] });
      await qc.invalidateQueries({ queryKey: ["exam-prep-plan-questions", effectivePlanId] });
    },
  });

  function chooseRecommendation(rec: ExamPrepRecommendedQuestion) {
    setSelectedRecId(rec.id);
    setCoachMarkdown("");
  }

  if (!classId) {
    return <div className="text-sm text-slate-500">Select a course first.</div>;
  }

  if (plansQ.isLoading) {
    return <div className="text-sm text-slate-500">Loading Exam Lockdown plans...</div>;
  }

  if (!plansQ.data?.length) {
    return (
      <div className="rounded-xl border border-amber-100 bg-amber-50 p-4 text-sm text-amber-800">
        No active Exam Lockdown plan yet. <Link href="/planner" className="underline">Create one in Planner</Link>.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-2xl border border-slate-100 bg-white/90 p-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Exam Lockdown</div>
              <h2 className="mt-1 text-2xl font-semibold text-slate-900">{plan?.exam_title ?? "Exam prep plan"}</h2>
              <div className="mt-1 text-sm text-slate-500">{formatDateTime(plan?.exam_date)}</div>
              <p className="mt-3 max-w-3xl text-sm text-slate-600">
                Work from your active evidence-based plan. Recommendations are estimated from uploaded materials and linked to located questions.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge tone="blue">{recommendations.length} recommended questions</Badge>
              <Badge>likely exam scope</Badge>
            </div>
          </div>
        </div>
        <LockdownProgressPanel progress={progressQ.data} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-100 bg-white/90 p-4 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-900">Today&apos;s block</div>
                <div className="text-xs text-slate-500">{todayBlock?.date ?? "No date assigned"}</div>
              </div>
              {todayBlock ? (
                <div className="rounded-full bg-slate-50 px-2 py-1 text-xs text-slate-500">
                  {todayBlock.tasks.reduce((sum, task) => sum + Number(task.minutes || 0), 0)} min
                </div>
              ) : null}
            </div>

            {todayBlock ? (
              <div className="mt-3 space-y-2">
                {todayBlock.tasks.map((task, index) => (
                  <div key={`${todayBlock.date}-${index}`} className="rounded-xl border border-slate-100 bg-slate-50/70 px-3 py-3">
                    <div className="text-sm font-medium text-slate-900">{task.title}</div>
                    <div className="mt-1 text-xs text-slate-500">{task.minutes} min · {task.task_type.replace("_", " ")}</div>
                    {task.learning_goal ? <div className="mt-2 text-xs text-slate-600">Goal: {task.learning_goal}</div> : null}
                    {task.assigned_questions?.length ? (
                      <div className="mt-3 space-y-1">
                        {task.assigned_questions.map((question) => {
                          const rec = recommendations.find((item) => item.id === question.recommended_question_id);
                          const source = question.source || {};
                          const label = [
                            `Rank ${question.rank ?? rec?.rank ?? "?"}`,
                            source.filename,
                            source.problem_number ? `Problem ${source.problem_number}` : null,
                          ].filter(Boolean).join(" - ");
                          return (
                            <button
                              key={question.recommended_question_id}
                              onClick={() => {
                                if (rec) chooseRecommendation(rec);
                              }}
                              className="block w-full rounded-lg bg-white px-2 py-1 text-left text-xs text-slate-600 transition hover:bg-slate-100"
                            >
                              {label}
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-3 text-sm text-slate-500">
                No day block is attached to this plan yet.
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-100 bg-white/90 p-4 shadow-sm">
            <div className="text-sm font-semibold text-slate-900">Likely exam scope</div>
            <div className="mt-3 space-y-2">
              {(plan?.topics ?? []).slice(0, 7).map((topic, index) => (
                <div key={topic.id ?? topic.topic_name} className="rounded-xl bg-slate-50 px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0 truncate text-sm font-medium text-slate-800">
                      {index + 1}. {topic.topic_name}
                    </div>
                    <Badge>{topic.confidence}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">{topic.recommended_study_action}</div>
                </div>
              ))}
              {!(plan?.topics ?? []).length ? (
                <div className="text-sm text-slate-500">Ranked topics will appear after a plan is generated.</div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="min-w-0 space-y-4">
          <div className="rounded-2xl border border-slate-100 bg-white/90 p-4 shadow-sm">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">Recommended questions</div>
                  <div className="text-xs text-slate-500">{recommendations.length} linked to this plan</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {(["all", "today", "unattempted", "completed"] as QuestionFilter[]).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setQuestionFilter(filter)}
                    className={[
                      "rounded-full border px-3 py-1 text-xs capitalize transition",
                      questionFilter === filter ? "border-pink-200 bg-pink-50 text-pink-700" : "border-slate-100 bg-slate-50 text-slate-600",
                    ].join(" ")}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4 max-h-[620px] space-y-2 overflow-y-auto pr-1">
              {filteredRecommendations.length ? (
                filteredRecommendations.map((rec) => {
                  const selected = selectedRec?.id === rec.id;
                  const q = rec.question;
                  return (
                    <button
                      key={rec.id}
                      onClick={() => chooseRecommendation(rec)}
                      className={[
                        "block w-full rounded-xl border p-3 text-left transition",
                        selected ? "border-pink-200 bg-pink-50/70 shadow-sm" : "border-slate-100 bg-slate-50/70 hover:bg-slate-50",
                      ].join(" ")}
                    >
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge tone="blue">Rank {rec.rank}</Badge>
                        {q?.topic_name ? <Badge>{q.topic_name}</Badge> : null}
                        <Badge tone={statusTone(rec.status)}>{rec.status}</Badge>
                      </div>
                      <div className="mt-2 text-xs font-medium text-slate-700">{sourceLine(rec) || "Uploaded question"}</div>
                      {q?.prompt_text ? <div className="mt-2 line-clamp-3 text-sm leading-5 text-slate-600">{q.prompt_text}</div> : null}
                      {rec.why_selected ? <div className="mt-2 line-clamp-2 text-xs text-slate-500">{rec.why_selected}</div> : null}
                    </button>
                  );
                })
              ) : recommendations.length ? (
                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-3 text-sm text-slate-500">
                  No questions match this filter.
                </div>
              ) : (
                <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-800">
                  No recommended questions are linked to this plan. Go to Planner, extract questions from selected materials, then regenerate the plan.
                  <div className="mt-1 text-xs">0 recommendations found for this plan.</div>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-100 bg-white/90 p-5 shadow-sm">
            {selectedRec ? (
              <div className="space-y-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    {selectedRec.question?.topic_name ? <Badge>{selectedRec.question.topic_name}</Badge> : null}
                    <Badge tone={statusTone(selectedRec.status)}>{selectedRec.status}</Badge>
                    <Badge>{confidenceLabel(selectedRec.confidence)}</Badge>
                  </div>
                  <h3 className="mt-3 text-lg font-semibold text-slate-900">Selected question</h3>
                  <div className="mt-1 break-words text-sm text-slate-500">{sourceLine(selectedRec) || "Uploaded material question"}</div>
                </div>

                {selectedRec.question?.prompt_text ? (
                  <div className="max-h-[360px] overflow-y-auto whitespace-pre-wrap break-words rounded-xl border border-slate-100 bg-slate-50/70 p-4 text-sm leading-6 text-slate-800">
                    {selectedRec.question.prompt_text}
                  </div>
                ) : null}

                {selectedRec.why_selected ? (
                  <div className="rounded-xl border border-slate-100 bg-slate-50/70 px-4 py-3 text-sm leading-6 text-slate-600">
                    <span className="font-medium text-slate-900">Why selected: </span>
                    <span className="break-words">{selectedRec.why_selected}</span>
                  </div>
                ) : null}

                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_120px]">
                  <div className="min-w-0">
                    <div className="mb-1 text-xs text-slate-500">Optional question for the coach</div>
                    <Input value={userQuestion} onChange={(e) => setUserQuestion(e.target.value)} placeholder="What should I notice first?" />
                  </div>
                  <div>
                    <div className="mb-1 text-xs text-slate-500">Confidence</div>
                    <Input type="number" min={1} max={5} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} />
                  </div>
                </div>

                <div>
                  <div className="mb-1 text-xs text-slate-500">Your attempt or setup</div>
                  <textarea
                    value={userAttempt}
                    onChange={(e) => setUserAttempt(e.target.value)}
                    className="w-full app-input min-h-28 px-3 py-2 text-sm"
                    placeholder="Paste your setup, answer, or what you tried."
                  />
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => tutorM.mutate()} disabled={!selectedRec || tutorM.isPending}>
                    {tutorM.isPending ? "Coaching..." : "Coach This Question"}
                  </Button>
                  <Button variant="secondary" onClick={() => saveM.mutate("attempted")} disabled={!selectedRec || saveM.isPending}>
                    Save Attempt
                  </Button>
                  <Button
                    variant="secondary"
                    className="border-emerald-100 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                    onClick={() => saveM.mutate("completed")}
                    disabled={!selectedRec || saveM.isPending}
                  >
                    Mark Complete
                  </Button>
                  <Button variant="ghost" onClick={() => saveM.mutate("skipped")} disabled={!selectedRec || saveM.isPending}>
                    Skip
                  </Button>
                </div>

                {tutorM.error ? <div className="text-sm text-pink-600">{String(tutorM.error)}</div> : null}
                {saveM.error ? <div className="text-sm text-pink-600">{String(saveM.error)}</div> : null}
                {saveM.data ? <div className="text-sm text-slate-500">Saved. Pitfalls captured: {saveM.data.pitfalls_saved}</div> : null}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-6 text-center">
                <div className="text-sm font-semibold text-slate-900">Choose a recommended question</div>
                <div className="mt-1 text-sm text-slate-500">
                  Pick one from the list to see the full prompt, source context, and exam-coach controls.
                </div>
              </div>
            )}
          </div>

          <ExamCoachResponse markdown={selectedRec ? coachMarkdown : ""} />
        </div>
      </div>
    </div>
  );
}