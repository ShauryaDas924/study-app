
"use client";

import { useCallback, useMemo, useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type UUID } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Card, CardHeader } from "@/components/ui/Card";
import UploadNotes from "@/components/UploadNotes";
import NoteEditor from "@/components/NoteEditor";
import { authFetch } from "@/lib/auth";
import RequireAuth from "@/components/RequireAuth";


function getGenericSectionKind(label: string) {
  const key = label.trim().toLowerCase();

  if (
    key.includes("definition") ||
    key === "meaning" ||
    key === "overview" ||
    key === "summary"
  ) {
    return "definition";
  }

  if (
    key.includes("key idea") ||
    key.includes("main idea") ||
    key.includes("important") ||
    key.includes("takeaway") ||
    key.includes("concept") ||
    key.includes("principle")
  ) {
    return "key";
  }

  if (
    key.includes("example") ||
    key.includes("application") ||
    key.includes("use case")
  ) {
    return "example";
  }

  if (
    key.includes("pitfall") ||
    key.includes("mistake") ||
    key.includes("warning") ||
    key.includes("trap") ||
    key.includes("common error")
  ) {
    return "pitfall";
  }

  if (
    key.includes("exam") ||
    key.includes("quiz") ||
    key.includes("test") ||
    key.includes("professor") ||
    key.includes("insight")
  ) {
    return "exam";
  }

  if (
    key.includes("formula") ||
    key.includes("equation") ||
    key.includes("calculation")
  ) {
    return "formula";
  }

  if (
    key.includes("step") ||
    key.includes("process") ||
    key.includes("method") ||
    key.includes("procedure") ||
    key.includes("workflow")
  ) {
    return "process";
  }

  if (
    key.includes("compare") ||
    key.includes("comparison") ||
    key.includes("versus") ||
    key.includes(" vs ") ||
    key.includes("difference")
  ) {
    return "comparison";
  }

  if (
    key.includes("relationship") ||
    key.includes("connection") ||
    key.includes("linked") ||
    key.includes("related")
  ) {
    return "relationship";
  }

  return "notes";
}

function getSectionStyle(label: string) {
  const kind = getGenericSectionKind(label);

  if (kind === "definition") {
    return {
      badge: label,
      color: "var(--accent-green-strong)",
      bg: "rgba(191, 216, 184, 0.16)",
      border: "rgba(191, 216, 184, 0.48)",
    };
  }

  if (kind === "key") {
    return {
      badge: label,
      color: "var(--accent-pink-strong)",
      bg: "rgba(247, 167, 195, 0.12)",
      border: "rgba(247, 167, 195, 0.38)",
    };
  }

  if (kind === "example") {
    return {
      badge: label,
      color: "#9a6a00",
      bg: "rgba(246, 223, 139, 0.18)",
      border: "rgba(246, 223, 139, 0.54)",
    };
  }

  if (kind === "pitfall") {
    return {
      badge: label,
      color: "#b44b62",
      bg: "rgba(255, 215, 223, 0.30)",
      border: "rgba(247, 167, 195, 0.48)",
    };
  }

  if (kind === "exam") {
    return {
      badge: label,
      color: "#7b5cff",
      bg: "rgba(123, 92, 255, 0.08)",
      border: "rgba(123, 92, 255, 0.25)",
    };
  }

  if (kind === "formula") {
    return {
      badge: label,
      color: "#4f46e5",
      bg: "rgba(79, 70, 229, 0.07)",
      border: "rgba(79, 70, 229, 0.22)",
    };
  }

  if (kind === "process") {
    return {
      badge: label,
      color: "#4d7c8a",
      bg: "rgba(77, 124, 138, 0.08)",
      border: "rgba(77, 124, 138, 0.25)",
    };
  }

  if (kind === "comparison") {
    return {
      badge: label,
      color: "#8a5a00",
      bg: "rgba(246, 223, 139, 0.14)",
      border: "rgba(246, 223, 139, 0.42)",
    };
  }

  if (kind === "relationship") {
    return {
      badge: label,
      color: "#4d7c8a",
      bg: "rgba(77, 124, 138, 0.08)",
      border: "rgba(77, 124, 138, 0.25)",
    };
  }

  return {
    badge: label,
    color: "var(--text-soft)",
    bg: "rgba(255,255,255,0.72)",
    border: "var(--border-soft)",
  };
}

function looksLikeSectionHeading(line: string, nextLine?: string) {
  const trimmed = line.trim();
  const next = nextLine?.trim() ?? "";

  if (!trimmed) return false;
  if (trimmed.startsWith("-") || trimmed.startsWith("•")) return false;
  if (trimmed.startsWith("#")) return false;
  if (trimmed.length > 46) return false;
  if (/[.!?]$/.test(trimmed)) return false;

  const kind = getGenericSectionKind(trimmed);

  if (kind !== "notes") return true;

  if (
    next &&
    /^[-•]|\d+\.|[A-Z][a-z]/.test(next) &&
    /^[A-Z][A-Za-z0-9 &/+():'-]{2,45}$/.test(trimmed)
  ) {
    return true;
  }

  return false;
}

function splitIntoTopicBlocks(text: string) {
  const normalized = text.replace(/\r\n/g, "\n").trim();

  const headingMatches = [...normalized.matchAll(/^###\s+(.+)$/gm)];

  if (headingMatches.length > 0) {
    const intro =
      headingMatches[0].index && headingMatches[0].index > 0
        ? normalized.slice(0, headingMatches[0].index).trim()
        : "";

    const blocks = headingMatches.map((match, index) => {
      const start = match.index ?? 0;
      const end =
        index + 1 < headingMatches.length
          ? headingMatches[index + 1].index ?? normalized.length
          : normalized.length;

      const rawBlock = normalized.slice(start, end).trim();
      const title = match[1].trim();
      const body = rawBlock.replace(/^###\s+.+$/m, "").trim();

      return { title, body };
    });

    return { intro, blocks };
  }

  return {
    intro: "",
    blocks: [{ title: "Study Note", body: normalized }],
  };
}

function parseTopicSections(body: string) {
  const lines = body.split("\n");
  const sections: { heading: string; lines: string[] }[] = [];
  let current: { heading: string; lines: string[] } | null = null;

  lines.forEach((rawLine, index) => {
    const line = rawLine.trim();
    const nextLine = lines[index + 1];

    if (!line) return;

    if (looksLikeSectionHeading(line, nextLine)) {
      current = { heading: line, lines: [] };
      sections.push(current);
      return;
    }

    if (!current) {
      current = { heading: "Notes", lines: [] };
      sections.push(current);
    }

    current.lines.push(line);
  });

  return sections;
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

  const { intro, blocks } = splitIntoTopicBlocks(text);

  return (
    <div
      className="rounded-[2rem] border overflow-hidden"
      style={{
        background: "rgba(255,255,255,0.94)",
        borderColor: "var(--border-soft)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div
        className="px-5 py-4 border-b"
        style={{
          borderColor: "var(--border-soft)",
          background:
            "linear-gradient(90deg, rgba(247,167,195,0.12), rgba(246,223,139,0.12), rgba(191,216,184,0.12))",
        }}
      >
        <div
          className="text-xs uppercase tracking-[0.18em] font-semibold"
          style={{ color: "var(--text-soft)" }}
        >
          Study Note Preview
        </div>

        <div
          className="mt-1 text-lg font-semibold"
          style={{ color: "var(--text-main)" }}
        >
          Readable, structured notes
        </div>
      </div>

      <div className="p-5 space-y-5 max-h-[760px] overflow-y-auto">
        {intro && (
          <div
            className="rounded-3xl border p-5"
            style={{
              background: "rgba(255,255,255,0.78)",
              borderColor: "var(--border-soft)",
            }}
          >
            <div
              className="text-xs uppercase tracking-[0.16em] font-bold mb-3"
              style={{ color: "var(--text-soft)" }}
            >
              Header
            </div>

            <div className="space-y-2">
              {intro
                .split("\n")
                .map((line) => line.trim())
                .filter(Boolean)
                .map((line, index) => (
                  <p
                    key={index}
                    className="text-sm leading-relaxed"
                    style={{ color: "var(--text-main)" }}
                  >
                    {line}
                  </p>
                ))}
            </div>
          </div>
        )}

        {blocks.map((block, blockIndex) => {
          const sections = parseTopicSections(block.body);

          return (
            <article
              key={`${block.title}-${blockIndex}`}
              className="rounded-3xl border overflow-hidden"
              style={{
                background: "rgba(255,255,255,0.82)",
                borderColor: "var(--border-soft)",
                boxShadow: "var(--shadow-soft)",
              }}
            >
              <div
                className="px-5 py-4 border-b flex items-start gap-3"
                style={{
                  borderColor: "var(--border-soft)",
                  background:
                    "linear-gradient(90deg, rgba(255,255,255,0.90), rgba(248,255,247,0.62))",
                }}
              >
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
                  <h3
                    className="text-xl font-semibold leading-tight"
                    style={{ color: "var(--text-main)" }}
                  >
                    {block.title}
                  </h3>

                  <p
                    className="text-sm mt-1"
                    style={{ color: "var(--text-soft)" }}
                  >
                    Organized from your uploaded note
                  </p>
                </div>
              </div>

              <div className="p-5 space-y-4">
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
                          const clean = line.replace(/^[-•]\s*/, "");
                          const isBullet = /^[-•]\s*/.test(line);
                          const isNumbered = /^\d+\./.test(line);
                          const isCode =
                            clean.includes("SELECT") ||
                            clean.includes("WHERE") ||
                            clean.includes("NULL;") ||
                            clean.includes("`");

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
                                {clean.replace(/`/g, "")}
                              </code>
                            );
                          }

                          return (
                            <div
                              key={lineIndex}
                              className="flex gap-2 text-sm leading-relaxed"
                              style={{ color: "var(--text-main)" }}
                            >
                              {(isBullet || isNumbered) && (
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

function formatConceptName(name?: string) {
  if (!name) return "Untitled Concept";

  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

type ConceptPreview = {
  id?: UUID;
  name?: string;
  description?: string | null;
  evidence?: string | null;
  summary?: string | null;
};

function getNoteText(content?: Record<string, unknown>) {
  return typeof content?.text === "string" ? content.text : "";
}

function getConceptTone(concept: ConceptPreview, index: number) {
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

function SavedConceptsPreview({ concepts }: { concepts: ConceptPreview[] }) {
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
        {concepts.map((concept, index) => {
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
  const [concepts, setConcepts] = useState<ConceptPreview[]>([]);
  const [selectedNoteId, setSelectedNoteId] = useState<UUID | null>(null);

  useEffect(() => {
    setSelectedNoteId(null);
    setUploadedText("");
    setConcepts([]);
  }, [classId]);

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
        notesQ.data.some((n) => n.id === meta.noteId)
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
      const data = query.state.data;
      const status = data?.status;
    if (status === "queued" || status === "running") return 8000;
      return false;
    },
  });

  const fetchConcepts = useCallback(() => {
    if (!classId) return Promise.resolve();

    return authFetch(`/notes/concepts/by-class/${classId}`, {
      credentials: "include",
    })
      .then((response) => response.json())
      .then((data: unknown) => {
        setConcepts(Array.isArray(data) ? (data as ConceptPreview[]) : []);
      })
      .catch(() => setConcepts([]));
  }, [classId]);

useEffect(() => {
  const text = getNoteText(noteQ.data?.content_json);

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
    }

  if (status === "failed" || status === "cancelled") {
    localStorage.removeItem("activeExtractionMeta");
    localStorage.removeItem("activeExtractionNoteId");
  }
}, [extractionStatusQ.data?.status, classId, fetchConcepts, qc, selectedNoteId]);

  useEffect(() => {
    void fetchConcepts();
  }, [fetchConcepts]);

  const selected = useMemo(() => selectedNoteId, [selectedNoteId]);
  const extractionStatus = extractionStatusQ.data?.status ?? "idle";
  const extractionProgress = extractionStatusQ.data?.progress ?? 0;
  const extractionError = extractionStatusQ.data?.error ?? null;
  const extractionStage =
    extractionStatus === "failed"
      ? "Failed"
      : extractionStatus === "cancelled"
      ? "Cancelled"
      : extractionProgress >= 100
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
    setUploadedText(text);
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
             <NotePreview text={getNoteText(noteQ.data?.content_json)} />

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

              {extractionStatus === "cancelled" && (
                <div className="text-xs" style={{ color: "var(--text-soft)" }}>
  Extraction was cancelled.
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
