"use client";

import { useState } from "react";
import { useStore } from "@/store/useStore";

export default function UploadNotes({
  onExtracted,
}: {
  onExtracted: (text: string, flashcards: any[]) => void;
}) {
  const [loading, setLoading] = useState(false);
  const selectedClassId = useStore((s) => s.selectedClassId);

  async function handleUpload(e: any) {
    const file = e.target.files[0];
    if (!file) return;

    if (!selectedClassId) {
      alert("Please select a class first.");
      return;
    }

    setLoading(true);

    try {
      // ✅ BUILD FORMDATA CORRECTLY
      const form = new FormData();
      form.append("file", file);
      form.append("class_id", String(selectedClassId)); // ⭐ THE FIX

      const res = await fetch("http://localhost:8000/upload/notes", {
        method: "POST",
        body: form,
      });

      // ✅ HANDLE FAILURE
      if (!res.ok) {
        const errText = await res.text();
        console.error("UPLOAD FAILED:", errText);
        alert("Upload failed. Check console.");
        setLoading(false);
        return;
      }

      const data = await res.json();

      console.log("FULL RESPONSE:", data);

      const extractedText = data.extracted_text || "";

      console.log(
        "EXTRACTED TEXT:",
        extractedText.slice(0, 200)
      );

      // ✅ SAVE NOTE WITH REAL TEXT
      await fetch("http://localhost:8000/notes", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          class_id: selectedClassId,
          title: file.name,
          content_json: {
            text: extractedText,
          },
        }),
      });

      onExtracted(extractedText, data.flashcards || []);

    } catch (err) {
      console.error("Upload failed:", err);
    }

    setLoading(false);
  }

  return (
    <div className="space-y-2">
      <input type="file" onChange={handleUpload} />

      {loading && (
        <div className="text-xs text-slate-500">
          Uploading and saving notes...
        </div>
      )}
    </div>
  );
}