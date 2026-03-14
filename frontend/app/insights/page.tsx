"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { useStore } from "@/store/useStore";

export default function InsightsPage(){

const classId = useStore(s => s.selectedClassId)

const [analysis,setAnalysis] = useState("")
const [loading,setLoading] = useState(false)
const [error,setError] = useState("")
const [exams,setExams] = useState<any[]>([])
useEffect(() => {

if(!classId) return

async function loadSaved(){

const res = await fetch(
`http://localhost:8000/performance/insights/${classId}`
)

const data = await res.json()

setExams(data)

if(data.length > 0){
setAnalysis(data[0].analysis)
}

}

loadSaved()

},[classId])
async function upload(e:any){

const file = e.target.files?.[0]
if(!file) return

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

const res = await fetch(
"http://localhost:8000/performance/analyze-exam",
{
method:"POST",
body:form
}
)

if(!res.ok){
const text = await res.text()
throw new Error(text || "Server error")
}

const data = await res.json()

if(data.analysis){

setAnalysis(data.analysis)

setExams(prev => [
{
id: crypto.randomUUID(),
analysis: data.analysis,
created_at: new Date().toISOString()
},
...prev
])

}else{
setError("No analysis returned from server.")
}

}catch(err:any){

console.error(err)
setError(err.message || "Something went wrong")

}

setLoading(false)
}

return(

<div className="max-w-4xl mx-auto space-y-6">

<h1 className="text-2xl font-semibold">
Exam Insights
</h1>
{exams.length > 0 && (

<div className="border p-5 rounded-lg bg-white">

<div className="font-semibold mb-3">
Past Exam Analyses
</div>

<div className="space-y-2">

{exams.map((exam,i)=>(
<button
key={exam.id}
className="block w-full text-left border rounded p-3 hover:bg-gray-50"
onClick={()=>setAnalysis(exam.analysis)}
>
Exam {i+1} — {new Date(exam.created_at).toLocaleDateString()}
</button>
))}

</div>

</div>

)}
<div className="border p-5 rounded-lg bg-gray-50">

<div className="font-semibold mb-2">
Upload graded exam or assignment
</div>

<input type="file" onChange={upload}/>

<p className="text-sm text-gray-500 mt-2">
Upload past exams or homework with grades and corrections.
The AI will analyze your mistakes and show how to improve.
</p>

</div>

{loading && (

<div className="text-blue-600">
Analyzing your exam...
</div>

)}

{error && (

<div className="text-red-600 border p-4 rounded">
{error}
</div>

)}

{analysis && (

<div className="border p-6 rounded-xl bg-white shadow-sm prose max-w-none break-words">

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