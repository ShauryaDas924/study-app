"use client";

import { Card, CardHeader } from "@/components/ui/Card";
import StudyPlanGenerator from "@/components/StudyPlanGenerator";
import WeeklyPlanGenerator from "@/components/WeeklyPlanGenerator";

export default function PlannerPage() {
  return (
    <div className="py-7 space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-900">Study Planner</h1>
        <p className="text-slate-500 mt-1">
          A realistic plan that adapts as your mastery changes.
        </p>
      </div>

      <Card>
        <CardHeader title="Daily Plan" subtitle="Simple daily loop: review → practice → reflection." />
        <StudyPlanGenerator />
      </Card>

      <Card>
        <CardHeader title="Weekly Curriculum" subtitle="Week-by-week plan until your exam date." />
        <WeeklyPlanGenerator />
      </Card>
    </div>
  );
}