"use client";

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/Button";

type Msg = { role: "user" | "tutor"; text: string };

export default function TutorChat() {
  const currentQuestion = useStore((s) => s.currentQuestion);

  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);

  const qid = currentQuestion?.id;

  const ask = useMutation({
    mutationFn: async (question: string) => {
      if (!qid) throw new Error("No active question. Start Practice or Exam first.");
      return api.tutorAsk(qid, { question });
    },
    onSuccess: (data) => {
      setMsgs((m) => [...m, { role: "tutor", text: data.hint }]);
    },
  });

  const header = useMemo(() => {
    if (!qid) return "No active question selected.";
    return `Question ID: ${qid}`;
  }, [qid]);

  function send() {
    const text = input.trim();
    if (!text) return;

    setMsgs((m) => [...m, { role: "user", text }]);
    setInput("");
    ask.mutate(text);
  }

  return (
    <div className="space-y-3">
      <div className="text-xs text-slate-500">{header}</div>

      <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4 h-[320px] overflow-auto space-y-3">
        {msgs.length === 0 ? (
          <div className="text-sm text-slate-500">
            Ask: “What method should I use?” or “What’s a good first step?”
          </div>
        ) : null}

        {msgs.map((m, i) => (
          <div
            key={i}
            className={[
              "max-w-[85%] rounded-2xl px-4 py-2 text-sm",
              m.role === "user"
                ? "ml-auto bg-blue-100 text-slate-900 border border-blue-200"
                : "bg-white text-slate-900 border border-slate-200",
            ].join(" ")}
          >
            {m.text}
          </div>
        ))}
      </div>

      {ask.error ? <div className="text-sm text-pink-600">{String(ask.error)}</div> : null}

      <div className="flex gap-2">
        <input
          className="flex-1 rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-200"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask for a hint (not the answer)…"
          onKeyDown={(e) => {
            if (e.key === "Enter") send();
          }}
        />
        <Button onClick={send} disabled={ask.isPending}>
          Send
        </Button>
      </div>
    </div>
  );
}