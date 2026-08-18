"use client";

import { useEffect } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import PracticeSetup from "@/components/PracticeSetup";
import PracticePlayer from "@/components/PracticePlayer";
import { useStore } from "@/store/useStore";
import { authFetch } from "@/lib/auth";
import RequireAuth from "@/components/RequireAuth";

function PracticeContent() {

  const classId = useStore(s => s.selectedClassId);
  const setPracticeSession = useStore(s => s.setPracticeSession);
  const setPracticeIndex = useStore(s => s.setPracticeIndex);

  // ✅ AUTO LOAD LATEST PRACTICE
  useEffect(() => {
    if (!classId) return;

    authFetch(`/practice/latest/${classId}`)
      .then(r => r.json())
      .then(data => {
        if (!data.questions?.length) return;

        setPracticeSession(
          data.practice_set_id,
          data.questions
        );

        // restore saved index
        const savedIndex = Number(
          localStorage.getItem("practiceIndex") || 0
        );

        setTimeout(() => {
          setPracticeIndex(savedIndex);
        }, 50);
      })
      .catch(() => undefined);

  }, [classId, setPracticeIndex, setPracticeSession]);

  return (
    <div className="py-7 space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-900">
          Practice
        </h1>

        <p className="text-slate-500 mt-1">
          Exam-style questions. Structured reasoning.
          Misconceptions tracked automatically.
        </p>
      </div>

      <Card>
        <CardHeader
          title="Generate Practice"
          subtitle="Uses your extracted concepts + mastery weighting in the backend."
        />
        <PracticeSetup />
      </Card>

      <PracticePlayer />
    </div>
  );
}

export default function PracticePage() {
  return (
    <RequireAuth>
      <PracticeContent />
    </RequireAuth>
  );
}
