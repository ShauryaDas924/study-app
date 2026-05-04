"use client";

import { Card, CardHeader } from "@/components/ui/Card";
import AnalyticsMistakeHeatmap from "@/components/AnalyticsMistakeHeatmap";
import AnalyticsTagFrequency from "@/components/AnalyticsTagFrequency";
import AnalyticsWeaknessMap from "@/components/AnalyticsWeaknessMap";
import KnowledgeGraph from "@/components/KnowledgeGraph";
import { Button } from "@/components/ui/Button";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import RequireAuth from "@/components/RequireAuth";

function AnalyticsContent() {
  const classId = useStore((s) => s.selectedClassId);

  const depsM = useMutation({
    mutationFn: () => api.autoBuildDependencies(classId),
  });

  return (
    <div className="py-7 space-y-6">
      <div>
        <h1 className="text-3xl font-semibold" style={{ color: "var(--text-main)" }}>
  Analytics
</h1>
<p className="mt-1" style={{ color: "var(--text-soft)" }}>
          Misconceptions repeat across concepts. Track patterns, then fix root causes.
        </p>
      </div>

      <Card>
        <CardHeader
          title="Dependency Graph"
          subtitle="Auto-build concept prerequisites (LLM) and view the knowledge graph."
          right={
            <Button variant="secondary" onClick={() => depsM.mutate()} disabled={depsM.isPending}>
              Auto-build dependencies
            </Button>
          }
        />
        {depsM.data ? (
<div className="text-sm mb-3" style={{ color: "var(--text-soft)" }}>            Created edges: <b>{depsM.data.edges_created}</b>
          </div>
        ) : null}
       {depsM.error ? (
  <div className="text-sm" style={{ color: "var(--accent-pink-strong)" }}>
    {String(depsM.error)}
  </div>
) : null}
        <KnowledgeGraph />
      </Card>

      <div className="grid lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader title="Mistake Heatmap" subtitle="Concept mistake counts." />
          <AnalyticsMistakeHeatmap />
        </Card>

        <Card>
          <CardHeader title="Tag Frequency" subtitle="Most common misconception tags." />
          <AnalyticsTagFrequency />
        </Card>

        <Card>
          <CardHeader title="Weakness Map" subtitle="Tags that repeat across concepts." />
          <AnalyticsWeaknessMap />
        </Card>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <RequireAuth>
      <AnalyticsContent />
    </RequireAuth>
  );
}
