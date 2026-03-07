"use client";

import { useStore } from "@/store/useStore";
import { api } from "@/lib/api";

export default function QuestionPlayer() {
  const q = useStore((s) => s.currentQuestion);

  if (!q) return null;

  return (
    <div className="mt-6 p-4 bg-white rounded-xl shadow">
      <p>{q.prompt}</p>

      <button
        onClick={() =>
          api.submitAttempt(q.id, {
            user_answer_json: {},
            is_correct: false,
            confidence: 3,
            time_spent_sec: 30,
            session_id: null,
          })
        }
        className="bg-pink-300 px-3 py-2 mt-4 rounded"
      >
        Submit Attempt
      </button>

      <button
        onClick={() => api.getHint(q.id, 1)}
        className="ml-4 bg-blue-200 px-3 py-2 rounded"
      >
        Hint
      </button>
    </div>
  );
}