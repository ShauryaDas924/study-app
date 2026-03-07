"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type KnowledgeGraphOut, type KnowledgeGraphNode } from "@/lib/api";
import { useStore } from "@/store/useStore";

function isConcept(n: KnowledgeGraphNode): n is Extract<KnowledgeGraphNode, { type: "concept" }> {
  return n.type === "concept";
}

export default function KnowledgeGraph() {
  const classId = useStore((s) => s.selectedClassId);

  const q = useQuery({
    queryKey: ["knowledgeGraph", classId],
    queryFn: () => api.knowledgeGraph(classId),
  });

  const { nodes, edges } = (q.data || { nodes: [], edges: [] }) as KnowledgeGraphOut;

  const layout = useMemo(() => computeLayout(nodes), [nodes]);

  if (q.isLoading) return <div className="text-sm text-slate-500">Loading graph…</div>;
  if (q.error) return <div className="text-sm text-pink-600">{String(q.error)}</div>;
  if (!nodes.length) return <div className="text-sm text-slate-500">No nodes yet. Extract concepts and practice.</div>;

  const W = 900;
  const H = 520;

  return (
    <div className="overflow-auto">
      <svg width={W} height={H} className="min-w-[900px]">
        {/* edges */}
        {edges.map((e, i) => {
          const src = layout.positions.get(e.source);
          const tgt = layout.positions.get(e.target);
          if (!src || !tgt) return null;

          const stroke =
            e.type === "prereq" ? "rgba(59,130,246,0.35)" : "rgba(236,72,153,0.25)";
          const sw = e.type === "prereq" ? Math.max(1, e.weight) : Math.max(1, Math.min(6, e.weight));

          return (
            <line
              key={i}
              x1={src.x}
              y1={src.y}
              x2={tgt.x}
              y2={tgt.y}
              stroke={stroke}
              strokeWidth={sw}
            />
          );
        })}

        {/* nodes */}
        {nodes.map((n) => {
          const p = layout.positions.get(n.id);
          if (!p) return null;

          const radius = isConcept(n)
            ? 10 + Math.min(10, Math.max(0, n.mistake_count))
            : 8;

          const fill = isConcept(n) ? "rgba(34,197,94,0.35)" : "rgba(148,163,184,0.35)";
          const stroke = isConcept(n) ? "rgba(34,197,94,0.9)" : "rgba(100,116,139,0.9)";

          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={radius} fill={fill} stroke={stroke} strokeWidth={2}>
                <title>
                  {isConcept(n)
                    ? `${n.label}\nmastery: ${(n.mastery_prob * 100).toFixed(0)}%\nmistakes: ${n.mistake_count}`
                    : `${n.label}`}
                </title>
              </circle>

              {/* labels */}
              <text
                x={p.x}
                y={p.y + radius + 14}
                textAnchor="middle"
                fontSize="11"
                fill="rgba(15,23,42,0.75)"
              >
                {truncate(n.label, 18)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function truncate(s: string, n: number) {
  if (s.length <= n) return s;
  return s.slice(0, n - 1) + "…";
}

function computeLayout(nodes: KnowledgeGraphNode[]) {
  const positions = new Map<string, { x: number; y: number }>();

  const concepts = nodes.filter((n) => n.type === "concept");
  const tags = nodes.filter((n) => n.type === "tag");

  const cx = 450;
  const cy = 240;

  const rConcept = 170;
  const rTag = 230;

  concepts.forEach((n, i) => {
    const a = (i / Math.max(1, concepts.length)) * Math.PI * 2;
    positions.set(n.id, { x: cx + Math.cos(a) * rConcept, y: cy + Math.sin(a) * rConcept });
  });

  tags.forEach((n, i) => {
    const a = (i / Math.max(1, tags.length)) * Math.PI * 2;
    positions.set(n.id, { x: cx + Math.cos(a) * rTag, y: cy + Math.sin(a) * rTag });
  });

  return { positions };
}