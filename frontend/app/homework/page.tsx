"use client";

import { useEffect, useRef, useState } from "react";
import { useStore } from "@/store/useStore";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
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

export default function HomeworkPage() {
  const classId = useStore((s) => s.selectedClassId);

  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  const [reviewSessionId, setReviewSessionId] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState("");
  const [stepPrompt, setStepPrompt] = useState("");
  const [stepAction, setStepAction] = useState<
    "check_this_step" | "help_me_continue" | "what_did_i_do_right" | "what_to_watch_next_time"
  >("check_this_step");
  const [uploadedWorkName, setUploadedWorkName] = useState("");
  const [stepHistory, setStepHistory] = useState<StepHistoryItem[]>([]);
  const [reviewSessions, setReviewSessions] = useState<ReviewSession[]>([]);
  const [selectedRegion, setSelectedRegion] = useState<any | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [questions, setQuestions] = useState<string[]>([]);
  const [qIndex, setQIndex] = useState(0);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!classId) return;

    const saved = localStorage.getItem(`chat_${classId}`);
    if (saved) {
      try {
        setMessages(JSON.parse(saved));
      } catch {
        setMessages([]);
      }
    } else {
      setMessages([]);
    }
  }, [classId]);

  useEffect(() => {
    async function loadChat() {
      if (!classId) return;

      const res = await fetch(`http://localhost:8000/homework/chat-history/${classId}`);
      const data = await res.json();

      if (Array.isArray(data) && data.length > 0) {
        setMessages(data);
      }
    }

    loadChat();
  }, [classId]);

  useEffect(() => {
    async function loadReviewSessions() {
      if (!classId) return;

      const res = await fetch(`http://localhost:8000/homework/review-work-sessions/${classId}`);
      const data = await res.json();
      setReviewSessions(Array.isArray(data) ? data : []);
    }

    loadReviewSessions();
  }, [classId]);

  useEffect(() => {
    if (!classId) return;
    localStorage.setItem(`chat_${classId}`, JSON.stringify(messages));
  }, [messages, classId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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

  function AssistantMessage({ content }: { content: string }) {
    const text = formatTutorText(content);

    return (
      <div className="prose prose-slate themed-markdown max-w-none leading-7 break-words">
        <ReactMarkdown
          remarkPlugins={[remarkMath]}
          rehypePlugins={[rehypeKatex]}
          components={{
            p: ({ children }) => <p className="mb-3 leading-7">{children}</p>,
            pre: ({ children }) => (
              <pre className="my-4 overflow-x-auto rounded-lg bg-slate-50 p-4 text-sm leading-6">
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
            h2: ({ children }) => <h2 className="mt-4 mb-2 text-lg font-semibold">{children}</h2>,
            h3: ({ children }) => <h3 className="mt-3 mb-2 text-base font-semibold">{children}</h3>,
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
    );
  }

  async function ask(text?: string) {
    const question = text ?? q;

    if (!classId) return;
    if (!question.trim()) return;

    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/homework/help", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ class_id: classId, question }),
      });

      const data = await res.json();

      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.help || "No response returned." },
      ]);
      setQ("");
    } finally {
      setLoading(false);
    }
  }

  async function loadStepHistory(sessionId?: string) {
    const sid = sessionId || reviewSessionId;
    if (!sid) return;

    const res = await fetch(`http://localhost:8000/homework/step-review-history/${sid}`);
    const data = await res.json();
    setStepHistory(Array.isArray(data) ? data : []);
  }

  async function refreshReviewSessions() {
    if (!classId) return;

    const res = await fetch(`http://localhost:8000/homework/review-work-sessions/${classId}`);
    const data = await res.json();
    setReviewSessions(Array.isArray(data) ? data : []);
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
      const res = await fetch("http://localhost:8000/homework/step-check", {
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

      const data = await res.json();

      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.response_markdown || "No response returned.",
        },
      ]);

      await loadStepHistory(reviewSessionId);
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
      const res = await fetch(`http://localhost:8000/homework/upload-help?class_id=${classId}`, {
        method: "POST",
        body: form,
      });

      const data = await res.json();

      setQuestions(Array.isArray(data.questions) ? data.questions : []);
      setQIndex(0);
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
      const res = await fetch(`http://localhost:8000/homework/review-work?class_id=${classId}`, {
        method: "POST",
        body: form,
      });

      const data = await res.json();

      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.review || "No review returned.",
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
      const res = await fetch(
        `http://localhost:8000/homework/review-work-session?class_id=${classId}`,
        {
          method: "POST",
          body: form,
        }
      );

      const data = await res.json();

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
          }** for step check.\n\nNow tell me what step you're confused at, or paste the step text.`,
        },
      ]);
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  async function clearChat() {
    if (!classId) return;

    await fetch(`http://localhost:8000/homework/chat-history/${classId}`, {
      method: "DELETE",
    });

    setMessages([]);
  }

  return (
    <div className="app-shell min-h-[calc(100vh-100px)] px-4 py-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <h1 className="text-2xl font-semibold">Homework Helper</h1>

        {questions.length > 0 && (
          <div className="app-panel max-w-4xl p-5">
            <div className="mb-2 font-semibold text-green-800">
              Question {qIndex + 1} / {questions.length}
            </div>
            <ReactMarkdown>{questions[qIndex]}</ReactMarkdown>
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
          <section className="min-w-0">
            <div className="app-panel flex min-h-[360px] flex-col p-4">
              <div className="mb-4 text-lg font-semibold">Chat</div>

              <div className="min-h-[240px] space-y-4">
                {messages.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                    Ask a question, upload work for review, or use Step Check Tutor.
                  </div>
                ) : (
                  messages.map((m, i) => (
                    <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
                      <div
                        className={
                          m.role === "user"
                            ? "inline-block max-w-[85%] whitespace-pre-wrap break-words rounded-2xl border px-4 py-3 text-left"
                            : "inline-block max-w-full rounded-2xl p-4 text-left"
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
                          <AssistantMessage content={m.content} />
                        ) : (
                          <div className="whitespace-pre-wrap break-words leading-7">
                            {m.content}
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}

                <div ref={chatEndRef} />
              </div>
            </div>
          </section>

          <aside className="min-w-0">
            <div className="flex flex-col gap-4">
              <div className="app-panel p-4">
                <div className="mb-3 text-sm font-semibold">Ask Tutor</div>

                <textarea
                  className="w-full app-input rounded-2xl p-3 shadow-sm"
                  rows={3}
                  placeholder="Ask something..."
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                />

                {loading && <div className="mt-2 text-sm text-slate-500">Thinking...</div>}

                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    onClick={() => {
                      if (qIndex > 0) setQIndex(qIndex - 1);
                    }}
                    className="app-button-secondary px-3 py-2"
                  >
                    Prev
                  </button>

                  <button
                    onClick={() => {
                      if (qIndex < questions.length - 1) setQIndex(qIndex + 1);
                    }}
                    className="app-button-secondary px-3 py-2"
                  >
                    Next
                  </button>

                  <button
                    onClick={() => ask(questions[qIndex])}
                    disabled={questions.length === 0}
                    className="app-button-primary px-3 py-2 disabled:opacity-50"
                  >
                    Solve This Question
                  </button>

                  <button
                    disabled={!classId || loading}
                    onClick={() => ask()}
                    className="app-button-primary px-4 py-2"
                  >
                    Ask
                  </button>

                  <button
                    disabled={loading}
                    onClick={() => ask("hint")}
                    className="app-button-secondary px-3 py-2"
                  >
                    Hint
                  </button>

                  <button
                    disabled={loading}
                    onClick={() => ask("next step")}
                    className="app-button-secondary px-3 py-2"
                  >
                    Next Step
                  </button>

                  <button
                    disabled={loading}
                    onClick={() =>
                      ask("analyze my work what did I do well and what are my pitfalls and mistakes")
                    }
                    className="app-button-primary px-3 py-2"
                  >
                    Analyze My Work
                  </button>
                </div>
              </div>

              <div className="app-panel p-4">
                <div className="mb-2 text-sm font-semibold">Upload Assignment / Extract Questions</div>
                <div className="mb-3 text-xs text-slate-600">
                  Upload a homework sheet or document and extract question text.
                </div>
                <input type="file" onChange={upload} />
              </div>

              <div className="app-panel p-4">
                <div className="mb-2 text-sm font-semibold">Review My Full Work</div>
                <div className="mb-3 text-xs text-slate-600">
                  Upload your whole solution and get broad feedback on what is correct, what
                  is off, and the next step.
                </div>
                <input type="file" onChange={reviewUpload} />
              </div>

              <div className="app-panel p-4">
                <div className="mb-2 text-sm font-semibold">Step Check Tutor</div>

                <div className="mb-3 text-xs text-slate-600">
                  Upload your work, point to the step you’re stuck on, and the tutor will tell
                  you what’s right, what’s off, and what to do next.
                </div>

                {reviewSessions.length > 0 && (
                  <div className="mb-3">
                    <div className="mb-1 text-xs text-slate-600">
                      Reuse a previous uploaded work session
                    </div>
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
                      className="w-full rounded-xl border bg-white px-3 py-2"
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

                <input type="file" onChange={uploadStepCheckWork} className="mb-3" />

                {uploadedWorkName && (
                  <div className="mb-2 text-sm">
                    Uploaded: <span className="font-medium">{uploadedWorkName}</span>
                  </div>
                )}

                <div className="mb-2 rounded-xl border border-dashed border-slate-300 p-3 text-sm text-slate-600">
                  Region selection coming next. For now, describe the exact step in the box below.
                </div>

                <select
                  value={stepAction}
                  onChange={(e) => setStepAction(e.target.value as any)}
                  className="mb-2 w-full rounded-xl border bg-white px-3 py-2"
                >
                  <option value="check_this_step">Check this step</option>
                  <option value="help_me_continue">Help me continue</option>
                  <option value="what_did_i_do_right">What did I do right?</option>
                  <option value="what_to_watch_next_time">What should I watch next time?</option>
                </select>

                <textarea
                  className="mb-2 w-full app-input rounded-2xl p-3 shadow-sm"
                  rows={2}
                  placeholder="Which step are you confused at? Example: 'From the point where I wrote PV = ...' or 'Step 3 where I converted the nominal rate.'"
                  value={selectedStep}
                  onChange={(e) => setSelectedStep(e.target.value)}
                />

                <textarea
                  className="mb-2 w-full app-input rounded-2xl p-3 shadow-sm"
                  rows={3}
                  placeholder="Ask specifically: 'Did I do this step right?' or 'Why is this step wrong?' or 'What should I do next from here?'"
                  value={stepPrompt}
                  onChange={(e) => setStepPrompt(e.target.value)}
                />

                <button
                  disabled={!reviewSessionId || loading}
                  onClick={runStepCheck}
                  className="app-button-primary px-4 py-2"
                >
                  Run Step Check
                </button>

                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setStepPrompt("Did I do this right?")}
                    className="app-button-secondary px-3 py-1.5 text-sm"
                  >
                    Did I do this right?
                  </button>

                  <button
                    type="button"
                    onClick={() => setStepPrompt("What do I do next from here?")}
                    className="app-button-secondary px-3 py-1.5 text-sm"
                  >
                    What do I do next?
                  </button>

                  <button
                    type="button"
                    onClick={() => setStepPrompt("What mistake am I making here?")}
                    className="app-button-secondary px-3 py-1.5 text-sm"
                  >
                    What mistake am I making?
                  </button>

                  <button
                    type="button"
                    onClick={() => setStepPrompt("What should I remember next time?")}
                    className="app-button-secondary px-3 py-1.5 text-sm"
                  >
                    What should I remember next time?
                  </button>
                </div>

                {stepHistory.length > 0 && (
                  <div className="mt-4">
                    <div className="mb-2 text-sm font-semibold">Step Review History</div>

                    <div className="space-y-3">
                      {stepHistory.map((item) => (
                        <div
                          key={item.id}
                          className="rounded-2xl border border-slate-200 bg-white p-3"
                        >
                          <div className="mb-1 text-xs text-slate-500">
                            {item.created_at
                              ? new Date(item.created_at).toLocaleString()
                              : ""}
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
                            <div className="mt-2">
                              <AssistantMessage content={item.raw_feedback} />
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div>
                <button
                  onClick={clearChat}
                  className="rounded-xl bg-red-500 px-4 py-2 text-white"
                >
                  Clear Chat
                </button>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}