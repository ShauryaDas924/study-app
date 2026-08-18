"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Input } from "@/components/ui/Input";

export default function PracticeSetup() {
  const classId = useStore((s) => s.selectedClassId);
  const setPracticeSession = useStore((s) => s.setPracticeSession);

  const [mode, setMode] = useState<"standard" | "remedial">("standard");
  const [difficulty, setDifficulty] = useState(3);
  const [n, setN] = useState(5);
  const [subjectTag, setSubjectTag] = useState("general");

  const [lookbackDays, setLookbackDays] = useState(14);
  const [topTags, setTopTags] = useState(5);
  const [includeDeps, setIncludeDeps] = useState(true);
const [questionType, setQuestionType] = useState<"open" | "mcq">("open");
  const gen = useMutation({
    mutationFn: async () => {
      if (mode === "standard") {
        return api.generatePractice({
  class_id: classId,
  difficulty,
  n,
  subject_tag: subjectTag,
  question_type: questionType,
});
      }
      return api.generateRemedial({
        class_id: classId,
        difficulty,
        n,
        subject_tag: "remedial",
        lookback_days: lookbackDays,
        top_tags: topTags,
        include_dependencies: includeDeps,
      });
    },
    onSuccess: (data) => {
      setPracticeSession(data.practice_set_id, data.questions);
    },
  });

  return (
    <div className="grid md:grid-cols-3 gap-4">
      <div>
        <div className="text-xs text-slate-500 mb-1">Mode</div>
        <Select
          value={mode}
          onChange={(e) => setMode(e.target.value as "standard" | "remedial")}
        >
          <option value="standard">Standard</option>
          <option value="remedial">Remedial</option>
        </Select>
      </div>

      <div>
        <div className="text-xs text-slate-500 mb-1">Difficulty (1–5)</div>
<div>
  <div className="text-xs text-slate-500 mb-1">Question Type</div>
  <Select
    value={questionType}
    onChange={(e) => setQuestionType(e.target.value as "open" | "mcq")}
  >
    <option value="open">Open Response</option>
    <option value="mcq">Multiple Choice</option>
  </Select>
</div>
        <Select value={String(difficulty)} onChange={(e) => setDifficulty(Number(e.target.value))}>
          {[1, 2, 3, 4, 5].map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </Select>
      </div>

      <div>
        <div className="text-xs text-slate-500 mb-1"># Questions</div>
        <Input
          type="number"
          min={1}
          value={n}
          onChange={(e) => setN(Number(e.target.value))}
        />
      </div>

      <div className="md:col-span-2">
        <div className="text-xs text-slate-500 mb-1">Subject tag</div>
        <Input value={subjectTag} onChange={(e) => setSubjectTag(e.target.value)} />
      </div>

      {mode === "remedial" ? (
        <div className="md:col-span-3 grid md:grid-cols-3 gap-4">
          <div>
            <div className="text-xs text-slate-500 mb-1">Lookback days</div>
            <Input
              type="number"
              min={1}
              value={lookbackDays}
              onChange={(e) => setLookbackDays(Number(e.target.value))}
            />
          </div>
          <div>
            <div className="text-xs text-slate-500 mb-1">Top tags</div>
            <Input
              type="number"
              min={1}
              value={topTags}
              onChange={(e) => setTopTags(Number(e.target.value))}
            />
          </div>
          <div className="flex items-end gap-2">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={includeDeps}
                onChange={(e) => setIncludeDeps(e.target.checked)}
              />
              Include dependencies
            </label>
          </div>
        </div>
      ) : null}

      <div className="md:col-span-3">
        <Button onClick={() => gen.mutate()} disabled={gen.isPending}>
          {mode === "standard" ? "Generate Practice" : "Generate Remedial"}
        </Button>
        {gen.error ? <div className="text-sm text-pink-600 mt-2">{String(gen.error)}</div> : null}
      </div>
    </div>
  );
}
