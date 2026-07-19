"use client";

import type { ReactNode } from "react";
import type { ExamPrepRecommendedQuestion } from "@/lib/api";

function typeLabel(value?: string | null) {
  return value ? value.replace(/_/g, " ") : "uploaded evidence";
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

function sourceLine(rec: ExamPrepRecommendedQuestion) {
  const q = rec.question;
  const material = q?.material;
  const ref = q?.source_ref_json || {};
  const pieces = [
    material?.filename,
    q?.problem_number ? `Problem ${q.problem_number}` : null,
    typeof ref.page === "number" || typeof ref.page === "string" ? `Page ${ref.page}` : null,
  ].filter(Boolean);
  return pieces.join(" - ");
}

function confidenceLabel(value?: number | null) {
  if (typeof value !== "number") return "confidence pending";
  return `${Math.round(value * 100)}% confidence`;
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
    <div className="grid gap-3 lg:grid-cols-2">
      {recommendations.map((rec) => {
        const q = rec.question;
        const material = q?.material;
        const statusTone: "slate" | "green" | "amber" =
          rec.status === "completed" ? "green" : rec.status === "skipped" ? "amber" : "slate";

        return (
          <div key={rec.id} className="rounded-xl border border-slate-100 bg-white/90 p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="blue">Rank {rec.rank}</Badge>
              {q?.topic_name ? <Badge>{q.topic_name}</Badge> : null}
              <Badge tone={statusTone}>{rec.status}</Badge>
              {q?.status === "stale" ? <Badge tone="amber">stale source</Badge> : null}
            </div>

            <div className="mt-3 text-sm font-semibold text-slate-900">
              {sourceLine(rec) || "Uploaded question"}
            </div>
            <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
              <span>{typeLabel(material?.material_type)}</span>
              <span>{confidenceLabel(rec.confidence)}</span>
            </div>

            {q?.prompt_text ? (
              <div className="mt-3 line-clamp-4 rounded-lg bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">
                {q.prompt_text}
              </div>
            ) : null}

            {rec.why_selected ? (
              <div className="mt-3 rounded-lg border border-slate-100 bg-white px-3 py-2 text-xs leading-5 text-slate-600">
                <span className="font-medium text-slate-800">Why selected: </span>
                {rec.why_selected}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
