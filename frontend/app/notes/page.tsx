
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
      if (status === "queued" || status === "running") return 2000;
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

  /* ===============================
     UI
  =============================== */
  return (
    <div className="py-7 space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-900">Notes</h1>
        <p className="text-slate-500 mt-1">
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
              setUploadedText(text);
              setFlashcards(fc);
              localStorage.setItem("flashcards", JSON.stringify(fc));
            }}
          />

                    <NoteEditor
            key={selectedNoteId || "new"}
            initialText={uploadedText}
            onCreatedNote={(noteId) => setSelectedNoteId(noteId)}
          />

          {/* ================= FLASHCARDS ================= */}
          {allFlashcards.length > 0 && (
            <div className="mt-6">
              <div className="font-semibold text-lg mb-4">
                📚 Flashcards
              </div>

              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {allFlashcards.map((c: any, i: number) => (
                  <div
                    key={i}
                    className="
                      p-6 rounded-2xl 
                      bg-gradient-to-br from-white to-slate-50
                      border border-slate-200
                      shadow-sm hover:shadow-xl
                      transition
                    "
                  >
                    <div className="text-xs uppercase text-blue-500 font-semibold">
                      Question
                    </div>

                    <div className="mt-2 font-medium text-slate-900">
                      {c.question}
                    </div>

                    <div className="h-px bg-slate-200 my-4" />

                    <div className="text-xs uppercase text-green-600 font-semibold">
                      Answer
                    </div>

                    <div className="mt-2 text-sm text-slate-700">
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
                className={[
                  "w-full text-left rounded-xl border p-3",
                  selected === n.id
                    ? "border-green-200 bg-green-50"
                    : "border-slate-100 hover:bg-slate-50",
                ].join(" ")}
                onClick={() => setSelectedNoteId(n.id)}
              >
                <div className="font-medium">{n.title}</div>
                <div className="text-xs text-slate-500">{n.id}</div>
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
          right={
            selectedNoteId && (
              <div className="flex gap-2">
  <Button
  onClick={() => extractM.mutate({ noteId: selectedNoteId })}
  disabled={
    extractM.isPending ||
    extractionStatus === "queued" ||
    extractionStatus === "running"
  }
>
  Extract Concepts
</Button>

<Button
  onClick={() => extractM.mutate({ noteId: selectedNoteId, mode: "math" })}
  disabled={
    extractM.isPending ||
    extractionStatus === "queued" ||
    extractionStatus === "running"
  }
>
  Extract Math Concepts
</Button>
</div>
            )
          }
        />

               {!selectedNoteId ? (
          <div>Select a note above.</div>
        ) : noteQ.isLoading ? (
          <div>Loading…</div>
        ) : (
          <>
            <pre className="text-sm bg-slate-50 rounded-xl p-4 whitespace-pre-wrap">
              {(noteQ.data?.content_json as any)?.text}
            </pre>

            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between text-sm">
                <div className="font-medium text-slate-700">
                  Extraction Status: {extractionStatus}
                </div>
                <div className="text-slate-500">{extractionProgress}%</div>
              </div>

              <div className="w-full h-3 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className={[
                    "h-full transition-all duration-500",
                    extractionStatus === "failed"
                      ? "bg-red-500"
                      : extractionStatus === "completed"
                      ? "bg-green-500"
                      : "bg-blue-500",
                  ].join(" ")}
                  style={{ width: `${extractionProgress}%` }}
                />
              </div>

              {(extractionStatus === "queued" ||
                extractionStatus === "running") && (
                <div className="text-xs text-slate-500">
                  Extraction is running in the background. You can leave this page.
                </div>
              )}

              {extractionStatus === "completed" && (
                <div className="text-xs text-green-600">
                  Extraction completed.
                </div>
              )}

              {extractionStatus === "failed" && extractionError && (
                <div className="text-xs text-red-600">
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
              <div key={c.id} className="p-4 border rounded-xl shadow-sm">
                <div className="font-medium">{c.name}</div>
                <div className="text-sm text-slate-600">
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