"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type KnowledgeGraphOut, type KnowledgeGraphNode } from "@/lib/api";
import { useStore } from "@/store/useStore";

function isConcept(
  n: KnowledgeGraphNode
): n is Extract<KnowledgeGraphNode, { type: "concept" }> {
  return n.type === "concept";
}

export default function KnowledgeGraph() {
  const classId = useStore((s) => s.selectedClassId);

  const [hovered, setHovered] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["knowledgeGraph", classId],
    queryFn: () => api.knowledgeGraph(classId),
  });

  const { nodes, edges } = (q.data || { nodes: [], edges: [] }) as KnowledgeGraphOut;

  const layout = useMemo(() => computeLayout(nodes), [nodes]);

  if (q.isLoading) return <div className="text-sm text-slate-500">Loading graph…</div>;
  if (q.error) return <div className="text-sm text-pink-600">{String(q.error)}</div>;
  if (!nodes.length)
    return (
      <div className="text-sm text-slate-500">
        No nodes yet. Extract concepts and practice.
      </div>
    );

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
            e.type === "prereq"
              ? "rgba(59,130,246,0.15)"
              : "rgba(236,72,153,0.12)";

          const sw =
            e.type === "prereq"
              ? Math.max(1, e.weight)
              : Math.max(1, Math.min(4, e.weight));

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
            ? 4 + (1 - n.mastery_prob) * 8 + Math.min(3, n.mistake_count)
            : 6;

          const fill = isConcept(n)
            ? "rgba(34,197,94,0.35)"
            : "rgba(148,163,184,0.35)";

          const stroke = isConcept(n)
            ? "rgba(34,197,94,0.9)"
            : "rgba(100,116,139,0.9)";

          return (
            <g key={n.id}>

              <circle
                cx={p.x}
                cy={p.y}
                r={radius}
                fill={fill}
                stroke={stroke}
                strokeWidth={2}
                onMouseEnter={() => setHovered(n.id)}
                onMouseLeave={() => setHovered(null)}
              >
                <title>
                  {isConcept(n)
                    ? `${n.label}\nmastery: ${(n.mastery_prob * 100).toFixed(0)}%\nmistakes: ${n.mistake_count}`
                    : `${n.label}`}
                </title>
              </circle>

              {/* show label only on hover */}
              {hovered === n.id && renderLabel(n, p, radius)}

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

function renderLabel(
  n: KnowledgeGraphNode,
  p: { x: number; y: number },
  radius: number
) {
  const cx = 450;
  const cy = 240;

  const angle = Math.atan2(p.y - cy, p.x - cx);
  const deg = (angle * 180) / Math.PI;

  const rotate = deg > 90 || deg < -90 ? deg + 180 : deg;

  return (
    <text
      x={p.x}
      y={p.y}
      transform={`rotate(${rotate}, ${p.x}, ${p.y}) translate(0 ${radius + 14})`}
      textAnchor="middle"
      fontSize="12"
      fill="rgba(15,23,42,0.85)"
      pointerEvents="none"
    >
      {truncate(n.label, 18)}
    </text>
  );
}

function computeLayout(nodes: KnowledgeGraphNode[]) {
  const positions = new Map<string, { x: number; y: number }>();

  const concepts = nodes.filter((n) => n.type === "concept");
  const tags = nodes.filter((n) => n.type === "tag");

  const cx = 450;
  const cy = 240;

  const rConcept = 240;
  const rTag = 320;

  concepts.forEach((n, i) => {
    const a = (i / Math.max(1, concepts.length)) * Math.PI * 2;

    positions.set(n.id, {
      x: cx + Math.cos(a) * rConcept,
      y: cy + Math.sin(a) * rConcept,
    });
  });

  tags.forEach((n, i) => {
    const a = (i / Math.max(1, tags.length)) * Math.PI * 2;

    positions.set(n.id, {
      x: cx + Math.cos(a) * rTag,
      y: cy + Math.sin(a) * rTag,
    });
  });

  return { positions };
}