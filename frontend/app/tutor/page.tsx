"use client";

import { useEffect, useState } from "react";
import { useStore } from "@/store/useStore";
import { Card, CardHeader } from "@/components/ui/Card";
import TutorChat from "@/components/TutorChat";

export default function TutorPage() {
  const classId = useStore((s) => s.selectedClassId);

  const [pitfalls, setPitfalls] = useState<any[]>([]);
  const [generated, setGenerated] = useState("");
  const [loading, setLoading] = useState(false);
  const [clearing, setClearing] = useState(false);

  // ----------------------
  // LOAD PITFALLS
  // ----------------------
  const fetchPitfalls = async () => {
    if (!classId) return;

    try {
      const res = await fetch(
        `http://localhost:8000/homework/pitfalls/${classId}`
      );
      const data = await res.json();
      setPitfalls(data || []);
    } catch {
      setPitfalls([]);
    }
  };

  useEffect(() => {
    fetchPitfalls();
  }, [classId]);

  // ----------------------
  // SELECT PITFALL → GENERATE PRACTICE
  // ----------------------
  const handleSelect = async (val: string) => {
    if (!classId || val === "Select a pitfall") return;

    setLoading(true);
    setGenerated("");

    try {
      const res = await fetch(
        "http://localhost:8000/homework/practice-pitfall",
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
      await fetch(
        `http://localhost:8000/homework/pitfalls/${classId}`,
        {
          method: "DELETE",
        }
      );

      // refresh UI
      await fetchPitfalls();
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
      <h1 className="text-3xl font-semibold text-slate-900">Tutor</h1>

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
    </div>
  );
}