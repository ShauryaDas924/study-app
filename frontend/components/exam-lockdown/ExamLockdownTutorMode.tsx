"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
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

function sameDate(a?: string | null, b?: Date) {
  if (!a || !b) return false;
  return new Date(a).toISOString().slice(0, 10) === b.toISOString().slice(0, 10);
}

function sourceLine(rec?: ExamPrepRecommendedQuestion | null) {
  const q = rec?.question;
  const material = q?.material;
  const ref = q?.source_ref_json || {};
  return [
    material?.filename,
    material?.material_type?.replace(/_/g, " "),
    q?.problem_number ? `Problem ${q.problem_number}` : null,
    typeof ref.page === "number" || typeof ref.page === "string" ? `Page ${ref.page}` : null,
    q?.topic_name,
  ].filter(Boolean).join(" - ");
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

  const plansQ = useQuery({
    queryKey: ["exam-prep-plans", classId, "active"],
    queryFn: () => api.listExamPrepPlans(classId, true),
    enabled: Boolean(classId),
  });

  const effectivePlanId = plansQ.data?.[0]?.id ?? null;

  const planQ = useQuery({
    queryKey: ["exam-prep-plan", effectivePlanId],
    queryFn: () => api.getExamPrepPlan(effectivePlanId as UUID),
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
  const recommendations = useMemo(() => plan?.recommended_questions ?? [], [plan?.recommended_questions]);
  const selectedRec = useMemo(
    () => recommendations.find((rec) => rec.id === selectedRecId) ?? recommendations[0],
    [recommendations, selectedRecId]
  );

  const todayBlock = useMemo(() => {
    const today = new Date();
    return plan?.plan_days?.find((day) => sameDate(day.date, today)) ?? plan?.plan_days?.[0];
  }, [plan?.plan_days]);

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
    },
  });

  if (!classId) {
    return <div className="text-sm text-slate-500">Select a course first.</div>;
  }

  if (plansQ.isLoading) {
    return <div className="text-sm text-slate-500">Loading Exam Lockdown plans...</div>;
  }

  if (!plansQ.data?.length) {
    return (
      <div className="rounded-xl border border-amber-100 bg-amber-50 p-4 text-sm text-amber-800">
        No active evidence-based exam prep plan found. <Link href="/planner" className="underline">Create one in Planner</Link>.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="rounded-xl border border-slate-100 p-4">
          <div className="text-xs uppercase tracking-[0.14em] text-slate-400">Exam Lockdown</div>
          <div className="mt-1 text-xl font-semibold text-slate-900">{plan?.exam_title ?? "Exam prep plan"}</div>
          {plan?.exam_date ? (
            <div className="text-sm text-slate-500">{new Date(plan.exam_date).toLocaleString()}</div>
          ) : null}
          <div className="mt-3 text-sm text-slate-600">
            Evidence-based plan based on uploaded materials. It estimates likely exam scope; it is not a guarantee.
          </div>
        </div>
        <LockdownProgressPanel progress={progressQ.data} />
      </div>

      {todayBlock ? (
        <div className="rounded-xl border border-slate-100 p-4">
          <div className="text-sm font-semibold text-slate-900">Today&apos;s block</div>
          <div className="mt-2 space-y-2">
            {todayBlock.tasks.map((task, index) => (
              <div key={`${todayBlock.date}-${index}`} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                <span className="font-medium">{task.title}</span>
                <span className="text-slate-500"> - {task.minutes} min</span>
                {task.description ? <div className="text-xs text-slate-500">{task.description}</div> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        <div className="space-y-3">
          <div className="rounded-xl border border-slate-100 p-3">
            <div className="text-sm font-semibold text-slate-900">Likely exam scope</div>
            <div className="mt-2 space-y-2">
              {(plan?.topics ?? []).slice(0, 6).map((topic, index) => (
                <div key={topic.id ?? topic.topic_name} className="text-sm text-slate-700">
                  {index + 1}. {topic.topic_name}
                  <span className="text-xs text-slate-500"> - {topic.confidence} confidence</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-100 p-3">
            <div className="text-sm font-semibold text-slate-900">Recommended questions</div>
            <div className="mt-2 space-y-2">
              {recommendations.length ? recommendations.map((rec) => (
                <button
                  key={rec.id}
                  onClick={() => {
                    setSelectedRecId(rec.id);
                    setCoachMarkdown("");
                  }}
                  className="block w-full rounded-lg border px-3 py-2 text-left text-sm"
                  style={{
                    borderColor: selectedRec?.id === rec.id ? "rgba(247,167,195,0.55)" : "var(--border-soft)",
                    background: selectedRec?.id === rec.id ? "var(--gradient-main)" : "rgba(255,255,255,0.72)",
                    color: "var(--text-main)",
                  }}
                >
                  <div className="font-medium">Rank {rec.rank}</div>
                  <div className="line-clamp-2 text-xs opacity-75">{sourceLine(rec) || rec.question?.prompt_text}</div>
                </button>
              )) : (
                <div className="text-sm text-slate-500">No recommended questions were saved with this plan.</div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-3">
          {selectedRec ? (
            <div className="rounded-xl border border-slate-100 p-4">
              <div className="text-sm font-semibold text-slate-900">{sourceLine(selectedRec) || "Selected question"}</div>
              <div className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{selectedRec.question?.prompt_text}</div>
              {selectedRec.why_selected ? <div className="mt-2 text-xs text-slate-500">{selectedRec.why_selected}</div> : null}
            </div>
          ) : null}

          <div className="grid gap-3 md:grid-cols-2">
            <div>
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
              className="w-full app-input min-h-24 px-3 py-2 text-sm"
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
            <Button variant="secondary" onClick={() => saveM.mutate("completed")} disabled={!selectedRec || saveM.isPending}>
              Mark Complete
            </Button>
            <Button variant="ghost" onClick={() => saveM.mutate("skipped")} disabled={!selectedRec || saveM.isPending}>
              Skip
            </Button>
          </div>

          {tutorM.error ? <div className="text-sm text-pink-600">{String(tutorM.error)}</div> : null}
          {saveM.error ? <div className="text-sm text-pink-600">{String(saveM.error)}</div> : null}
          {saveM.data ? <div className="text-sm text-slate-500">Saved. Pitfalls captured: {saveM.data.pitfalls_saved}</div> : null}

          <ExamCoachResponse markdown={coachMarkdown} />
        </div>
      </div>
    </div>
  );
}
