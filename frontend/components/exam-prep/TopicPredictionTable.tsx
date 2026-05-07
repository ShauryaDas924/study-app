"use client";

import type { ExamPrepTopicPrediction } from "@/lib/api";

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function confidenceStyle(confidence: string) {
  if (confidence === "high") {
    return "bg-emerald-50 text-emerald-700 border-emerald-100";
  }
  if (confidence === "medium") {
    return "bg-amber-50 text-amber-700 border-amber-100";
  }
  return "bg-slate-50 text-slate-600 border-slate-100";
}

export default function TopicPredictionTable({ topics }: { topics: ExamPrepTopicPrediction[] }) {
  if (!topics.length) {
    return <div className="text-sm text-slate-500">No estimated topics yet.</div>;
  }

  return (
    <div className="space-y-3">
      {topics.map((topic, index) => (
        <div key={topic.id ?? topic.topic_name} className="rounded-xl border border-slate-100 p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <div className="text-xs text-slate-500">Rank {index + 1}</div>
              <div className="font-semibold text-slate-900">{topic.topic_name}</div>
              <div className="mt-1 text-sm text-slate-600">{topic.recommended_study_action}</div>
            </div>

            <div className="flex shrink-0 flex-wrap gap-2 text-xs">
              <span className="rounded-full border border-slate-100 bg-slate-50 px-3 py-1 text-slate-700">
                Likelihood {pct(topic.exam_likelihood_score)}
              </span>
              <span className="rounded-full border border-slate-100 bg-slate-50 px-3 py-1 text-slate-700">
                Priority {pct(topic.student_priority_score)}
              </span>
              <span className={`rounded-full border px-3 py-1 capitalize ${confidenceStyle(topic.confidence)}`}>
                {topic.confidence} confidence
              </span>
            </div>
          </div>

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div>
              <div className="text-xs font-medium text-slate-500">Evidence</div>
              <div className="mt-1 space-y-1">
                {topic.evidence.slice(0, 3).map((item, i) => (
                  <div key={`${item.source}-${i}`} className="text-xs text-slate-600">
                    <span className="font-medium capitalize">{item.source}</span>
                    {item.quote ? `: ${item.quote}` : `: ${item.label}`}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="text-xs font-medium text-slate-500">Missing data</div>
              <div className="mt-1 space-y-1">
                {topic.missing_data.length ? (
                  topic.missing_data.slice(0, 3).map((item) => (
                    <div key={item} className="text-xs text-slate-600">
                      {item}
                    </div>
                  ))
                ) : (
                  <div className="text-xs text-slate-500">No major missing evidence flagged.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
