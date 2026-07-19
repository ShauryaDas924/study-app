"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

export default function ExamCoachResponse({ markdown }: { markdown: string }) {
  if (!markdown) return null;

  return (
    <div className="rounded-2xl border border-slate-100 bg-white/95 p-5 text-sm leading-7 text-slate-800 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">Exam coach response</div>
          <div className="text-xs text-slate-500">Pattern first, setup second, solving last.</div>
        </div>
      </div>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          h1: ({ children }) => <h2 className="mt-5 first:mt-0 text-base font-semibold text-slate-900">{children}</h2>,
          h2: ({ children }) => (
            <h2 className="mt-5 first:mt-0 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-900">
              {children}
            </h2>
          ),
          h3: ({ children }) => <h3 className="mt-4 text-sm font-semibold text-slate-900">{children}</h3>,
          p: ({ children }) => <p className="mt-2 text-sm leading-7 text-slate-700">{children}</p>,
          ul: ({ children }) => <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">{children}</ul>,
          ol: ({ children }) => <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">{children}</ol>,
          li: ({ children }) => <li className="leading-7">{children}</li>,
          code: ({ children }) => <code className="rounded bg-slate-100 px-1 py-0.5 text-xs text-slate-800">{children}</code>,
          blockquote: ({ children }) => (
            <blockquote className="mt-3 rounded-xl border-l-4 border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
              {children}
            </blockquote>
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
