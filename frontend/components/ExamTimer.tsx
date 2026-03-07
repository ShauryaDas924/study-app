"use client";

import { useEffect } from "react";
import { useStore } from "@/store/useStore";

export default function ExamTimer() {
  const exam = useStore((s) => s.exam);
  const examTimer = useStore((s) => s.examTimer);
  const setExamTimer = useStore((s) => s.setExamTimer);

  const totalSeconds = exam.time_limit_min * 60;
  const remaining = Math.max(0, totalSeconds - examTimer);

  useEffect(() => {
    if (!exam.exam_session_id) return;

    const id = setInterval(() => {
      setExamTimer(examTimer + 1);
    }, 1000);

    return () => clearInterval(id);
  }, [exam.exam_session_id, examTimer, setExamTimer]);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="text-xs text-slate-500">Time Remaining</div>
      <div className="text-lg font-semibold text-slate-900 mt-1">
        {format(remaining)}
      </div>
    </div>
  );
}

function format(sec: number) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}