"use client";

import {
  type ExamPrepIntensity,
  type ExamPrepSyllabusSummary,
  type UUID,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

export default function ExamPrepForm({
  syllabi,
  selectedSyllabusId,
  setSelectedSyllabusId,
  examTitle,
  setExamTitle,
  examDateIso,
  setExamDateIso,
  minutes,
  setMinutes,
  intensity,
  setIntensity,
  targetScore,
  setTargetScore,
  targetGrade,
  setTargetGrade,
  currentScores,
  setCurrentScores,
  weakTopics,
  setWeakTopics,
  onGenerate,
  isGenerating,
}: {
  syllabi: ExamPrepSyllabusSummary[];
  selectedSyllabusId: UUID;
  setSelectedSyllabusId: (id: UUID) => void;
  examTitle: string;
  setExamTitle: (value: string) => void;
  examDateIso: string;
  setExamDateIso: (value: string) => void;
  minutes: number;
  setMinutes: (value: number) => void;
  intensity: ExamPrepIntensity;
  setIntensity: (value: ExamPrepIntensity) => void;
  targetScore?: string;
  setTargetScore?: (value: string) => void;
  targetGrade?: string;
  setTargetGrade?: (value: string) => void;
  currentScores?: string;
  setCurrentScores?: (value: string) => void;
  weakTopics?: string;
  setWeakTopics?: (value: string) => void;
  onGenerate: () => void;
  isGenerating: boolean;
}) {
  return (
    <div className="grid md:grid-cols-4 gap-4">
      <div className="md:col-span-2">
        <div className="text-xs text-slate-500 mb-1">Uploaded syllabus</div>
        <Select value={selectedSyllabusId} onChange={(e) => setSelectedSyllabusId(e.target.value)}>
          <option value="">Select syllabus</option>
          {syllabi.map((s) => (
            <option key={s.id} value={s.id}>
              {s.filename}
            </option>
          ))}
        </Select>
      </div>

      <div className="md:col-span-2">
        <div className="text-xs text-slate-500 mb-1">Exam title</div>
        <Input value={examTitle} onChange={(e) => setExamTitle(e.target.value)} placeholder="Midterm 2" />
      </div>

      <div>
        <div className="text-xs text-slate-500 mb-1">Exam date</div>
        <Input type="datetime-local" value={examDateIso} onChange={(e) => setExamDateIso(e.target.value)} />
      </div>

      <div>
        <div className="text-xs text-slate-500 mb-1">Minutes per day</div>
        <Input
          type="number"
          min={10}
          max={480}
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
        />
      </div>

      <div>
        <div className="text-xs text-slate-500 mb-1">Intensity</div>
        <Select value={intensity} onChange={(e) => setIntensity(e.target.value as ExamPrepIntensity)}>
          <option value="light">Light</option>
          <option value="balanced">Balanced</option>
          <option value="aggressive">Aggressive</option>
        </Select>
      </div>

      <div className="flex items-end">
        <Button className="w-full" onClick={onGenerate} disabled={isGenerating}>
          {isGenerating ? "Generating..." : "Generate Plan"}
        </Button>
      </div>

      <div>
        <div className="text-xs text-slate-500 mb-1">Target score</div>
        <Input value={targetScore ?? ""} onChange={(e) => setTargetScore?.(e.target.value)} placeholder="90" />
      </div>

      <div>
        <div className="text-xs text-slate-500 mb-1">Target grade</div>
        <Input value={targetGrade ?? ""} onChange={(e) => setTargetGrade?.(e.target.value)} placeholder="A-" />
      </div>

      <div className="md:col-span-2">
        <div className="text-xs text-slate-500 mb-1">Current scores</div>
        <Input
          value={currentScores ?? ""}
          onChange={(e) => setCurrentScores?.(e.target.value)}
          placeholder="HW avg 82, quiz avg 76"
        />
      </div>

      <div className="md:col-span-4">
        <div className="text-xs text-slate-500 mb-1">Known weak topics</div>
        <textarea
          value={weakTopics ?? ""}
          onChange={(e) => setWeakTopics?.(e.target.value)}
          placeholder="Separate topics with commas"
          className="w-full app-input min-h-20 px-3 py-2 text-sm"
        />
      </div>
    </div>
  );
}
