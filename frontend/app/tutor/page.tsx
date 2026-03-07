"use client";

import { Card, CardHeader } from "@/components/ui/Card";
import TutorChat from "@/components/TutorChat";

export default function TutorPage() {
  return (
    <div className="py-7 space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-900">Tutor</h1>
        <p className="text-slate-500 mt-1">
          Ask for hints. You’ll get guidance—not answers.
        </p>
      </div>

      <Card>
        <CardHeader
          title="Tutor Chat"
          subtitle="Works best while you have an active question selected in Practice or Exam."
        />
        <TutorChat />
      </Card>
    </div>
  );
}