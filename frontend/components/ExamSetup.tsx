"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function ExamSetup() {
  const classId = useStore((s) => s.selectedClassId);
  const setExamSession = useStore((s) => s.setExamSession);

  const [timeLimitMin, setTimeLimitMin] = useStateNumber(60);
  const [nQuestions, setNQuestions] = useStateNumber(20);

  const start = useMutation({
    mutationFn: () =>
      api.startExam({
        class_id: classId,
        time_limit_min: timeLimitMin,
        n_questions: nQuestions,
      }),
    onSuccess: (data) => {
      setExamSession(data.exam_session_id, data.questions, timeLimitMin);
    },
  });

  return (
    <div className="grid md:grid-cols-3 gap-4">
      <div>
        <div className="text-xs text-slate-500 mb-1">Time limit (min)</div>
        <Input type="number" min={1} value={timeLimitMin} onChange={(e) => setTimeLimitMin(Number(e.target.value))} />
      </div>
      <div>
        <div className="text-xs text-slate-500 mb-1"># Questions</div>
        <Input type="number" min={1} value={nQuestions} onChange={(e) => setNQuestions(Number(e.target.value))} />
      </div>
      <div className="flex items-end">
        <Button className="w-full" onClick={() => start.mutate()} disabled={start.isPending}>
          Start Exam
        </Button>
      </div>

      {start.error ? <div className="md:col-span-3 text-sm text-pink-600">{String(start.error)}</div> : null}
    </div>
  );
}

function useStateNumber(initial: number) {
  const [v, setV] = (require("react") as typeof import("react")).useState<number>(initial);
  return [v, setV] as const;
}