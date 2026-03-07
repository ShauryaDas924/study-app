"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import ExamTimer from "@/components/ExamTimer";
import StepCoach from "@/components/StepCoach";

export default function ExamRunner() {
  const exam = useStore((s) => s.exam);
  const setExamIndex = useStore((s) => s.setExamIndex);
  const currentQuestion = useStore((s) => s.currentQuestion);

  const [showReport, setShowReport] = useState(false);

  const reportQ = useQuery({
    queryKey: ["examReport", exam.exam_session_id],
    queryFn: () => api.examReport(exam.exam_session_id!),
    enabled: !!exam.exam_session_id && showReport,
  });

  const idx = exam.currentIndex;
  const total = exam.questions.length;

  const sessionId = exam.exam_session_id;

  const headerRight = useMemo(() => {
    if (!sessionId) return null;
    return (
      <div className="flex items-center gap-3">
        <ExamTimer />
        <Button variant="ghost" onClick={() => setShowReport((s) => !s)}>
          {showReport ? "Hide report" : "View report"}
        </Button>
      </div>
    );
  }, [sessionId, showReport]);

  if (!sessionId) {
    return (
      <Card>
        <CardHeader title="Exam Runner" subtitle="Start an exam to begin." />
        <div className="text-sm text-slate-500">No active exam session.</div>
      </Card>
    );
  }

  if (!currentQuestion) {
    return (
      <Card>
        <CardHeader title="Exam Runner" subtitle="Loading question..." right={headerRight} />
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title={`Exam Question ${idx + 1} / ${total}`}
        subtitle="Use the step coach to stay structured under time pressure."
        right={headerRight}
      />

      {showReport ? (
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 mb-4">
          {reportQ.isLoading ? (
            <div className="text-sm text-slate-500">Loading report…</div>
          ) : reportQ.error ? (
            <div className="text-sm text-pink-600">{String(reportQ.error)}</div>
          ) : reportQ.data ? (
            <div className="grid md:grid-cols-3 gap-4">
              <div>
                <div className="text-xs text-slate-500">Accuracy</div>
                <div className="text-2xl font-semibold text-slate-900">{reportQ.data.accuracy}%</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Avg time</div>
                <div className="text-2xl font-semibold text-slate-900">{reportQ.data.avg_time_sec ?? 0}s</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Attempts</div>
                <div className="text-2xl font-semibold text-slate-900">{reportQ.data.attempts ?? 0}</div>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
        {currentQuestion.prompt}
      </div>

      <div className="mt-4">
        <StepCoach questionId={currentQuestion.id} />
      </div>

      <div className="mt-4 flex gap-2">
        <Button variant="ghost" onClick={() => setExamIndex(idx - 1)} disabled={idx <= 0}>
          Prev
        </Button>
        <Button variant="ghost" onClick={() => setExamIndex(idx + 1)} disabled={idx >= total - 1}>
          Next
        </Button>
      </div>
    </Card>
  );
}