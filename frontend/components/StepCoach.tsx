"use client";

import { useMemo, useState } from "react";
import { api, type UUID } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export default function StepCoach({ questionId }: { questionId: UUID }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [expectedStep, setExpectedStep] = useState<string | null>(null);

  const [studentStep, setStudentStep] = useState("");
  const [checkResult, setCheckResult] = useState<{ correct: boolean; feedback: string } | null>(null);

  const [whyWrong, setWhyWrong] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  const stepLabel = useMemo(() => `Step ${stepIndex + 1}`, [stepIndex]);

  async function loadNextStep() {
    const out = await api.nextStep(questionId, stepIndex);
    if (out.message === "Done") {
      setExpectedStep("Done — you’ve completed the expected reasoning path.");
    } else if (out.next_step) {
      setExpectedStep(out.next_step);
    } else {
      setExpectedStep("No step returned.");
    }
    setCheckResult(null);
    setWhyWrong(null);
    setHint(null);
  }

  async function checkStep() {
    const out = await api.checkStep(questionId, {
      step: studentStep,
      step_index: stepIndex,
    });
    setCheckResult(out);
    setWhyWrong(null);
  }

  async function explainWhyWrong() {
    const out = await api.whyWrong(questionId, { step: studentStep });
    setWhyWrong(out.explanation);
  }

  async function getHint(level: 1 | 2 | 3) {
    const out = await api.nextHint(questionId, level);
    setHint(out.hint);
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-slate-900">Step Coach</div>
          <div className="text-xs text-slate-500 mt-1">
            Pull the next expected step, write your step, then check it.
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setStepIndex((s) => Math.max(0, s - 1))}>
            Back
          </Button>
          <Button variant="ghost" onClick={() => setStepIndex((s) => s + 1)}>
            Next
          </Button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 items-center">
        <div className="text-xs text-slate-500">{stepLabel}</div>
        <Button variant="secondary" onClick={loadNextStep}>
          Get expected step
        </Button>
        <Button variant="ghost" onClick={() => getHint(1)}>
          Hint 1
        </Button>
        <Button variant="ghost" onClick={() => getHint(2)}>
          Hint 2
        </Button>
        <Button variant="ghost" onClick={() => getHint(3)}>
          Hint 3
        </Button>
      </div>

      {expectedStep ? (
        <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50 p-3 text-sm text-slate-800">
          <div className="text-xs text-blue-700 mb-1">Expected</div>
          {expectedStep}
        </div>
      ) : null}

      {hint ? (
        <div className="mt-3 rounded-xl border border-green-100 bg-green-50 p-3 text-sm text-slate-800">
          <div className="text-xs text-green-700 mb-1">Hint</div>
          {hint}
        </div>
      ) : null}

      <div className="mt-4">
        <div className="text-xs text-slate-500 mb-1">Your step</div>
        <textarea
          className="w-full rounded-xl border border-slate-200 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-200"
          rows={3}
          value={studentStep}
          onChange={(e) => setStudentStep(e.target.value)}
          placeholder="Write the next reasoning step in your own words."
        />
      </div>

      <div className="mt-3 flex gap-2">
        <Button onClick={checkStep} disabled={!studentStep.trim()}>
          Check step
        </Button>
        <Button variant="danger" onClick={explainWhyWrong} disabled={!studentStep.trim()}>
          Why wrong?
        </Button>
      </div>

      {checkResult ? (
        <div
          className={[
            "mt-3 rounded-xl border p-3 text-sm",
            checkResult.correct ? "border-green-200 bg-green-50" : "border-pink-200 bg-pink-50",
          ].join(" ")}
        >
          <div className="text-xs mb-1">
            {checkResult.correct ? "Correct" : "Needs work"}
          </div>
          {checkResult.feedback}
        </div>
      ) : null}

      {whyWrong ? (
        <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-800">
          <div className="text-xs text-slate-500 mb-1">Misconception explanation</div>
          {whyWrong}
        </div>
      ) : null}
    </Card>
  );
}