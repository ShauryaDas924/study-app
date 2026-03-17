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

  useEffect(() => {
    if (!classId) return;

    fetch(`http://localhost:8000/homework/pitfalls/${classId}`)
      .then((r) => r.json())
      .then(setPitfalls)
      .catch(() => setPitfalls([]));
  }, [classId]);

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
    } catch (err) {
      setGenerated("Failed to generate practice. Try again.");
    }

    setLoading(false);
  };

  return (
    <div className="py-7 space-y-6">
      <h1 className="text-3xl font-semibold text-slate-900">Tutor</h1>

      <Card>
        <CardHeader
          title="Practice Weak Areas"
          subtitle="Train specific weaknesses detected from homework"
        />

        <select
          className="border p-2 rounded w-full"
          onChange={(e) => handleSelect(e.target.value)}
        >
          <option>Select a pitfall</option>

          {pitfalls.map((p, i) => (
            <option key={i} value={p.pitfall}>
              {p.pitfall}
            </option>
          ))}
        </select>

        {/* ✅ OUTPUT AREA */}
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
      </Card>

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