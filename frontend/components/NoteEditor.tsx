"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/Button";

export default function NoteEditor({
  initialText = "",
  onCreatedNote,
}: {
  initialText?: string;
  onCreatedNote?: (noteId: string) => void;
}) {
  const classId = useStore((s) => s.selectedClassId);
  const qc = useQueryClient();

  const [title, setTitle] = useState("Study Note");
  const [text, setText] = useState(initialText);

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
    any,
    Error,
    string | undefined
  >({
    mutationFn: async (mode) => {
  const cleanText = text.trim();
  const cleanTitle = title.trim() || "Study Note";

  if (!classId) {
    throw new Error("Please select a class first.");
  }

  if (!cleanText) {
    throw new Error("Note text is empty.");
  }

  const note = await api.createNote({
    class_id: classId,
    title: cleanTitle,
    content_json: { text: cleanText },
  });

  await api.startConceptExtraction(note.id, mode);

  return note;
},
    onSuccess: async (note) => {
      await qc.invalidateQueries({ queryKey: ["notes", classId] });
      await qc.invalidateQueries({ queryKey: ["readiness", classId] });
      setText("");

      if (note?.id && onCreatedNote) {
        onCreatedNote(note.id);
      }
    },
  });

  return (
    <div className="space-y-3">
      <input
        className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />

      <textarea
        className="w-full rounded-xl border border-slate-200 p-3 text-sm"
        rows={8}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      <div className="flex gap-3">
        {/* Normal Extract */}
        <Button
          onClick={() => createM.mutate(undefined)}
          disabled={createM.isPending}
        >
          Save Note + Extract Concepts
        </Button>

        {/* Math Extract (Blue) */}
        <Button
          className="bg-blue-600 hover:bg-blue-700 text-white"
          onClick={() => createM.mutate("math")}
          disabled={createM.isPending}
        >
          Extract Math Concepts
        </Button>
      </div>
    </div>
  );
}