"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useStore } from "@/store/useStore";

type Card = {
  id: string;            // ✅ use backend UUID (stable)
  question: string;
  answer: string;
  confidence: number;
};

type ApiFlashcard = {
  id?: string | number;
  question: string;
  answer: string;
  confidence?: number;
};

type Mode = "normal" | "hard" | "medium";

type SessionPayload = {
  cards: Card[];
  index: number;
  hardPile: Card[];
  mediumPile: Card[];
  mode: Mode;
};

function shuffle<T>(array: T[]): T[] {
  const arr = [...array];
  for (let j = arr.length - 1; j > 0; j--) {
    const k = Math.floor(Math.random() * (j + 1));
    [arr[j], arr[k]] = [arr[k], arr[j]];
  }
  return arr;
}

function saveSession(key: string, data: SessionPayload) {
  localStorage.setItem(key, JSON.stringify(data));
}

function loadSession(key: string): SessionPayload | null {
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionPayload;
  } catch {
    return null;
  }
}

export default function FlashcardsPage() {
  const classId = useStore((s) => s.selectedClassId);
  const noteId = useStore((s) => s.selectedNoteId);
  const setSelectedNoteId = useStore((s) => s.setSelectedNoteId);

  const [notes, setNotes] = useState<any[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [i, setI] = useState(0);
  const [show, setShow] = useState(false);

  const [hardPile, setHardPile] = useState<Card[]>([]);
  const [mediumPile, setMediumPile] = useState<Card[]>([]);
  const [mode, setMode] = useState<Mode>("normal");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ✅ prevents spam / strict-mode double fetch
  const lastLoadedNoteId = useRef<string | undefined>(undefined);

  const sessionKey = useMemo(() => {
    return noteId ? `flashcards_session_${noteId}` : "";
  }, [noteId]);

  // ----------------------------
  // 1) LOAD NOTES ON CLASS CHANGE
  // ----------------------------
  useEffect(() => {
    if (!classId) return;

    let cancelled = false;

    async function loadNotes() {
      try {
        const res = await fetch(`http://localhost:8000/notes/by-class/${classId}`);
        const data = await res.json();
        if (cancelled) return;

        const arr = Array.isArray(data) ? data : [];
        setNotes(arr);

        // auto-pick a note if none selected
        if (arr.length && !noteId) {
          setSelectedNoteId(arr[0].id);
        }
      } catch (e) {
        console.error(e);
      }
    }

    loadNotes();
    return () => {
      cancelled = true;
    };
  }, [classId, noteId, setSelectedNoteId]);

  // ---------------------------------
  // 2) LOAD DECK ON NOTE CHANGE (ONCE)
  // ---------------------------------
  useEffect(() => {
    if (!classId || !noteId) return;
    if (!sessionKey) return;

    // prevent refetch loop
    if (lastLoadedNoteId.current === noteId) return;
    lastLoadedNoteId.current = noteId;

    // try restore session per-note
    const saved = loadSession(sessionKey);
    if (saved && saved.cards?.length) {
      setCards(saved.cards);
      setI(Math.min(saved.index ?? 0, Math.max(saved.cards.length - 1, 0)));
      setHardPile(saved.hardPile ?? []);
      setMediumPile(saved.mediumPile ?? []);
      setMode(saved.mode ?? "normal");
      setShow(false);
      setError(null);
      setLoading(false);
      return;
    }

    void loadFreshDeck(noteId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId, noteId, sessionKey]);

  // ----------------------------
  // 3) SAVE SESSION (PER NOTE)
  // ----------------------------
  useEffect(() => {
    if (!noteId) return;
    if (!cards.length) return;

    saveSession(sessionKey, {
      cards,
      index: i,
      hardPile,
      mediumPile,
      mode,
    });
  }, [noteId, sessionKey, cards, i, hardPile, mediumPile, mode]);

  // ----------------------------
  // LOAD FRESH DECK (API)
  // ----------------------------
  async function loadFreshDeck(nid: string) {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`http://localhost:8000/notes/flashcards/by-note/${nid}`);

      if (!res.ok) {
        const t = await res.text();
        throw new Error(`Flashcards API error ${res.status}: ${t}`);
      }

      const json = (await res.json()) as unknown;
      const data: ApiFlashcard[] = Array.isArray(json) ? (json as ApiFlashcard[]) : [];

      const mapped: Card[] = data.map((c) => ({
        id: String(c.id ?? crypto.randomUUID()),
        question: String(c.question ?? ""),
        answer: String(c.answer ?? ""),
        confidence: Number(c.confidence ?? 0.5),
      }));

      const shuffled = shuffle(mapped);

      setCards(shuffled);
      setI(0);
      setShow(false);
      setHardPile([]);
      setMediumPile([]);
      setMode("normal");

      // save per-note session even if empty deck
      saveSession(sessionKey, {
        cards: shuffled,
        index: 0,
        hardPile: [],
        mediumPile: [],
        mode: "normal",
      });
    } catch (err: any) {
      console.error(err);
      setCards([]);
      setError(err?.message ?? "Failed to load flashcards");
    } finally {
      setLoading(false);
    }
  }

  function reshuffleRemaining() {
    const remaining = cards.slice(i);
    const shuffled = shuffle(remaining);
    setCards([...cards.slice(0, i), ...shuffled]);
  }

  function clearSession() {
    if (!sessionKey) return;
    localStorage.removeItem(sessionKey);
    lastLoadedNoteId.current = undefined; // allow reload
    if (noteId) void loadFreshDeck(noteId);
  }

  function finishSession() {
    alert("🎉 All reviews complete!");
    setMode("normal");
    setI(0);
    setShow(false);
  }

  function grade(level: "hard" | "medium" | "easy") {
    const current = cards[i];

    if (level === "hard") setHardPile((p) => [...p, current]);
    if (level === "medium") setMediumPile((p) => [...p, current]);

    setShow(false);

    if (i + 1 < cards.length) {
      setI(i + 1);
      return;
    }

    if (mode === "normal") {
      const nextHard = level === "hard" ? [...hardPile, current] : hardPile;
      const nextMed = level === "medium" ? [...mediumPile, current] : mediumPile;

      if (nextHard.length) {
        setCards(shuffle(nextHard));
        setHardPile([]);
        setI(0);
        setMode("hard");
        return;
      }

      if (nextMed.length) {
        setCards(shuffle(nextMed));
        setMediumPile([]);
        setI(0);
        setMode("medium");
        return;
      }

      finishSession();
      return;
    }

    if (mode === "hard") {
      const nextMed = level === "medium" ? [...mediumPile, current] : mediumPile;
      if (nextMed.length) {
        setCards(shuffle(nextMed));
        setMediumPile([]);
        setI(0);
        setMode("medium");
        return;
      }
      finishSession();
      return;
    }

    finishSession();
  }

  async function exportCSV() {
    if (!noteId) return;

    try {
      const res = await fetch(`http://localhost:8000/notes/flashcards/export-by-note/${noteId}`);
      if (!res.ok) {
        alert("Export failed");
        return;
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = "flashcards.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("CSV export error:", err);
    }
  }

  // ----------------------------
  // RENDER STATES (IMPORTANT!)
  // ----------------------------
  if (!classId) return <div className="p-8">Select a class first.</div>;
  if (!noteId) return <div className="p-8">Pick a note to study.</div>;

  if (loading) return <div className="p-8">Loading flashcards…</div>;

  if (error) {
    return (
      <div className="p-8 space-y-3">
        <div className="text-red-600 font-semibold">Flashcards error</div>
        <pre className="text-xs bg-gray-100 p-3 rounded">{error}</pre>
        <button
          onClick={() => loadFreshDeck(noteId)}
          className="px-3 py-2 bg-blue-600 text-white rounded"
        >
          Retry
        </button>
      </div>
    );
  }

  // ✅ THIS IS THE FIX: empty deck ≠ loading
  if (!cards.length) {
    return (
      <div className="p-8 space-y-4">
        <div>No flashcards yet 📭</div>

        <select
          value={noteId}
          onChange={(e) => {
            lastLoadedNoteId.current = undefined;
            setSelectedNoteId(e.target.value);
          }}
          className="border px-2 py-1 rounded"
        >
          {notes.map((n) => (
            <option key={n.id} value={n.id}>
              {n.title}
            </option>
          ))}
        </select>

        <button
          onClick={() => loadFreshDeck(noteId)}
          className="px-3 py-2 bg-blue-600 text-white rounded"
        >
          Refresh
        </button>
      </div>
    );
  }

  const c = cards[Math.min(i, cards.length - 1)];

  return (
    <div className="p-8 max-w-xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold">Flashcard Study</h1>

      <select
        value={noteId}
        onChange={(e) => {
          lastLoadedNoteId.current = undefined;
          setSelectedNoteId(e.target.value);
        }}
        className="border px-2 py-1 rounded"
      >
        {notes.map((n) => (
          <option key={n.id} value={n.id}>
            {n.title}
          </option>
        ))}
      </select>

      <div className="flex gap-4 text-sm">
        <button
          disabled={!hardPile.length}
          onClick={() => {
            setCards(shuffle(hardPile));
            setHardPile([]);
            setI(0);
            setMode("hard");
            setShow(false);
          }}
          className="bg-red-100 px-3 py-1 rounded hover:bg-red-200 disabled:opacity-50"
        >
          Hard: {hardPile.length}
        </button>

        <button
          disabled={!mediumPile.length}
          onClick={() => {
            setCards(shuffle(mediumPile));
            setMediumPile([]);
            setI(0);
            setMode("medium");
            setShow(false);
          }}
          className="bg-yellow-100 px-3 py-1 rounded hover:bg-yellow-200 disabled:opacity-50"
        >
          Medium: {mediumPile.length}
        </button>

        <div className="bg-gray-100 px-3 py-1 rounded">Mode: {mode}</div>
      </div>

      <div className="flex gap-3">
        <button onClick={reshuffleRemaining} className="px-3 py-1 bg-purple-600 text-white rounded text-sm">
          🔀 Shuffle
        </button>

        <button onClick={clearSession} className="px-3 py-1 bg-gray-600 text-white rounded text-sm">
          ♻️ Reset
        </button>

        <button onClick={exportCSV} className="px-3 py-1 bg-blue-700 text-white rounded text-sm">
          ⬇️ Export CSV
        </button>
      </div>

      <div className="border p-6 rounded-xl shadow-sm bg-white relative">
        <div
          className={`absolute top-3 right-3 text-xs px-2 py-1 rounded-full ${
            c.confidence >= 0.85
              ? "bg-green-100 text-green-800"
              : c.confidence >= 0.65
              ? "bg-yellow-100 text-yellow-800"
              : "bg-red-100 text-red-800"
          }`}
        >
          {Math.round(c.confidence * 100)}%
        </div>

        <div className="text-lg font-medium">{c.question}</div>

        {!show ? (
          <button onClick={() => setShow(true)} className="mt-6 px-4 py-2 rounded bg-blue-600 text-white">
            Reveal
          </button>
        ) : (
          <>
            <div className="mt-4 text-green-700">
              {c.answer && !c.answer.toLowerCase().includes("named concept found")
                ? c.answer
                : "No answer extracted from notes yet."}
            </div>

            <div className="flex gap-3 mt-6">
              <button onClick={() => grade("hard")} className="px-3 py-2 bg-red-500 text-white rounded">
                Hard
              </button>

              <button onClick={() => grade("medium")} className="px-3 py-2 bg-yellow-500 text-white rounded">
                Medium
              </button>

              <button onClick={() => grade("easy")} className="px-3 py-2 bg-green-600 text-white rounded">
                Easy
              </button>
            </div>
          </>
        )}
      </div>

      <div className="text-sm text-gray-500">
        Card {Math.min(i + 1, cards.length)} / {cards.length}
      </div>
    </div>
  );
}