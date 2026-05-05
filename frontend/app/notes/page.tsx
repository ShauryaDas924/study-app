
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


function getSectionStyle(label: string) {
  const key = label.toLowerCase();

  if (key.includes("definition")) {
    return {
      badge: "Definition",
      color: "var(--accent-green-strong)",
      bg: "rgba(191, 216, 184, 0.18)",
      border: "rgba(191, 216, 184, 0.55)",
    };
  }

  if (key.includes("key ideas") || key.includes("components") || key.includes("benefits")) {
    return {
      badge: label,
      color: "var(--accent-pink-strong)",
      bg: "rgba(247, 167, 195, 0.13)",
      border: "rgba(247, 167, 195, 0.45)",
    };
  }

  if (key.includes("example")) {
    return {
      badge: "Examples",
      color: "#9a6a00",
      bg: "rgba(246, 223, 139, 0.20)",
      border: "rgba(246, 223, 139, 0.62)",
    };
  }

  if (key.includes("pitfall")) {
    return {
      badge: "Common Pitfalls",
      color: "#b44b62",
      bg: "rgba(255, 215, 223, 0.35)",
      border: "rgba(247, 167, 195, 0.55)",
    };
  }

  if (key.includes("exam")) {
    return {
      badge: "Exam Insight",
      color: "#7b5cff",
      bg: "rgba(123, 92, 255, 0.08)",
      border: "rgba(123, 92, 255, 0.28)",
    };
  }

  if (key.includes("syntax") || key.includes("process") || key.includes("relationship")) {
    return {
      badge: label,
      color: "#4d7c8a",
      bg: "rgba(77, 124, 138, 0.08)",
      border: "rgba(77, 124, 138, 0.25)",
    };
  }

  return {
    badge: label,
    color: "var(--text-main)",
    bg: "rgba(255,255,255,0.62)",
    border: "var(--border-soft)",
  };
}

function NotePreview({ text }: { text?: string }) {
  if (!text) {
    return (
      <div
        className="rounded-2xl border p-5 text-sm"
        style={{
          background: "rgba(255,255,255,0.72)",
          borderColor: "var(--border-soft)",
          color: "var(--text-soft)",
        }}
      >
        No note content found.
      </div>
    );
  }

  const blocks = text
    .split(/\n---\n/g)
    .map((block) => block.trim())
    .filter(Boolean);

  return (
    <div
      className="rounded-[2rem] border overflow-hidden"
      style={{
        background:
          "linear-gradient(180deg, rgba(255,255,255,0.92) 0%, rgba(255,248,251,0.86) 48%, rgba(248,255,247,0.86) 100%)",
        borderColor: "var(--border-soft)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div
        className="px-5 py-4 border-b"
        style={{
          borderColor: "var(--border-soft)",
          background:
            "linear-gradient(90deg, rgba(247,167,195,0.16), rgba(246,223,139,0.15), rgba(191,216,184,0.16))",
        }}
      >
        <div className="text-xs uppercase tracking-[0.18em] font-semibold" style={{ color: "var(--text-soft)" }}>
          Study Note Preview
        </div>
        <div className="mt-1 text-lg font-semibold" style={{ color: "var(--text-main)" }}>
          Clean, structured, exam-ready notes
        </div>
      </div>

      <div className="p-5 space-y-5 max-h-[760px] overflow-y-auto">
        {blocks.map((block, blockIndex) => {
          const lines = block.split("\n").map((line) => line.trimEnd());
          const titleLine = lines.find((line) => line.startsWith("### "));
          const title = titleLine?.replace(/^###\s*/, "") || `Section ${blockIndex + 1}`;

          const bodyLines = lines.filter((line) => line !== titleLine);
          const sections: { heading: string; lines: string[] }[] = [];
          let current: { heading: string; lines: string[] } | null = null;

          bodyLines.forEach((line) => {
            const trimmed = line.trim();

            if (!trimmed) return;

            const isSectionHeading =
              !trimmed.startsWith("-") &&
              !trimmed.startsWith("`") &&
              trimmed.length < 42 &&
              !trimmed.includes(".") &&
              !trimmed.includes(": `");

            if (isSectionHeading) {
              current = { heading: trimmed, lines: [] };
              sections.push(current);
            } else {
              if (!current) {
                current = { heading: "Notes", lines: [] };
                sections.push(current);
              }
              current.lines.push(trimmed);
            }
          });

          return (
            <article
              key={`${title}-${blockIndex}`}
              className="rounded-3xl border p-5"
              style={{
                background: "rgba(255,255,255,0.72)",
                borderColor: "var(--border-soft)",
                boxShadow: "var(--shadow-soft)",
              }}
            >
              <div className="flex items-start gap-3 mb-4">
                <div
                  className="h-10 w-10 rounded-2xl flex items-center justify-center text-sm font-bold shrink-0"
                  style={{
                    background: "var(--gradient-main)",
                    color: "var(--text-main)",
                    boxShadow: "var(--shadow-button)",
                  }}
                >
                  {blockIndex + 1}
                </div>

                <div>
                  <h3 className="text-xl font-semibold leading-tight" style={{ color: "var(--text-main)" }}>
                    {title}
                  </h3>
                  <p className="text-sm mt-1" style={{ color: "var(--text-soft)" }}>
                    Key concept from this note
                  </p>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-3">
                {sections.map((section, sectionIndex) => {
                  const style = getSectionStyle(section.heading);

                  return (
                    <section
                      key={`${section.heading}-${sectionIndex}`}
                      className="rounded-2xl border p-4"
                      style={{
                        background: style.bg,
                        borderColor: style.border,
                      }}
                    >
                      <div
                        className="text-xs uppercase tracking-[0.12em] font-bold mb-3"
                        style={{ color: style.color }}
                      >
                        {style.badge}
                      </div>

                      <div className="space-y-2">
                        {section.lines.map((line, lineIndex) => {
                          const clean = line.replace(/^-\s*/, "");
                          const isBullet = line.trim().startsWith("-");
                          const isCode = clean.includes("SELECT") || clean.includes("WHERE") || clean.includes("NULL;");

                          if (isCode) {
                            return (
                              <code
                                key={lineIndex}
                                className="block rounded-xl px-3 py-2 text-xs whitespace-pre-wrap"
                                style={{
                                  background: "rgba(45, 39, 48, 0.92)",
                                  color: "rgba(255,255,255,0.92)",
                                }}
                              >
                                {clean}
                              </code>
                            );
                          }

                          return (
                            <div
                              key={lineIndex}
                              className="flex gap-2 text-sm leading-relaxed"
                              style={{ color: "var(--text-main)" }}
                            >
                              {isBullet && (
                                <span
                                  className="mt-[0.55rem] h-1.5 w-1.5 rounded-full shrink-0"
                                  style={{ background: style.color }}
                                />
                              )}
                              <span>{clean}</span>
                            </div>
                          );
                        })}
                      </div>
                    </section>
                  );
                })}
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
             <NotePreview text={(noteQ.data?.content_json as any)?.text} />

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

export default function NotesPage() {
  return (
    <RequireAuth>
      <NotesContent />
    </RequireAuth>
  );
}
