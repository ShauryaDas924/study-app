"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

export default function ExamCoachResponse({ markdown }: { markdown: string }) {
  if (!markdown) return null;

  return (
    <div className="rounded-xl border border-slate-100 bg-white p-4 text-sm leading-6 text-slate-800">
      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
