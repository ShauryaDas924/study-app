"use client";

import { Card, CardHeader } from "@/components/ui/Card";
import ExamSetup from "@/components/ExamSetup";
import ExamRunner from "@/components/ExamRunner";

export default function ExamPage() {
  return (
   <div className="app-shell py-7 space-y-6">
      <div>
       <h1 className="text-3xl font-semibold" style={{ color: "var(--text-main)" }}>
  Exam Mode
</h1>
<p className="mt-1" style={{ color: "var(--text-soft)" }}>
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