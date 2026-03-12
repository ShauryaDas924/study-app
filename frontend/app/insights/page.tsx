"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";

export default function InsightsPage(){

const [analysis,setAnalysis] = useState("")
const [loading,setLoading] = useState(false)
const [error,setError] = useState("")

// 🔧 Replace this with however your app stores selected class
const selectedClassId = "REPLACE_WITH_SELECTED_CLASS_ID"

async function upload(e:any){

const file = e.target.files?.[0]
if(!file) return

setLoading(true)
setError("")
setAnalysis("")

try{

const form = new FormData()
form.append("file",file)
form.append("class_id",selectedClassId)

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

<div className="border p-6 rounded-xl bg-white shadow-sm">

<ReactMarkdown>
{analysis}
</ReactMarkdown>

</div>

)}

</div>

)

}