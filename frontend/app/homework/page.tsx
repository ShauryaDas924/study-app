"use client";

import { useState } from "react";
import { useStore } from "@/store/useStore";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

export default function HomeworkPage(){

  const classId = useStore(s=>s.selectedClassId);

  const [q,setQ] = useState("");
  const [loading,setLoading] = useState(false);

  const [messages,setMessages] = useState<
    {role:"user"|"assistant",content:string}[]
  >([]);
const [questions,setQuestions] = useState<string[]>([]);
const [qIndex,setQIndex] = useState(0);
  // ================= ASK =================
  async function ask(text?:string){

    const question = text ?? q;

    if(!classId) return;
    if(!question.trim()) return;

    setMessages(m=>[
      ...m,
      {role:"user",content:question}
    ]);

    setLoading(true);

    const res = await fetch(
      "http://localhost:8000/homework/help",
      {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          class_id:classId,
          question
        })
      }
    );

    const data = await res.json();

    setMessages(m=>[
      ...m,
      {role:"assistant",content:data.help}
    ]);

    setQ("");
    setLoading(false);
  }

  // ================= FILE UPLOAD =================
  async function upload(e:any){

  if(!classId) return;

  const file = e.target.files[0];
  if(!file) return;

  const form = new FormData();
  form.append("file",file);

  setLoading(true);

  const res = await fetch(
    `http://localhost:8000/homework/upload-help?class_id=${classId}`,
    {method:"POST",body:form}
  );

  const data = await res.json();

  setQuestions(data.questions || []);
  setQIndex(0);

  setLoading(false);
}

  // ================= CLEAR CHAT =================
  async function clearChat(){

    if(!classId) return;

    await fetch(
      `http://localhost:8000/homework/chat-history/${classId}`,
      {method:"DELETE"}
    );

    setMessages([]);
  }

  return(
    <div className="space-y-4">

      <h1 className="text-2xl font-semibold">
        Homework Helper
      </h1>

      {/* INPUT */}
      <textarea
        className="w-full border p-3 rounded"
        rows={4}
        placeholder="Ask something..."
        value={q}
        onChange={e=>setQ(e.target.value)}
      />

      {/* BUTTONS */}
      <div className="flex gap-3 flex-wrap">
	<button
onClick={()=>{
  if(qIndex>0) setQIndex(qIndex-1)
}}
className="bg-gray-500 text-white px-3 py-2 rounded"
>
Prev
</button>

<button
onClick={()=>{
  if(qIndex<questions.length-1)
    setQIndex(qIndex+1)
}}
className="bg-gray-500 text-white px-3 py-2 rounded"
>
Next
</button>

<button
onClick={()=>ask(questions[qIndex])}
className="bg-purple-600 text-white px-3 py-2 rounded"
>
Solve This Question
</button>
        <button
          disabled={!classId || loading}
          onClick={()=>ask()}
          className="bg-green-500 text-white px-4 py-2 rounded"
        >
          Ask
        </button>

        <button
          disabled={loading}
          onClick={()=>ask("hint")}
          className="bg-yellow-500 text-white px-3 py-2 rounded"
        >
          Hint
        </button>

        <button
          disabled={loading}
          onClick={()=>ask("next step")}
          className="bg-blue-500 text-white px-3 py-2 rounded"
        >
          Next Step
        </button>

        <input type="file" onChange={upload}/>

        <button
          onClick={clearChat}
          className="bg-red-500 text-white px-3 py-2 rounded"
        >
          Clear Chat
        </button>
      </div>

      {loading && <div>Thinking...</div>}

      {/* CHAT */}
       {questions.length>0 && (

<div className="border p-3 rounded bg-gray-50">

<b>
Question {qIndex+1} / {questions.length}
</b>

<ReactMarkdown>
{questions[qIndex]}
</ReactMarkdown>

</div>

)}
      <div className="space-y-3">

        {messages.map((m,i)=>(
          <div key={i} className={m.role==="user"?"text-right":"text-left"}>
            <div className={
              m.role==="user"
                ?"inline-block bg-green-200 p-3 rounded"
                :"inline-block bg-white border p-3 rounded prose max-w-none"
            }>
              <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
              >
                {m.content}
              </ReactMarkdown>
            </div>
          </div>
        ))}

      </div>

    </div>
  );
}