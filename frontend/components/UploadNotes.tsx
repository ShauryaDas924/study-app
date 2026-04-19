"use client";

import { useState } from "react";
import { useStore } from "@/store/useStore";

export default function UploadNotes({
  onExtracted,
  onCreatedNote,
}: {
  onExtracted?: (text: string, flashcards: any[]) => void;
  onCreatedNote?: (noteId: string) => void;
}) {
  const [loading, setLoading] = useState(false);
  const selectedClassId = useStore((s) => s.selectedClassId);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!selectedClassId) {
      alert("Please select a class first.");
      e.target.value = "";
      return;
    }

    setLoading(true);

    try {
      const form = new FormData();
      form.append("file", file);
      form.append("class_id", String(selectedClassId));
      form.append("mode", "normal"); // old grey upload button now defaults to normal extraction

      const res = await fetch("http://localhost:8000/upload/notes", {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const errText = await res.text();
        console.error("UPLOAD FAILED:", errText);
        alert("Upload failed. Check console.");
        return;
      }

      const data = await res.json();

      console.log("FULL RESPONSE:", data);

      const extractedText =
        typeof data.extracted_text === "string" ? data.extracted_text : "";

      console.log("EXTRACTED TEXT:", extractedText.slice(0, 200));

      onExtracted?.(
        extractedText,
        Array.isArray(data.flashcards) ? data.flashcards : []
      );

      if (data.note_id) {
        onCreatedNote?.(data.note_id);
      }
    } catch (err) {
      console.error("Upload failed:", err);
      alert("Upload failed. Check console.");
    } finally {
      setLoading(false);
      e.target.value = "";
    }
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