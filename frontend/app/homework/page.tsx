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
function formatTutorText(text:string){

  return text
    .replace(/Concept used:/g,"### 🧠 Concept Used")
    .replace(/Definition:/g,"**Definition**")
    .replace(/When to use:/g,"**When to use**")
    .replace(/Common pitfall:/g,"⚠️ **Common pitfall**")
    .replace(/Step (\d+):/g,"### Step $1")
}
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
className="w-full border shadow-sm p-3 rounded-lg"
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

<div className="border shadow-sm p-5 rounded-xl bg-green-50 max-w-3xl">

<div className="font-semibold text-green-800 mb-2">
Question {qIndex+1} / {questions.length}
</div>

<ReactMarkdown>
{questions[qIndex]}
</ReactMarkdown>

</div>

)}
      <div className="space-y-4 max-w-3xl max-h-[600px] overflow-y-auto pr-2">

        {messages.map((m,i)=>(
          <div key={i} className={m.role==="user"?"text-right":"text-left"}>
            <div
  className={
    m.role==="user"
      ?"inline-block bg-green-200 p-3 rounded-lg max-w-xl"
      :"inline-block bg-white border shadow-sm p-4 rounded-xl prose max-w-none"
  }
>
              <ReactMarkdown
  remarkPlugins={[remarkMath]}
  rehypePlugins={[rehypeKatex]}
  components={{
  code({children, className, ...props}) {

    const isInline = !className

    return isInline
      ? (
        <code className="bg-gray-100 px-1 rounded">
          {children}
        </code>
      )
      : (
        <pre className="bg-gray-100 p-3 rounded overflow-x-auto text-sm">
          <code {...props}>
            {children}
          </code>
        </pre>
      )
  }
}}
>
                {m.role==="assistant"
  ? formatTutorText(m.content)
  : m.content
}
              </ReactMarkdown>
            </div>
          </div>
        ))}

      </div>

    </div>
  );
}