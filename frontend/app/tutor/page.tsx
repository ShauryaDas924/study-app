"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useStore } from "@/store/useStore";
import { Card, CardHeader } from "@/components/ui/Card";
import TutorChat from "@/components/TutorChat";
import { authFetch } from "@/lib/auth";
import RequireAuth from "@/components/RequireAuth";
import { Button } from "@/components/ui/Button";
import ExamLockdownTutorMode from "@/components/exam-lockdown/ExamLockdownTutorMode";

type TutorPitfall = {
  pitfall: string;
  [key: string]: unknown;
};

function TutorContent() {
  const classId = useStore((s) => s.selectedClassId);

  const [generated, setGenerated] = useState("");
  const [loading, setLoading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [mode, setMode] = useState<"normal" | "lockdown">("normal");

  const pitfallsQ = useQuery({
    queryKey: ["homework-pitfalls", classId],
    queryFn: async (): Promise<TutorPitfall[]> => {
      if (!classId) return [];
      const res = await authFetch(`/homework/pitfalls/${classId}`);
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    },
    enabled: Boolean(classId),
  });
  const pitfalls = pitfallsQ.data ?? [];

  // ----------------------
  // SELECT PITFALL -> GENERATE PRACTICE
  // ----------------------
  const handleSelect = async (val: string) => {
    if (!classId || val === "Select a pitfall") return;

    setLoading(true);
    setGenerated("");

    try {
      const res = await authFetch(
        "/homework/practice-pitfall",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            class_id: classId,
            pitfall: val,
          }),
        }
      );

      const data = await res.json();
      setGenerated(data.questions);
    } catch {
      setGenerated("Failed to generate practice. Try again.");
    }

    setLoading(false);
  };

  // ----------------------
  // CLEAR PITFALLS
  // ----------------------
  const handleClearPitfalls = async () => {
    if (!classId) return;

    const confirmClear = window.confirm(
      "Are you sure you want to clear all detected weaknesses?"
    );
    if (!confirmClear) return;

    setClearing(true);

    try {
      await authFetch(
        `/homework/pitfalls/${classId}`,
        {
          method: "DELETE",
        }
      );

      await pitfallsQ.refetch();
      setGenerated("");
    } catch {
      alert("Failed to clear pitfalls");
    }

    setClearing(false);
  };

  // ----------------------
  // UI
  // ----------------------
  return (
    <div className="py-7 space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-slate-900">Tutor</h1>
          <div className="mt-1 text-sm text-slate-500">
            Use normal tutoring or switch into an evidence-based exam prep plan.
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant={mode === "normal" ? "primary" : "secondary"} onClick={() => setMode("normal")}>
            Normal Tutor
          </Button>
          <Button variant={mode === "lockdown" ? "primary" : "secondary"} onClick={() => setMode("lockdown")}>
            Exam Lockdown
          </Button>
        </div>
      </div>

      {mode === "lockdown" ? (
        <Card>
          <ExamLockdownTutorMode />
        </Card>
      ) : (
        <>

      {/* ---------------- PRACTICE WEAK AREAS ---------------- */}
      <Card>
        <CardHeader
          title="Practice Weak Areas"
          subtitle="Train specific weaknesses detected from homework"
        />

        {/* Dropdown */}
        <select
          className="border p-2 rounded w-full"
          onChange={(e) => handleSelect(e.target.value)}
          disabled={pitfalls.length === 0}
        >
          <option>Select a pitfall</option>

          {pitfalls.map((p, i) => (
            <option key={i} value={p.pitfall}>
              {p.pitfall}
            </option>
          ))}
        </select>

        {/* Buttons */}
        <div className="flex gap-2 mt-3">
          <button
            onClick={handleClearPitfalls}
            disabled={pitfalls.length === 0 || clearing}
            className="px-3 py-1 text-sm bg-red-100 text-red-600 rounded hover:bg-red-200 disabled:opacity-50"
          >
            {clearing ? "Clearing..." : "Clear Pitfalls"}
          </button>
        </div>

        {/* OUTPUT */}
        {loading && (
          <div className="mt-4 text-sm text-slate-500">
            Generating practice...
          </div>
        )}

        {generated && (
          <div className="mt-4 p-4 border rounded bg-slate-50 whitespace-pre-wrap">
            {generated}
          </div>
        )}

        {/* Empty State */}
        {!loading && pitfalls.length === 0 && (
          <div className="mt-4 text-sm text-slate-400">
            No weaknesses detected yet.
          </div>
        )}
      </Card>

      {/* ---------------- TUTOR CHAT ---------------- */}
      <Card>
        <CardHeader
          title="Tutor Chat"
          subtitle="Ask for hints or explanations."
        />

        <TutorChat />
      </Card>
        </>
      )}
    </div>
  );
}

export default function TutorPage() {
  return (
    <RequireAuth>
      <TutorContent />
    </RequireAuth>
  );
}
