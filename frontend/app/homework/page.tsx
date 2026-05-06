"use client";

import { useEffect, useRef, useState } from "react";
import { useStore } from "@/store/useStore";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { authFetch } from "@/lib/auth";
import RequireAuth from "@/components/RequireAuth";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  grounding?: GroundingMetadata | null;
};

type GroundingConcept = {
  id?: string | null;
  name?: string | null;
  concept_name?: string | null;
  score?: number | null;
  confidence?: number | null;
};

type GroundingMetadata = {
  grounding_confidence?: number | null;
  grounding_mode?: string | null;
  concepts_used?: GroundingConcept[] | null;
};

type TutorResponse = GroundingMetadata & {
  help?: string;
  answer?: string;
  response?: string;
  message?: string;
  review?: string;
  response_markdown?: string;
  detail?: string;
  error?: string;
};

type UploadHelpResponse = {
  questions?: string[];
  count?: number;
  detail?: string;
  error?: string;
};

type ReviewWorkSessionCreateResponse = {
  session_id?: string | null;
  filename?: string | null;
  extracted_text?: string | null;
  detail?: string;
  error?: string;
};

type ReviewSession = {
  id: string;
  filename?: string | null;
  source_type?: string | null;
  created_at?: string | null;
};

type StepHistoryItem = {
  id: string;
  user_prompt?: string | null;
  selected_step?: string | null;
  concept_name?: string | null;
  step_verdict?: string | null;
  error_type?: string | null;
  root_cause_step?: string | null;
  correct_parts?: string[];
  issues?: string[];
  next_step?: string | null;
  next_time_rule?: string | null;
  pitfall_tag?: string | null;
  confidence?: number | null;
  raw_feedback?: string | null;
  created_at?: string | null;
};

type ToolModal =
  | null
  | "upload"
  | "review"
  | "step"
  | "history"
  | "sessions";

function firstText(...values: Array<string | undefined | null>) {
  return values.find((value) => typeof value === "string" && value.trim())?.trim();
}

function getAssistantText(data: TutorResponse, fallback = "No response returned.") {
  return (
    firstText(
      data.help,
      data.answer,
      data.response,
      data.message,
      data.review,
      data.response_markdown
    ) || fallback
  );
}

function normalizeGroundingMode(mode?: string | null) {
  if (!mode) return null;
  const value = mode.toLowerCase();

  if (value.includes("strong") || value.includes("grounded")) return "grounded";
  if (value.includes("weak") || value.includes("general") || value.includes("no_context")) {
    return "general";
  }

  return null;
}

function getConceptDisplayNames(concepts?: GroundingConcept[] | null) {
  if (!Array.isArray(concepts)) return [];

  const names = concepts
    .map((concept) => firstText(concept.name, concept.concept_name))
    .filter((name): name is string => Boolean(name));

  return Array.from(new Set(names));
}

function formatGroundingConfidence(value?: number | null) {
  if (typeof value !== "number" || Number.isNaN(value) || value <= 0) return null;
  const pct = Math.round(Math.max(0, Math.min(value, 1)) * 100);
  return `Course match: ${pct}%`;
}

function getGroundingMetadata(data: TutorResponse): GroundingMetadata | null {
  if (!normalizeGroundingMode(data.grounding_mode)) return null;

  return {
    grounding_confidence: data.grounding_confidence,
    grounding_mode: data.grounding_mode,
    concepts_used: Array.isArray(data.concepts_used) ? data.concepts_used : null,
  };
}

function parseStoredMessages(raw: string | null): ChatMessage[] {
  if (!raw) return [];

  try {
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

function preserveStoredGrounding(
  serverMessages: ChatMessage[],
  storedMessages: ChatMessage[]
) {
  const usedStoredIndexes = new Set<number>();

  return serverMessages.map((message) => {
    if (message.grounding || message.role !== "assistant") return message;

    const storedIndex = storedMessages.findIndex((stored, index) => {
      return (
        !usedStoredIndexes.has(index) &&
        stored.role === "assistant" &&
        stored.content === message.content &&
        Boolean(stored.grounding)
      );
    });

    if (storedIndex === -1) return message;

    usedStoredIndexes.add(storedIndex);
    return {
      ...message,
      grounding: storedMessages[storedIndex].grounding,
    };
  });
}

function HomeworkContent() {
  const classId = useStore((s) => s.selectedClassId);

  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeModal, setActiveModal] = useState<ToolModal>(null);

  const [reviewSessionId, setReviewSessionId] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState("");
  const [stepPrompt, setStepPrompt] = useState("");
  const [stepAction, setStepAction] = useState<
    | "check_this_step"
    | "help_me_continue"
    | "what_did_i_do_right"
    | "what_to_watch_next_time"
  >("check_this_step");

  const [uploadedWorkName, setUploadedWorkName] = useState("");
  const [stepHistory, setStepHistory] = useState<StepHistoryItem[]>([]);
  const [reviewSessions, setReviewSessions] = useState<ReviewSession[]>([]);
  const [selectedRegion, setSelectedRegion] = useState<any | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [questions, setQuestions] = useState<string[]>([]);
  const [qIndex, setQIndex] = useState(0);

  const chatEndRef = useRef<HTMLDivElement>(null);

  const currentQuestion = questions[qIndex] || "";

  useEffect(() => {
    if (!classId) return;

    setMessages(parseStoredMessages(localStorage.getItem(`chat_${classId}`)));
  }, [classId]);

  useEffect(() => {
    async function loadChat() {
      if (!classId) return;

      try {
        const res = await authFetch(`/homework/chat-history/${classId}`);
        const data = (await res.json()) as unknown;

        if (Array.isArray(data) && data.length > 0) {
          const serverMessages = data as ChatMessage[];
          const storedMessages = parseStoredMessages(localStorage.getItem(`chat_${classId}`));
          setMessages(preserveStoredGrounding(serverMessages, storedMessages));
        }
      } catch {
        // Keep local messages if server history fails.
      }
    }

    loadChat();
  }, [classId]);

  useEffect(() => {
    async function loadReviewSessions() {
      if (!classId) return;

      try {
        const res = await authFetch(`/homework/review-work-sessions/${classId}`);
        const data = (await res.json()) as unknown;
        setReviewSessions(Array.isArray(data) ? (data as ReviewSession[]) : []);
      } catch {
        setReviewSessions([]);
      }
    }

    loadReviewSessions();
  }, [classId]);

  useEffect(() => {
    if (!classId) return;
    localStorage.setItem(`chat_${classId}`, JSON.stringify(messages));
  }, [messages, classId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function formatTutorText(text: string) {
    let t = text || "";

    t = t.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

    t = t.replace(/\\\[/g, "$$").replace(/\\\]/g, "$$");
    t = t.replace(/\\\(/g, "$").replace(/\\\)/g, "$");

    t = t
      .replace(/^Concept used:/gm, "🧠 Concept Used:")
      .replace(/^Common pitfall:/gm, "⚠️ Common pitfall:");

    t = t.replace(/\n{3,}/g, "\n\n");

    return t.trim();
  }

  function GroundingBadge({ grounding }: { grounding?: GroundingMetadata | null }) {
    const mode = normalizeGroundingMode(grounding?.grounding_mode);
    if (!mode) return null;

    const isGrounded = mode === "grounded";
    const conceptNames = getConceptDisplayNames(grounding?.concepts_used);
    const visibleConcepts = conceptNames.slice(0, 3);
    const hiddenCount = Math.max(0, conceptNames.length - visibleConcepts.length);
    const confidence = isGrounded
      ? formatGroundingConfidence(grounding?.grounding_confidence)
      : null;

    const subtext = isGrounded
      ? visibleConcepts.length > 0
        ? `${visibleConcepts.join(" · ")}${hiddenCount ? ` · +${hiddenCount} more` : ""}`
        : "Course context used"
      : "No strong match found in your uploaded notes.";

    return (
      <div
        className="mb-3 rounded-2xl border px-3 py-2 text-xs"
        style={{
          background: isGrounded ? "var(--gradient-card)" : "rgba(255,255,255,0.72)",
          borderColor: "var(--border-soft)",
          boxShadow: "var(--shadow-soft)",
          color: "var(--text-main)",
        }}
      >
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span
            className="h-2 w-2 rounded-full"
            style={{
              background: isGrounded ? "var(--gradient-main)" : "rgba(95,89,96,0.38)",
            }}
          />
          <span className="font-semibold">
            {isGrounded ? "Using your course notes" : "General explanation"}
          </span>
          {confidence && (
            <span style={{ color: "var(--text-soft)" }}>{confidence}</span>
          )}
        </div>
        <div className="mt-1 leading-5" style={{ color: "var(--text-soft)" }}>
          {subtext}
        </div>
      </div>
    );
  }

  function AssistantMessage({
    content,
    grounding,
  }: {
    content: string;
    grounding?: GroundingMetadata | null;
  }) {
    const text = formatTutorText(content);

    return (
      <>
        <GroundingBadge grounding={grounding} />
        <div className="prose prose-slate themed-markdown max-w-none leading-7 break-words">
          <ReactMarkdown
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{
              p: ({ children }) => <p className="mb-3 leading-7">{children}</p>,
              pre: ({ children }) => (
                <pre className="my-4 overflow-x-auto rounded-2xl bg-slate-50 p-4 text-sm leading-6">
                  {children}
                </pre>
              ),
              code: ({ inline, children, ...props }: any) =>
                inline ? (
                  <code className="rounded bg-slate-100 px-1 py-0.5 text-sm" {...props}>
                    {children}
                  </code>
                ) : (
                  <code className="text-sm" {...props}>
                    {children}
                  </code>
                ),
              ul: ({ children }) => <ul className="my-3 list-disc pl-6">{children}</ul>,
              ol: ({ children }) => <ol className="my-3 list-decimal pl-6">{children}</ol>,
              li: ({ children }) => <li className="mb-1">{children}</li>,
              h1: ({ children }) => <h1 className="mb-3 text-xl font-semibold">{children}</h1>,
              h2: ({ children }) => (
                <h2 className="mt-5 mb-2 text-lg font-semibold">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="mt-4 mb-2 text-base font-semibold">{children}</h3>
              ),
              blockquote: ({ children }) => (
                <blockquote className="my-3 border-l-4 border-slate-300 pl-4 italic text-slate-700">
                  {children}
                </blockquote>
              ),
            }}
          >
            {text}
          </ReactMarkdown>
        </div>
      </>
    );
  }

  function Modal({
    title,
    children,
  }: {
    title: string;
    children: React.ReactNode;
  }) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 py-6 backdrop-blur-sm">
        <div className="w-full max-w-2xl overflow-hidden rounded-3xl border border-orange-100 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-orange-100 px-5 py-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
              <p className="text-xs text-slate-500">Homework Helper tool</p>
            </div>

            <button
              onClick={() => setActiveModal(null)}
              className="rounded-full border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-50"
            >
              Close
            </button>
          </div>

          <div className="max-h-[75vh] overflow-y-auto p-5">{children}</div>
        </div>
      </div>
    );
  }

  async function ask(text?: string) {
    const question = text ?? q;

    if (!classId) return;
    if (!question.trim()) return;

    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);

    try {
      const res = await authFetch("/homework/help", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ class_id: classId, question }),
      });

      let data: TutorResponse = {};
      try {
        data = (await res.json()) as TutorResponse;
      } catch {
        data = {};
      }

      if (!res.ok) {
        const detail = data?.detail || data?.error || `Request failed with ${res.status}`;
        setMessages((m) => [
          ...m,
          { role: "assistant", content: `Error: ${detail}` },
        ]);
        return;
      }

      const answer = getAssistantText(data);

      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: answer,
          grounding: getGroundingMetadata(data),
        },
      ]);
      setQ("");
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            "Error: could not reach the homework tutor. Check that the backend is running.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function loadStepHistory(sessionId?: string) {
    const sid = sessionId || reviewSessionId;
    if (!sid) return;

    try {
      const res = await authFetch(`/homework/step-review-history/${sid}`);
      const data = (await res.json()) as unknown;
      setStepHistory(Array.isArray(data) ? (data as StepHistoryItem[]) : []);
    } catch {
      setStepHistory([]);
    }
  }

  async function refreshReviewSessions() {
    if (!classId) return;

    try {
      const res = await authFetch(`/homework/review-work-sessions/${classId}`);
      const data = (await res.json()) as unknown;
      setReviewSessions(Array.isArray(data) ? (data as ReviewSession[]) : []);
    } catch {
      setReviewSessions([]);
    }
  }

  async function runStepCheck() {
    if (!classId || !reviewSessionId) return;
    if (!stepPrompt.trim()) return;

    setMessages((m) => [
      ...m,
      {
        role: "user",
        content: `Step Check\nAction: ${stepAction}\nStep: ${
          selectedStep || "(not specified)"
        }\nPrompt: ${stepPrompt}`,
      },
    ]);

    setLoading(true);

    try {
      const res = await authFetch("/homework/step-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          class_id: classId,
          session_id: reviewSessionId,
          user_prompt: stepPrompt,
          selected_step: selectedStep,
          selected_region: selectedRegion,
          action: stepAction,
        }),
      });

      const data = (await res.json()) as TutorResponse;

      if (!res.ok) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: `Error: ${data?.detail || data?.error || "Step check failed."}`,
          },
        ]);
        return;
      }

      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: getAssistantText(data),
        },
      ]);

      await loadStepHistory(reviewSessionId);
      setActiveModal(null);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Error: could not run step check.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    if (!classId) return;

    const file = e.target.files?.[0];
    if (!file) return;

    const form = new FormData();
    form.append("file", file);

    setLoading(true);

    try {
      const res = await authFetch(
        `/homework/upload-help?class_id=${classId}`,
        {
          method: "POST",
          body: form,
        }
      );

      const data = (await res.json()) as UploadHelpResponse;

      if (!res.ok) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: `Error: ${data?.detail || "Could not extract questions."}`,
          },
        ]);
        return;
      }

      setQuestions(Array.isArray(data.questions) ? data.questions : []);
      setQIndex(0);
      setActiveModal(null);

      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Extracted ${Array.isArray(data.questions) ? data.questions.length : 0} question(s). Use the question card at the top to solve them one at a time.`,
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Error: could not upload or extract the assignment.",
        },
      ]);
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  async function reviewUpload(e: React.ChangeEvent<HTMLInputElement>) {
    if (!classId) return;

    const file = e.target.files?.[0];
    if (!file) return;

    const form = new FormData();
    form.append("file", file);

    setLoading(true);

    try {
      const res = await authFetch(
        `/homework/review-work?class_id=${classId}`,
        {
          method: "POST",
          body: form,
        }
      );

      const data = (await res.json()) as TutorResponse;

      if (!res.ok) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: `Error: ${data?.detail || data?.error || "Review failed."}`,
          },
        ]);
        return;
      }

      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: getAssistantText(data, "No review returned."),
        },
      ]);

      setActiveModal(null);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Error: could not review the uploaded work.",
        },
      ]);
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  async function uploadStepCheckWork(e: React.ChangeEvent<HTMLInputElement>) {
    if (!classId) return;

    const file = e.target.files?.[0];
    if (!file) return;

    const form = new FormData();
    form.append("file", file);

    setLoading(true);

    try {
      const res = await authFetch(
        `/homework/review-work-session?class_id=${classId}`,
        {
          method: "POST",
          body: form,
        }
      );

      const data = (await res.json()) as ReviewWorkSessionCreateResponse;

      if (!res.ok) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            content: `Error: ${data?.detail || "Could not create review session."}`,
          },
        ]);
        return;
      }

      setReviewSessionId(data.session_id || null);
      setUploadedWorkName(data.filename || file.name);

      if (data.session_id) {
        await loadStepHistory(data.session_id);
      } else {
        setStepHistory([]);
      }

      await refreshReviewSessions();

      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Uploaded **${
            data.filename || file.name
          }** for step check.\n\nNow describe the exact step you want checked.`,
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Error: could not upload work for step check.",
        },
      ]);
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  async function clearChat() {
    if (!classId) return;

    try {
      await authFetch(`/homework/chat-history/${classId}`, {
        method: "DELETE",
      });
    } finally {
      setMessages([]);
    }
  }

  return (
    <div className="app-shell min-h-[calc(100vh-80px)] px-4 py-5">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Homework Helper</h1>
            <p className="text-sm text-slate-500">
              Grounded tutor for homework, notes, and step-by-step review.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setActiveModal("upload")}
              className="rounded-2xl border border-orange-100 bg-white px-4 py-2 text-sm shadow-sm hover:bg-orange-50"
            >
              Upload Assignment
            </button>

            <button
              onClick={() => setActiveModal("review")}
              className="rounded-2xl border border-orange-100 bg-white px-4 py-2 text-sm shadow-sm hover:bg-orange-50"
            >
              Review Work
            </button>

            <button
              onClick={() => setActiveModal("step")}
              className="rounded-2xl border border-orange-100 bg-white px-4 py-2 text-sm shadow-sm hover:bg-orange-50"
            >
              Step Check
            </button>

            <button
              onClick={() => setActiveModal("history")}
              className="rounded-2xl border border-orange-100 bg-white px-4 py-2 text-sm shadow-sm hover:bg-orange-50"
            >
              History
            </button>
          </div>
        </div>

        {questions.length > 0 && (
          <div className="rounded-3xl border border-orange-100 bg-white/90 p-4 shadow-sm">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-green-700">
                  Extracted Question
                </div>
                <div className="text-sm text-slate-500">
                  Question {qIndex + 1} / {questions.length}
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => setQIndex((i) => Math.max(0, i - 1))}
                  disabled={qIndex === 0}
                  className="rounded-xl border border-slate-200 px-3 py-2 text-sm disabled:opacity-40"
                >
                  Prev
                </button>

                <button
                  onClick={() =>
                    setQIndex((i) => Math.min(questions.length - 1, i + 1))
                  }
                  disabled={qIndex >= questions.length - 1}
                  className="rounded-xl border border-slate-200 px-3 py-2 text-sm disabled:opacity-40"
                >
                  Next
                </button>

                <button
  onClick={() =>
    ask(
      `Teach me how to set this up. Do not give the final answer yet. Stop after the first important setup step and ask me one check question:\n\n${currentQuestion}`
    )
  }
  disabled={loading || !currentQuestion}
  className="rounded-xl bg-gradient-to-r from-pink-300 to-yellow-300 px-4 py-2 text-sm font-medium shadow-sm disabled:opacity-50"
>
  Teach Setup
</button>
<button
  onClick={() =>
    ask(
      `Solve this question fully step by step and give the final answer:\n\n${currentQuestion}`
    )
  }
  disabled={loading || !currentQuestion}
  className="rounded-xl border border-slate-200 px-4 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
>
  Full Solution
</button>
              </div>
            </div>

            <div className="max-h-48 overflow-y-auto rounded-2xl bg-slate-50 p-4 text-sm leading-7 text-slate-800">
              <ReactMarkdown>{currentQuestion}</ReactMarkdown>
            </div>
          </div>
        )}

        <section className="rounded-3xl border border-orange-100 bg-white/90 shadow-sm">
          <div className="border-b border-orange-100 px-5 py-4">
            <div className="font-semibold text-slate-900">Chat</div>
            <div className="text-xs text-slate-500">
              Ask directly or use the tool buttons above.
            </div>
          </div>

          <div className="min-h-[420px] space-y-4 px-4 py-5">
            {messages.length === 0 ? (
              <div className="rounded-3xl border border-dashed border-slate-200 p-8 text-center text-sm text-slate-500">
                Ask a question, upload an assignment, or use Step Check Tutor.
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
                  <div
                    className={
                      m.role === "user"
                        ? "inline-block max-w-[85%] whitespace-pre-wrap break-words rounded-3xl border px-4 py-3 text-left leading-7 shadow-sm"
                        : "inline-block max-w-full rounded-3xl bg-white p-4 text-left"
                    }
                    style={
                      m.role === "user"
                        ? {
                            background:
                              "linear-gradient(135deg, rgba(247,167,195,0.32), rgba(191,216,184,0.28))",
                            borderColor: "var(--border-soft)",
                          }
                        : undefined
                    }
                  >
                    {m.role === "assistant" ? (
                      <AssistantMessage content={m.content} grounding={m.grounding} />
                    ) : (
                      <div className="whitespace-pre-wrap break-words leading-7">
                        {m.content}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {loading && (
              <div className="text-left">
                <div className="inline-flex items-center gap-2 rounded-2xl border border-orange-100 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-orange-300" />
                  Thinking...
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          <div className="sticky bottom-0 border-t border-orange-100 bg-white/95 p-4 backdrop-blur">
            <div className="flex flex-col gap-3">
              <textarea
                className="min-h-[72px] w-full resize-none rounded-3xl border border-orange-100 bg-white p-4 shadow-sm outline-none focus:border-orange-200"
                placeholder="Ask the tutor..."
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    ask();
                  }
                }}
              />

              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap gap-2">
                  <button
                    disabled={loading}
                    onClick={() => ask("hint")}
                    className="rounded-2xl border border-slate-200 px-4 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
                  >
                    Hint
                  </button>

                  <button
                    disabled={loading}
                    onClick={() => ask("next step")}
                    className="rounded-2xl border border-slate-200 px-4 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
                  >
                    Next Step
                  </button>

                  <button
                    disabled={loading}
                    onClick={() =>
                      ask("analyze my work what did I do well and what are my pitfalls and mistakes")
                    }
                    className="rounded-2xl border border-slate-200 px-4 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
                  >
                    Analyze My Work
                  </button>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={clearChat}
                    disabled={loading}
                    className="rounded-2xl border border-red-100 px-4 py-2 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                  >
                    Clear
                  </button>

                  <button
                    disabled={!classId || loading || !q.trim()}
                    onClick={() => ask()}
                    className="rounded-2xl bg-gradient-to-r from-pink-300 to-yellow-300 px-5 py-2 text-sm font-semibold shadow-sm disabled:opacity-50"
                  >
                    Ask
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      {activeModal === "upload" && (
        <Modal title="Upload Assignment / Extract Questions">
          <div className="space-y-4">
            <p className="text-sm leading-6 text-slate-600">
              Upload a homework sheet or document. The app will extract individual
              questions so you can solve them one at a time.
            </p>

            <div className="rounded-2xl border border-dashed border-slate-300 p-5">
              <input type="file" onChange={upload} />
            </div>

            {questions.length > 0 && (
              <div className="rounded-2xl bg-green-50 p-4 text-sm text-green-800">
                {questions.length} question(s) currently extracted.
              </div>
            )}
          </div>
        </Modal>
      )}

      {activeModal === "review" && (
        <Modal title="Review My Full Work">
          <div className="space-y-4">
            <p className="text-sm leading-6 text-slate-600">
              Upload your full solution. The tutor will review what is correct, what
              is off, and what the next step should be.
            </p>

            <div className="rounded-2xl border border-dashed border-slate-300 p-5">
              <input type="file" onChange={reviewUpload} />
            </div>
          </div>
        </Modal>
      )}

      {activeModal === "step" && (
        <Modal title="Step Check Tutor">
          <div className="space-y-4">
            <p className="text-sm leading-6 text-slate-600">
              Upload your work, select a previous session, then describe the exact
              step you want checked.
            </p>

            {reviewSessions.length > 0 && (
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Reuse previous uploaded work
                </label>

                <select
                  value={reviewSessionId || ""}
                  onChange={async (e) => {
                    const sid = e.target.value || null;
                    setReviewSessionId(sid);

                    const found = reviewSessions.find((s) => s.id === sid);
                    setUploadedWorkName(found?.filename || "");

                    if (sid) {
                      await loadStepHistory(sid);
                    } else {
                      setStepHistory([]);
                    }
                  }}
                  className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-3"
                >
                  <option value="">Select previous session</option>
                  {reviewSessions.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.filename || "Untitled upload"} —{" "}
                      {s.created_at ? new Date(s.created_at).toLocaleString() : ""}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="rounded-2xl border border-dashed border-slate-300 p-5">
              <input type="file" onChange={uploadStepCheckWork} />
            </div>

            {uploadedWorkName && (
              <div className="rounded-2xl bg-green-50 p-3 text-sm text-green-800">
                Uploaded: <span className="font-medium">{uploadedWorkName}</span>
              </div>
            )}

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Action
              </label>

              <select
                value={stepAction}
                onChange={(e) => setStepAction(e.target.value as any)}
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-3"
              >
                <option value="check_this_step">Check this step</option>
                <option value="help_me_continue">Help me continue</option>
                <option value="what_did_i_do_right">What did I do right?</option>
                <option value="what_to_watch_next_time">
                  What should I watch next time?
                </option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Selected step
              </label>

              <textarea
                className="w-full rounded-2xl border border-slate-200 bg-white p-3 shadow-sm outline-none focus:border-orange-200"
                rows={3}
                placeholder="Example: Step 3 where I converted the nominal rate."
                value={selectedStep}
                onChange={(e) => setSelectedStep(e.target.value)}
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Your prompt
              </label>

              <textarea
                className="w-full rounded-2xl border border-slate-200 bg-white p-3 shadow-sm outline-none focus:border-orange-200"
                rows={3}
                placeholder="Example: Did I do this step right?"
                value={stepPrompt}
                onChange={(e) => setStepPrompt(e.target.value)}
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setStepPrompt("Did I do this right?")}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
              >
                Did I do this right?
              </button>

              <button
                type="button"
                onClick={() => setStepPrompt("What do I do next from here?")}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
              >
                What do I do next?
              </button>

              <button
                type="button"
                onClick={() => setStepPrompt("What mistake am I making here?")}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
              >
                What mistake am I making?
              </button>

              <button
                type="button"
                onClick={() => setStepPrompt("What should I remember next time?")}
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
              >
                What should I remember?
              </button>
            </div>

            <button
              disabled={!reviewSessionId || loading || !stepPrompt.trim()}
              onClick={runStepCheck}
              className="w-full rounded-2xl bg-gradient-to-r from-pink-300 to-yellow-300 px-5 py-3 text-sm font-semibold shadow-sm disabled:opacity-50"
            >
              Run Step Check
            </button>
          </div>
        </Modal>
      )}

      {activeModal === "history" && (
        <Modal title="Step Review History">
          {stepHistory.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
              No step history loaded yet. Upload or select a step-check session first.
            </div>
          ) : (
            <div className="space-y-3">
              {stepHistory.map((item) => (
                <div
                  key={item.id}
                  className="rounded-2xl border border-slate-200 bg-white p-4"
                >
                  <div className="mb-1 text-xs text-slate-500">
                    {item.created_at ? new Date(item.created_at).toLocaleString() : ""}
                  </div>

                  <div className="text-sm font-medium">
                    Verdict: {item.step_verdict || "unknown"}
                  </div>

                  {item.selected_step && (
                    <div className="mt-1 text-sm">
                      <span className="font-medium">Step:</span> {item.selected_step}
                    </div>
                  )}

                  {item.user_prompt && (
                    <div className="mt-1 text-sm">
                      <span className="font-medium">Prompt:</span> {item.user_prompt}
                    </div>
                  )}

                  {item.raw_feedback && (
                    <div className="mt-3">
                      <AssistantMessage content={item.raw_feedback} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

export default function HomeworkPage() {
  return (
    <RequireAuth>
      <HomeworkContent />
    </RequireAuth>
  );
}
