"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type NoteCreateOut } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/Button";

export default function NoteEditor({
  initialText = "",
  onCreatedNote,
  disableCreate = false,
}: {
  initialText?: string;
  onCreatedNote?: (noteId: string) => void;
  disableCreate?: boolean;
}) {
  const classId = useStore((s) => s.selectedClassId);
  const qc = useQueryClient();

  const [title, setTitle] = useState("Study Note");
  const [text, setText] = useState(initialText);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof initialText === "string") {
      setText(initialText);
    }
  }, [initialText]);

  /**
   * Mutation now accepts optional "mode"
   * mode === undefined → normal extractor
   * mode === "math" → math extractor
   */
  const createM = useMutation<
    NoteCreateOut,
    Error,
    "math" | undefined
  >({
    mutationFn: async (mode) => {
      const cleanText = text.trim();
      const cleanTitle = title.trim() || "Study Note";

      setLocalError(null);

      if (!classId) {
        throw new Error("Please select a class first.");
      }

      if (!cleanText) {
        throw new Error("Note text is empty.");
      }

      return api.createNote({
        class_id: classId,
        title: cleanTitle,
        content_json: { text: cleanText },
        auto_extract: true,
        mode: mode ?? "normal",
      });
    },
    onSuccess: async (note) => {
      await qc.invalidateQueries({ queryKey: ["notes", classId] });
      await qc.invalidateQueries({ queryKey: ["readiness", classId] });
      setText("");

      if (note?.id && onCreatedNote) {
        onCreatedNote(note.id);
      }
if (note?.id) {
  localStorage.setItem("activeExtractionNoteId", note.id);
}
if (note?.id && classId) {
  localStorage.setItem(
    "activeExtractionMeta",
    JSON.stringify({ noteId: note.id, classId })
  );
}
    },
    onError: (err) => {
      setLocalError(err.message || "Failed to create note.");
    },
  });

  return (
    <div className="space-y-3">
      <input
        className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={200}
      />

      <textarea
        className="w-full rounded-xl border border-slate-200 p-3 text-sm"
        rows={8}
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={2_000_000}
      />
{localError && (
  <div className="text-sm text-red-600">
    {localError}
  </div>
)}
      <div className="flex gap-3">
{disableCreate && (
  <div className="text-xs text-slate-500">
    This uploaded note was already saved and extraction has already started below.
  </div>
)}
        {/* Normal Extract */}
        <Button
          onClick={() => createM.mutate(undefined)}
         disabled={createM.isPending || disableCreate}
        >
          Save Note + Extract Concepts
        </Button>

        {/* Math Extract (Blue) */}
        <Button
          className="bg-blue-600 hover:bg-blue-700 text-white"
          onClick={() => createM.mutate("math")}
         disabled={createM.isPending || disableCreate}
        >
          Extract Math Concepts
        </Button>
      </div>
    </div>
  );
}
