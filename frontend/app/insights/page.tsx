"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { useStore } from "@/store/useStore";
import { authFetch } from "@/lib/auth";
import RequireAuth from "@/components/RequireAuth";

type ExamAnalysis = {
  id: string;
  analysis: string;
  created_at: string;
};

function InsightsContent(){

const classId = useStore(s => s.selectedClassId)

const [analysis,setAnalysis] = useState("")
const [loading,setLoading] = useState(false)
const [error,setError] = useState("")
const [exams,setExams] = useState<ExamAnalysis[]>([])
useEffect(() => {

if(!classId) return

async function loadSaved(){

const res = await authFetch(
`/performance/insights/${classId}`
)

const data: unknown = await res.json()

if (!Array.isArray(data)) return

setExams(data as ExamAnalysis[])

if(data.length > 0){
setAnalysis(data[0].analysis)
}

}

loadSaved()

},[classId])
async function upload(e: React.ChangeEvent<HTMLInputElement>){

const file = e.target.files?.[0]
if(!file) return

if (file.size > 10 * 1024 * 1024) {
  setError("Upload must be 10 MiB or smaller")
  e.target.value = ""
  return
}

if(!classId){
  setError("Please select a class first")
  return
}

setLoading(true)
setError("")
setAnalysis("")

try{

const form = new FormData()
form.append("file",file)
form.append("class_id",classId)

const res = await authFetch(
"/performance/analyze-exam",
{
method:"POST",
body:form
}
)

if(!res.ok){
const text = await res.text()
throw new Error(text || "Server error")
}

const data = await res.json() as { analysis?: string }
const returnedAnalysis = data.analysis

if(typeof returnedAnalysis === "string" && returnedAnalysis){

setAnalysis(returnedAnalysis)

setExams(prev => [
{
id: crypto.randomUUID(),
analysis: returnedAnalysis,
created_at: new Date().toISOString()
},
...prev
])

}else{
setError("No analysis returned from server.")
}

}catch(err: unknown){

setError(err instanceof Error ? err.message : "Something went wrong")

}

setLoading(false)
}

return(

<div className="app-shell max-w-4xl mx-auto space-y-6">

<h1 className="text-2xl font-semibold" style={{ color: "var(--text-main)" }}>
  Exam Insights
</h1>
{exams.length > 0 && (

<div className="app-panel p-5">

<div className="font-semibold mb-3">
Past Exam Analyses
</div>

<div className="space-y-2">

{exams.map((exam,i)=>(
<button
key={exam.id}
className="block w-full text-left border rounded-2xl p-3 transition"
style={{
  background: "rgba(255,255,255,0.74)",
  borderColor: "var(--border-soft)",
  color: "var(--text-main)",
}}
>
Exam {i+1} — {new Date(exam.created_at).toLocaleDateString()}
</button>
))}

</div>

</div>

)}
<div className="app-soft-panel p-5">

<div className="font-semibold mb-2">
Upload graded exam or assignment
</div>

<input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={upload}/>

<p className="text-sm mt-2" style={{ color: "var(--text-soft)" }}>
Upload past exams or homework with grades and corrections.
The AI will analyze your mistakes and show how to improve.
</p>

</div>

{loading && (

<div style={{ color: "var(--accent-pink-strong)" }}>
  Analyzing your exam...
</div>

)}

{error && (

<div
  className="p-4 rounded-2xl border"
  style={{
    color: "#7b4250",
    background: "linear-gradient(135deg, #ffe8ee 0%, #fff4d8 100%)",
    borderColor: "var(--border-soft)",
  }}
>
  {error}
</div>

)}

{analysis && (

<div className="app-panel p-6 prose themed-markdown max-w-none break-words">

<ReactMarkdown
remarkPlugins={[remarkMath]}
rehypePlugins={[[rehypeKatex, { strict: false }]]}
>
{analysis}
</ReactMarkdown>

</div>

)}

</div>

	)

	}

export default function InsightsPage() {
return (
<RequireAuth>
<InsightsContent />
</RequireAuth>
)
}
