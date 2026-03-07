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

export default function AnalyticsPage() {
  const classId = useStore((s) => s.selectedClassId);

  const depsM = useMutation({
    mutationFn: () => api.autoBuildDependencies(classId),
  });

  return (
    <div className="py-7 space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-900">Analytics</h1>
        <p className="text-slate-500 mt-1">
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
          <div className="text-sm text-slate-700 mb-3">
            Created edges: <b>{depsM.data.edges_created}</b>
          </div>
        ) : null}
        {depsM.error ? <div className="text-sm text-pink-600">{String(depsM.error)}</div> : null}
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