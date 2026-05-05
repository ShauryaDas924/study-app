
"use client";

import { useMemo, useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type UUID } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import UploadNotes from "@/components/UploadNotes";
import NoteEditor from "@/components/NoteEditor";
import { authFetch } from "@/lib/auth";
import RequireAuth from "@/components/RequireAuth";

function formatConceptName(name?: string) {
  if (!name) return "Untitled Concept";

  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function getConceptTone(concept: any, index: number) {
  const text = `${concept?.name ?? ""} ${concept?.description ?? ""}`.toLowerCase();

  if (
    text.includes("primary key") ||
    text.includes("foreign key") ||
    text.includes("key")
  ) {
    return {
      label: "Keys",
      icon: "🔑",
      color: "#7b5cff",
      bg: "rgba(123, 92, 255, 0.08)",
      border: "rgba(123, 92, 255, 0.26)",
      chipBg: "rgba(123, 92, 255, 0.12)",
    };
  }

  if (
    text.includes("cardinality") ||
    text.includes("relationship") ||
    text.includes("entity relationship") ||
    text.includes("erd") ||
    text.includes("erm")
  ) {
    return {
      label: "Relationships",
      icon: "🔗",
      color: "#4d7c8a",
      bg: "rgba(77, 124, 138, 0.08)",
      border: "rgba(77, 124, 138, 0.26)",
      chipBg: "rgba(77, 124, 138, 0.12)",
    };
  }

  if (
    text.includes("attribute") ||
    text.includes("entity") ||
    text.includes("record") ||
    text.includes("table") ||
    text.includes("column")
  ) {
    return {
      label: "Structure",
      icon: "🧱",
      color: "var(--accent-pink-strong)",
      bg: "rgba(247, 167, 195, 0.12)",
      border: "rgba(247, 167, 195, 0.34)",
      chipBg: "rgba(247, 167, 195, 0.16)",
    };
  }

  if (
    text.includes("normalization") ||
    text.includes("integrity") ||
    text.includes("redundancy") ||
    text.includes("anomal")
  ) {
    return {
      label: "Data Quality",
      icon: "✅",
      color: "var(--accent-green-strong)",
      bg: "rgba(191, 216, 184, 0.16)",
      border: "rgba(191, 216, 184, 0.45)",
      chipBg: "rgba(191, 216, 184, 0.22)",
    };
  }

  if (
    text.includes("sql") ||
    text.includes("null") ||
    text.includes("operator") ||
    text.includes("syntax")
  ) {
    return {
      label: "SQL",
      icon: "💻",
      color: "#9a6a00",
      bg: "rgba(246, 223, 139, 0.18)",
      border: "rgba(246, 223, 139, 0.58)",
      chipBg: "rgba(246, 223, 139, 0.26)",
    };
  }

  if (
    text.includes("database") ||
    text.includes("dbms") ||
    text.includes("spreadsheet") ||
    text.includes("metadata")
  ) {
    return {
      label: "Database Basics",
      icon: "🗂️",
      color: "#b44b62",
      bg: "rgba(255, 215, 223, 0.28)",
      border: "rgba(247, 167, 195, 0.42)",
      chipBg: "rgba(255, 215, 223, 0.38)",
    };
  }

  const fallbacks = [
    {
      label: "Core Concept",
      icon: "✨",
      color: "var(--accent-pink-strong)",
      bg: "rgba(247, 167, 195, 0.10)",
      border: "rgba(247, 167, 195, 0.30)",
      chipBg: "rgba(247, 167, 195, 0.14)",
    },
    {
      label: "Study Point",
      icon: "🌿",
      color: "var(--accent-green-strong)",
      bg: "rgba(191, 216, 184, 0.14)",
      border: "rgba(191, 216, 184, 0.36)",
      chipBg: "rgba(191, 216, 184, 0.20)",
    },
    {
      label: "Exam Idea",
      icon: "⭐",
      color: "#9a6a00",
      bg: "rgba(246, 223, 139, 0.18)",
      border: "rgba(246, 223, 139, 0.52)",
      chipBg: "rgba(246, 223, 139, 0.24)",
    },
  ];

  return fallbacks[index % fallbacks.length];
}

function SavedConceptsPreview({ concepts }: { concepts: any[] }) {
  if (concepts.length === 0) {
    return (
      <div
        className="rounded-3xl border p-6 text-sm"
        style={{
          background:
            "linear-gradient(135deg, rgba(255,255,255,0.82), rgba(255,247,251,0.72))",
          borderColor: "var(--border-soft)",
          color: "var(--text-soft)",
        }}
      >
        No concepts saved yet.
      </div>
    );
  }

  return (
    <div
      className="rounded-[2rem] border overflow-hidden"
      style={{
        background:
          "linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(255,248,251,0.84) 50%, rgba(248,255,247,0.84) 100%)",
        borderColor: "var(--border-soft)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div
        className="px-5 py-4 border-b flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
        style={{
          borderColor: "var(--border-soft)",
          background:
            "linear-gradient(90deg, rgba(247,167,195,0.15), rgba(246,223,139,0.15), rgba(191,216,184,0.15))",
        }}
      >
        <div>
          <div
            className="text-xs uppercase tracking-[0.18em] font-semibold"
            style={{ color: "var(--text-soft)" }}
          >
            Concept Library
          </div>

          <div
            className="mt-1 text-lg font-semibold"
            style={{ color: "var(--text-main)" }}
          >
            {concepts.length} saved concept{concepts.length === 1 ? "" : "s"}
          </div>
        </div>

        <div
          className="rounded-full px-4 py-2 text-xs font-semibold"
          style={{
            color: "var(--text-main)",
            background: "rgba(255,255,255,0.68)",
            border: "1px solid var(--border-soft)",
          }}
        >
          Ready for practice + tutor grounding
        </div>
      </div>

      <div className="p-5 grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {concepts.map((concept: any, index: number) => {
          const tone = getConceptTone(concept, index);
          const title = formatConceptName(concept.name);
          const description =
            concept.description ||
            concept.evidence ||
            concept.summary ||
            "No description saved for this concept yet.";

          return (
            <article
              key={concept.id ?? `${concept.name}-${index}`}
              className="group rounded-3xl border p-5 transition"
              style={{
                background: tone.bg,
                borderColor: tone.border,
                boxShadow: "var(--shadow-soft)",
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div
                  className="h-11 w-11 rounded-2xl flex items-center justify-center text-lg shrink-0"
                  style={{
                    background: "rgba(255,255,255,0.76)",
                    border: `1px solid ${tone.border}`,
                    boxShadow: "var(--shadow-soft)",
                  }}
                >
                  {tone.icon}
                </div>

                <div
                  className="rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.12em] font-bold"
                  style={{
                    color: tone.color,
                    background: tone.chipBg,
                    border: `1px solid ${tone.border}`,
                  }}
                >
                  {tone.label}
                </div>
              </div>

              <div className="mt-4">
                <h3
                  className="text-base font-semibold leading-snug"
                  style={{ color: "var(--text-main)" }}
                >
                  {title}
                </h3>

                <p
                  className="mt-2 text-sm leading-relaxed"
                  style={{ color: "var(--text-soft)" }}
                >
                  {description}
                </p>
              </div>

              <div
                className="mt-4 h-px"
                style={{
                  background:
                    "linear-gradient(90deg, transparent, rgba(0,0,0,0.10), transparent)",
                }}
              />

              <div className="mt-3 flex items-center justify-between gap-3">
                <div
                  className="text-xs font-medium"
                  style={{ color: "var(--text-soft)" }}
                >
                  Concept #{index + 1}
                </div>

                <div
                  className="h-2 w-16 rounded-full overflow-hidden"
                  style={{ background: "rgba(255,255,255,0.72)" }}
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: "72%",
                      background: tone.color,
                      opacity: 0.72,
                    }}
                  />
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}

function NotesContent() {
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

    authFetch(`/notes/concepts/by-class/${classId}`, {
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

    authFetch(`/notes/flashcards/by-class/${classId}`, {
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
              subtitle="Concepts persist across sessions and power practice, tutor help, and analytics."
            />

            <SavedConceptsPreview concepts={concepts} />
          </Card>
    </div>
  );
}

export default function NotesPage() {
  return (
    <RequireAuth>
      <NotesContent />
    </RequireAuth>
  );
}
