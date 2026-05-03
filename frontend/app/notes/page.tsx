
"use client";

import { useMemo, useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type UUID } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import UploadNotes from "@/components/UploadNotes";
import NoteEditor from "@/components/NoteEditor";

export default function NotesPage() {
  const classId = useStore((s) => s.selectedClassId);
  const qc = useQueryClient();

  const [uploadedText, setUploadedText] = useState("");
  const [flashcards, setFlashcards] = useState<any[]>([]);
  const [dbFlashcards, setDbFlashcards] = useState<any[]>([]);
  const [concepts, setConcepts] = useState<any[]>([]);
  const [selectedNoteId, setSelectedNoteId] = useState<UUID | null>(null);

  /* ===============================
     LOAD LOCAL FLASHCARDS
  =============================== */
  useEffect(() => {
    const saved = localStorage.getItem("flashcards");
    if (saved) setFlashcards(JSON.parse(saved));
  }, []);

  /* ===============================
     NOTES QUERY
  =============================== */
  const notesQ = useQuery({
    queryKey: ["notes", classId],
    queryFn: () => api.notesByClass(classId),
    enabled: !!classId,
  });

useEffect(() => {
  if (!classId) return;
  if (!notesQ.data?.length) return;
  if (selectedNoteId) return;

  const raw = localStorage.getItem("activeExtractionMeta");

  if (raw) {
    try {
      const meta = JSON.parse(raw);

      if (
        meta?.classId === classId &&
        meta?.noteId &&
        notesQ.data.some((n: any) => n.id === meta.noteId)
      ) {
        setSelectedNoteId(meta.noteId);
        return;
      }
    } catch {
      localStorage.removeItem("activeExtractionMeta");
      localStorage.removeItem("activeExtractionNoteId");
    }
  }

  const latestNote = notesQ.data[0];
  if (latestNote?.id) {
    setSelectedNoteId(latestNote.id);
  }
}, [classId, notesQ.data, selectedNoteId]);

  /* ===============================
     SINGLE NOTE QUERY
  =============================== */
  const noteQ = useQuery({
    queryKey: ["note", selectedNoteId],
    queryFn: () => api.getNote(selectedNoteId as UUID),
    enabled: !!selectedNoteId,
  });
  const extractionStatusQ = useQuery({
    queryKey: ["note-extraction-status", selectedNoteId],
    queryFn: () => api.getConceptExtractionStatus(selectedNoteId as UUID),
    enabled: !!selectedNoteId,
    refetchInterval: (query) => {
      const data: any = query.state.data;
      const status = data?.status;
    if (status === "queued" || status === "running") return 8000;
      return false;
    },
  });
useEffect(() => {
  const text = (noteQ.data?.content_json as any)?.text;

  if (typeof text === "string") {
    setUploadedText(text);
  }
}, [noteQ.data]);

useEffect(() => {
  const status = extractionStatusQ.data?.status;

  if (status === "completed") {
    qc.invalidateQueries({ queryKey: ["readiness", classId] });
    qc.invalidateQueries({ queryKey: ["note", selectedNoteId] });
    fetchConcepts();
    fetchDBFlashcards();
  }

  if (status === "failed") {
    localStorage.removeItem("activeExtractionMeta");
    localStorage.removeItem("activeExtractionNoteId");
  }
}, [extractionStatusQ.data?.status, classId, qc, selectedNoteId]);
  /* ===============================
     EXTRACT CONCEPTS
  =============================== */
    const extractM = useMutation({
    mutationFn: ({ noteId, mode }: { noteId: UUID; mode?: string }) =>
      api.startConceptExtraction(noteId, mode),
  });

  /* ===============================
     FETCH CONCEPTS
  =============================== */
  const fetchConcepts = () => {
    if (!classId) return;

    fetch(`http://localhost:8000/notes/concepts/by-class/${classId}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) setConcepts(data);
        else setConcepts([]);
      })
      .catch(() => setConcepts([]));
  };

  useEffect(fetchConcepts, [classId]);

  /* ===============================
     FETCH DB FLASHCARDS
  =============================== */
  const fetchDBFlashcards = () => {
    if (!classId) return;

    fetch(`http://localhost:8000/notes/flashcards/by-class/${classId}`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) setDbFlashcards(data);
      });
  };

  useEffect(fetchDBFlashcards, [classId]);

  /* ===============================
     MERGE + DEDUPE FLASHCARDS
  =============================== */
  const allFlashcards = useMemo(() => {
    const map = new Map();

    [...dbFlashcards, ...flashcards].forEach((fc) => {
      map.set(fc.question, fc);
    });

    return Array.from(map.values());
  }, [dbFlashcards, flashcards]);

  const selected = useMemo(() => selectedNoteId, [selectedNoteId]);
  const extractionStatus = extractionStatusQ.data?.status ?? "idle";
  const extractionProgress = extractionStatusQ.data?.progress ?? 0;
  const extractionError = extractionStatusQ.data?.error ?? null;
  const extractionStage =
    extractionProgress >= 100
      ? "Completed"
      : extractionProgress >= 90
      ? "Saving flashcards"
      : extractionProgress >= 80
      ? "Generating flashcards"
      : extractionProgress >= 72
      ? "Preparing flashcard payloads"
      : extractionProgress >= 50
      ? "Saving concepts"
      : extractionProgress >= 28
      ? "Enriching concepts"
      : extractionProgress >= 12
      ? "Extracting concepts"
      : extractionStatus === "queued"
      ? "Queued"
      : "Idle";
  /* ===============================
     UI
  =============================== */
  return (
   <div className="app-shell py-7 space-y-6">
      <div>
       <h1 className="text-3xl font-semibold" style={{ color: "var(--text-main)" }}>
  Notes
</h1>
<p className="mt-1" style={{ color: "var(--text-soft)" }}>
  Write clean notes. Extract concepts. Generate grounded practice.
</p>
      </div>

      {/* ================= CREATE NOTE ================= */}
      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader
            title="Create Note"
            subtitle="Notes are stored as content_json."
          />

        <UploadNotes
  onExtracted={(text, fc) => {
    console.log("[NotesPage] UploadNotes onExtracted", {
      textLength: typeof text === "string" ? text.length : -1,
      preview: typeof text === "string" ? text.slice(0, 120) : null,
      flashcards: Array.isArray(fc) ? fc.length : -1,
    });

    setUploadedText(text);
    setFlashcards(fc);
    localStorage.setItem("flashcards", JSON.stringify(fc));
  }}
  onCreatedNote={async (noteId) => {
    setSelectedNoteId(noteId);

    await qc.invalidateQueries({ queryKey: ["notes", classId] });
    await qc.invalidateQueries({ queryKey: ["readiness", classId] });

    localStorage.setItem("activeExtractionNoteId", noteId);

    if (classId) {
      localStorage.setItem(
        "activeExtractionMeta",
        JSON.stringify({ noteId, classId })
      );
    }
  }}
/>

                    <NoteEditor
  key={selectedNoteId || "new"}
  initialText={uploadedText}
  onCreatedNote={(noteId) => setSelectedNoteId(noteId)}
  disableCreate={!!selectedNoteId && !!uploadedText}
/>

          {/* ================= FLASHCARDS ================= */}
          {allFlashcards.length > 0 && (
            <div className="mt-6">
              <div className="font-semibold text-lg mb-4" style={{ color: "var(--text-main)" }}>
  📚 Flashcards
</div>

              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {allFlashcards.map((c: any, i: number) => (
                <div
  key={i}
  className="p-6 rounded-2xl border transition"
  style={{
    background:
      "linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(255,247,251,0.96) 52%, rgba(248,255,247,0.96) 100%)",
    borderColor: "var(--border-soft)",
    boxShadow: "var(--shadow-card)",
  }}
>
  <div
    className="text-xs uppercase font-semibold"
    style={{ color: "var(--accent-pink-strong)" }}
  >
    Question
  </div>

  <div className="mt-2 font-medium" style={{ color: "var(--text-main)" }}>
    {c.question}
  </div>

  <div
    className="h-px my-4"
    style={{
      background:
        "linear-gradient(90deg, rgba(247,167,195,0.55), rgba(246,223,139,0.55), rgba(191,216,184,0.55))",
    }}
  />

  <div
    className="text-xs uppercase font-semibold"
    style={{ color: "var(--accent-green-strong)" }}
  >
    Answer
  </div>

  <div className="mt-2 text-sm" style={{ color: "var(--text-soft)" }}>
    {c.answer}
  </div>
</div>
                ))}
              </div>
            </div>
          )}
        </Card>

        {/* ================= NOTES LIST ================= */}
        <Card>
          <CardHeader
            title="Notes in this class"
            subtitle="Select a note to preview and extract concepts."
          />

          {notesQ.isLoading && <div>Loading…</div>}

          <div className="space-y-2">
            {(notesQ.data || []).map((n) => (
              <button
  key={n.id}
  className="w-full text-left rounded-2xl border p-3 transition"
  style={
    selected === n.id
      ? {
          background: "var(--gradient-main)",
          borderColor: "var(--border-soft)",
          color: "var(--text-main)",
          boxShadow: "var(--shadow-button)",
        }
      : {
          background: "rgba(255,255,255,0.72)",
          borderColor: "var(--border-soft)",
          color: "var(--text-main)",
        }
  }
  onClick={() => setSelectedNoteId(n.id)}
>
  <div className="font-medium">{n.title}</div>
  <div className="text-xs" style={{ color: "var(--text-soft)" }}>
    {n.id}
  </div>
</button>
            ))}
          </div>
        </Card>
      </div>

      {/* ================= SELECTED NOTE ================= */}
      <Card>
        <CardHeader
          title="Selected Note"
          subtitle="Extract concepts multiple times if needed."
         
        />

               {!selectedNoteId ? (
          <div>Select a note above.</div>
        ) : noteQ.isLoading ? (
          <div>Loading…</div>
        ) : (
          <>
            <pre
  className="text-sm rounded-2xl p-4 whitespace-pre-wrap border"
  style={{
    background: "rgba(255,255,255,0.75)",
    borderColor: "var(--border-soft)",
    color: "var(--text-main)",
  }}
>
  {(noteQ.data?.content_json as any)?.text}
</pre>

            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between text-sm">
                <div className="font-medium" style={{ color: "var(--text-soft)" }}>
  Extraction Status: {extractionStatus} — {extractionStage}
</div>
<div style={{ color: "var(--text-soft)" }}>{extractionProgress}%</div>
              </div>

              <div
  className="w-full h-3 rounded-full overflow-hidden"
  style={{ background: "rgba(231, 218, 203, 0.7)" }}
>
  <div
    className="h-full transition-all duration-500"
    style={{
      width: `${extractionProgress}%`,
      background:
        extractionStatus === "failed"
          ? "linear-gradient(135deg, #ffd7df 0%, #ffb8c8 100%)"
          : extractionStatus === "completed"
          ? "linear-gradient(135deg, #bfd8b8 0%, #f6df8b 100%)"
          : "linear-gradient(135deg, #f7a7c3 0%, #f6df8b 52%, #bfd8b8 100%)",
    }}
  />
</div>

              {(extractionStatus === "queued" ||
                extractionStatus === "running") && (
                <div className="text-xs" style={{ color: "var(--text-soft)" }}>
  Extraction is running in the background. You can leave this page.
</div>
              )}

              {extractionStatus === "completed" && (
                <div className="text-xs" style={{ color: "var(--accent-green-strong)" }}>
  Extraction completed.
</div>
              )}

              {extractionStatus === "failed" && extractionError && (
                <div className="text-xs" style={{ color: "var(--accent-pink-strong)" }}>
  Extraction failed: {String(extractionError)}
</div>
              )}
            </div>
          </>
        )}
      </Card>

      {/* ================= SAVED CONCEPTS ================= */}
      <Card>
        <CardHeader
          title="Saved Concepts"
          subtitle="Concepts persist across sessions."
        />

        {concepts.length === 0 ? (
          <div>No concepts saved yet.</div>
        ) : (
          <div className="space-y-3">
            {concepts.map((c: any) => (
              <div
  key={c.id}
  className="p-4 rounded-2xl border"
  style={{
    background: "rgba(255,255,255,0.74)",
    borderColor: "var(--border-soft)",
    boxShadow: "var(--shadow-soft)",
  }}
>
  <div className="font-medium" style={{ color: "var(--text-main)" }}>
    {c.name}
  </div>
  <div className="text-sm" style={{ color: "var(--text-soft)" }}>
    {c.description}
  </div>
</div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}