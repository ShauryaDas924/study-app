"use client";

import { Card, CardHeader } from "@/components/ui/Card";
import RequireAuth from "@/components/RequireAuth";
import ExamPrepPlannerPanel from "@/components/exam-prep/ExamPrepPlannerPanel";

const steps = [
  "Upload syllabus",
  "Add exam details",
  "Generate plan",
  "Create tasks",
];

const trustChips = [
  "Syllabus-based",
  "Uses course concepts",
  "Confidence-ranked",
  "Creates study tasks",
];

function PlannerContent() {
  return (
    <div className="py-7 space-y-7">
      <section className="overflow-hidden rounded-[2rem] border border-slate-100 bg-white px-6 py-7 shadow-sm md:px-8 md:py-9">
        <div className="max-w-4xl">
          <div className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-400">
            Planner
          </div>
          <h1 className="mt-3 max-w-3xl text-4xl font-semibold leading-tight text-slate-950 md:text-5xl">
            Turn your syllabus into an exam plan.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
            Upload your syllabus, choose your exam date, and get an evidence-based study schedule built from your course material.
          </p>

          <div className="mt-5 flex flex-wrap gap-2">
            {trustChips.map((chip) => (
              <span
                key={chip}
                className="rounded-full border border-slate-100 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700"
              >
                {chip}
              </span>
            ))}
          </div>

          <div className="mt-5 rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            This is an estimate based on available evidence, not a guarantee.
          </div>
        </div>
      </section>

      <Card className="p-0">
        <div className="border-b border-slate-100 px-6 py-5">
          <CardHeader
            title="Exam Prep Planner"
            subtitle="Upload your syllabus, rank likely exam topics, and create a day-by-day study plan."
          />
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, index) => (
              <div
                key={step}
                className="flex items-center gap-3 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-xs font-semibold text-slate-700 shadow-sm">
                  {index + 1}
                </div>
                <div className="text-sm font-medium text-slate-700">{step}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="px-6 py-6">
          <ExamPrepPlannerPanel />
        </div>
      </Card>
    </div>
  );
}

export default function PlannerPage() {
  return (
    <RequireAuth>
      <PlannerContent />
    </RequireAuth>
  );
}
