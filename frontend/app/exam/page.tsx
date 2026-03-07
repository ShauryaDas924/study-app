"use client";

import { Card, CardHeader } from "@/components/ui/Card";
import ExamSetup from "@/components/ExamSetup";
import ExamRunner from "@/components/ExamRunner";

export default function ExamPage() {
  return (
    <div className="py-7 space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-900">Exam Mode</h1>
        <p className="text-slate-500 mt-1">
          Simulate real testing: time pressure, focus, and clean reasoning.
        </p>
      </div>

      <Card>
        <CardHeader
          title="Start an Exam Session"
          subtitle="Generates exam-tagged questions through the same engine."
        />
        <ExamSetup />
      </Card>

      <ExamRunner />
    </div>
  );
}