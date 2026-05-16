"use client";

import type { ExamPrepRecommendedQuestion } from "@/lib/api";

function sourceLine(rec: ExamPrepRecommendedQuestion) {
  const q = rec.question;
  const material = q?.material;
  const ref = q?.source_ref_json || {};
  const pieces = [
    material?.filename,
    q?.problem_number ? `Problem ${q.problem_number}` : null,
    typeof ref.page === "number" || typeof ref.page === "string" ? `Page ${ref.page}` : null,
    q?.topic_name,
    q?.status === "stale" ? "stale source" : null,
  ].filter(Boolean);
  return pieces.join(" - ");
}

export default function RecommendedQuestionList({
  recommendations,
}: {
  recommendations: ExamPrepRecommendedQuestion[];
}) {
  if (!recommendations.length) {
    return (
      <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-800">
        No recommended questions yet. Extract questions from uploaded materials before generating the plan.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {recommendations.map((rec) => (
        <div key={rec.id} className="rounded-xl border border-slate-100 p-3">
          <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <div className="text-xs text-slate-500">Rank {rec.rank}</div>
              <div className="text-sm font-medium text-slate-900">{sourceLine(rec) || "Uploaded question"}</div>
              <div className="mt-1 line-clamp-3 text-sm text-slate-600">
                {rec.question?.prompt_text}
              </div>
              {rec.why_selected ? (
                <div className="mt-1 text-xs text-slate-500">{rec.why_selected}</div>
              ) : null}
            </div>
            <div className="shrink-0 rounded-full border border-slate-100 bg-slate-50 px-3 py-1 text-xs text-slate-600">
              {Math.round(Number(rec.confidence ?? 0) * 100)}% confidence
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
