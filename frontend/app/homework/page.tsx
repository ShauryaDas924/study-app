"use client";

import { useState, useRef, useEffect } from "react";
import { useStore } from "@/store/useStore";
import ReactMarkdown from "react-markdown";

import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

export default function HomeworkPage() {
  const classId = useStore((s) => s.selectedClassId);

  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  const [messages, setMessages] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([]);

  const [questions, setQuestions] = useState<string[]>([]);
  const [qIndex, setQIndex] = useState(0);

  const chatEndRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  if (!classId) return;

  const saved = localStorage.getItem(`chat_${classId}`);
  if (saved) {
    setMessages(JSON.parse(saved));
  }
}, [classId]);

useEffect(() => {
  async function loadChat() {
    if (!classId) return;

    const res = await fetch(
      `http://localhost:8000/homework/chat-history/${classId}`
    );

    const data = await res.json();

    // ✅ ONLY overwrite if backend actually has data
    if (data.length > 0) {
      setMessages(data);
    }
  }

  loadChat();
}, [classId]);

useEffect(() => {
  if (classId) {
    localStorage.setItem(
      `chat_${classId}`,
      JSON.stringify(messages)
    );
  }
}, [messages, classId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function formatTutorText(text: string) {
  let t = text || "";

  // normalize line endings only
  t = t.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

  // normalize escaped display math
  t = t
    .replace(/\\\[/g, "$$")
    .replace(/\\\]/g, "$$");

  // normalize escaped inline math
  t = t
    .replace(/\\\(/g, "$")
    .replace(/\\\)/g, "$");

  // optional label polish only
  t = t
    .replace(/^Concept used:/gm, "🧠 Concept Used:")
    .replace(/^Common pitfall:/gm, "⚠️ Common pitfall:");

  // collapse absurd blank lines only
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
          h1: ({ children }) => <h1 className="text-xl font-semibold mb-3">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-semibold mb-2 mt-4">{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-semibold mb-2 mt-3">{children}</h3>,
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

  // ================= ASK =================
  async function ask(text?: string) {
    const question = text ?? q;

    if (!classId) return;
    if (!question.trim()) return;

    setMessages((m) => [...m, { role: "user", content: question }]);

    setLoading(true);

    const res = await fetch("http://localhost:8000/homework/help", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        class_id: classId,
        question,
      }),
    });

    const data = await res.json();

    setMessages((m) => [...m, { role: "assistant", content: data.help }]);

    setQ("");
    setLoading(false);
  }

  // ================= FILE UPLOAD =================
  async function upload(e: any) {
    if (!classId) return;

    const file = e.target.files[0];
    if (!file) return;

    const form = new FormData();
    form.append("file", file);

    setLoading(true);

    const res = await fetch(
      `http://localhost:8000/homework/upload-help?class_id=${classId}`,
      { method: "POST", body: form }
    );

    const data = await res.json();

    setQuestions(data.questions || []);
    setQIndex(0);

    setLoading(false);
  }

  // ================= REVIEW WORK =================
  async function reviewUpload(e: any) {
    if (!classId) return;

    const file = e.target.files[0];
    if (!file) return;

    const form = new FormData();
    form.append("file", file);

    setLoading(true);

    const res = await fetch(
      `http://localhost:8000/homework/review-work?class_id=${classId}`,
      {
        method: "POST",
        body: form,
      }
    );

    const data = await res.json();

    setMessages((m) => [
      ...m,
      {
        role: "assistant",
        content: data.review,
      },
    ]);

    setLoading(false);
  }

  // ================= CLEAR CHAT =================
  async function clearChat() {
    if (!classId) return;

    await fetch(`http://localhost:8000/homework/chat-history/${classId}`, {
      method: "DELETE",
    });

    setMessages([]);
  }

  return (
   <div className="app-shell flex flex-col h-[calc(100vh-100px)] overflow-hidden">
      <h1 className="text-2xl font-semibold mb-4">Homework Helper</h1>

      {/* QUESTION PREVIEW */}
      {questions.length > 0 && (
        <div className="app-panel p-5 max-w-3xl mb-4">
          <div className="font-semibold text-green-800 mb-2">
            Question {qIndex + 1} / {questions.length}
          </div>

          <ReactMarkdown>{questions[qIndex]}</ReactMarkdown>
        </div>
      )}

      {/* CHAT WINDOW */}
      <div className="space-y-4 max-w-3xl overflow-y-auto flex-1 pr-2 min-h-0">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
           <div
  className={
    m.role === "user"
      ? "inline-block max-w-xl whitespace-pre-wrap break-words text-left px-4 py-3 rounded-2xl border"
      : "inline-block app-panel p-4 max-w-none text-left"
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
        ))}

        <div ref={chatEndRef}></div>
      </div>

      {loading && <div className="mt-2">Thinking...</div>}

      {/* INPUT BAR (BOTTOM) */}
     <div className="pt-3 mt-3 sticky bottom-0">
       <textarea
  className="w-full app-input shadow-sm p-3 rounded-2xl"
          rows={3}
          placeholder="Ask something..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />

        <div className="flex gap-3 flex-wrap mt-2">
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
            className="app-button-primary px-3 py-2"
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

          <input type="file" onChange={upload} />

          <div className="app-soft-panel p-3">
            <div className="text-sm font-semibold mb-1">
              Upload your work for feedback
            </div>

            <input type="file" onChange={reviewUpload} />
          </div>

          <button
            onClick={clearChat}
            className="bg-red-500 text-white px-3 py-2 rounded"
          >
            Clear Chat
          </button>
        </div>
      </div>
    </div>
  );
}