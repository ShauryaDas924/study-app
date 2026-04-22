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
    enabled: !!classId,
  });

  const { nodes, edges } = (q.data || { nodes: [], edges: [] }) as KnowledgeGraphOut;
  const layout = useMemo(() => computeLayout(nodes), [nodes]);

  if (q.isLoading) {
    return (
      <div className="text-sm" style={{ color: "var(--text-soft)" }}>
        Loading graph…
      </div>
    );
  }

  if (q.error) {
    return (
      <div className="text-sm" style={{ color: "var(--accent-pink-strong)" }}>
        {String(q.error)}
      </div>
    );
  }

  if (!nodes.length) {
    return (
      <div className="text-sm" style={{ color: "var(--text-soft)" }}>
        No nodes yet. Extract concepts and practice.
      </div>
    );
  }

  const W = 900;
  const H = 520;

  return (
    <div
      className="overflow-auto rounded-[28px] border p-4"
      style={{
        background:
          "linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(255,248,252,0.96) 52%, rgba(248,255,247,0.96) 100%)",
        borderColor: "var(--border-soft)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <svg width={W} height={H} className="min-w-[900px]">
        <defs>
          <radialGradient id="graphGlowPink" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(247,167,195,0.20)" />
            <stop offset="100%" stopColor="rgba(247,167,195,0)" />
          </radialGradient>

          <radialGradient id="graphGlowGreen" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(191,216,184,0.22)" />
            <stop offset="100%" stopColor="rgba(191,216,184,0)" />
          </radialGradient>

          <radialGradient id="graphGlowYellow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(246,223,139,0.20)" />
            <stop offset="100%" stopColor="rgba(246,223,139,0)" />
          </radialGradient>
        </defs>

        {/* soft background glows */}
        <circle cx="180" cy="120" r="130" fill="url(#graphGlowPink)" />
        <circle cx="700" cy="170" r="140" fill="url(#graphGlowGreen)" />
        <circle cx="470" cy="380" r="150" fill="url(#graphGlowYellow)" />

        {/* edges */}
        {edges.map((e, i) => {
          const src = layout.positions.get(e.source);
          const tgt = layout.positions.get(e.target);
          if (!src || !tgt) return null;

          const stroke =
            e.type === "prereq"
              ? "rgba(191,216,184,0.50)"
              : "rgba(247,167,195,0.42)";

          const sw =
            e.type === "prereq"
              ? Math.max(1.5, e.weight)
              : Math.max(1.5, Math.min(4, e.weight));

          return (
            <line
              key={i}
              x1={src.x}
              y1={src.y}
              x2={tgt.x}
              y2={tgt.y}
              stroke={stroke}
              strokeWidth={sw}
              strokeLinecap="round"
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
            ? "rgba(191,216,184,0.72)"
            : "rgba(246,223,139,0.66)";

          const stroke = isConcept(n)
            ? "rgba(159,196,156,0.98)"
            : "rgba(240,205,89,0.96)";

          return (
            <g key={n.id}>
              <circle
                cx={p.x}
                cy={p.y}
                r={radius + 6}
                fill={isConcept(n) ? "rgba(191,216,184,0.14)" : "rgba(246,223,139,0.12)"}
              />

              <circle
                cx={p.x}
                cy={p.y}
                r={radius}
                fill={fill}
                stroke={stroke}
                strokeWidth={2}
                onMouseEnter={() => setHovered(n.id)}
                onMouseLeave={() => setHovered(null)}
                style={{
                  filter: "drop-shadow(0 8px 16px rgba(190, 176, 158, 0.16))",
                  cursor: "default",
                }}
              >
                <title>
                  {isConcept(n)
                    ? `${n.label}\nmastery: ${(n.mastery_prob * 100).toFixed(0)}%\nmistakes: ${n.mistake_count}`
                    : `${n.label}`}
                </title>
              </circle>

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
      transform={`rotate(${rotate}, ${p.x}, ${p.y}) translate(0 ${radius + 16})`}
      textAnchor="middle"
      fontSize="12"
      fontWeight="600"
      fill="rgba(47,42,47,0.88)"
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