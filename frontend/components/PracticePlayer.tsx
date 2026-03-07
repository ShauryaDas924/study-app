"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useStore } from "@/store/useStore";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import StepCoach from "@/components/StepCoach";
import { api } from "@/lib/api";

export default function PracticePlayer() {
  const practice = useStore((s) => s.practice);
  const currentQuestion = useStore((s) => s.currentQuestion);
  const setPracticeIndex = useStore((s) => s.setPracticeIndex);

  const [confidence, setConfidence] = useState(3);
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  const startedAtRef = useRef<number | null>(null);

  const idx = practice.currentIndex;
  const total = practice.questions.length;

  /* ================= RESET ON QUESTION CHANGE ================= */
  useEffect(() => {
    if (!currentQuestion) return;

    startedAtRef.current = Date.now();
    setFeedback(null);
    setIsCorrect(null);
    setSelectedIndex(null);
  }, [currentQuestion]);

  /* ================= TIMER ================= */
  const elapsedSec = useMemo(() => {
    if (!startedAtRef.current) return 0;
    return Math.floor((Date.now() - startedAtRef.current) / 1000);
  }, [currentQuestion]);

  /* ================= GUARD ================= */
  if (!currentQuestion) {
    return <div className="text-slate-500">No question loaded</div>;
  }

  const isMCQ = currentQuestion.question_json?.type === "mcq";

  /* ================= SUBMIT ================= */
  async function submitAttempt() {
    if (!currentQuestion) return;

    const t0 = startedAtRef.current ?? Date.now();
    const time_spent_sec = Math.floor((Date.now() - t0) / 1000);

    const out = await api.submitAttempt(currentQuestion.id, {
      user_answer_json: isMCQ
        ? { selected_index: selectedIndex }
        : {},
      is_correct: Boolean(isCorrect),
      confidence,
      time_spent_sec,
      session_id: null,
    });

    setFeedback(out.feedback ? out.feedback.mistake : "Saved.");

    // ✅ AUTO NEXT
    if (idx < total - 1) {
      setTimeout(() => {
        setPracticeIndex(idx + 1);
      }, 600);
    }
  }

  /* ================= UI ================= */
  return (
    <Card className="mt-6">
      <CardHeader title={`Question ${idx + 1}/${total}`} />

      {/* PROMPT */}
      <div className="p-4 bg-slate-50 rounded text-slate-900">
        {currentQuestion.prompt}
      </div>

      {/* MCQ OPTIONS */}
      {isMCQ && (
        <div className="mt-4 space-y-2">
          {currentQuestion.question_json.options.map(
            (opt: string, i: number) => (
              <button
                key={i}
                className={`block w-full text-left border rounded px-3 py-2 transition
                ${
                  selectedIndex === i
                    ? "bg-emerald-100 border-emerald-400"
                    : "hover:bg-slate-100"
                }`}
                onClick={() => {
                  setSelectedIndex(i);
                  setIsCorrect(
                    i === currentQuestion.question_json.correct_index
                  );
                }}
              >
                {opt}
              </button>
            )
          )}
        </div>
      )}

      {/* STEP COACH (open questions) */}
      {!isMCQ && <StepCoach questionId={currentQuestion.id} />}

      {/* ACTIONS */}
      <div className="mt-4 flex items-center gap-3">
        <Button
          onClick={submitAttempt}
          disabled={isMCQ && selectedIndex === null}
        >
          Save Attempt
        </Button>

        {/* NEXT BUTTON */}
        <Button
          onClick={() => setPracticeIndex(idx + 1)}
          disabled={idx >= total - 1}
        >
          Next →
        </Button>

        {isCorrect === true && (
          <span className="text-emerald-600 text-sm">
            Marked correct
          </span>
        )}

        {isCorrect === false && (
          <span className="text-rose-600 text-sm">
            Marked incorrect
          </span>
        )}
      </div>

      {/* FEEDBACK */}
      {feedback && (
        <div className="mt-3 text-sm text-slate-700">
          {feedback}
        </div>
      )}
    </Card>
  );
}