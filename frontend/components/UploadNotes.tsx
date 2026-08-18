"use client";

import { useState } from "react";
import { useStore } from "@/store/useStore";
import { authFetch } from "@/lib/auth";

export default function UploadNotes({
  onExtracted,
  onCreatedNote,
}: {
  onExtracted?: (text: string, flashcards: unknown[]) => void;
  onCreatedNote?: (noteId: string) => void;
}) {
  const [loading, setLoading] = useState(false);
  const selectedClassId = useStore((s) => s.selectedClassId);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      alert("Upload must be 10 MiB or smaller.");
      e.target.value = "";
      return;
    }

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

      const res = await authFetch("/upload/notes", {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        alert("Upload failed. Check the file type and size, then try again.");
        return;
      }

      const data = await res.json();

      const extractedText =
        typeof data.extracted_text === "string" ? data.extracted_text : "";

      onExtracted?.(
        extractedText,
        Array.isArray(data.flashcards) ? data.flashcards : []
      );

      if (data.note_id) {
        onCreatedNote?.(data.note_id);
      }
    } catch {
      alert("Upload failed. Please try again.");
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  return (
    <div className="space-y-2">
      <input
        type="file"
        accept=".pdf,.txt,.md,.pptx,.png,.jpg,.jpeg"
        onChange={handleUpload}
      />

      {loading && (
        <div className="text-xs text-slate-500">
          Uploading and saving notes...
        </div>
      )}
    </div>
  );
}
