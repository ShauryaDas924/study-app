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
    <div className="prose prose-slate max-w-none leading-7 break-words">
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
    <div className="flex flex-col h-[calc(100vh-100px)] overflow-hidden">
      <h1 className="text-2xl font-semibold mb-4">Homework Helper</h1>

      {/* QUESTION PREVIEW */}
      {questions.length > 0 && (
        <div className="border shadow-sm p-5 rounded-xl bg-green-50 max-w-3xl mb-4">
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
                  ? "inline-block bg-green-200 p-3 rounded-lg max-w-xl whitespace-pre-wrap break-words text-left"
                  : "inline-block bg-white border shadow-sm p-4 rounded-xl max-w-none text-left"
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
      <div className="border-t pt-3 mt-3 bg-white sticky bottom-0">
        <textarea
          className="w-full border shadow-sm p-3 rounded-lg"
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
            className="bg-gray-500 text-white px-3 py-2 rounded"
          >
            Prev
          </button>

          <button
            onClick={() => {
              if (qIndex < questions.length - 1) setQIndex(qIndex + 1);
            }}
            className="bg-gray-500 text-white px-3 py-2 rounded"
          >
            Next
          </button>

          <button
            onClick={() => ask(questions[qIndex])}
            className="bg-purple-600 text-white px-3 py-2 rounded"
          >
            Solve This Question
          </button>

          <button
            disabled={!classId || loading}
            onClick={() => ask()}
            className="bg-green-500 text-white px-4 py-2 rounded"
          >
            Ask
          </button>

          <button
            disabled={loading}
            onClick={() => ask("hint")}
            className="bg-yellow-500 text-white px-3 py-2 rounded"
          >
            Hint
          </button>

          <button
            disabled={loading}
            onClick={() => ask("next step")}
            className="bg-blue-500 text-white px-3 py-2 rounded"
          >
            Next Step
          </button>

          <button
            disabled={loading}
            onClick={() =>
              ask("analyze my work what did I do well and what are my pitfalls and mistakes")
            }
            className="bg-indigo-600 text-white px-3 py-2 rounded"
          >
            Analyze My Work
          </button>

          <input type="file" onChange={upload} />

          <div className="border p-3 rounded bg-blue-50">
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