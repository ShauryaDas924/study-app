"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Card, CardHeader } from "@/components/ui/Card";
import MasteryCard from "@/components/MasteryCard";
import { Button } from "@/components/ui/Button";
import RequireAuth from "@/components/RequireAuth";

function DashboardContent() {
  const classId = useStore((s) => s.selectedClassId);

  const readinessQ = useQuery({
    queryKey: ["readiness", classId],
    queryFn: () => api.readiness(classId),
    enabled: Boolean(classId),
  });

  const readiness = readinessQ.data?.readiness_percent ?? 0;

  return (
   <div className="app-shell space-y-10">
      <div>
       <h1 className="text-3xl font-semibold" style={{ color: "var(--text-main)" }}>
  Your Learning Progress
</h1>
<p className="mt-2" style={{ color: "var(--text-soft)" }}>
  Small daily practice leads to long-term mastery.
</p>
      </div>

      <Card>
        <CardHeader
          title="Overall Readiness"
          subtitle="How prepared you are for exams."
        />

        <div
  className="text-5xl font-semibold"
  style={{
    background: "var(--gradient-main)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
  }}
>
  {readiness}%
</div>
      </Card>
        {classId && (
 <Button
  className="px-4 py-2 rounded-xl border"
  style={{
    background: "linear-gradient(135deg, #ffe3ea 0%, #fff2cf 100%)",
    color: "#6b3d49",
    borderColor: "var(--border-soft)",
  }}
    onClick={async () => {
      const ok = confirm(
       "⚠️ This will DELETE all notes, concepts, and mastery for this course.\n\nType OK to continue."
      );

      if (!ok) return;

      await api.clearClass(classId);

      alert("Course data cleared.");

      window.location.reload();
    }}
  >
    Clear Class Data
  </Button>
)}
      <div className="grid md:grid-cols-2 gap-6">
        {(readinessQ.data?.weak_concepts || []).slice(0, 4).map((c) => (
          <MasteryCard
            key={c.concept_id}
            title={c.name}
            mastery={Math.round(c.mastery_prob * 100)}
          />
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}
